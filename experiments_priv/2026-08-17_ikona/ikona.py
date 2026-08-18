"""Ikona DanceLab — bohaterem jest SZEW, nie utwory.

DLACZEGO NIE FALA
-----------------
Trzy podejścia i trzy wnioski:

  1. dwie splecione nici          → „wygląda jak aplikacja matematyczna" (Janek)
  2. jedna fala zmieniająca kolor → muzyczne, ale mówi „jeden utwór", nie „dwa"
  3. dwie fale, jedna nad drugą   → „generyczne strasznie" (Janek) — i słusznie,
                                     bo falę ma KAŻDA aplikacja dźwiękowa

Wniosek: dopóki rysuję utwory, rysuję to samo, co wszyscy. A DanceLab nie jest
o utworach. Twoje własne zdanie z sierpnia: *utwory są jedynie motorem tego,
co jest pomiędzy*.

Więc ikoną jest PRZERWA. Dwa pola — talia A i talia B — a między nimi szew.
Szew jest wąski przy brzegach i szeroki w środku, bo tam grają oba utwory
naraz. Volt istnieje wyłącznie w nim.

  · bursztyn #e0a458  — talia A          (motyw aplikacji, app.py:904)
  · błękit   #6db3c9  — talia B
  · volt     #d6f549  — szew, i tylko szew
  · grafit   #171614  — tło aplikacji

TRZY UJĘCIA
-----------
  A · SZEW PEŁNY   dwa pełne pola, między nimi voltowa soczewka
  B · SZEW CIĘTY   to samo, ale krawędzie pól są nacięte rytmem — szept
                   o dźwięku, bez rysowania fali
  C · SAM SZEW     pola przygaszone, świeci wyłącznie przerwa
"""

from __future__ import annotations

import math
import pathlib

from PIL import Image, ImageDraw

KATALOG = pathlib.Path(__file__).parent
BOK = 1024

GRAFIT = (23, 22, 20)
BURSZTYN = (224, 164, 88)
BLEKIT = (109, 179, 201)
VOLT = (214, 245, 73)
CICHY_A = (96, 72, 42)
CICHY_B = (46, 76, 88)


def zbuduj(bok: int = BOK, wariant: str = "A") -> Image.Image:
    """Szew POZIOMY. Talia A u góry, talia B u dołu, między nimi volt.

    Pionowa soczewka z poprzedniej wersji wyglądała jednoznacznie niedobrze —
    symetryczny kształt zwężający się do dwóch czubków zawsze tak wygląda.
    Poziom to kasuje i przy okazji jest bliższy prawdzie: na CDJ-ach czas
    biegnie w poziomie, więc szew też ma leżeć w poprzek, a nie stać.

    A: szew równej grubości — najspokojniejszy.
    B: szew grubieje w miejscu, gdzie oba utwory grają najgłośniej.
    C: talie przygaszone, świeci wyłącznie szew.
    """
    NAD = 4 if bok >= 128 else 8
    R = bok * NAD
    img = Image.new("RGB", (R, R), GRAFIT)
    d = ImageDraw.Draw(img)

    sr = R / 2
    kol_a = CICHY_A if wariant == "C" else BURSZTYN
    kol_b = CICHY_B if wariant == "C" else BLEKIT

    def polgrub(t):
        if wariant == "A":
            return R * 0.070
        # grubieje tam, gdzie grają oba naraz
        return R * (0.038 + 0.075 * math.sin(math.pi * t) ** 1.6)

    gora, dol = [], []
    n = 300
    for i in range(n + 1):
        t = i / n
        x = R * t
        g = polgrub(t)
        gora.append((x, sr - g))
        dol.append((x, sr + g))

    d.polygon([(0, 0)] + gora + [(R, 0)], fill=kol_a)
    d.polygon([(0, R)] + dol + [(R, R)], fill=kol_b)
    d.polygon(gora + dol[::-1], fill=VOLT)

    img = img.resize((bok, bok), Image.LANCZOS)
    maska = Image.new("L", (bok, bok), 0)
    ImageDraw.Draw(maska).rounded_rectangle(
        [0, 0, bok - 1, bok - 1], radius=int(bok * 0.225), fill=255)
    out = Image.new("RGBA", (bok, bok), (0, 0, 0, 0))
    out.paste(img, (0, 0), maska)
    return out


def main() -> int:
    warianty = ("A", "B", "C")
    for w in warianty:
        zbuduj(BOK, w).save(KATALOG / f"ikona_{w}.png")
        print(f"  ikona_{w}.png")
    skale = (128, 64, 32)
    szer = BOK + 40
    ark = Image.new("RGB", (szer * len(warianty), BOK + 260), (12, 12, 12))
    for i, w in enumerate(warianty):
        ark.paste(zbuduj(BOK, w).convert("RGB"), (i * szer + 20, 20))
        x = i * szer + 20
        for sk in skale:
            ark.paste(zbuduj(sk, w).convert("RGB").resize(
                (sk * 2, sk * 2), Image.NEAREST), (x, BOK + 50))
            x += sk * 2 + 30
    ark.save(KATALOG / "porownanie.png")
    print("  porownanie.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
