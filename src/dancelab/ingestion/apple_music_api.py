"""Apple Music API client: developer token, user library, and the catalog join.

Why it exists: 82 % of the owner's collection are Apple Music streams that
rekordbox stores as ``apple-music:tracks:<catalogId>`` with no audio and no
genre. With a MusicKit key the Apple Music API returns the user's own library
(songs, playlists) and coarse catalog genres, which is the only genre source
those streams will ever have.

Design constraints, all deliberate:

* The private key never enters Python memory: ES256 signing is delegated to
  the ``openssl`` binary, which reads the ``.p8`` file itself. This also keeps
  the dependency list unchanged (no PyJWT, no cryptography).
* Tokens are never persisted by this module and never logged. The developer
  token is minted fresh per run with a short lifetime.
* The key file must live outside the repository and outside ``~/Desktop``
  (the Desktop is iCloud-synced and wired to other tools).
* Pagination follows the ``next`` path the API returns; offsets are never
  hand-rolled.
"""

from __future__ import annotations

import base64
import json
import subprocess
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

API = "https://api.music.apple.com"
MAX_TTL_S = 15_777_000  # Apple caps developer tokens at six months
REPO_ROOT = Path(__file__).resolve().parents[3]


# ------------------------------------------------------------------ key guard

def check_key_path(key_path: Path) -> Path:
    """Refuse a key that sits on the Desktop or inside the repository.

    Returns the resolved path. Raises ``ValueError`` with the reason, so a
    script can print it and stop before anything is signed.
    """
    p = Path(key_path).expanduser().resolve()
    if not p.exists():
        raise ValueError(f"key file does not exist: {p}")
    desktop = (Path.home() / "Desktop").resolve()
    if desktop in p.parents:
        raise ValueError("the key sits on the Desktop — that folder is iCloud-synced; "
                         "move it to ~/.dancelab/musickit/")
    if REPO_ROOT in p.parents:
        raise ValueError("the key sits inside the repository — move it to "
                         "~/.dancelab/musickit/")
    return p


# ------------------------------------------------------------- JWT plumbing

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def der_to_raw(sig: bytes, size: int = 32) -> bytes:
    """Convert a DER ``ECDSA-Sig-Value`` into the raw ``r || s`` form JWT wants.

    ``openssl dgst -sign`` emits DER (SEQUENCE of two INTEGERs); JOSE ES256
    requires each integer left-padded to 32 bytes and concatenated.
    """
    if len(sig) < 8 or sig[0] != 0x30:
        raise ValueError("not a DER ECDSA signature")
    idx = 2 if sig[1] < 0x80 else 2 + (sig[1] & 0x7F)
    out = b""
    for _ in range(2):
        if sig[idx] != 0x02:
            raise ValueError("expected INTEGER in DER signature")
        length = sig[idx + 1]
        value = sig[idx + 2: idx + 2 + length]
        idx += 2 + length
        value = value.lstrip(b"\x00")
        if len(value) > size:
            raise ValueError("integer longer than the curve size")
        out += value.rjust(size, b"\x00")
    return out


