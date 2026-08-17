"""Four Tet @ Awakenings ADE 2024 — analiza CAŁOŚCI, równo (decyzja Janka:
znacznik 2h NIE jest punktem odniesienia).

Trzy warstwy, wszystko mierzone, zero zmyślania:
1. głośność chwilowa (ebur128 M) co ~1 s przez 4:28:06;
2. tempo w oknach 120 s (librosa, onsety) — krzywa tempa seta;
3. złożenie z tracklistą MixesDB: dwell time, głośność i tempo per utwór,
   lokalny kształt głośności wokół każdego szwu (±40 s).
"""

import json
import pathlib
import re
import subprocess

import librosa
import numpy as np

KAT = pathlib.Path(__file__).parent
AUDIO = KAT / "fourtet_awakenings_ade2024.m4a"
TRACKLISTA = json.loads((KAT / "tracklista_mixesdb.json").read_text())
OUT = KAT / "analiza_calosci.json"

print("1/3 głośność (ebur128)…", flush=True)
proc = subprocess.run(
    ["ffmpeg", "-nostats", "-i", str(AUDIO), "-filter_complex",
     "ebur128", "-f", "null", "-"],
    capture_output=True, text=True)
glosnosc = []          # (sekunda, M)
for linia in proc.stderr.splitlines():
    m = re.search(r"t:\s*([\d.]+)\s+.*?M:\s*(-?[\d.]+)", linia)
    if m:
        t, M = float(m.group(1)), float(m.group(2))
        if not glosnosc or t - glosnosc[-1][0] >= 1.0:
            glosnosc.append((round(t, 1), M))
print(f"   punktów głośności: {len(glosnosc)}", flush=True)

print("2/3 tempo w oknach 120 s…", flush=True)
okno, tempa = 120.0, []
dl = 16086
t = 0.0
while t < dl - okno / 2:
    y, sr = librosa.load(str(AUDIO), sr=11025, mono=True,
                         offset=t, duration=okno)
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    bpm = librosa.feature.tempo(onset_envelope=onset, sr=sr,
                                aggregate=np.median)[0]
    tempa.append((round(t + okno / 2), round(float(bpm), 1)))
    t += okno
    if len(tempa) % 20 == 0:
        print(f"   okno {len(tempa)} · t={t:.0f}s", flush=True)

print("3/3 złożenie z tracklistą…", flush=True)
gl_t = np.array([g[0] for g in glosnosc])
gl_v = np.array([g[1] for g in glosnosc])
tm_t = np.array([x[0] for x in tempa])
tm_v = np.array([x[1] for x in tempa])
utwory = TRACKLISTA["utwory"]
per_utwor, szwy = [], []
for i, u in enumerate(utwory):
    a = u["start_sec"]
    b = utwory[i + 1]["start_sec"] if i + 1 < len(utwory) else dl
    sel = (gl_t >= a) & (gl_t < b)
    selt = (tm_t >= a) & (tm_t < b)
    per_utwor.append({
        **u, "dwell_sec": b - a,
        "glosnosc_M_srednia": round(float(gl_v[sel].mean()), 2)
        if sel.any() else None,
        "tempo_mediana": round(float(np.median(tm_v[selt])), 1)
        if selt.any() else None})
    if i + 1 < len(utwory):
        w_ok = (gl_t >= b - 40) & (gl_t <= b + 40)
        przed_ok = (gl_t >= b - 40) & (gl_t < b)
        po_ok = (gl_t >= b) & (gl_t <= b + 40)
        szwy.append({
            "po_utworze": u["tytul"][:40], "sekunda": b,
            "glosnosc_przed": round(float(gl_v[przed_ok].mean()), 2)
            if przed_ok.any() else None,
            "glosnosc_po": round(float(gl_v[po_ok].mean()), 2)
            if po_ok.any() else None,
            "dol_szwu": round(float(gl_v[w_ok].min()), 2)
            if w_ok.any() else None})

OUT.write_text(json.dumps({
    "schema": "fourtet-awakenings-analiza-v1",
    "glosnosc_1s": glosnosc, "tempo_120s": tempa,
    "per_utwor": per_utwor, "szwy": szwy}, ensure_ascii=False))
print(f"KONIEC → {OUT}")
