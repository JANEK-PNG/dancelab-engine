"""Set from the window → a playlist in the owner's Apple Music library.

Why this path exists: rekordbox shows Apple Music playlists in its own tree
without anyone touching ``master.db``. For a collection that is 82 % streams
this is the one way to hand a set to the hardware that never risks the
database — the STRAŻNIK rule (no writes to the real ``master.db``) is kept
by construction, not by a backup.

Two stages, like every other write in the window:

* :func:`plan_apple_playlist` is pure. It maps the set order onto Apple
  catalog ids (rekordbox stores streams as ``apple-music:tracks:<id>``) and
  names every track it cannot send, with the reason. Local files have no
  catalog id yet — the ISRC bridge is the next step and plugs in through
  ``id_map`` without touching the publish path.
* :func:`publish_apple_playlist` does one POST and then reads the playlist
  back, because Apple documents a delay before a new library resource is
  visible. It reports *sent* and *verified* as two numbers and never rounds
  the second up to the first.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from dancelab.ingestion.apple_music_api import AppleMusicClient

STREAM_PREFIX = "apple-music:tracks:"
REASON_LOCAL = "plik lokalny — brak w Apple Music (most ISRC to następny krok)"
REASON_NO_ANALYSIS = "brak analizy — nie wiem, co to za utwór"
REASON_DUPLICATE = "powtórzony w secie — Apple przyjmuje utwór raz"
DESCRIPTION = "Set ułożony w DanceLab. Kolejność jak na ekranie."


@dataclass
class ApplePlaylistPlan:
    """What would be sent: catalog ids in set order plus the named leftovers."""

    name: str
    tracks: list[tuple[str, str]] = field(default_factory=list)   # (track_id, catalog_id)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (track_id, reason)

    @property
    def catalog_ids(self) -> list[str]:
        """Catalog ids in the order they will be sent."""
        return [cid for _tid, cid in self.tracks]

    def to_dict(self) -> dict[str, Any]:
        """The shape the window shows: counts first, names second."""
        return {"nazwa": self.name, "zgloszone": len(self.tracks) + len(self.skipped),
                "dopasowane": len(self.tracks),
                "pominiete": [{"track_id": t, "powod": r} for t, r in self.skipped],
                "notki": [f"POMINIĘTY ({r}): {t}" for t, r in self.skipped]}


def catalog_id_of(source_path: str | None) -> str | None:
    """``apple-music:tracks:123`` → ``"123"``; anything else → ``None``."""
    if not source_path:
        return None
    s = str(source_path)
    if not s.startswith(STREAM_PREFIX):
        return None
    cid = s[len(STREAM_PREFIX):].strip()
    return cid or None


def plan_apple_playlist(order: list[str], analyses: Mapping[str, Any], name: str,
                        id_map: Mapping[str, str] | None = None) -> ApplePlaylistPlan:
    """Pure stage one: which tracks of the set have an Apple catalog id.

    ``id_map`` (track_id → catalog id) is the seam for tracks that are not
    streams; it wins over the source path when present. A catalog id that
    appears twice is kept at its first position only.
    """
    plan = ApplePlaylistPlan(name=name)
    seen: set[str] = set()
    for tid in order:
        analysis = analyses.get(tid)
        cid = (id_map or {}).get(tid)
        if cid is None:
            if analysis is None:
                plan.skipped.append((tid, REASON_NO_ANALYSIS))
                continue
            cid = catalog_id_of(getattr(getattr(analysis, "track", None), "source_path", None))
        if cid is None:
            plan.skipped.append((tid, REASON_LOCAL))
            continue
        if cid in seen:
            plan.skipped.append((tid, REASON_DUPLICATE))
            continue
        seen.add(cid)
        plan.tracks.append((tid, cid))
    return plan


def _playlist_body(plan: ApplePlaylistPlan, description: str) -> dict[str, Any]:
    return {"attributes": {"name": plan.name, "description": description},
            "relationships": {"tracks": {"data": [{"id": cid, "type": "songs"}
                                                  for cid in plan.catalog_ids]}}}


def publish_apple_playlist(client: AppleMusicClient, plan: ApplePlaylistPlan,
                           description: str = DESCRIPTION, verify_attempts: int = 3,
                           sleep: Callable[[float], None] | None = None) -> dict[str, Any]:
    """Stage two: one POST, then read the playlist back.

    Returns ``ok``, the library playlist id, ``wyslane`` (what the POST
    carried) and ``zweryfikowane`` (what the GET showed, or ``None`` when
    Apple had not surfaced the playlist after ``verify_attempts`` reads).
    """
    if not plan.tracks:
        return {"ok": False, "blad": "żaden utwór setu nie ma id katalogu Apple — "
                                     "nie ma czego wysłać"}
    status, body = client.post("/v1/me/library/playlists", _playlist_body(plan, description))
    if status not in (200, 201):
        err = (body.get("errors") or [{}])[0] if isinstance(body, dict) else {}
        detail = None
        if isinstance(body, dict):
            detail = err.get("detail") or err.get("title") or body.get("raw")
        return {"ok": False, "blad": f"Apple Music odpowiedziało {status}"
                                     + (f": {detail}" if detail else "")}
    data = body.get("data") or []
    pl_id = data[0].get("id") if data and isinstance(data[0], dict) else None
    out: dict[str, Any] = {"ok": True, "id": pl_id, "nazwa": plan.name,
                           "wyslane": len(plan.tracks), "zweryfikowane": None,
                           "pominiete": [{"track_id": t, "powod": r} for t, r in plan.skipped],
                           "notki": [f"POMINIĘTY ({r}): {t}" for t, r in plan.skipped]}
    if not pl_id:
        out["notki"].append("Apple nie zwróciło id playlisty — nie mogę jej odczytać z powrotem")
        return out
    wait = sleep or client.sleep
    for attempt in range(verify_attempts):
        try:
            got = client.all_pages(f"/v1/me/library/playlists/{pl_id}/tracks", {"limit": "100"})
        except RuntimeError as exc:
            # 404 right after creation is the documented delay, not a failure
            if attempt + 1 < verify_attempts:
                wait(2.0 * (attempt + 1))
                continue
            out["notki"].append(f"odczyt zwrotny nie wyszedł: {str(exc)[:120]}")
            return out
        out["zweryfikowane"] = len(got)
        if len(got) >= len(plan.tracks) or attempt + 1 >= verify_attempts:
            break
        wait(2.0 * (attempt + 1))
    if out["zweryfikowane"] is not None and out["zweryfikowane"] < len(plan.tracks):
        out["notki"].append(f"Apple pokazuje na razie {out['zweryfikowane']} z "
                            f"{len(plan.tracks)} — nowa playlista bywa widoczna z opóźnieniem")
    return out
