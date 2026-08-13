"""Ten sam utwór w kilku kopiach — scalanie widoku biblioteki.

Janek 13.08, ze zrzutu: „mocne multiplikacje utworów". Zmierzone na jego
bibliotece: 1914 analiz to w rzeczywistości **1690 utworów** — 222 wpisy
nadmiarowe w 159 grupach. „Bodhi — 433Mhz" występuje sześć razy.

To NIE jest błąd silnika. Ten sam plik leży w kilku folderach (LEKCJA nr5,
PREMIER, Media.localized, Dj Sets, pule eksperymentów), a do tego dochodzi
bliźniak z Apple Music. Każda kopia dostała własną analizę.

Scalamy WIDOK, nie dane: żaden plik ani żadna analiza nie znika, a ulubione
i filary dalej wskazują na swoje identyfikatory. Zostaje jeden
przedstawiciel grupy, wybrany tak, żeby niczego nie stracić:

  1. plik, który NAPRAWDĘ jest na dysku — bo tylko taki da się odsłuchać,
  2. z nich ten z NAJWIĘKSZĄ liczbą policzonych cech — analiza z pełnego
     pliku wie więcej niż wpis z Rekordboxa,
  3. dopiero potem Apple Music, a na końcu ścieżka bez pliku.
"""

from __future__ import annotations

import pathlib
import re
import unicodedata

CECHY = ("spectral_flux", "low_freq_energy_ratio", "onset_density",
         "pulse_clarity_proxy", "syncopation_proxy", "bass_energy")


def klucz(track) -> str:
    """Wykonawca + tytuł, sprowadzone do porównywalnej postaci."""
    tytul = getattr(track, "title", None) or ""
    if not tytul:
        tytul = pathlib.Path(getattr(track, "source_path", "") or "").stem
    s = f"{getattr(track, 'artist', None) or ''} {tytul}"
    s = unicodedata.normalize("NFC", s).casefold()
    s = re.sub(r"[\(\[].*?[\)\]]", " ", s)          # (Original Mix) itp.
    s = re.sub(r"[^0-9a-zà-ɏ]+", " ", s)
    return " ".join(s.split())


def _bogactwo(a) -> int:
    """Ile realnie policzonych cech niesie ta analiza."""
    for f in (getattr(a, "features", None) or [])[:8]:
        ile = sum(1 for c in CECHY if getattr(f, c, None) is not None)
        if ile:
            return ile
    return 0


def _ranga(a) -> tuple:
    t = a.track
    sp = str(getattr(t, "source_path", "") or "")
    na_dysku = False
    if sp and not sp.startswith("apple-music:"):
        try:
            na_dysku = pathlib.Path(sp).exists()
        except OSError:
            na_dysku = False
    # większe = lepsze
    return (na_dysku, _bogactwo(a), not sp.startswith("apple-music:"))


def scal(analizy: list) -> tuple[list, int]:
    """(widok bez duplikatów, ile wpisów scalono). Kolejność zachowana."""
    najlepszy: dict[str, object] = {}
    ile_w_grupie: dict[str, int] = {}
    kolejnosc: list[str] = []
    for a in analizy:
        k = klucz(a.track)
        if not k:
            k = f"__bez_nazwy__{id(a)}"
        if k not in najlepszy:
            najlepszy[k] = a
            ile_w_grupie[k] = 1
            kolejnosc.append(k)
            continue
        ile_w_grupie[k] += 1
        if _ranga(a) > _ranga(najlepszy[k]):
            najlepszy[k] = a
    widok = [najlepszy[k] for k in kolejnosc]
    return widok, len(analizy) - len(widok)


def ile_kopii(analizy: list) -> dict[str, int]:
    """track_id przedstawiciela → ile kopii ma w bibliotece."""
    grupy: dict[str, list] = {}
    for a in analizy:
        grupy.setdefault(klucz(a.track), []).append(a)
    out: dict[str, int] = {}
    for lista in grupy.values():
        rep = max(lista, key=_ranga)
        out[rep.track.track_id] = len(lista)
    return out
