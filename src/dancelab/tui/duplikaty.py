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

Tożsamość Apple (11.09). Wykonawca+tytuł łapał tylko część bliźniaków
plik ↔ strumień: zmierzone na 8260 analizach — 135 par o tym samym id
katalogu Apple, z czego po tytule scalało się 46, a 89 było widocznych dwa
razy („feat." w tytule, inna kolejność wykonawców, „entranas" zamiast
„entrañas" w tagu pliku). Dlatego grupa to spójna składowa: łączą się wpisy
o tym samym kluczu tytułu ALBO tym samym id Apple (most ISRC dla plików,
ścieżka dla strumieni). Składowa, nie dwa słowniki — inaczej kopia WAV bez
ISRC odkleiłaby się od swojego pliku z ISRC, z którym łączy ją tytuł.
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


def apple_id(track) -> str | None:
    """Id katalogu Apple Music: z mostu ISRC (`apple_catalog_id`) albo ze ścieżki strumienia."""
    cid = getattr(track, "apple_catalog_id", None)
    if cid:
        return str(cid)
    sp = str(getattr(track, "source_path", "") or "")
    if sp.startswith("apple-music:tracks:"):
        return sp.rsplit(":", 1)[1] or None
    return None


def _grupy(analizy: list) -> list[list]:
    """Spójne składowe po kluczu tytułu i po id Apple, w kolejności pierwszego wystąpienia."""
    rodzic = list(range(len(analizy)))

    def korzen(i: int) -> int:
        while rodzic[i] != i:
            rodzic[i] = rodzic[rodzic[i]]
            i = rodzic[i]
        return i

    pierwszy: dict[str, int] = {}
    for i, a in enumerate(analizy):
        klucze = []
        k = klucz(a.track)
        if k:
            klucze.append("t:" + k)
        cid = apple_id(a.track)
        if cid:
            klucze.append("a:" + cid)
        for kl in klucze:
            if kl not in pierwszy:
                pierwszy[kl] = i
                continue
            x, y = korzen(pierwszy[kl]), korzen(i)
            if x != y:                       # korzeń = najmniejszy indeks składowej
                rodzic[max(x, y)] = min(x, y)
    grupy: dict[int, list] = {}
    for i, a in enumerate(analizy):
        grupy.setdefault(korzen(i), []).append(a)
    return [grupy[r] for r in sorted(grupy)]


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
    """(widok bez duplikatów, ile wpisów scalono). Kolejność zachowana;
    przy remisie rangi zostaje pierwszy wpis grupy."""
    widok = [max(g, key=_ranga) for g in _grupy(analizy)]
    return widok, len(analizy) - len(widok)


def ile_kopii(analizy: list) -> dict[str, int]:
    """track_id przedstawiciela → ile kopii ma w bibliotece."""
    out: dict[str, int] = {}
    for lista in _grupy(analizy):
        rep = max(lista, key=_ranga)
        out[rep.track.track_id] = len(lista)
    return out