def developer_token(key_path: Path, key_id: str, team_id: str, ttl_s: int = 3600,
                    now: int | None = None, openssl: str = "openssl") -> str:
    """Mint an ES256 developer token signed by ``openssl`` from a ``.p8`` key.

    The key is read by the ``openssl`` process only. ``ttl_s`` is clamped to
    Apple's six-month ceiling.
    """
    p = check_key_path(key_path)
    iat = int(now if now is not None else time.time())
    ttl = min(int(ttl_s), MAX_TTL_S)
    header = _b64url(json.dumps({"alg": "ES256", "kid": key_id}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps({"iss": team_id, "iat": iat, "exp": iat + ttl},
                                 separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode("ascii")
    proc = subprocess.run([openssl, "dgst", "-sha256", "-sign", str(p)],
                          input=signing_input, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError("openssl could not sign with the key "
                           f"(exit {proc.returncode}): {proc.stderr.decode(errors='replace')[:200]}")
    return f"{header}.{payload}.{_b64url(der_to_raw(proc.stdout))}"


# ------------------------------------------------------------------- client

Fetch = Callable[[str, dict[str, str], dict[str, str]], tuple[int, dict[str, str], bytes]]


def _fetch_requests(url: str, params: dict[str, str],
                    headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    import requests

    resp = requests.get(url, params=params, headers=headers, timeout=60)
    return resp.status_code, {k.lower(): v for k, v in resp.headers.items()}, resp.content


class AppleMusicClient:
    """Thin authenticated GET client with ``next``-driven pagination.

    ``fetch`` is injectable so tests never touch the network. Tokens are held
    in memory only and are not part of ``repr``.
    """

    def __init__(self, dev_token: str, user_token: str | None = None,
                 fetch: Fetch | None = None, sleep: Callable[[float], None] = time.sleep,
                 max_retries: int = 5) -> None:
        self._dev = dev_token
        self._user = user_token
        self._fetch = fetch or _fetch_requests
        self._sleep = sleep
        self._max_retries = max_retries

    def __repr__(self) -> str:  # never leak tokens
        return f"AppleMusicClient(user_token={'set' if self._user else 'none'})"

    def _headers(self) -> dict[str, str]:
        h = {"Authorization": f"Bearer {self._dev}"}
        if self._user:
            h["Music-User-Token"] = self._user
        return h

    def get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        """GET one page; retries on 429/5xx honouring ``Retry-After``."""
        url = path if path.startswith("http") else f"{API}{path}"
        attempt = 0
        while True:
            status, headers, body = self._fetch(url, params or {}, self._headers())
            if status == 200:
                return json.loads(body.decode("utf-8"))
            if status in (429, 500, 502, 503, 504) and attempt < self._max_retries:
                attempt += 1
                self._sleep(float(headers.get("retry-after", 2 ** attempt)))
                continue
            raise RuntimeError(f"Apple Music API {status} for {path}: "
                               f"{body[:200].decode('utf-8', errors='replace')}")

    def all_pages(self, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """Follow ``next`` until the API stops returning it."""
        out: list[dict[str, Any]] = []
        page = self.get(path, params)
        out.extend(page.get("data", []))
        while page.get("next"):
            page = self.get(page["next"])
            out.extend(page.get("data", []))
        return out


# ------------------------------------------------------------- library read

def fetch_library(client: AppleMusicClient, with_playlist_tracks: bool = True) -> dict[str, Any]:
    """Storefront, every library song and every library playlist (with tracks)."""
    storefront = client.get("/v1/me/storefront").get("data", [{}])[0].get("id")
    songs = client.all_pages("/v1/me/library/songs", {"limit": "100"})
    playlists = client.all_pages("/v1/me/library/playlists", {"limit": "100"})
    if with_playlist_tracks:
        for pl in playlists:
            pl_id = pl.get("id")
            if pl_id:
                pl["tracks"] = client.all_pages(f"/v1/me/library/playlists/{pl_id}/tracks",
                                                {"limit": "100"})
    return {"schema_version": "apple-library-v1", "storefront": storefront,
            "fetched_at": int(time.time()), "songs": songs, "playlists": playlists}


def catalog_ids(songs: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Map library song id → catalog id for songs that match the catalog.

    Songs uploaded from disc or other apps have no ``playParams.catalogId``
    and are left out; they are exactly the ones rekordbox could not stream.
    """
    out: dict[str, str] = {}
    for s in songs:
        cid = ((s.get("attributes") or {}).get("playParams") or {}).get("catalogId")
        if cid and s.get("id"):
            out[s["id"]] = str(cid)
    return out


def summarize(library: dict[str, Any], collection_stream_ids: set[str] | None) -> dict[str, Any]:
    """The numbers that say whether the read was worth it.

    ``collection_stream_ids`` are the catalog ids rekordbox stores for streams;
    the overlap is what unlocks a genre for them. ``None`` means rekordbox
    could not be read and the overlap is reported as unknown, not zero.
    """
    songs = library.get("songs", [])
    cids = catalog_ids(songs)
    genres = sum(1 for s in songs if (s.get("attributes") or {}).get("genreNames"))
    overlap = (len(set(cids.values()) & collection_stream_ids)
               if collection_stream_ids is not None else None)
    return {"songs": len(songs), "with_catalog_id": len(cids), "with_genre": genres,
            "playlists": len(library.get("playlists", [])),
            "collection_streams": (len(collection_stream_ids)
                                   if collection_stream_ids is not None else None),
            "matching_collection": overlap}
