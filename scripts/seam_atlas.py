"""Draw every measured seam as one page: a console readout, not a report.

Twenty-one transitions are too many to read as tables and too few to reduce to a
single average. Each one gets the same small chart on the same axes, aligned at
the moment the incoming record arrives, so shape can be compared by eye — which
is the only way to notice that two seams with identical numbers were played
differently.

Everything drawn is measured. The noise floor is shaded on every panel, because a
curve inside it is not a quiet deck, it is an unknown one.
"""

from __future__ import annotations

import argparse
import glob
import html
import json
from pathlib import Path

import numpy as np

BANDS = ("bas", "środek", "góra")
W, H = 1160, 74           # per-band panel, user units
MAX_PTS = 110
Y_MAX = 1.5


def _poly(t, g, t0, span, floor):
    """A gain curve as SVG points, plus the same curve clipped to the floor."""
    if len(t) == 0:
        return "", ""
    idx = np.linspace(0, len(t) - 1, min(MAX_PTS, len(t))).astype(int)
    x = (np.asarray(t)[idx] - t0) / span * W
    y = H - np.clip(np.asarray(g)[idx], 0, Y_MAX) / Y_MAX * H
    solid, faint = [], []
    for xi, yi, gi in zip(x, y, np.asarray(g)[idx]):
        (solid if gi > floor else faint).append(f"{xi:.0f},{yi:.0f}")
    return " ".join(solid), " ".join(faint)


def panel(seam, band, t0, span) -> str:
    d = seam["bands"][band]
    t = d["t"]
    floor = seam["floors"][band]
    fy = H - floor / Y_MAX * H
    out = [f'<svg class="panel" viewBox="0 0 {W} {H}" preserveAspectRatio="none" '
           f'role="img" aria-label="pasmo {band}">']
    out.append(f'<rect class="floor" x="0" y="{fy:.0f}" width="{W}" height="{H - fy:.0f}"/>')
    for lvl in (0.5, 1.0):
        y = H - lvl / Y_MAX * H
        out.append(f'<line class="grid" x1="0" y1="{y:.0f}" x2="{W}" y2="{y:.0f}"/>')
    # handover markers: where the incoming record is first heard and the outgoing last
    for key, cls in (("b_in_sec", "mark-in"), ("a_out_sec", "mark-out")):
        x = (seam[key] - t0) / span * W
        out.append(f'<line class="{cls}" x1="{x:.0f}" y1="0" x2="{x:.0f}" y2="{H}"/>')
    for deck, key in (("a", "a"), ("b", "b")):
        solid, faint = _poly(t, d[key], t0, span, floor)
        if faint:
            out.append(f'<polyline class="c{deck} faint" points="{faint}"/>')
        if solid:
            out.append(f'<polyline class="c{deck}" points="{solid}"/>')
    out.append("</svg>")
    return "".join(out)


def card(seam) -> str:
    t = seam["bands"]["bas"]["t"]
    t0, span = t[0], max(t[-1] - t[0], 1e-6)
    verdict = seam.get("b_bass_hold_verdict")
    hold = seam.get("b_bass_held_sec") or 0
    thin = seam.get("a_thinned_sec") or 0
    tag = ""
    if hold >= 4:
        cls = {"ręka": "ok", "utwór sam nie ma tam basu": "no",
               "niepewne": "maybe"}.get(verdict, "maybe")
        label = {"ręka": "ręka", "utwór sam nie ma tam basu": "to nagranie, nie ręka",
                 "niepewne": "niepewne"}.get(verdict, "niepewne")
        tag = f'<span class="tag {cls}">{label}</span>'
    rows = "".join(
        f'<div class="lane"><span class="band">{b}</span>{panel(seam, b, t0, span)}</div>'
        for b in BANDS)
    a_from = html.escape(seam["from"])
    b_to = html.escape(seam["to"])
    return f"""<article class="seam">
<header>
  <h3><span class="deck-a">{a_from}</span><span class="arrow">→</span><span class="deck-b">{b_to}</span></h3>
  <dl>
    <div><dt>nakładanie</dt><dd>{seam['blend_sec']:.0f}<i>s</i></dd></div>
    <div><dt>bas zamknięty</dt><dd>{hold:.0f}<i>s</i> {tag}</dd></div>
    <div><dt>wychudzenie</dt><dd>{thin:.0f}<i>s</i></dd></div>
  </dl>
</header>
{rows}
<footer><span>{t[0]/60:.0f}:{int(t[0])%60:02d}</span><span>{span:.0f} s</span>
<span>{t[-1]/60:.0f}:{int(t[-1])%60:02d}</span></footer>
</article>"""


