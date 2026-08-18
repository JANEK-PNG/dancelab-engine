"""Formularz do druku (A4) z `playlisty_dane.json` — ocena setów na papierze.

Skąd wzory: skala 1–5 = MOS wg ITU-T P.800; wymiary całej playlisty
(spójność, różnorodność, przebieg) = Bonnin & Jannach, ACM Computing
Surveys 2014; ocena przejść per aspekt = Vande Veire & De Bie, EURASIP
JASMP 2018; kategorie „co zgrzyta" = 1:1 TOPIC_KEYWORDS z naszego
`validation/dj_benchmark.py`, żeby papier dało się przepisać do CSV.

Na życzenie Janka (17.08): na końcu każdej playlisty siatka do ODRĘCZNEGO
szkicu krzywej energii miksu — oś X to numery utworów, oś Y energia.
"""

from __future__ import annotations

import html
import json
import pathlib

KATALOG = pathlib.Path(__file__).parent
SESJE = [("SESJA 1", ["OCENA A", "OCENA B"]), ("SESJA 2", ["OCENA C", "OCENA D"]),
         ("SESJA 3", ["OCENA E", "OCENA F"]), ("SESJA 4", ["OCENA G", "OCENA H"]),
         ("SESJA 5", ["OCENA I", "OCENA J"])]

CSS = """
@page { size: A4; margin: 14mm 12mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
       font-size: 9.5pt; line-height: 1.35; color: #111; margin: 0; }
h1 { font-size: 15pt; margin: 0 0 2mm; }
h2 { font-size: 12pt; margin: 0 0 1mm; }
.playlista { page-break-before: always; }
.pierwsza { page-break-before: auto; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 0.4pt solid #999; padding: 1.2mm 1.5mm; text-align: left;
         vertical-align: middle; }
th { background: #eee; font-size: 8pt; text-transform: uppercase;
     letter-spacing: 0.04em; }
.nr { width: 7mm; text-align: right; color: #666; }
.ocena { width: 26mm; text-align: center; font-size: 10.5pt;
         letter-spacing: 0.45em; white-space: nowrap; }
.zgrzyt { width: 34mm; text-align: center; font-size: 8.5pt;
          letter-spacing: 0.28em; white-space: nowrap; }
.utwor { font-size: 8.5pt; }
.utwor b { font-size: 9pt; }
.meta { color: #555; font-size: 8.5pt; margin: 0 0 2mm; }
.ramka { border: 0.6pt solid #333; padding: 2.5mm 3mm; margin: 2mm 0 4mm;
         font-size: 8.8pt; }
.skala td { border: 0.4pt solid #bbb; font-size: 8.6pt; }
.podsum td { height: 7mm; }
.kreska { border-bottom: 0.5pt solid #888; display: inline-block;
          min-width: 42mm; }
.zrodla { font-size: 7.6pt; color: #555; margin-top: 3mm; }
.naglowek-pola { display: flex; gap: 8mm; margin: 1mm 0 2.5mm;
                 font-size: 9pt; }
.energia { margin-top: 3mm; }
.energia .tytul { font-size: 8.8pt; margin: 0 0 1mm; }
"""


