"""His seam and mine, side by side, in the same units.

The DJ's challenge was fair: measuring transitions is not the same as making one.
So every seam he played was rebuilt from the same two records and rendered, and
both are drawn here on one axis — his measured from the recording, mine read off
the envelope that produced the audio. Where the lines diverge, the copy failed,
and the page is built so that is the easiest thing to see.

Audio is embedded for the two seams he described from memory, since those are the
ones where his ear has already been on record.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path

import numpy as np

from dancelab.preview.transition_simulation import build_transition_envelope

MIX_BPM = 136.0
W, H = 560, 62
BANDS = (("bas", "low"), ("środek", "mid"), ("góra", "high"))
EMBED = ("01_Open_Deck_13", "01_Open_Deck_14")


def _pts(x, y, span):
    return " ".join(f"{xi / span * W:.0f},{H - min(max(yi, 0), 1.5) / 1.5 * H:.0f}"
                    for xi, yi in zip(x, y) if xi <= span * 1.001)


def his_panel(seam, band, span) -> str:
    d = seam["bands"][band]
    t = np.asarray(d["t"]) - seam["b_in_sec"]
    keep = (t >= -2) & (t <= span)
    floor = seam["floors"][band]
    fy = H - floor / 1.5 * H
    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none">'
            f'<rect class="floor" x="0" y="{fy:.0f}" width="{W}" height="{H - fy:.0f}"/>'
            f'<polyline class="ca" points="{_pts(t[keep], np.asarray(d["a"])[keep], span)}"/>'
            f'<polyline class="cb" points="{_pts(t[keep], np.asarray(d["b"])[keep], span)}"/>'
            f"</svg>")


def mine_panel(row, key, span) -> str:
    env = build_transition_envelope(row["profile"], duration_beats=row["beats_rendered"],
                                    grid_beats=8, bass_open_at=row.get("bass_open_at"))
    c = env.curves()
    dur = row["beats_rendered"] * 60.0 / MIX_BPM
    t = np.asarray(env.beat_positions) / row["beats_rendered"] * dur
    fa = np.asarray(c["fader_a"]) * np.asarray(c[f"{key}_a"])
    fb = np.asarray(c["fader_b"]) * np.asarray(c[f"{key}_b"])
    end = "" if dur >= span * 0.99 else (
        f'<line class="cut" x1="{dur / span * W:.0f}" y1="0" '
        f'x2="{dur / span * W:.0f}" y2="{H}"/>')
    return (f'<svg viewBox="0 0 {W} {H}" preserveAspectRatio="none">{end}'
            f'<polyline class="ca" points="{_pts(t, fa, span)}"/>'
            f'<polyline class="cb" points="{_pts(t, fb, span)}"/>'
            f"</svg>")


def audio(base: Path, side: str, name: str) -> str:
    f = base / "m4a" / f"{side}_{name}.m4a"
    if not f.exists():
        return ""
    b64 = base64.b64encode(f.read_bytes()).decode()
    return (f'<audio controls preload="none" '
            f'src="data:audio/mp4;base64,{b64}"></audio>')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--seam-dirs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    base = Path(args.pairs).parent
    rows = json.loads(Path(args.pairs).read_text())
    seams = {}
    for d in args.seam_dirs:
        for f in Path(d).glob("seam_*.json"):
            seams[f"{Path(d).name}_{f.stem[-2:]}"] = json.loads(f.read_text())

    cards, opens = [], []
    for r in rows:
        s = seams.get(r["seam"])
        if not s or not r.get("mine"):
            continue
        span = max(r["blend_measured_sec"], r["beats_rendered"] * 60.0 / MIX_BPM)
        lanes = "".join(
            f'<div class="lane"><span class="bl">{lab}</span>'
            f'<div class="side">{his_panel(s, lab, span)}</div>'
            f'<div class="side">{mine_panel(r, key, span)}</div></div>'
            for lab, key in BANDS)
        oa = r.get("bass_open_at")
        if oa:
            opens.append(oa)
        chips = f'<span class="chip">{r["profile"].replace("_", " ")}</span>'
        if oa:
            chips += f'<span class="chip on">bas otwarty w {oa*100:.0f}%</span>'
        short = r["beats_rendered"] * 60.0 / MIX_BPM < r["blend_measured_sec"] * 0.95
        if short:
            chips += (f'<span class="chip warn">skrócone do '
                      f'{r["beats_rendered"]} uderzeń</span>')
        snd = ""
        if r["seam"] in EMBED:
            snd = (f'<div class="audio"><div>{audio(base, "twoje", r["seam"])}</div>'
                   f'<div>{audio(base, "moje", r["seam"])}</div></div>')
        cards.append(f"""<article class="seam">
