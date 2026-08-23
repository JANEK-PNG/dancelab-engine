"""Widok setu: ruchy rąk z MIDI na tle krzywych utworów. Wyjście: widok_setu.html.

UCZCIWOŚĆ: bez nagrania audio (Apple Music blokuje REC) pozycja w utworze
jest PRZYBLIŻONA — krzywa utworu zakotwiczona w momencie wpisu do Historii
Rekordboxa i rysowana przerywaną kreską. Dokładne pozycje da dopiero
dopasowanie audio przy secie z plików lokalnych.
"""
import json, glob, html, pathlib
from datetime import datetime

K = pathlib.Path(__file__).parent
ROOT = K.parents[1]
PROC = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
PXS = 3.0  # px na sekundę

midi = [json.loads(l) for l in open(sorted(glob.glob(str(K / "set_*_midi.jsonl")))[-1])]
hist_all = [json.loads(l) for l in open(sorted(glob.glob(str(K / "set_*_utwory.jsonl")))[-1])]
h0 = hist_all[0]["ts"]
hist = [r for r in hist_all if r["ts"] > h0 + 60]
T0, T1 = midi[0]["ts"] - 10, midi[-1]["ts"] + 10
W = (T1 - T0) * PXS
def X(ts): return (ts - T0) * PXS

def czas_hist(r):
    return datetime.strptime(r["created_at"][:19], "%Y-%m-%d %H:%M:%S").timestamp()

# ---- serie 14-bit ----
PARY = {(0,0):"d1_tempo",(0,4):"d1_trim",(0,7):"d1_hi",(0,11):"d1_mid",(0,15):"d1_low",(0,19):"d1_fader",
        (1,0):"d2_tempo",(1,4):"d2_trim",(1,7):"d2_hi",(1,11):"d2_mid",(1,15):"d2_low",(1,19):"d2_fader",
        (6,31):"cross",(6,23):"cfx1",(6,24):"cfx2",(4,2):"fxlevel"}
serie = {v: [] for v in PARY.values()}
msb = {}
jog = {0: {}, 1: {}}
przyciski = []
NAZWY_N = {11:"PLAY",12:"CUE",77:"4BEAT",54:"JOG dotyk",88:"SYNC",16:"IN",17:"OUT"}
for r in midi:
    ch, d1, d2, ts = r["ch"], r["d1"], r["d2"], r["ts"]
    if r["type"] == "control_change":
        if (ch, d1) in PARY: msb[(ch, d1)] = d2
        elif (ch, d1 - 32) in PARY and (ch, d1 - 32) in msb:
            serie[PARY[(ch, d1 - 32)]].append((ts, (msb[(ch, d1 - 32)] << 7) | d2))
        elif ch in (0, 1) and d1 in (33, 34, 35, 41):
            kubel = int(ts); jog[ch][kubel] = jog[ch].get(kubel, 0) + abs(d2 - 64)
    elif r["type"] == "note_on" and d2 > 0:
        if ch in (0, 1) and d1 in NAZWY_N: przyciski.append((ts, ch, NAZWY_N[d1]))
        elif ch in (7, 8, 9, 10): przyciski.append((ts, 0 if ch in (7, 8) else 1, f"PAD{(d1 & 15) + 1}"))
        elif ch == 6 and d1 == 0: przyciski.append((ts, None, "SMART CFX"))
        elif ch == 6 and d1 == 1: przyciski.append((ts, None, "SMART FADER"))
        elif ch == 6 and d1 in (70, 71): przyciski.append((ts, d1 - 70, "LOAD"))

# ---- przydział utworów do decków po LOAD ----
loady = [(ts, deck) for ts, deck, n in przyciski if n == "LOAD"]
bloki = []
for i, r in enumerate(hist):
    t = czas_hist(r)
    kon = czas_hist(hist[i + 1]) if i + 1 < len(hist) else T1
    kand = [(abs(t - lt), d) for lt, d in loady if lt < t + 5]
    deck, pewny = (min(kand)[1], min(kand)[0] < 120) if kand else (i % 2, False)
    bloki.append({"r": r, "t0": t, "t1": kon, "deck": deck, "pewny": pewny})

def rms_krzywa(cid):
    p = PROC / f"rb{cid}.json"
    if not p.exists(): return None
    a = json.loads(p.read_text())
    fr = [(f["timestamp_sec"], f["rms"]) for f in a.get("features", [])
          if f.get("rms") is not None]
    return fr or None

# ---- SVG ----
LANES = {"osie": (0, 26), "tracks": (26, 66), "d1": (74, 218), "d2": (226, 370),
         "mix": (378, 452), "fx": (460, 512)}
H = 540
out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H}" '
       f'style="background:#0d0e11;font-family:-apple-system,system-ui">']