def siatka_energii(n: int) -> str:
    """Siatka do odręcznej krzywej energii: X = utwory 1..n, Y = energia."""
    szer, wys = 700, 120
    lewy, prawy, gora, dol = 34, 8, 6, 18
    pole_w = szer - lewy - prawy
    pole_h = wys - gora - dol
    linie = []
    # poziome linie pomocnicze (5 poziomów energii)
    for i in range(6):
        y = gora + pole_h * i / 5
        linie.append(f'<line x1="{lewy}" y1="{y:.1f}" x2="{szer - prawy}" '
                     f'y2="{y:.1f}" stroke="#ccc" stroke-width="0.6" '
                     f'stroke-dasharray="2 3"/>')
    # pionowa kreska na każdy utwór + numer pod spodem
    for i in range(n):
        x = lewy + pole_w * i / max(n - 1, 1)
        linie.append(f'<line x1="{x:.1f}" y1="{gora}" x2="{x:.1f}" '
                     f'y2="{gora + pole_h}" stroke="#ddd" stroke-width="0.5"/>')
        linie.append(f'<text x="{x:.1f}" y="{wys - 5}" font-size="7.5" '
                     f'fill="#666" text-anchor="middle">{i + 1}</text>')
    # ramka i opisy osi
    linie.append(f'<rect x="{lewy}" y="{gora}" width="{pole_w}" '
                 f'height="{pole_h}" fill="none" stroke="#333" '
                 f'stroke-width="0.9"/>')
    linie.append(f'<text x="{lewy - 5}" y="{gora + 8}" font-size="7.5" '
                 f'fill="#333" text-anchor="end">szczyt</text>')
    linie.append(f'<text x="{lewy - 5}" y="{gora + pole_h}" font-size="7.5" '
                 f'fill="#333" text-anchor="end">cicho</text>')
    return (f'<div class="energia"><p class="tytul"><b>Krzywa energii</b> — '
            f'narysuj z grubsza, jak Twoim zdaniem płynie energia tej '
            f'playlisty od startu do końca (oś pozioma = numery utworów):</p>'
            f'<svg viewBox="0 0 {szer} {wys}" width="100%" '
            f'style="display:block">{"".join(linie)}</svg></div>')


def strona_instrukcji() -> str:
    return """
<h1>DanceLab · Ocena setów na papierze</h1>
<p class="meta">10 playlist w Rekordboksie, folder <b>DanceLab Ocena</b> (OCENA A–J).
Oceniasz W CIEMNO: część playlist to pełne wyjście silnika, część to kontrola —
nie wiadomo która jest którą, przydział leży zapieczętowany i otwieramy go po
wpisaniu wszystkich ocen. Oceniaj w 5 sesjach (2 playlisty na sesję) — tyle
wymaga bramka pomiarowa (≥30 przejść na sesję).</p>

<div class="ramka">
<b>Jak oceniać przejście — skala 1–5 (wg ITU-T P.800, kotwice DJ-skie):</b>
<table class="skala" style="margin-top:1.5mm">
<tr><td style="width:8mm;text-align:center"><b>5</b></td><td>Zagrałbym to przejście publicznie bez zmian.</td></tr>
<tr><td style="text-align:center"><b>4</b></td><td>Dobre — drobiazg do poprawki, ale broni się.</td></tr>
<tr><td style="text-align:center"><b>3</b></td><td>Poprawne — nie boli, nie zachwyca.</td></tr>
<tr><td style="text-align:center"><b>2</b></td><td>Słabe — słychać zgrzyt, wymagałoby przeróbki.</td></tr>
<tr><td style="text-align:center"><b>1</b></td><td>Złe — nie zagrałbym tego w żadnej formie.</td></tr>
</table>
<p style="margin:2mm 0 0"><b>„Co zgrzyta” — zakreśl literę</b> (kategorie zgodne z naszym
agregatorem ocen):&nbsp;
<b>T</b>&nbsp;tempo/siatka · <b>S</b>&nbsp;styl/klimat · <b>E</b>&nbsp;energia ·
<b>M</b>&nbsp;moment przejścia · <b>D</b>&nbsp;duplikat/ta sama płyta ·
<b>K</b>&nbsp;kontekst setu</p>
<p style="margin:1.5mm 0 0">Słuchaj przejścia z playlisty w Rekordboksie (koniec utworu →
początek następnego wystarczy). Oceniaj pierwszym uchem — powtórka najwyżej raz.
Przerwa między sesjami minimum godzina. Na końcu każdej playlisty narysuj
odręcznie krzywą energii — jak set płynął.</p>
</div>

<div class="zrodla"><b>Skąd ten formularz (źródła):</b> skala pięciostopniowa MOS —
ITU-T P.800; wymiary oceny całej playlisty (spójność, różnorodność, płynność) —
Bonnin &amp; Jannach, „Automated Generation of Music Playlists”, ACM Computing
Surveys 2014; ocena przejść automatycznego DJ-a per aspekt — Vande Veire &amp;
De Bie, EURASIP J. Audio Speech Music Proc. 2018; kategorie zgrzytu — słownik
tematów naszego <span style="font-family:monospace">dj_benchmark.py</span>
(5 sesji × ≥30 przejść).</div>
"""