def bars(seams) -> str:
    """Every blend length on one axis — the distribution, not the average."""
    mx = max(s["blend_sec"] for s in seams)
    rows = []
    for s in sorted(seams, key=lambda x: -x["blend_sec"]):
        w = s["blend_sec"] / mx * 100
        hold = (s.get("b_bass_held_sec") or 0) / max(s["blend_sec"], 1e-9) * 100
        rows.append(
            f'<div class="brow"><span class="blab">{html.escape(s["to"].split("—")[-1].strip()[:30])}</span>'
            f'<span class="btrack"><span class="bfill" style="width:{w:.1f}%">'
            f'<span class="bhold" style="width:{min(hold,100):.1f}%"></span></span></span>'
            f'<span class="bnum">{s["blend_sec"]:.0f}s</span></div>')
    return "".join(rows)


def stems(content) -> str:
    """Drums up, bass down — the entry-point rule, one column per seam."""
    rows = content["rows"]
    si = {n: i for i, n in enumerate(content["stems"])}
    cells = []
    for r in rows:
        d, b = r["entry"][si["drums"]], r["entry"][si["bass"]]
        cells.append(
            f'<div class="scol" title="{html.escape(r["to"])}">'
            f'<span class="sup" style="height:{min(abs(d)*100,50):.0f}%"></span>'
            f'<span class="sdn" style="height:{min(abs(b)*100,50):.0f}%"></span></div>')
    return "".join(cells)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("seam_dirs", nargs="+")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--content", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    seams = []
    for d in args.seam_dirs:
        for f in sorted(glob.glob(str(Path(d) / "seam_*.json"))):
            s = json.loads(Path(f).read_text())
            if s.get("blend_sec"):
                s["set"] = Path(d).name.replace("_", " ")
                seams.append(s)
    prof = json.loads(Path(args.profile).read_text())
    cont = json.loads(Path(args.content).read_text())

    by_set = {}
    for s in seams:
        by_set.setdefault(s["set"], []).append(s)
    sections = "".join(
        f'<h2 class="setname">{html.escape(name)}<em>{len(v)} zmierzonych przejść</em></h2>'
        + "".join(card(s) for s in v)
        for name, v in by_set.items())

    hand = sum(1 for s in seams if s.get("b_bass_hold_is_hand"))
    Path(args.out).write_text(TEMPLATE.format(
        n=len(seams), total=prof["n_total"],
        median=prof["blend_sec"]["median"], beats=prof["blend_beats_median"],
        lo=prof["blend_sec"]["min"], hi=prof["blend_sec"]["max"],
        hand=hand, hand_pct=hand / len(seams) * 100,
        thin_pct=prof["thinned_share"] * 100,
        real=cont["corr_real"], shuf=cont["corr_shuffled_mean"],
        bars=bars(seams), stems=stems(cont), sections=sections),
        encoding="utf-8")
    print(f"Wrote {args.out}  ({Path(args.out).stat().st_size/1024:.0f} kB)")
    return 0


