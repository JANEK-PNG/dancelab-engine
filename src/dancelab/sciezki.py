"""Korzeń repozytorium — jedno miejsce, z którego liczą go obie skóry.

Leży na SZCZYCIE pakietu, poza `stan/` i `tui/`, bo nie może niczego
importować ani być importowany przez `__init__` pakietu, który ciągnie
wszystko naraz: `stan/__init__` importuje `stan.plan`, a ten czyta
`plan_store.PLANS_DIR` — więc `plan_store` sięgające po `stan.sciezki`
kończyło się cyklem (złapane 02.09 przy pierwszej próbie).

Dane, które zbierają się TYLKO DO PRZODU (dziennik decyzji, edycje padów),
nie mogą wisieć na bieżącym katalogu procesu. Terminal startuje z korzenia,
więc ścieżki względne działały mu przez przypadek; okno odpalone z ikony
dostaje `cwd` ustawiony przez launchd i pisałoby gdzie indziej — albo wcale,
bo `/data/exports/…` nie jest zapisywalne. Rozwidlona po cichu historia jest
gorsza niż jej brak, bo wygląda na kompletną.

Ograniczenie, które trzeba znać: to działa dla repozytorium (`src/` obok
`data/`). Po spakowaniu do `.app` katalogi danych będą musiały pójść do
`~/Library/Application Support` — wtedy zmienia się TEN plik, nie pięć
miejsc, które go wołają.
"""

from __future__ import annotations

import pathlib

#: src/dancelab/sciezki.py → korzeń repo dwa poziomy wyżej
KORZEN = pathlib.Path(__file__).resolve().parents[2]