def strona_playlisty(nazwa: str, tracki: list, sesja: str,
                     pierwsza: bool = False) -> str:
    wiersze = []
    for i in range(len(tracki) - 1):
        a, b = tracki[i], tracki[i + 1]
        wiersze.append(f"""<tr>
<td class="nr">{i + 1}</td>
<td class="utwor"><b>{html.escape(a['artysta'][:26])}</b> — {html.escape(a['tytul'][:34])}<br>
<b>{html.escape(b['artysta'][:26])}</b> — {html.escape(b['tytul'][:34])}</td>
<td style="width:12mm;text-align:center;color:#555">{a['bpm']:.0f}→{b['bpm']:.0f}</td>
<td class="ocena">1&nbsp;2&nbsp;3&nbsp;4&nbsp;5</td>
<td class="zgrzyt">T&nbsp;S&nbsp;E&nbsp;M&nbsp;D&nbsp;K</td>
<td style="width:30mm"></td></tr>""")
    likert = "1&nbsp;&nbsp;2&nbsp;&nbsp;3&nbsp;&nbsp;4&nbsp;&nbsp;5"
    return f"""
<div class="playlista{' pierwsza' if pierwsza else ''}">
<h2>{nazwa} <span style="font-weight:normal;color:#555">· {len(tracki)} utworów · {sesja}</span></h2>
<div class="naglowek-pola">
<span>Data: <span class="kreska"></span></span>
<span>Gdzie słuchane: <span class="kreska"></span></span>
</div>
<table>
<tr><th>#</th><th>wychodzi → wchodzi</th><th>BPM</th><th>ocena przejścia</th>
<th>co zgrzyta</th><th>notatka</th></tr>
{''.join(wiersze)}
</table>
<table class="podsum" style="margin-top:2.5mm">
<tr><th colspan="2">Cała playlista (zakreśl) — wymiary wg Bonnin &amp; Jannach 2014</th></tr>
<tr><td>Spójność — czy to się trzyma razem jako jeden set</td><td class="ocena">{likert}</td></tr>
<tr><td>Różnorodność — czy nie jest monotonnie</td><td class="ocena">{likert}</td></tr>
<tr><td>Przebieg — czy energia prowadzi gdzieś sensownie</td><td class="ocena">{likert}</td></tr>
<tr><td><b>Zagrałbym to publicznie</b> (całość, po poprawkach dopuszczalnych ręką)</td><td class="ocena">{likert}</td></tr>
<tr><td colspan="2" style="height:10mm">Uwaga o całości:</td></tr>
</table>
{siatka_energii(len(tracki))}
</div>"""


def main() -> int:
    dane = json.loads((KATALOG / "playlisty_dane.json").read_text(encoding="utf-8"))
    czesci = [f"<style>{CSS}</style>", strona_instrukcji()]
    pierwsza = True
    for snazwa, czlonkowie in SESJE:
        for nazwa in czlonkowie:
            czesci.append(strona_playlisty(nazwa, dane[nazwa], snazwa, pierwsza))
            pierwsza = False
    out = KATALOG / "formularz_oceny.html"
    out.write_text("<!doctype html><meta charset='utf-8'>"
                   "<title>DanceLab — formularz oceny</title>" + "".join(czesci),
                   encoding="utf-8")
    przejscia = sum(len(v) - 1 for v in dane.values())
    print(f"zapisano: {out}")
    print(f"przejść do oceny łącznie: {przejscia}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
