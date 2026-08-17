"""Systematyczne przemiatanie: gdzie silnik gubi oktawę, przed i po naprawie.

Dziesięć ręcznie dobranych przypadków to za mało, żeby coś twierdzić.
Tu lecimy po całym zakresie temp i po czterech rodzajach materiału —
ostra stopa, długie basowe nuty (ambient/rock), stopa z łamanymi
perkusjonaliami (jungle) i stopa z hi-hatami (house/techno).
"""
from __future__ import annotations
import sys, pathlib, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, str(pathlib.Path(__file__).parents[1].parent / "src"))
import numpy as np
from dancelab.core.rigid_grid import fit_rigid_grid

SR = 22050

def sygnal(bpm, rodzaj, seconds=30.0, seed=5):
    rng = np.random.default_rng(seed)
    y = rng.normal(0, 0.003, int(seconds * SR)); period = 60.0 / bpm
    def hit(at, amp, length, f, atak=0.002):
        i, n = int(at * SR), int(length * SR)
        if i < 0 or i + n > y.size: return
        t = np.arange(n) / SR
        y[i:i+n] += amp*np.sin(2*np.pi*f*t)*(1-np.exp(-t/atak))*np.exp(-t/(length/3))
    for k in range(int(seconds / period)):
        at = 0.11 + k * period
        if rodzaj == "dlugie basy":      hit(at, 1.0, 0.30, 70)
        else:                            hit(at, 1.0, 0.09, 55)
        if rodzaj == "breaki":
            for s in (0.25, 0.5, 0.75): hit(at + period*s, 0.6, 0.05, 90)
        if rodzaj == "hi-haty":
            for s in (0.25, 0.5, 0.75): hit(at + period*s, 0.5, 0.02, 8000)
    return y

RODZAJE = ["ostra stopa", "dlugie basy", "breaki", "hi-haty"]
TEMPA = list(range(64, 186, 6))
print(f"{'rodzaj':14s} " + " ".join(f"{b:4d}" for b in TEMPA))
zle_all = 0; n_all = 0
for r in RODZAJE:
    wiersz = []
    for b in TEMPA:
        g = fit_rigid_grid(sygnal(float(b), r), SR)
        ok = g is not None and abs(g.bpm - b) <= 1.5
        wiersz.append(" ok " if ok else ("2x " if g and abs(g.bpm-2*b)<3 else "ZLE"))
        zle_all += (not ok); n_all += 1
    print(f"{r:14s} " + " ".join(f"{w:>4s}" for w in wiersz))
print(f"\nbłędnych: {zle_all}/{n_all} = {zle_all/n_all*100:.1f}%")
