"""Profil DJ-a z mostu danych mapy — karta w zakładce DJ-e.

Most (spec 2026-08-12): `data/reports/dj_profile.json` generuje skrypt
w kanale R&D z fakty_szew + encje_utwor. Tu tylko czytamy i rysujemy —
pola bez pomiaru pokazujemy jako brak, nigdy nie zgadujemy.

Rysowanie jest w czystych funkcjach (testowalne bez aplikacji), kolory
to te same role co na kartach GUI: chłodny błękit → ciepły bursztyn na
zakresie temp, bursztyn/oliwka/błękit na miernikach, volt tylko na stanie
kolekcji (wybór), nie na danych.
"""

from __future__ import annotations

import json
import pathlib
import unicodedata

PROFIL_PATH = pathlib.Path("data/reports/dj_profile.json")

CHLODNY = "#6db3c9"
CIEPLY = "#e0a458"
OLIWKA = "#a8c952"
FIOLET = "#b48ce8"
ROZ = "#e88cc3"

# tagony: kolor stały dla tej samej nazwy (jak na kartach GUI); dziś niosą
# edycje wydarzeń — slot przejmą gatunki, gdy mapa dostanie ich źródło
PALETA_TAGOW = (CIEPLY, CHLODNY, OLIWKA, FIOLET, ROZ)


def kolor_tagu(nazwa: str) -> str:
    h = 7
    for c in nazwa:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return PALETA_TAGOW[h % len(PALETA_TAGOW)]


def tagony(nazwy: list[str], ile: int = 2) -> str:
    return "  ".join(
        f"[#161509 on {kolor_tagu(n)}] {n.upper()} [/]" for n in nazwy[:ile])


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s or "").casefold().strip()


def wczytaj(path: pathlib.Path | None = None) -> dict:
    """Profil po ZNORMALIZOWANEJ ksywie; brak pliku = pusty słownik
    (karta wraca do skromnej wersji z księgi kotwic, bez zgadywania).
    Ścieżkę czytamy w CHWILI wywołania (nie w definicji) — inaczej
    podmiana w testach nic nie daje."""
    if path is None:
        path = PROFIL_PATH
    if not path.exists():
        return {}
    dane = json.loads(path.read_text()).get("djs", {})
    return {_norm(k): {**v, "ksywa": k} for k, v in dane.items()}


def znajdz(profile: dict, dj: str) -> dict | None:
    return profile.get(_norm(dj))


def pasek_tempa(lo: float, med: float, hi: float, szer: int = 34,
                os_lo: float = 95, os_hi: float = 190) -> str:
    """Oś temp jak na karcie GUI: zakres p10–p90 na wspólnej osi 95–190,
    chłodna połowa → ciepła połowa, kreska mediany."""
    def poz(v: float) -> int:
        return max(0, min(szer - 1, round(
            (v - os_lo) / (os_hi - os_lo) * (szer - 1))))

    a, m, b = poz(lo), poz(med), poz(hi)
    znaki = []
    for i in range(szer):
        if i == m:
            znaki.append("[#e8e4da]┃[/]")
        elif a <= i <= b:
            kolor = CHLODNY if i < m else CIEPLY
            znaki.append(f"[{kolor}]█[/]")
        else:
            znaki.append("[dim]─[/]")
    return "".join(znaki)


def miernik(v: float | None, kolor: str, szer: int = 14) -> str:
    if v is None:
        return "[dim]" + "░" * szer + "[/]  —"
    pelne = max(0, min(szer, round(v * szer)))
    return (f"[{kolor}]{'▮' * pelne}[/][dim]{'▯' * (szer - pelne)}[/]"
            f"  {v:.2f}")


