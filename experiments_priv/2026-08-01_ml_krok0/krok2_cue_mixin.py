"""KROK 2 · cue MIX IN jako model, zamiast progu.

Reguła wejścia jest zmierzona i mocna: Janek wprowadza utwór tam, gdzie ten
utwór opiera się na perkusji i schodzi z basu — 71% jego wejść wobec 18%
losowych momentów. W produkcji (`scripts/render_set.entry_point`) żyje jako
ARGMAX ręcznie złożonego wyrażenia: (środek/średnia) − (dół/średnia), z podłogą
„musi w ogóle grać" na 0,33 średniej.

Ten skrypt zamienia to wyrażenie na model, który zwraca PRAWDOPODOBIEŃSTWO,
a nie bezwymiarowy wynik. Trzy powody, wszystkie praktyczne:
  * prawdopodobieństwa da się porównywać między utworami, wyników argmaxu nie;
  * prawdopodobieństwo da się skalibrować i sprawdzić, czy nie kłamie;
  * model może się WSTRZYMAĆ, a argmax zawsze coś wskaże — nawet gdy nie ma na
    czym się oprzeć. Bez tego nie wchodzi do DanceLaba (zasada #2 z pliku 05).

ROZMIAR — pilnowany świadomie. 21 szwów × (1 wejście + 5 okien kontrolnych)
= 126 przykładów. Budżet danych daje przy tym 3–6 parametrów i tyle jest
używane. Walidacja: leave-one-seam-out — cały utwór wypada z treningu razem
ze swoimi kontrolami, więc model nigdy nie ogląda utworu, na którym jest
sprawdzany.

Kontrole ustawione tak samo jak w pomiarze z 30.07 (5 równomiernych okien
z tego samego utworu), żeby porównanie szło do zmierzonej liczby, a nie do
nowej. Okna NIE są wyrównane do fraz — celowo: gdyby były, model mógłby
nauczyć się „wyrównane = dobre", co jest artefaktem konstrukcji, nie muzyką.

Wynik jest wynikiem także wtedy, gdy wychodzi negatywny.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import seam_decompose as S  # noqa: E402

SEAM_DIRS = [ROOT / "experiments_priv/seams"]
WINDOW_SEC = 15.0          # tak jak w seam_content.py
N_CONTROLS = 5             # tak jak w pomiarze z 30.07 (5 × 21 = 105)
GUARD_SEC = 30.0           # kontrola nie może leżeć przy prawdziwym wejściu
STEMS = ("drums", "bass", "other", "vocals")
LOW_HZ = 200.0             # ten sam podział pasm co produkcyjny entry_point
SEED = 20260801

FEATURES = ["drums_delta", "bass_delta", "other_delta", "vocals_delta",
            "mid_ratio", "pos"]
CORE = ["drums_delta", "bass_delta", "mid_ratio", "pos"]


def cached(path: str) -> bool:
    h = hashlib.sha256(str(path).encode()).hexdigest()[:16]
    return (S.CACHE / h / "drums.npy").exists()


def features(stems: dict[str, np.ndarray], low: np.ndarray, mid: np.ndarray,
             t0: float, span: float) -> dict[str, float] | None:
    """Cechy okna [t0, t0+15] w CZASIE UTWORU. None = brak podstaw."""
    a, b = int(t0 * S.SR), int((t0 + WINDOW_SEC) * S.SR)
    if b > len(mid) or a < 0 or b - a < S.SR:
        return None

    here, whole = [], []
    for name in STEMS:
        y = stems[name]
        if b > len(y):
            return None
        here.append(float((y[a:b] ** 2).mean()))
        whole.append(float((y[: S.SR * 240] ** 2).mean()))
    here, whole = np.asarray(here), np.asarray(whole)
    if here.sum() <= 0 or whole.sum() <= 0:
        return None
    delta = here / here.sum() - whole / whole.sum()

    ref_mid = float((mid ** 2).mean())
    ref_low = float((low ** 2).mean())
    if ref_mid <= 0 or ref_low <= 0:
        return None
    md = float((mid[a:b] ** 2).mean())
    lo = float((low[a:b] ** 2).mean())

    f = {f"{n}_delta": float(d) for n, d in zip(STEMS, delta)}
    f["mid_ratio"] = md / ref_mid
    f["low_ratio"] = lo / ref_low
    f["pos"] = t0 / span if span > 0 else 0.0
    return f


def build_dataset() -> tuple[list[dict], list[str]]:
    from scipy.signal import butter, sosfiltfilt

    files = sorted(f for d in SEAM_DIRS for f in glob.glob(str(d / "*/seam_*.json")))
    rng = np.random.default_rng(SEED)
    rows, skipped = [], []

    for f in files:
        s = json.loads(pathlib.Path(f).read_text())
        if not s.get("blend_sec"):
            continue
        b = s["deck_b"]
        path = b["path"]
        seam = f"{pathlib.Path(f).parent.name}/{pathlib.Path(f).stem}"

        if not pathlib.Path(path).exists():
            skipped.append(f"{seam}: brak pliku")
            continue
        if not cached(path):
            skipped.append(f"{seam}: brak stemów w cache (nie liczę Demucsa)")
            continue

        stems = S.separate(path)
        y = sum(stems[n] for n in STEMS).astype(np.float32)
        span = len(y) / S.SR
        sos = butter(4, LOW_HZ / (S.SR / 2), btype="lowpass", output="sos")
        low = sosfiltfilt(sos, y).astype(np.float32)
        mid = (y - low).astype(np.float32)

        # Prawdziwe wejście, przeliczone z zegara miksu na zegar utworu.
        t_true = (s["b_in_sec"] - b["origin"]) * b["rate"]
        pos = features(stems, low, mid, t_true, span)
        if pos is None:
            skipped.append(f"{seam}: brak cech w punkcie wejścia")
            continue
        pos.update(seam=seam, track=pathlib.Path(path).stem, y=1, t=t_true)
        rows.append(pos)

        # Kontrole: równomiernie po utworze, z odstępem od prawdziwego wejścia.
        usable = span - WINDOW_SEC
        cand = np.linspace(0.02 * usable, 0.95 * usable, N_CONTROLS * 4)
        cand = [t for t in cand if abs(t - t_true) > GUARD_SEC]
        rng.shuffle(cand)
        taken = 0
        for t in cand:
            if taken >= N_CONTROLS:
                break
            neg = features(stems, low, mid, float(t), span)
            if neg is None:
                continue
            neg.update(seam=seam, track=pathlib.Path(path).stem, y=0, t=float(t))
            rows.append(neg)
            taken += 1
        if taken < N_CONTROLS:
            skipped.append(f"{seam}: tylko {taken} kontroli z {N_CONTROLS}")

    return rows, skipped


# ─────────────────────────────────────────────────────────── ocena

def rule_score(r: dict) -> float:
    """Produkcyjny `entry_point`: (środek/średnia) − (dół/średnia), z podłogą."""
    if r["mid_ratio"] <= 0.33:
        return -1e9
    return r["mid_ratio"] - r["low_ratio"]


def evaluate(rows, cols, C: float):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    seams = sorted({r["seam"] for r in rows})
    X = np.array([[r[c] for c in cols] for r in rows], dtype=float)
    y = np.array([r["y"] for r in rows])
    grp = np.array([r["seam"] for r in rows])

    proba = np.zeros(len(rows))
    for held in seams:                       # leave-one-seam-out
        tr, te = grp != held, grp == held
        if y[tr].sum() < 2 or (1 - y[tr]).sum() < 2:
            continue
        sc = StandardScaler().fit(X[tr])
        m = LogisticRegression(C=C, max_iter=2000).fit(sc.transform(X[tr]), y[tr])
        proba[te] = m.predict_proba(sc.transform(X[te]))[:, 1]

    def hit_at_1(score_of):
        hits = 0
        for sm in seams:
            idx = [i for i, r in enumerate(rows) if r["seam"] == sm]
            if not any(rows[i]["y"] for i in idx):
                continue
            best = max(idx, key=lambda i: score_of(i))
            hits += rows[best]["y"]
        return hits, sum(1 for sm in seams
                         if any(rows[i]["y"] for i in range(len(rows))
                                if rows[i]["seam"] == sm))

    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(y, proba)
    h, n = hit_at_1(lambda i: proba[i])

    # Model na PEŁNYCH danych — tylko po to, żeby pokazać znaki wag.
    sc = StandardScaler().fit(X)
    full = LogisticRegression(C=C, max_iter=2000).fit(sc.transform(X), y)
    return auc, h, n, dict(zip(cols, full.coef_[0])), proba


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(pathlib.Path(__file__).parent / "krok2_dataset.json"))
    args = ap.parse_args()

    rows, skipped = build_dataset()
    seams = sorted({r["seam"] for r in rows})
    npos = sum(r["y"] for r in rows)
    print("═" * 72)
    print("KROK 2 · cue MIX IN jako model")
    print("═" * 72)
    print(f"\n  szwów użytych: {len(seams)} · przykładów: {len(rows)} "
          f"({npos} wejść · {len(rows) - npos} kontroli)")
    for s in skipped:
        print(f"  ⚠ pominięte — {s}")
    if npos < 10:
        print("\n  za mało wejść, nie uczę")
        return 1

    y = np.array([r["y"] for r in rows])

    # ── punkty odniesienia, policzone PRZED modelem
    from sklearn.metrics import roc_auc_score
    rs = np.array([rule_score(r) for r in rows])
    auc_rule = roc_auc_score(y, rs)
    hits_rule = 0
    for sm in seams:
        idx = [i for i, r in enumerate(rows) if r["seam"] == sm]
        hits_rule += rows[max(idx, key=lambda i: rs[i])]["y"]

    rng = np.random.default_rng(SEED)
    rnd_hits = np.mean([
        np.mean([rows[rng.choice([i for i, r in enumerate(rows) if r["seam"] == sm])]["y"]
                 for sm in seams]) for _ in range(2000)])

    print(f"\n  {'strategia':<34} {'AUC':>6} {'trafione #1':>14}")
    print("  " + "─" * 56)
    print(f"  {'losowo':<34} {0.5:6.3f} {rnd_hits*len(seams):8.1f}/{len(seams):<5}")
    print(f"  {'produkcyjna reguła (argmax)':<34} {auc_rule:6.3f} "
          f"{hits_rule:8d}/{len(seams):<5}")

    for label, cols, C in [("model · 4 cechy (rdzeń)", CORE, 0.5),
                           ("model · 6 cech", FEATURES, 0.5),
                           ("model · 4 cechy, mocna regularyzacja", CORE, 0.1)]:
        auc, h, n, coef, _ = evaluate(rows, cols, C)
        print(f"  {label:<34} {auc:6.3f} {h:8d}/{n:<5}")

    auc, h, n, coef, proba = evaluate(rows, CORE, 0.5)
    print(f"\n  wagi modelu rdzeniowego (znak = kierunek, na cechach skalowanych):")
    for k, v in sorted(coef.items(), key=lambda x: -abs(x[1])):
        print(f"    {k:<14} {v:+.3f}")

    # ── kalibracja: czy „70% pewności" znaczy 70%
    print(f"\n  kalibracja (przewidziane vs rzeczywiste, leave-one-seam-out):")
    edges = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    for a, b in zip(edges, edges[1:]):
        m = (proba >= a) & (proba < b)
        if m.sum():
            print(f"    p ∈ [{a:.1f},{b:.1f})  n={m.sum():3d}  "
                  f"przewidziane {proba[m].mean():.2f}  rzeczywiste {y[m].mean():.2f}")

    pathlib.Path(args.out).write_text(json.dumps(
        {"n_seams": len(seams), "rows": rows, "features_core": CORE,
         "window_sec": WINDOW_SEC, "n_controls": N_CONTROLS,
         "guard_sec": GUARD_SEC, "seed": SEED}, ensure_ascii=False))
    print(f"\n  zbiór zapisany: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