TEMPLATE = """<title>Atlas szwów — 21 przejść zmierzonych</title>
<style>
:root {{
  --ground:#faf9f7; --panel:#ffffff; --edge:#e2ded7; --ink:#1b1a18; --dim:#78736c;
  --a:#c8562a; --b:#1d7f8c; --floor:#00000010; --grid:#00000012;
  --ok:#1d7f8c; --no:#b0342c; --maybe:#9a7b21;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:"Helvetica Neue",Helvetica,Arial,sans-serif;
}}
@media (prefers-color-scheme:dark) {{
  :root {{ --ground:#0f1114; --panel:#161a1f; --edge:#262c34; --ink:#e8e6e2; --dim:#8b9199;
    --a:#e8834f; --b:#4cbecd; --floor:#ffffff0f; --grid:#ffffff14;
    --ok:#4cbecd; --no:#e8695e; --maybe:#d4b155; }}
}}
:root[data-theme="dark"] {{
  --ground:#0f1114; --panel:#161a1f; --edge:#262c34; --ink:#e8e6e2; --dim:#8b9199;
  --a:#e8834f; --b:#4cbecd; --floor:#ffffff0f; --grid:#ffffff14;
  --ok:#4cbecd; --no:#e8695e; --maybe:#d4b155;
}}
:root[data-theme="light"] {{
  --ground:#faf9f7; --panel:#ffffff; --edge:#e2ded7; --ink:#1b1a18; --dim:#78736c;
  --a:#c8562a; --b:#1d7f8c; --floor:#00000010; --grid:#00000012;
  --ok:#1d7f8c; --no:#b0342c; --maybe:#9a7b21;
}}
* {{ box-sizing:border-box; }}
body {{ background:var(--ground); color:var(--ink); font-family:var(--sans);
  line-height:1.55; margin:0; padding:clamp(20px,4vw,56px); }}
.wrap {{ max-width:1020px; margin:0 auto; display:flex; flex-direction:column; gap:44px; }}
h1 {{ font-size:clamp(26px,4.4vw,40px); margin:0 0 6px; letter-spacing:-.02em;
  text-wrap:balance; font-weight:700; }}
.sub {{ color:var(--dim); margin:0; max-width:62ch; }}
h2.setname {{ font-size:13px; text-transform:uppercase; letter-spacing:.14em;
  font-family:var(--mono); color:var(--dim); margin:34px 0 12px; display:flex;
  justify-content:space-between; align-items:baseline; border-bottom:1px solid var(--edge);
  padding-bottom:8px; }}
h2.setname em {{ font-style:normal; letter-spacing:0; text-transform:none; font-size:12px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:1px;
  background:var(--edge); border:1px solid var(--edge); border-radius:3px; overflow:hidden; }}
.stat {{ background:var(--panel); padding:16px 18px; }}
.stat b {{ display:block; font-family:var(--mono); font-size:26px; font-weight:600;
  letter-spacing:-.02em; font-variant-numeric:tabular-nums; }}
.stat span {{ color:var(--dim); font-size:12.5px; }}
.stat i {{ font-style:normal; font-size:15px; color:var(--dim); }}
.block {{ background:var(--panel); border:1px solid var(--edge); border-radius:3px;
  padding:20px 22px; }}
.block h3 {{ margin:0 0 4px; font-size:15px; }}
.block p {{ margin:0 0 16px; color:var(--dim); font-size:13.5px; max-width:66ch; }}
.brow {{ display:grid; grid-template-columns:minmax(0,1fr) 2.6fr 44px; gap:12px;
  align-items:center; padding:2.5px 0; }}
.blab {{ font-size:12px; color:var(--dim); overflow:hidden; text-overflow:ellipsis;
  white-space:nowrap; }}
.btrack {{ background:var(--floor); height:13px; border-radius:2px; }}
.bfill {{ display:block; height:100%; background:var(--b); opacity:.32; border-radius:2px; }}
.bhold {{ display:block; height:100%; background:var(--b); border-radius:2px; }}
.bnum {{ font-family:var(--mono); font-size:12px; text-align:right;
  font-variant-numeric:tabular-nums; color:var(--dim); }}
.stemchart {{ display:flex; gap:3px; height:130px; align-items:center;
  border-top:1px solid var(--edge); border-bottom:1px solid var(--edge); }}
.scol {{ flex:1; display:flex; flex-direction:column; justify-content:center;
  height:100%; gap:1px; }}
.sup {{ background:var(--b); border-radius:1px 1px 0 0; margin-top:auto; }}
.sdn {{ background:var(--a); border-radius:0 0 1px 1px; margin-bottom:auto; }}
.axis {{ display:flex; justify-content:space-between; font-family:var(--mono);
  font-size:11px; color:var(--dim); margin-top:8px; }}
.seam {{ background:var(--panel); border:1px solid var(--edge); border-radius:3px;
  padding:14px 16px 10px; margin-bottom:10px; }}
.seam header {{ display:flex; flex-wrap:wrap; gap:10px 26px; align-items:baseline;
  justify-content:space-between; margin-bottom:10px; }}
.seam h3 {{ margin:0; font-size:14px; font-weight:600; display:flex; flex-wrap:wrap;
  gap:8px; align-items:baseline; }}
.deck-a {{ color:var(--a); }} .deck-b {{ color:var(--b); }}
.arrow {{ color:var(--dim); }}
.seam dl {{ display:flex; gap:22px; margin:0; }}
.seam dl div {{ display:flex; flex-direction:column; }}
.seam dt {{ font-size:10.5px; text-transform:uppercase; letter-spacing:.1em;
  color:var(--dim); font-family:var(--mono); }}
.seam dd {{ margin:0; font-family:var(--mono); font-size:16px; font-weight:600;
  font-variant-numeric:tabular-nums; display:flex; align-items:baseline; gap:6px; }}
.seam dd i {{ font-style:normal; font-size:11px; color:var(--dim); }}
.tag {{ font-size:9.5px; letter-spacing:.07em; text-transform:uppercase; padding:1px 5px;
  border-radius:2px; border:1px solid currentColor; font-weight:500; }}
.tag.ok {{ color:var(--ok); }} .tag.no {{ color:var(--no); }} .tag.maybe {{ color:var(--maybe); }}
.lane {{ display:grid; grid-template-columns:52px minmax(0,1fr); align-items:center; gap:8px; }}
.band {{ font-family:var(--mono); font-size:10px; color:var(--dim); text-align:right; }}
.panel {{ width:100%; height:44px; display:block; overflow:visible; }}
.floor {{ fill:var(--floor); }}
.grid {{ stroke:var(--grid); stroke-width:1; }}
.mark-in {{ stroke:var(--b); stroke-width:1.5; stroke-dasharray:3 3; opacity:.6; }}
.mark-out {{ stroke:var(--a); stroke-width:1.5; stroke-dasharray:3 3; opacity:.6; }}
polyline {{ fill:none; stroke-width:1.7; vector-effect:non-scaling-stroke;
  stroke-linejoin:round; }}
.ca {{ stroke:var(--a); }} .cb {{ stroke:var(--b); }}
.faint {{ opacity:.22; stroke-width:1.2; }}
.seam footer {{ display:flex; justify-content:space-between; font-family:var(--mono);
  font-size:10px; color:var(--dim); margin-top:6px; padding-left:60px; }}
.legend {{ display:flex; flex-wrap:wrap; gap:18px; font-size:12px; color:var(--dim);
  font-family:var(--mono); }}
.legend span {{ display:flex; align-items:center; gap:6px; }}
.key {{ width:16px; height:2px; }}
.note {{ font-size:12.5px; color:var(--dim); border-left:2px solid var(--edge);
  padding-left:14px; max-width:70ch; }}
</style>
<div class="wrap">
<header>
  <h1>Atlas szwów</h1>
  <p class="sub">{n} przejść z {total} zmierzonych w dwóch nagranych setach. Każdy wykres
  pokazuje, ile z każdego utworu było słychać w trzech pasmach — czyli co robiły ręce.
  Szara strefa to podłoga szumu metody: krzywa w niej nie oznacza cichego decka,
  tylko nieznanego.</p>
</header>

<div class="stats">
  <div class="stat"><b>{median:.0f}<i> s</i></b><span>mediana nakładania · {beats:.0f} uderzeń</span></div>
  <div class="stat"><b>{lo:.0f}–{hi:.0f}<i> s</i></b><span>od najkrótszego do najdłuższego</span></div>
  <div class="stat"><b>{hand_pct:.0f}<i> %</i></b><span>bas wchodzącego zamknięty ręką ({hand} z {n})</span></div>
  <div class="stat"><b>{thin_pct:.0f}<i> %</i></b><span>wychodzący wychudzony przed wyjściem</span></div>
</div>

<section class="block">
  <h3>Długość każdego przejścia</h3>
  <p>Jasny pasek to całe nakładanie, ciemniejszy w środku — odcinek z zamkniętym basem
  wchodzącego utworu.</p>
  {bars}
</section>

<section class="block">
  <h3>Gdzie wchodzą utwory</h3>
  <p>Każda kolumna to jedno przejście. W górę — o ile mocniej utwór opiera się w tym
  miejscu na perkusji niż zwykle. W dół — o ile słabiej na basie. Mierzone względem
  średniej tego samego nagrania, więc to nie jest głośność, tylko charakter fragmentu.
  W losowo wybranych momentach tych samych utworów taki układ zdarza się w 18% przypadków;
  w punktach wejścia — w 71%.</p>
  <div class="stemchart">{stems}</div>
  <div class="axis"><span>↑ perkusja mocniej</span><span>↓ bas słabiej</span></div>
</section>

<section class="block">
  <h3>Czego nie znaleźliśmy</h3>
  <p class="note">Hipoteza brzmiała: wchodzący utwór wypełnia to, co wychodzący zwolnił.
  Korelacja dla prawdziwych par wyszła {real:+.3f}, a dla par przetasowanych — czyli
  wyjść zestawionych z cudzymi wejściami — {shuf:+.3f}. Prawdziwa wartość leży wewnątrz
  rozrzutu przypadkowego. Reguły komplementarności nie ma; hipoteza obalona i zapisana.</p>
</section>

<div class="legend">
  <span><i class="key" style="background:var(--a)"></i> utwór wychodzący</span>
  <span><i class="key" style="background:var(--b)"></i> utwór wchodzący</span>
  <span><i class="key" style="background:var(--floor);height:10px"></i> podłoga szumu</span>
  <span>linia przerywana — wejście B i wyjście A</span>
</div>

{sections}

<p class="note">Wszystko zmierzone z nagrań: miks minus oba utwory źródłowe. Przejścia,
których nie udało się zakotwiczyć w czasie, zostały pominięte, a nie oszacowane.</p>
</div>
"""


if __name__ == "__main__":
    raise SystemExit(main())
