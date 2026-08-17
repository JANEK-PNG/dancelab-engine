"""Test przejść na bazie Janka: czy silnik wybrałby to, co wybrał on.

Pytanie zadawane wprost, per przejście z jego dwóch nagranych setów:
mając utwór A na stole i CAŁĄ bibliotekę jako kandydatów, jak wysoko silnik
stawia utwór B — ten, który Janek NAPRAWDĘ zagrał następny?

Trzy liczby, każda z uczciwym punktem odniesienia:

  * top-5 / top-10: jak często prawdziwy następny mieści się w pierwszej
    piątce/dziesiątce rankingu. Baza losowa: 5/N i 10/N.
  * percentyl: gdzie w rankingu ląduje jego wybór (0,5 = silnik nie widzi
    nic; 1,0 = silnik widzi dokładnie jak on).
  * score prawdziwych par vs par losowych z tej samej biblioteki — czy
    prawdziwe przejścia w ogóle dostają wyższe oceny.

Scoring identyczny jak w plannerze (transition_score, tryb smart, lifty
z 6144 par korpusu włączone) — testujemy to, co gra w produkcie,
nie specjalną wersję.
"""

from __future__ import annotations

import pathlib
import sys
import unicodedata as U

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts"))
from cue_parse import parse_cue                                   # noqa: E402
from grid_cache import grid_for                                   # noqa: E402

from dancelab.core.config import load_config, load_weights        # noqa: E402
from dancelab.decision.set_builder import transition_score        # noqa: E402
from dancelab.storage.repositories import FileAnalysisRepository  # noqa: E402

PROCESSED = "experiments_priv/2026-07-30_rebuild/processed"
CUES = [
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Unknown Album/01 Premier.cue",
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.cue",
]

N = lambda s: U.normalize("NFC", str(s)).lower()                  # noqa: E731


def track_energy(a) -> float:
    frames = getattr(a, "features", None)
    vals = [f.rms for f in (frames or []) if getattr(f, "rms", None) is not None]
    return float(np.mean(vals)) if vals else 0.5


def main() -> int:
    cfg = load_config("configs/default.yaml")
    weights = load_weights(cfg.weights_file)
    repo = FileAnalysisRepository(PROCESSED)
    analyses = [repo.get(t) for t in repo.list_track_ids()]
    by_path = {N(a.track.source_path): a for a in analyses}
    # Tempo z SIATEK, nie ze starego trackera — dokładnie jak w produkcyjnym
    # propose_set. Pierwszy przebieg tego testu bez tej łaty dał percentyl
    # 0,533; bez niej testowalibyśmy nie ten silnik, który gra.
    patched = 0
    for a in analyses:
        g = grid_for(a.track.source_path)
        if g:
            a.track.bpm_estimate = g["bpm"]
            patched += 1
    print(f"biblioteka: {len(analyses)} analiz · tempo z siatek: {patched}", flush=True)

    energies = {a.track.track_id: track_energy(a) for a in analyses}
    e_vals = list(energies.values())
    e_range = max(e_vals) - min(e_vals) or 1.0

    rng = np.random.default_rng(17)
    ranks, real_scores, chance_scores = [], [], []
    rows = []

    for cue in CUES:
        _, entries = parse_cue(cue)
        order = []
        for e in entries:
            a = by_path.get(N(e.path))
            if a is not None and (not order or order[-1].track.track_id != a.track.track_id):
                order.append(a)
        print(f"\n{pathlib.Path(cue).stem}: {len(order)} utworów z analizą", flush=True)

        for i in range(len(order) - 1):
            a, real_b = order[i], order[i + 1]
            played = {t.track.track_id for t in order[: i + 1]}
            pool = [c for c in analyses if c.track.track_id not in played]
            if real_b.track.track_id not in {c.track.track_id for c in pool}:
                continue
            scored = []
            for c in pool:
                s, _, _ = transition_score(
                    a, c, weights, "build",
                    energies[a.track.track_id], energies[c.track.track_id],
                    e_range)
                scored.append((s, c.track.track_id))
            scored.sort(reverse=True)
            ids = [t for _, t in scored]
            rank = ids.index(real_b.track.track_id) + 1
            ranks.append((rank, len(pool)))
            real_s = dict((t, s) for s, t in scored)[real_b.track.track_id]
            real_scores.append(real_s)
            pick = rng.choice(len(pool), size=min(20, len(pool)), replace=False)
            chance_scores += [scored[j][0] for j in pick]
            top3 = [t for _, t in scored[:3]]
            names = {c.track.track_id: pathlib.Path(c.track.source_path).stem
                     for c in pool}
            rows.append((pathlib.Path(order[i].track.source_path).stem[:30],
                         pathlib.Path(real_b.track.source_path).stem[:30],
                         rank, len(pool), [names[t][:26] for t in top3]))

    n = len(ranks)
    top5 = sum(1 for r, _ in ranks if r <= 5) / n
    top10 = sum(1 for r, _ in ranks if r <= 10) / n
    pool_med = float(np.median([p for _, p in ranks]))
    pct = float(np.mean([1 - (r - 1) / p for r, p in ranks]))
    print(f"\n══ WYNIK: {n} prawdziwych przejść Janka ══")
    print(f"  top-5 : {top5 * 100:5.1f}%   (losowo: {5 / pool_med * 100:.1f}%)")
    print(f"  top-10: {top10 * 100:5.1f}%   (losowo: {10 / pool_med * 100:.1f}%)")
    print(f"  średni percentyl jego wyboru: {pct:.3f}  (0,5 = silnik ślepy)")
    print(f"  score prawdziwych par : mediana {np.median(real_scores):.3f}")
    print(f"  score par losowych    : mediana {np.median(chance_scores):.3f}")

    print("\nnajlepiej i najgorzej trafione (ranga = którym w kolejce był jego wybór):")
    rows.sort(key=lambda r: r[2])
    for r in rows[:3] + rows[-3:]:
        print(f"  ranga {r[2]:3d}/{r[3]}  {r[0]} → {r[1]}")
        print(f"           silnik radził: {' · '.join(r[4])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
