"""Nadanie kontrolkom TYPU — warunek rysowania ich jak sprzęt, a nie jak klocki.

Model FLX4 wygląda jak render między innymi dlatego, że ma **sześć osobnych
funkcji rysujących** (guzik, gałka, suwak, jog, pad, przełącznik), z których
każda buduje kontrolkę z kilku warstw. Panel klubowy miał jedną funkcję na
wszystko i dwa kształty: koło albo prostokąt. Zanim dojdzie faktura, każdy
element musi wiedzieć, CZYM jest.

Typ wynika z nazwy kontrolki, nie z kształtu — nazwa jest trwała
(etap 1 metody: identyfikatory ustalone raz i nietykalne), kształt się zmieniał.
"""

from __future__ import annotations

import json
import pathlib
import re

TU = pathlib.Path(__file__).parent

WZORCE = [
    (r"^Ekran dotykowy", "ekran"),
    (r"^Ekran na talerzu", "pomin"),          # rysuje go funkcja joga
    (r"^Jog ", "jog"),
    (r"^HOT CUE", "listwa_padow"),
    (r"Suwak TEMPO|^Fader kanału|^Crossfader", "suwak"),
    (r"^Pokrętło|TRIM|^EQ |Filtr kanałowy|MASTER LEVEL|BOOTH|Słuchawki", "galka"),
    (r"^BEAT FX$|^SOUND COLOR FX$|^SEND / RETURN$", "sekcja"),
    (r"^Cztery kanały", "sekcja"),
    (r"Przełącznik krzywej", "przelacznik"),
]
DOMYSLNY = "guzik"


def typ_dla(nazwa: str) -> str:
    for wzor, typ in WZORCE:
        if re.search(wzor, nazwa):
            return typ
    return DOMYSLNY


def main() -> int:
    plik = TU / "uklad.json"
    u = json.loads(plik.read_text(encoding="utf-8"))
    licznik: dict[str, int] = {}
    for d in u["urzadzenia"]:
        for e in d.get("elementy") or []:
            e["typ"] = typ_dla(e["k"])
            licznik[e["typ"]] = licznik.get(e["typ"], 0) + 1
    plik.write_text(json.dumps(u, ensure_ascii=False, indent=1), encoding="utf-8")
    for typ, ile in sorted(licznik.items(), key=lambda t: -t[1]):
        print(f"  {typ:<14} {ile}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
