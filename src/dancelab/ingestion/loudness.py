"""Głośność zintegrowana (LUFS, EBU R128) przez ffmpeg — kolumna w Bibliotece.

Pomiar wymaga pełnego zdekodowania utworu (~2–5 s/utwór), więc: liczony
W TLE, jeden utwór na raz, z TRWAŁYM cache (klucz: ścieżka+rozmiar+mtime —
podmiana pliku unieważnia wpis). Brak pomiaru pokazujemy jako brak („…"),
nigdy nie zmyślamy. Uruchamiacz ffmpeg jest wstrzykiwalny — testy nie
dekodują audio.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess

CACHE = pathlib.Path("data/cache/lufs.json")
_WZOR = re.compile(r"I:\s+(-?[\d.]+)\s+LUFS")


def _klucz(path: str) -> str | None:
    try:
        st = pathlib.Path(path).stat()
    except OSError:
        return None
    return f"{path}|{st.st_size}|{st.st_mtime_ns}"


def _ffmpeg_ebur128(path: str) -> str:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
         "-map", "0:a:0", "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
        capture_output=True, text=True, timeout=180)
    return proc.stderr


def wyluskaj_lufs(stderr: str) -> float | None:
    """Zintegrowane I z podsumowania ebur128; brak wzorca = None."""
    trafienia = _WZOR.findall(stderr)
    return float(trafienia[-1]) if trafienia else None


def wczytaj_cache() -> dict[str, float]:
    """ścieżka → LUFS dla wpisów, których klucz wciąż pasuje do pliku."""
    if not CACHE.exists():
        return {}
    try:
        surowe = json.loads(CACHE.read_text())
    except Exception:  # noqa: BLE001 — zepsuty cache = pusty, nie wywrotka
        return {}
    out: dict[str, float] = {}
    for klucz, lufs in surowe.items():
        path = klucz.split("|", 1)[0]
        if _klucz(path) == klucz:
            out[path] = lufs
    return out


def zmierz_brakujace(paths, *, progress=None, should_stop=None,
                     run_fn=_ffmpeg_ebur128) -> dict[str, float]:
    """Domierz LUFS tam, gdzie cache nie ma wpisu; zwraca pełną mapę."""
    try:
        surowe = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    except Exception:  # noqa: BLE001
        surowe = {}
    znane = wczytaj_cache()
    brakujace = [p for p in paths if p not in znane]
    for i, path in enumerate(brakujace):
        if should_stop and should_stop():
            break
        try:
            lufs = wyluskaj_lufs(run_fn(path))
        except Exception:  # noqa: BLE001 — jeden chory plik nie kładzie tła
            lufs = None
        if lufs is not None:
            znane[path] = lufs
            klucz = _klucz(path)
            if klucz:
                surowe[klucz] = lufs
        if progress:
            progress(i + 1, len(brakujace), path)
        if (i + 1) % 5 == 0 or i + 1 == len(brakujace):
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(surowe))
    return znane
