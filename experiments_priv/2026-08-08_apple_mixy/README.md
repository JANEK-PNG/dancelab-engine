# Żniwa Apple Music: katalog „Miksy DJ-skie" → tracklisty

Wejście: 20 zrzutów ekranu Janka (siatka katalogu DJ-miksów, 08.08.2026).
Pipeline (generator datasetu z rozmowy głosowej, zautomatyzowany):

1. `ocr_zrzutow.py` — Vision (macOS) czyta zrzuty; parsowanie po twardej
   własności UI: tytuł kończy się „(DJ Mix)", wiersz pod nim to DJ.
   227 wpisów (z zanieczyszczeniami z okładek — celowo nie czyszczone).
2. `dociagnij_tracklisty.py` — iTunes Search jako CZYŚCICIEL OCR-u:
   pewne dopasowanie do albumu „(DJ Mix)" albo odmowa. 227 → 126 albumów.
   LEKCJA: iTunes Lookup NIE zwraca segmentów DJ-miksów (streaming-only).
3. `tracklisty_web.py` — strony music.apple.com niosą pełny track-list
   w `serialized-server-data`. 126/126 stron, zero błędów.

Wynik: `miksy_katalog.json` + `tracklisty/*.json` —
**120 unikatowych miksów · 2114 utworów · 1994 przejścia · 1875 tripletów**,
z czasami utworów (dwell time: mediana 3,8 min, p10 2,2, p90 5,5).
Gatunki: Dance 70, House 25, Electronic 8, Techno 5, Afro House 5, plus
pojedyncze Jungle/DnB, Breakbeat, Dubstep, Bass, IDM.

Czego tu NIE ma: audio, tonacji, BPM. Do tripletu v2 cechy trzeba dociągnąć
z 30-sekundowych preview iTunes (previewUrl jest w JSON-ie stron) albo
z własnej analizy. 101 wpisów OCR bez pewnego dopasowania czeka w
`miksy_katalog.json` (powód przy każdym).