def portret_klockowy(dj: str, profil: dict | None, szer: int = 30) -> str:
    """Portret brzmienia w ziarnie terminala: dwa wiersze klocków ▁▂▃▅▇,
    deterministyczne (ziarno = ksywa), parametry jak na kartach GUI —
    energia → wysokość, skok tempa → poszarpanie, mediana tempa → ile
    ciepła w kolorze. Bez profilu — przerywana linia oczekiwania."""
    if not profil or "bpm_med" not in profil:
        return "[dim]" + "╌" * szer + "[/]"
    h = 7
    for c in dj:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    def r():
        nonlocal h
        h ^= (h << 13) & 0xFFFFFFFF
        h ^= h >> 17
        h ^= (h << 5) & 0xFFFFFFFF
        return (h & 0xFFFFFFFF) / 4294967296
    import math
    en = profil.get("energia") or 0.4
    skok = min((profil.get("skok_bpm") or 8) / 20, 1)
    cieplo = max(0.0, min(1.0, ((profil["bpm_med"] - 95) / 95)))
    klocki = "▁▂▃▄▅▆▇█"
    f1, f2 = 1.3 + r() * 2, 3.5 + r() * 3
    p1, p2 = r() * 6.28, r() * 6.28
    wiersze = []
    for baza in (0.66, 0.33):
        znaki = []
        for i in range(szer):
            x = i / szer
            y = 0.62 * math.sin(f1 * x * 6.28 + p1) \
                + 0.38 * math.sin(f2 * x * 6.28 + p2)
            y = (y + 1) / 2 * (0.45 + en) * baza + (r() - 0.5) * skok * 0.35
            y = max(0.0, min(0.999, y))
            kolor = CHLODNY if (x + (r() - 0.5) * 0.3) < (1 - cieplo) \
                else CIEPLY
            znaki.append(f"[{kolor}]{klocki[int(y * len(klocki))]}[/]")
        wiersze.append("".join(znaki))
    return "\n".join(wiersze)


def karta(dj: str, profil: dict | None, w_kolekcji: bool,
          grupa: str | None, min_pelnych: int = 10) -> str:
    """Treść karty (znaczniki Rich) — układ 1:1 z kartą GUI, na ile
    terminal pozwala: nazwa, stan, tempo, harmonia/skok, mierniki,
    w mapie, edycje."""
    chipy = tagony(profil.get("edycje", [])) if profil else ""
    akcja = ("[#d6f549]✓ w kolekcji[/]   [dim]K = ✕ wyrzuca · "
             "Enter = kotwica[/]" if w_kolekcji else
             "[b]＋[/b] [dim]K dodaje do kolekcji · Enter = kotwica[/]")
    czesci = [f"[b]{dj}[/b]" + (f"   {chipy}" if chipy else ""), "",
              portret_klockowy(dj, profil), ""]
    if profil is None:
        czesci += ["[dim]tego DJ-a nie ma w mapie festiwalowej —[/]",
                   "[dim]karta z pomiarów księgi kotwic:[/]", ""]
        if grupa:
            czesci += [f"grupa brzmieniowa:\n  {grupa}", ""]
        czesci += ["[dim]profil rozszerzony dojdzie, gdy jego sety[/]",
                   "[dim]trafią do mapy (arkusz Janka)[/]", "", akcja]
        return "\n".join(czesci)
    if "bpm_med" not in profil:
        czesci += [
            f"[dim]profil w budowie — {profil.get('szwy_pelne', 0)} z "
            f"{min_pelnych} policzonych szwów;[/]",
            "[dim]karta uzupełni się sama, gdy pomiary dojdą —[/]",
            "[dim]nic tu nie zgadujemy[/]", "",
            f"w mapie:\n{profil.get('sety', 0)} sety · "
            f"{profil.get('szwy', 0)} szwów"]
        czesci += ["", akcja]
        return "\n".join(czesci)
    czesci += [
        f"tempo (uderzenia na minutę) · mediana [b]{profil['bpm_med']}[/b]",
        pasek_tempa(profil["bpm_lo"], profil["bpm_med"], profil["bpm_hi"]),
        f"[b]{profil['bpm_lo']}[/b]" + " " * 24 + f"[b]{profil['bpm_hi']}[/b]",
        "",
        (f"[b]{profil['harm_proc']}%[/b] szwów zgodnych harmonicznie"
         if profil.get("harm_proc") is not None else
         "[dim]harmonia — brak pomiaru[/]"),
        (f"[b]±{profil['skok_bpm']:g}[/b] typowy skok tempa na szwie"
         if profil.get("skok_bpm") is not None else
         "[dim]skok tempa — brak pomiaru[/]"),
        "",
        f"energia  {miernik(profil.get('energia'), CIEPLY)}",
        f"groove   {miernik(profil.get('groove'), OLIWKA)}",
        f"bas      {miernik(profil.get('bas'), CHLODNY)}",
        "",
        "w mapie:",
        f"{profil.get('sety', 0)} sety",
        f"{profil.get('szwy_pelne', 0)} szwów policzonych",
    ]
    if profil.get("utwory_zmierzone"):
        czesci.append(f"{profil['utwory_zmierzone']} utworów")
    if grupa:
        czesci += ["", f"[dim]grupa brzmieniowa: {grupa}[/]"]
    czesci += ["", akcja]
    return "\n".join(czesci)