<header><h3><span class="da">{html.escape(r['from'].split('—')[-1].strip())}</span>
<span class="ar">→</span><span class="db">{html.escape(r['to'].split('—')[-1].strip())}</span></h3>
<div class="chips">{chips}<span class="chip q">{r['blend_measured_sec']:.0f} s</span></div></header>
<div class="heads"><span>TY — zmierzone z nagrania</span><span>JA — odtworzone</span></div>
{lanes}{snd}</article>""")

    Path(args.out).write_text(TEMPLATE.format(
        n=len(cards), median_open=np.median(opens) * 100 if opens else 0,
        n_open=len(opens), cards="".join(cards)), encoding="utf-8")
    print(f"Wrote {args.out} ({Path(args.out).stat().st_size/1024/1024:.1f} MB)")
    return 0


TEMPLATE = """<title>A/B — Twój set i moja kopia</title>
<style>
:root {{
  --g:#faf9f7; --p:#fff; --e:#e3dfd8; --ink:#1b1a18; --dim:#7a756d;
  --a:#c8562a; --b:#1d7f8c; --floor:#0000000d; --warn:#9a6b21;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:"Helvetica Neue",Helvetica,Arial,sans-serif;
}}
@media (prefers-color-scheme:dark) {{ :root {{
  --g:#0f1114; --p:#161a1f; --e:#272d35; --ink:#e8e6e2; --dim:#8d939b;
  --a:#e8834f; --b:#4cbecd; --floor:#ffffff0d; --warn:#d4b155; }} }}
:root[data-theme="dark"] {{
  --g:#0f1114; --p:#161a1f; --e:#272d35; --ink:#e8e6e2; --dim:#8d939b;
  --a:#e8834f; --b:#4cbecd; --floor:#ffffff0d; --warn:#d4b155; }}
:root[data-theme="light"] {{
  --g:#faf9f7; --p:#fff; --e:#e3dfd8; --ink:#1b1a18; --dim:#7a756d;
  --a:#c8562a; --b:#1d7f8c; --floor:#0000000d; --warn:#9a6b21; }}
* {{ box-sizing:border-box; }}
body {{ background:var(--g); color:var(--ink); font-family:var(--sans); margin:0;
  padding:clamp(18px,4vw,52px); line-height:1.55; }}
.wrap {{ max-width:980px; margin:0 auto; }}
h1 {{ font-size:clamp(25px,4.2vw,38px); margin:0 0 8px; letter-spacing:-.02em; }}
.sub {{ color:var(--dim); max-width:64ch; margin:0 0 30px; }}
.find {{ background:var(--p); border:1px solid var(--e); border-left:3px solid var(--b);
  border-radius:3px; padding:18px 20px; margin:0 0 34px; }}
.find b {{ font-family:var(--mono); font-size:22px; }}
.find p {{ margin:6px 0 0; color:var(--dim); font-size:13.5px; max-width:70ch; }}
.seam {{ background:var(--p); border:1px solid var(--e); border-radius:3px;
  padding:14px 16px 12px; margin-bottom:12px; }}
.seam header {{ display:flex; flex-wrap:wrap; justify-content:space-between;
  gap:8px 20px; align-items:baseline; margin-bottom:10px; }}
.seam h3 {{ margin:0; font-size:13.5px; font-weight:600; display:flex; gap:7px;
  flex-wrap:wrap; align-items:baseline; }}
.da {{ color:var(--a); }} .db {{ color:var(--b); }} .ar {{ color:var(--dim); }}
.chips {{ display:flex; gap:6px; flex-wrap:wrap; }}
.chip {{ font-family:var(--mono); font-size:10px; letter-spacing:.04em; padding:2px 6px;
  border:1px solid var(--e); border-radius:2px; color:var(--dim); }}
.chip.on {{ color:var(--b); border-color:currentColor; }}
.chip.warn {{ color:var(--warn); border-color:currentColor; }}
.heads {{ display:grid; grid-template-columns:44px 1fr 1fr; gap:8px;
  font-family:var(--mono); font-size:9.5px; letter-spacing:.09em; color:var(--dim);
  text-transform:uppercase; margin-bottom:3px; }}
.heads span:first-child {{ grid-column:2; }}
.lane {{ display:grid; grid-template-columns:44px 1fr 1fr; gap:8px; align-items:center; }}
.bl {{ font-family:var(--mono); font-size:9.5px; color:var(--dim); text-align:right; }}
.side {{ min-width:0; border-left:1px solid var(--e); padding-left:6px; }}
svg {{ width:100%; height:38px; display:block; overflow:visible; }}
.floor {{ fill:var(--floor); }}
polyline {{ fill:none; stroke-width:1.7; vector-effect:non-scaling-stroke;
  stroke-linejoin:round; }}
.ca {{ stroke:var(--a); }} .cb {{ stroke:var(--b); }}
.cut {{ stroke:var(--warn); stroke-width:1; stroke-dasharray:2 3; opacity:.7; }}
.audio {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:12px;
  padding-left:52px; }}
audio {{ width:100%; height:32px; }}
.legend {{ display:flex; gap:18px; flex-wrap:wrap; font-family:var(--mono); font-size:11px;
  color:var(--dim); margin:0 0 24px; }}
.legend i {{ display:inline-block; width:15px; height:2px; vertical-align:middle;
  margin-right:5px; }}
.note {{ font-size:12.5px; color:var(--dim); border-left:2px solid var(--e);
  padding-left:14px; max-width:70ch; margin-top:28px; }}
</style>
<div class="wrap">
<h1>Twój set i moja kopia</h1>
<p class="sub">{n} przejść. Po lewej Twoje — zmierzone z nagrania. Po prawej moje —
odtworzone z tych samych dwóch utworów i zrenderowane. Ta sama oś czasu, te same
trzy pasma, ten sam sposób rysowania.</p>

<div class="find">
  <b>{median_open:.0f}%</b>
  <p>Tu moja kopia najpierw przegrała. Podręcznikowy „bass swap" oddaje dół w połowie
  przejścia — Ty otwierasz bas wchodzącego utworu dopiero przy <b>{median_open:.0f}%</b>
  jego długości (mediana z {n_open} szwów zamkniętych ręką), czyli praktycznie w chwili
  przekazania. Pierwsze 21 renderów zrobiłem szablonem z 50% i żaden Cię nie odwzorował.
  Renderer dostał parametr; te wykresy są już po poprawce.</p>
</div>

<div class="legend">
  <span><i style="background:var(--a)"></i>utwór wychodzący</span>
  <span><i style="background:var(--b)"></i>utwór wchodzący</span>
  <span><i style="background:var(--floor);height:9px"></i>podłoga szumu (tylko po lewej)</span>
  <span><i style="background:var(--warn)"></i>koniec mojego renderu</span>
</div>

{cards}

<p class="note">Po lewej krzywe są odzyskane z nagrania i niosą szum metody — dlatego
mają podłogę. Po prawej to dokładna obwiednia, którą zagrał renderer, więc jest gładka;
gładkość nie oznacza, że jest lepsza. Przejścia dłuższe niż 256 uderzeń renderer skraca
i jest to zaznaczone.</p>
</div>
"""


if __name__ == "__main__":
    raise SystemExit(main())
