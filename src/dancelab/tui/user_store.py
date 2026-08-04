"""Ulubione i filary — trwały stan użytkownika Biblioteki (TUI 2.0, krok b).

Dwa piny, jak chciał Janek (wzór Apple Music): na utwory i na playlisty,
osobno FILARY — utwory OBOWIĄZKOWE dla generatora setu. Filarów jest 3–10
(Janek, 05.08 — minimum wróciło po dniu przerwy): górna granica to bezpiecznik
z jego uzasadnienia (set złożony z samych filarów nie zostawia silnikowi nic
do zaprojektowania — silnik projektuje drogę MIĘDZY filarami), dolna pilnuje,
żeby budowa „z filarów" miała z czego wyznaczyć trasę. Minimum egzekwuje
BUDOWA, nie przełącznik — pierwszy i drugi filar musi się dać zaznaczyć.

Wpisy trzymają track_id ORAZ ścieżkę: id to sha1 ścieżki, więc po przenosinach
pliku wpis ratuje dopasowanie po ścieżce (ten sam wzór co magazyn planów).
Utwór nieobecny w puli jest raportowany, nigdy zgadywany.

Pin na playlisty jest w strukturze od dziś, ale UI dostanie dopiero, gdy
powstanie widok playlist. Plik: `data/exports/` — osobiste, poza gitem.
"""

from __future__ import annotations

import json
import pathlib

STATE_PATH = pathlib.Path("data/exports/tui_stan.json")
MIN_FILARY = 3
MAX_FILARY = 10

_EMPTY = {"ulubione_utwory": [], "ulubione_playlisty": [], "filary": [],
          "tryb_filarow": "rozstaw"}


def _kopia(v):
    return list(v) if isinstance(v, list) else v


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {k: _kopia(v) for k, v in _EMPTY.items()}
    state = json.loads(STATE_PATH.read_text())
    for key, default in _EMPTY.items():
        state.setdefault(key, _kopia(default))
    return state


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))


def _entry_index(entries: list[dict], track_id: str, path: str) -> int | None:
    for i, e in enumerate(entries):
        if e.get("track_id") == track_id or e.get("path") == path:
            return i
    return None


def toggle_track(state: dict, kind: str, track_id: str,
                 path: str) -> tuple[bool, str | None]:
    """Przełącz wpis utworu. kind: 'ulubione_utwory' | 'filary'.

    Zwraca (czy_teraz_wpisany, powód_odmowy). Odmowa tylko przy limicie
    filarów — i mówi dlaczego, zgodnie z uzasadnieniem Janka."""
    entries = state[kind]
    i = _entry_index(entries, track_id, path)
    if i is not None:
        entries.pop(i)
        return False, None
    if kind == "filary" and len(entries) >= MAX_FILARY:
        return False, (f"limit {MAX_FILARY} filarów — więcej filarów niż "
                       f"przestrzeni do projektowania to już playlista ręczna")
    entries.append({"track_id": track_id, "path": path})
    return True, None


def resolve_tracks(entries: list[dict], by_id: dict) -> tuple[list[str], list[str]]:
    """Wpisy → track_id obecne w puli. Braki wracają po imieniu, nie znikają."""
    by_path = {a.track.source_path: tid for tid, a in by_id.items()}
    ids: list[str] = []
    missing: list[str] = []
    for e in entries:
        tid = e.get("track_id")
        if tid in by_id:
            ids.append(tid)
            continue
        alt = by_path.get(e.get("path", ""))
        if alt is not None:
            ids.append(alt)
        else:
            missing.append(pathlib.Path(e.get("path", "?")).stem[:40])
    return ids, missing
