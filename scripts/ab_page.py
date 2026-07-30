"""His seam and my rebuild of it, as spectrograms with the measurements laid over.

Three band curves answer "how much of each record, in three bands" and hide
everything that happens between the bands. A filter sweeping, a kick sitting under
a pad, where a record's air actually lives — none of it survives being flattened
into three numbers, and one of them hid a twenty-five second hole in the low end
that was plainly audible. The full transform was already computed for the fit;
only the display was throwing it away.

The measurements are not replaced by the picture, they are drawn onto it: where
the incoming record arrives, where the outgoing one leaves, where the bass was
opened. A spectrogram shows what happened; the markers say what we claim about it,
and putting them on the same image is what makes the claim checkable.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import math
from pathlib import Path

import numpy as np

F_LO, F_HI = 30.0, 16000.0
LABELS = (50, 100, 200, 500, 1000, 2000, 5000, 10000)
EMBED = ("01_Open_Deck_13", "01_Open_Deck_14")


def y_frac(f: float) -> float:
    """Where a frequency sits on the image, top to bottom."""
    return 1.0 - math.log(f / F_LO) / math.log(F_HI / F_LO)


def data_uri(path: Path) -> str:
    kind = "jpeg" if path.suffix in (".jpg", ".jpeg") else "png"
    return f"data:image/{kind};base64,{base64.b64encode(path.read_bytes()).decode()}"


def marks(items, dur) -> str:
    out = []
    for at, cls, label in items:
        if at is None or not (0 <= at <= dur):
            continue
        out.append(f'<span class="mk {cls}" style="left:{at / dur * 100:.2f}%">'
                   f'<i>{label}</i></span>')
    return "".join(out)


def panel(img: Path, dur: float, items) -> str:
    rows = "".join(f'<span class="hz" style="top:{y_frac(f) * 100:.1f}%">'
                   f'{f // 1000}k</span>' if f >= 1000 else
                   f'<span class="hz" style="top:{y_frac(f) * 100:.1f}%">{f}</span>'
                   for f in LABELS)
    return (f'<div class="spec"><img src="{data_uri(img)}" alt="spektrogram"/>'
            f'{marks(items, dur)}<div class="scale">{rows}</div>'
            f'<span class="dur">{dur:.0f} s</span></div>')


def audio(base: Path, side: str, name: str) -> str:
    f = base / "m4a" / f"{side}_{name}.m4a"
    if not f.exists():
        return ""
    return (f'<audio controls preload="none" '
            f'src="data:audio/mp4;base64,{base64.b64encode(f.read_bytes()).decode()}">'
            f"</audio>")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--seam-dirs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    base = Path(args.pairs).parent
    spec = base / "spektro"
    rows = json.loads(Path(args.pairs).read_text())
    seams = {}
    for d in args.seam_dirs:
        for f in Path(d).glob("seam_*.json"):
            seams[f"{Path(d).name}_{f.stem[-2:]}"] = json.loads(f.read_text())

    cards, opens = [], []
    for r in rows:
        s = seams.get(r["seam"])
        mine_img = spec / f"moje_{r['seam']}.jpg"
        his_img = spec / f"twoje_{r['seam']}.jpg"
        if not s or not mine_img.exists() or not his_img.exists():
            continue
        dur = r["beats_rendered"] * 60.0 / r.get("target_bpm", 136.0)
        oa = r.get("bass_open_at")
        if oa:
            opens.append(oa)

        # His clip was cut from the snapped cue, so the same instant sits at zero
        # in both images and the markers mean the same thing on each side.
        start = s["b_in_sec"] if r.get("his_start") is None else r["his_start"]
        his_marks = [(s["b_in_sec"] - start, "in", "wchodzi"),
                     (s["a_out_sec"] - start, "out", "wychodzi"),
                     ((s["b_in_sec"] + oa * s["blend_sec"] - start) if oa else None,
                      "bass", "bas")]
        mine_marks = [(0.0, "in", "wchodzi"), (dur, "out", "wychodzi"),
                      (oa * dur if oa else None, "bass", "bas")]

        chips = f'<span class="chip">{r["profile"].replace("_", " ")}</span>'
        if oa:
            chips += f'<span class="chip on">bas otwarty w {oa * 100:.0f}%</span>'
        if dur < s["blend_sec"] * 0.95:
            chips += (f'<span class="chip warn">skrócone do '
                      f'{r["beats_rendered"]} uderzeń</span>')
        chips += f'<span class="chip">{r.get("target_bpm", 0):.0f} BPM</span>'

        snd = ""
        if r["seam"] in EMBED:
            snd = (f'<div class="audio"><div>{audio(base, "twoje", r["seam"])}</div>'
                   f'<div>{audio(base, "moje", r["seam"])}</div></div>')
        cards.append(f"""<article class="seam">
