"""Bramkarz ffprobe — walidacja plików PRZED analizą.

Jeden uszkodzony plik potrafił kłaść całe przebiegi (EPERM w dedupie,
padnięte dekodery w analizie). ffprobe sprawdza w ~50 ms, czy plik ma
zdrowy strumień audio — chore odpadają Z IMIENNYM POWODEM zanim silnik
w nie ugryzie. Uruchamiacz wstrzykiwalny — testy nie wołają ffprobe.
"""

from __future__ import annotations

import json
import subprocess


def _ffprobe(path: str) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name,duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


def sprawdz_plik(path: str, run_fn=_ffprobe) -> str | None:
    """None = zdrowy; inaczej powód odrzutu po polsku."""
    try:
        kod, out, err = run_fn(path)
    except FileNotFoundError:
        return None          # brak ffprobe = bramkarz się wyłącza, nie blokuje
    except Exception as exc:  # noqa: BLE001
        return f"ffprobe nie dał rady: {exc}"
    if kod != 0:
        powod = (err or "").strip().splitlines()
        return f"uszkodzony plik ({powod[-1][:60] if powod else 'ffprobe error'})"
    try:
        strumienie = json.loads(out).get("streams", [])
    except Exception:  # noqa: BLE001
        return "ffprobe zwrócił śmieci zamiast JSON"
    if not strumienie:
        return "brak strumienia audio w pliku"
    return None


def przesiej(paths, run_fn=_ffprobe) -> tuple[list, list[tuple[str, str]]]:
    """(zdrowe, [(ścieżka, powód) dla odrzuconych])."""
    zdrowe, odrzucone = [], []
    for p in paths:
        powod = sprawdz_plik(str(p), run_fn=run_fn)
        if powod is None:
            zdrowe.append(p)
        else:
            odrzucone.append((str(p), powod))
    return zdrowe, odrzucone
