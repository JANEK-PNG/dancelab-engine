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