<header><h3><span class="da">{html.escape(r['from'].split('—')[-1].strip())}</span>
<span class="ar">→</span><span class="db">{html.escape(r['to'].split('—')[-1].strip())}</span></h3>
<div class="chips">{chips}</div></header>
<div class="pair">
  <div><div class="who">TY — nagranie</div>{panel(his_img, s['blend_sec'], his_marks)}</div>
  <div><div class="who">JA — render</div>{panel(mine_img, dur, mine_marks)}</div>
</div>{snd}</article>""")

    Path(args.out).write_text(TEMPLATE.format(
        n=len(cards), median_open=np.median(opens) * 100 if opens else 0,
        n_open=len(opens), cards="".join(cards)), encoding="utf-8")
    print(f"Wrote {args.out} ({Path(args.out).stat().st_size / 1024 / 1024:.1f} MB)")
    return 0


TEMPLATE = """<title>Spektrogramy — Twój set i moja kopia</title>
<style>
:root {{
  --g:#f7f6f4; --p:#fff; --e:#e2ded7; --ink:#191817; --dim:#78736c;
  --a:#c8562a; --b:#1d7f8c; --warn:#9a6b21;
  --mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
  --sans:"Helvetica Neue",Helvetica,Arial,sans-serif;
}}
@media (prefers-color-scheme:dark) {{ :root {{
  --g:#0e1013; --p:#15181d; --e:#262b33; --ink:#e9e7e3; --dim:#8c9299;
  --a:#e8834f; --b:#4cbecd; --warn:#d4b155; }} }}
:root[data-theme="dark"] {{
  --g:#0e1013; --p:#15181d; --e:#262b33; --ink:#e9e7e3; --dim:#8c9299;
  --a:#e8834f; --b:#4cbecd; --warn:#d4b155; }}
:root[data-theme="light"] {{
  --g:#f7f6f4; --p:#fff; --e:#e2ded7; --ink:#191817; --dim:#78736c;
  --a:#c8562a; --b:#1d7f8c; --warn:#9a6b21; }}
* {{ box-sizing:border-box; }}
body {{ background:var(--g); color:var(--ink); font-family:var(--sans); margin:0;
  padding:clamp(16px,3.5vw,48px); line-height:1.55; }}
.wrap {{ max-width:1180px; margin:0 auto; }}
h1 {{ font-size:clamp(24px,4vw,36px); margin:0 0 8px; letter-spacing:-.02em; }}
.sub {{ color:var(--dim); max-width:66ch; margin:0 0 26px; }}
.find {{ background:var(--p); border:1px solid var(--e); border-left:3px solid var(--b);
  border-radius:3px; padding:16px 18px; margin:0 0 26px; }}
.find b {{ font-family:var(--mono); font-size:21px; }}
.find p {{ margin:6px 0 0; color:var(--dim); font-size:13px; max-width:74ch; }}
.legend {{ display:flex; gap:16px; flex-wrap:wrap; font-family:var(--mono);
  font-size:11px; color:var(--dim); margin:0 0 22px; align-items:center; }}
.legend em {{ font-style:normal; border-left:2px dashed currentColor; padding-left:6px; }}
.seam {{ background:var(--p); border:1px solid var(--e); border-radius:3px;
  padding:13px 15px 11px; margin-bottom:12px; }}
.seam header {{ display:flex; flex-wrap:wrap; justify-content:space-between;
  gap:7px 18px; align-items:baseline; margin-bottom:9px; }}
.seam h3 {{ margin:0; font-size:13.5px; font-weight:600; display:flex; gap:7px;
  flex-wrap:wrap; align-items:baseline; }}
.da {{ color:var(--a); }} .db {{ color:var(--b); }} .ar {{ color:var(--dim); }}
.chips {{ display:flex; gap:5px; flex-wrap:wrap; }}
.chip {{ font-family:var(--mono); font-size:10px; padding:2px 6px; border-radius:2px;
  border:1px solid var(--e); color:var(--dim); }}
.chip.on {{ color:var(--b); border-color:currentColor; }}
.chip.warn {{ color:var(--warn); border-color:currentColor; }}
.pair {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
@media (max-width:760px) {{ .pair {{ grid-template-columns:1fr; }} }}
.who {{ font-family:var(--mono); font-size:9.5px; letter-spacing:.1em; color:var(--dim);
  text-transform:uppercase; margin-bottom:3px; }}
.spec {{ position:relative; border-radius:2px; overflow:hidden; background:#12141a;
  padding-left:26px; }}
.spec img {{ display:block; width:100%; height:auto; }}
.scale {{ position:absolute; inset:0 auto 0 0; width:26px; }}
.hz {{ position:absolute; right:3px; transform:translateY(-50%); font-family:var(--mono);
  font-size:8px; color:#8c9299; }}
.mk {{ position:absolute; top:0; bottom:0; width:0; border-left:1.5px dashed; }}
.mk i {{ position:absolute; top:1px; left:3px; font-family:var(--mono); font-size:8px;
  font-style:normal; white-space:nowrap; text-shadow:0 0 3px #000,0 0 3px #000; }}
.mk.in {{ border-color:#4cbecd; color:#4cbecd; }}
.mk.out {{ border-color:#e8834f; color:#e8834f; }}
.mk.bass {{ border-color:#f5d76e; color:#f5d76e; border-left-style:solid; }}
.mk.bass i {{ top:auto; bottom:1px; }}
.dur {{ position:absolute; right:4px; bottom:2px; font-family:var(--mono); font-size:8px;
  color:#8c9299; }}
.audio {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:9px; }}
@media (max-width:760px) {{ .audio {{ grid-template-columns:1fr; }} }}
audio {{ width:100%; height:30px; }}
.note {{ font-size:12.5px; color:var(--dim); border-left:2px solid var(--e);
  padding-left:14px; max-width:74ch; margin-top:26px; }}
</style>
<div class="wrap">
<h1>Spektrogramy — Twój set i moja kopia</h1>
<p class="sub">{n} przejść. Po lewej Twoje nagranie, po prawej mój render tych samych
dwóch utworów. Oś pionowa to częstotliwość w skali logarytmicznej — tak jak dzieli ją
ucho i każdy mikser. Jasne = głośne. Pionowe kreski to nasze pomiary nałożone na obraz,
żeby dało się sprawdzić, czy mówią prawdę.</p>

<div class="find">
  <b>{median_open:.0f}%</b>
  <p>Podręcznikowy „bass swap" oddaje dół w połowie przejścia. Ty otwierasz bas
  wchodzącego utworu dopiero przy <b>{median_open:.0f}%</b> jego długości (mediana z
  {n_open} szwów zamkniętych ręką) — praktycznie w chwili przekazania. Spektrogram
  wyłapał też drugi błąd, którego trzy krzywe nie pokazały: bas był mnożony przez fader,
  więc przy wczesnym otwarciu wchodził na jednej trzeciej głośności i przez pół minuty
  nie miał go żaden z decków. Na mikserze gałka basu nie chodzi przez fader — i Twój
  pomiar to potwierdza, bo bas Honey stoi na 1,05 przy środku 0,50.</p>
</div>

<div class="legend">
  <span><em style="color:#4cbecd">wchodzi</em></span>
  <span><em style="color:#e8834f">wychodzi</em></span>
  <span><em style="color:#f5d76e;border-left-style:solid">otwarcie basu</em></span>
  <span>oś pionowa 30 Hz – 16 kHz</span>
</div>

{cards}

<p class="note">Ukośne smugi w górnym rejestrze przy Honey to riser samego utworu, nie
artefakt renderu — sprawdzone na surowym pliku źródłowym. Przejścia dłuższe niż
256 uderzeń renderer skraca i jest to zaznaczone; siedem szwów w ogóle nie zostało
zrenderowanych, bo siatka bitów utworu kłóci się ze zmierzoną prędkością bardziej,
niż zniesie suwak.</p>
</div>
"""


if __name__ == "__main__":
    raise SystemExit(main())
