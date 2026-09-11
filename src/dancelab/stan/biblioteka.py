"""Biblioteka — nazwa utworu, filtr i karta INFO. Jedna reguła dla obu skór.

Do 02.09 filtr biblioteki istniał dwa razy: `tui/app.py::filter_library` na
obiektach analiz i `gui/most.py::szukaj` na słownikach z nagłówków — i już
się rozjechały. Terminal szukał także w nazwie PLIKU, okno nie; przy oknie
tempa terminal liczył „brak tempa" jako 0 (odpada, gdy jest dolny próg), okno
odrzucało go zawsze. Ten sam DJ, ta sama fraza, dwie różne listy.

Dlatego reguła jest napisana na POLACH (`pasuje`), a nie na kształcie
rekordu: terminal woła ją przez `filtruj` na analizach, okno — wprost na
słownikach nagłówków. Zmienia się jedno miejsce.

Rozstrzygnięcia przy scalaniu (jawnie, bo to zmiana zachowania jednej ze
skór): (1) nazwa pliku wchodzi do szukania — tak robił terminal, a to on jest
używany od miesiąca; (2) utwór BEZ tempa przy JAKIMKOLWIEK progu okna odpada
— tak mówił docstring terminala i tak robiło okno; kod terminala
zostawiał go przy samym górnym progu, ale `rozbierz_tempo` wymaga
„lo-hi", więc ta gałąź nigdy nie była osiągalna.
"""

from __future__ import annotations

import pathlib
from typing import Any


def wykonawca_tytul(t: Any) -> tuple[str, str]:
    """Wykonawca i tytuł: tag z analizy → uzupełnienie z RB → parsowanie
    nazwy pliku „Artysta - Tytuł" → sam stem."""
    art = (getattr(t, "artist", None) or "").strip()
    tit = (getattr(t, "title", None) or "").strip()
    if art and tit:
        return art, tit
    stem = pathlib.Path(str(getattr(t, "source_path", "") or "")).stem
    if " - " in stem:
        a, b = stem.split(" - ", 1)
        return (art or a.strip()), (tit or b.strip())
    return art, (tit or stem)


def pasuje(*, sciezka: str | None, wykonawca: str | None, tytul: str | None,
           gatunek: str | None, tonacja: str | None, bpm: float | None,
           szukaj: str = "", tonacja_szukana: str = "",
           bpm_lo: float | None = None, bpm_hi: float | None = None) -> bool:
    """Czy utwór o tych polach przechodzi filtr. Reguła, nie rekord.

    Fraza: podciąg w nazwie pliku, wykonawcy, tytule LUB gatunku, bez
    wielkości liter. Tonacja: dokładna. Okno tempa: domknięte; utwór bez
    tempa przy aktywnym oknie odpada — okno ma znaczyć to, co mówi.
    """
    s = (szukaj or "").strip().lower()
    if s:
        stog = " ".join((pathlib.Path(str(sciezka or "")).stem,
                         wykonawca or "", tytul or "", gatunek or "")).lower()
        if s not in stog:
            return False
    k = (tonacja_szukana or "").strip().upper()
    if k and str(tonacja or "").upper() != k:
        return False
    if bpm_lo is not None or bpm_hi is not None:
        if bpm is None:
            return False
        if bpm_lo is not None and bpm < bpm_lo:
            return False
        if bpm_hi is not None and bpm > bpm_hi:
            return False
    return True


def filtruj(analizy, *, search: str = "", key: str = "",
            bpm_lo: float | None = None, bpm_hi: float | None = None) -> list:
    """Filtr na analizach (terminal). Nazwy argumentów jak w starym
    `filter_library`, żeby wołający i testy nie musiały się zmieniać."""
    wynik = []
    for a in analizy:
        t = a.track
        art, tit = wykonawca_tytul(t)
        if pasuje(sciezka=t.source_path, wykonawca=art, tytul=tit,
                  gatunek=getattr(t, "style_label", None),
                  tonacja=getattr(t, "key_estimate", None),
                  bpm=getattr(t, "bpm_estimate", None),
                  szukaj=search, tonacja_szukana=key,
                  bpm_lo=bpm_lo, bpm_hi=bpm_hi):
            wynik.append(a)
    return wynik