def lin(x1,y1,x2,y2,kolor,w=1,dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{kolor}" stroke-width="{w}"{d}/>')
def txt(x,y,t,kolor="#7a8090",rozm=11,kot="start"):
    out.append(f'<text x="{x:.1f}" y="{y:.1f}" fill="{kolor}" font-size="{rozm}" text-anchor="{kot}">{html.escape(str(t))}</text>')
def poly(pts, kolor, w=1.5, dash=None, opac=1):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    s = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    out.append(f'<polyline points="{s}" fill="none" stroke="{kolor}" stroke-width="{w}" opacity="{opac}"{d}/>')

# oś czasu
t = int(T0 // 60 + 1) * 60
while t < T1:
    lin(X(t), 0, X(t), H, "#1b1e24")
    txt(X(t) + 3, 16, datetime.fromtimestamp(t).strftime("%H:%M"), "#565c68")
    t += 60
# bloki utworów + krzywe RMS
for b in bloki:
    y0, y1 = LANES["tracks"]
    dy0, dy1 = LANES["d1"] if b["deck"] == 0 else LANES["d2"]
    kolor = "#5ee0ff" if b["deck"] == 0 else "#ff9f43"
    out.append(f'<rect x="{X(b["t0"]):.1f}" y="{y0}" width="{(b["t1"]-b["t0"])*PXS:.1f}" height="{y1-y0-4}" fill="{kolor}" opacity="0.12"/>')
    txt(X(b["t0"]) + 4, y0 + 15, b["r"]["utwor"][:60], kolor, 12)
    txt(X(b["t0"]) + 4, y0 + 31, f'deck {b["deck"]+1}' + ("" if b["pewny"] else " (przydział niepewny)"), "#7a8090", 10)
    fr = rms_krzywa(b["r"]["content_id"])
    if fr:
        mx = max(v for _, v in fr) or 1
        okno = b["t1"] - b["t0"]
        pts = [(X(b["t0"] + fs), dy1 - 8 - (v / mx) * (dy1 - dy0 - 30))
               for fs, v in fr if fs <= okno]
        if len(pts) > 1: poly(pts, kolor, 1, dash="3 3", opac=0.55)
# etykiety pasm
for nazwa, (y0, y1) in [("DECK 1", LANES["d1"]), ("DECK 2", LANES["d2"])]:
    txt(6, y0 + 14, nazwa, "#d9dbe0", 12); lin(0, y0, W, y0, "#262a33")
# serie na deckach: LOW gruba, MID cienka, FADER biała
for d, (y0, y1) in [(1, LANES["d1"]), (2, LANES["d2"])]:
    for klucz, kolor, w in [(f"d{d}_low", "#ff5c7a", 2), (f"d{d}_mid", "#a78bfa", 1),
                            (f"d{d}_hi", "#2ee6c5", 1), (f"d{d}_fader", "#d9dbe0", 1.5)]:
        s = serie[klucz]
        if s: poly([(X(ts), y1 - 8 - v / 16383 * (y1 - y0 - 30)) for ts, v in s], kolor, w)
    # jog jako słupki u dołu pasma
    for kubel, suma in jog[d - 1].items():
        h = min(suma / 400, 1) * 18
        out.append(f'<rect x="{X(kubel):.1f}" y="{y1-8-h:.1f}" width="{PXS:.1f}" height="{h:.1f}" fill="#565c68"/>')
# przyciski jako kropki
for ts, deck, n in przyciski:
    if n == "LOAD": continue
    if deck is None: y = LANES["fx"][0] + 12; kolor = "#ffd166"
    else: y0, y1 = LANES["d1"] if deck == 0 else LANES["d2"]; y = y0 + 22; kolor = "#ffd166"
    out.append(f'<circle cx="{X(ts):.1f}" cy="{y}" r="3" fill="{kolor}"><title>{html.escape(n)} {datetime.fromtimestamp(ts).strftime("%H:%M:%S")}</title></circle>')
    if n.startswith(("SMART", "SYNC")): txt(X(ts) + 4, y + 4, n, "#ffd166", 9)
# mikser: crossfader + CFX
y0, y1 = LANES["mix"]; lin(0, y0, W, y0, "#262a33"); txt(6, y0 + 14, "CROSSFADER · CFX", "#d9dbe0", 12)
for klucz, kolor, w in [("cross", "#d9dbe0", 2), ("cfx1", "#5ee0ff", 1), ("cfx2", "#ff9f43", 1)]:
    s = serie[klucz]
    if s: poly([(X(ts), y1 - 6 - v / 16383 * (y1 - y0 - 26)) for ts, v in s], kolor, w)
y0, y1 = LANES["fx"]; lin(0, y0, W, y0, "#262a33"); txt(6, y0 + 14, "FX LEVEL/DEPTH", "#d9dbe0", 12)
if serie["fxlevel"]:
    poly([(X(ts), y1 - 6 - v / 16383 * (y1 - y0 - 26)) for ts, v in serie["fxlevel"]], "#ffd166", 1.5)
out.append("</svg>")

szkic = f"""<!doctype html><meta charset="utf-8"><title>Set 23.08 — ręce na krzywych</title>
<body style="margin:0;background:#0d0e11;color:#d9dbe0;font:14px -apple-system,system-ui">
<div style="padding:12px 16px;border-bottom:1px solid #262a33">
<b>Set 23.08.2026, {datetime.fromtimestamp(T0).strftime("%H:%M")}–{datetime.fromtimestamp(T1).strftime("%H:%M")}</b>
· {len(midi)} ruchów MIDI · {len(hist)} utworów z Historii Rekordboxa<br>
<span style="color:#7a8090">Krzywa utworu (przerywana) = nasza analiza RMS zakotwiczona w momencie wpisu do
Historii — pozycja PRZYBLIŻONA, bo Rekordbox nie nagrywa audio przy strumieniach Apple Music.
Czerwona linia = bas (EQ LOW), fioletowa = środek, morska = góra, biała = fader kanału / crossfader,
słupki szare = ruch joga, kropki żółte = przyciski (najedź myszą).</span></div>
<div style="overflow-x:auto">{''.join(out)}</div></body>"""
(K / "widok_setu.html").write_text(szkic, encoding="utf-8")
print("zapisano widok_setu.html · szerokość", int(W), "px · bloki:",
      [(b["r"]["utwor"][:20], f'deck{b["deck"]+1}', b["pewny"]) for b in bloki])
