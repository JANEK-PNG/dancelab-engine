"""Input gates for measurement scripts: no data means refuse, never zero.

`Path.glob()` on a directory that does not exist raises nothing — it yields an
empty iterator. A measurement loop then runs zero times, the statistics come out
as `None` or `0%`, the script exits 0 and overwrites its own result artifact
with the emptiness.

That is not hypothetical. On 2026-09-01 `corpus_priors.py` was run while the
corpus drive was unmounted. It reported medians of `None`, claimed every BPM
bucket at 0%, and overwrote `priors_v1.json` — the file the harmonic and tempo
lifts of Result 1 and Result 2 are built from. Only a backup taken minutes
earlier saved the artifact.

ADR-005 says an unknown is shown as unknown and never invented. The same rule
belongs one level up: a measurement with no input must refuse out loud instead
of publishing an empty result.
"""

from __future__ import annotations

from pathlib import Path


class BrakDanychWejsciowych(RuntimeError):
    """Raised instead of quietly measuring nothing."""


def wymagaj_plikow(katalog: Path, wzorzec: str, po_co: str) -> list[Path]:
    """Return the matching files, or refuse with a reason naming what is missing.

    Args:
        katalog: directory the measurement reads from.
        wzorzec: glob pattern, e.g. ``"mix*.json"``.
        po_co: what the files are for, quoted back in the error so the message
            says which measurement just refused to run.
    """
    katalog = Path(katalog)
    if not katalog.exists():
        raise BrakDanychWejsciowych(
            f"{po_co}: katalog nie istnieje — {katalog}\n"
            f"  Jeśli to dysk z korpusem, podepnij go i uruchom ponownie.\n"
            f"  Nie liczę i NIE nadpisuję wyniku pustką."
        )
    if not katalog.is_dir():
        raise BrakDanychWejsciowych(f"{po_co}: to nie jest katalog — {katalog}")

    pliki = sorted(katalog.glob(wzorzec))
    if not pliki:
        raise BrakDanychWejsciowych(
            f"{po_co}: katalog istnieje, ale nie ma w nim nic pasującego do "
            f"'{wzorzec}' — {katalog}\n"
            f"  Pusty wynik pomiaru to nie jest pomiar zerowy. Nie zapisuję."
        )
    return pliki