def karta_info(track: Any, rb: dict | None, rb_note: str | None) -> str:
    """Karta INFO (klawisz I): metadane utworu z NAZWANYM źródłem każdej
    liczby — silnik osobno, Rekordbox osobno (niezależny sędzia tempa)."""
    conf = track.key_confidence
    dur = track.duration_sec or 0
    lines = [
        "SILNIK:",
        f"  BPM {track.bpm_estimate or '—'} · ton {track.key_estimate or '?'}"
        + (" (źródło: Rekordbox)"
           if getattr(track, "key_detection_source", None) == "rekordbox"
           else (f" (pew. {conf:.2f})" if conf is not None else "")),
        f"  gatunek: {track.style_label or '—'}",
        f"  długość: {int(dur // 60)}:{int(dur % 60):02d}",
        "  wektor brzmienia: "
        + ("jest" if getattr(track, "sound_embedding", None) is not None
           else "brak"),
        "",
        "PLIK:",
        f"  {track.source_path}",
        "",
        "REKORDBOX:",
    ]
    if rb_note:
        lines.append(f"  {rb_note}")
    elif rb is None:
        lines.append("  nie ma w kolekcji")
    else:
        if rb.get("matched_by") == "twin":
            lines.append("  (dopasowany po tytule — inna ścieżka)")
        lines.append(f"  BPM wg Rekordboxa: {rb.get('bpm') or '—'}")
        if rb.get("comment"):
            lines.append(f"  komentarz: {str(rb['comment'])[:60]}")
        pls = rb.get("playlists") or []
        if pls:
            lines.append(f"  playlisty ({len(pls)}):")
            lines += [f"   · {p}" for p in pls[:12]]
            if len(pls) > 12:
                lines.append(f"   … i {len(pls) - 12} więcej")
        else:
            lines.append("  poza wszystkimi playlistami")
    return "\n".join(lines)


# ------------------------------------------------------ sekcje i sortowanie

#: Sekcje biblioteki (pasek boczny terminala od 11.08, okno od 02.09).
SEKCJE = ("", "ulubione", "filary", "dysk", "apple", "brak")


def zrodlo_wpisu(sciezka: str | None) -> str:
    """dysk / apple / brak — „niedostępne" to plik lokalny, którego nie ma
    (odpięty dysk), a NIE strumień; DJ chce to zobaczyć PRZED setem."""
    from dancelab.tui import zrodlo as Z
    return Z.zrodlo(sciezka)


#: Kolumny, po których sortują obie skóry; klucz jest jeden.
KOLUMNY_SORTU = ("tytul", "wykonawca", "bpm", "tonacja", "dlugosc", "gatunek")


def klucz_sortu(kolumna: str, *, sciezka: str | None, wykonawca: str | None,
                tytul: str | None, bpm: float | None, tonacja: str | None,
                dlugosc: float | None, gatunek: str | None) -> tuple[bool, Any]:
    """(brak_wartosci, klucz). Braki idą NA KONIEC niezależnie od kierunku —
    brak to brak, nie zero (reguła terminala `_lib_sort_missing`).

    Tonacja Camelota sortuje się po numerze, potem literze („8A" < „9A",
    „8A" < „8B"), nie alfabetycznie; wykonawca i tytuł mają nazwę pliku
    jako drugi klucz, żeby remisy były stabilne.
    """
    stem = pathlib.Path(str(sciezka or "")).stem.lower()
    if kolumna == "bpm":
        return bpm is None, (bpm or 0.0)
    if kolumna == "tonacja":
        k = str(tonacja or "")
        num = int(k[:-1]) if len(k) > 1 and k[:-1].isdigit() else 99
        return not k, (num, k[-1:])
    if kolumna == "dlugosc":
        return dlugosc is None, (dlugosc or 0.0)
    if kolumna == "gatunek":
        return not gatunek, (gatunek or "").lower()
    if kolumna == "wykonawca":
        return False, ((wykonawca or "").lower() or "~", stem)
    return False, ((tytul or "").lower() or "~", stem)


def sortuj(wiersze: list, kolumna: str, *, malejaco: bool = False,
           pola) -> list:
    """Posortuj po kolumnie; ``pola(w)`` oddaje słownik argumentów dla
    `klucz_sortu`. Znane wartości w zadanym kierunku, braki zawsze na końcu."""
    if kolumna not in KOLUMNY_SORTU:
        return list(wiersze)
    znane, braki = [], []
    for w in wiersze:
        brak, klucz = klucz_sortu(kolumna, **pola(w))
        (braki if brak else znane).append((klucz, w))
    znane.sort(key=lambda kw: kw[0], reverse=malejaco)
    return [w for _, w in znane] + [w for _, w in braki]
