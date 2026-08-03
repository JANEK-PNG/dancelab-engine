"""Wariant scoringu: dokładamy brzmienie (CLAP) i mierzymy, czy pomaga.

Zmierzone 01.08: produkcyjny scoring przewiduje Janka na poziomie 0,593
(dolne 7 % wśród DJ-ów korpusu), a cudzych DJ-ów na 0,750. Diagnoza była taka,
że w score nie ma NICZEGO z tego, co zmierzyliśmy o Janku — jest harmonia,
tempo i energia, czyli to, co tłumaczy wybory zachowawcze.

Pierwsza brakująca cecha: PODOBIEŃSTWO BRZMIENIA. Wektory CLAP mamy policzone
dla całego korpusu (12 668) i dla biblioteki Janka. Hipoteza: DJ częściej łączy
utwory, które brzmią pokrewnie, niż wynikałoby to z samej tonacji i tempa.

Zasada testu, żeby wynik coś znaczył:

  * dwa mierniki naraz — korpus (stroimy) i sety Janka (sędzia). Wariant, który
    poprawia korpus, a psuje Janka, jest ODRZUCONY, bo produkt służy jemu;
  * ta sama waga sprawdzana na obu — bez dobierania osobno pod każdy zbiór,
    bo to byłoby strojenie pod test;
  * wagi 0,0 (czyli stan dzisiejszy) zawsze w tabeli jako punkt odniesienia.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unicodedata as U

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_przejsc import core_score, load_features            # noqa: E402
from cue_parse import parse_cue                                    # noqa: E402
from grid_cache import grid_for                                    # noqa: E402
from dancelab.storage.repositories import FileAnalysisRepository   # noqa: E402

N = lambda s: U.normalize("NFC", str(s)).lower()                   # noqa: E731
MIXES = pathlib.Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")
CUES = [
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Unknown Album/01 Premier.cue",
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.cue",
]


def unit(d: dict[str, list]) -> dict[str, np.ndarray]:
    out = {}
    for k, v in d.items():
        a = np.asarray(v, dtype=np.float32)
        n = float(np.linalg.norm(a))
        if n > 0:
            out[k] = a / n
    return out


def key_of(x: str) -> str:
    """Klucz brzmienia: dla korpusu to id, dla biblioteki nazwa pliku."""
    return N(pathlib.Path(x).name) if "/" in x else x


def percentile(pairs, feats, emb, w_clap, pool_ids=None) -> tuple[float, int]:
    """Średni percentyl prawdziwego następnego przy danej wadze brzmienia."""
    ids = pool_ids if pool_ids is not None else list(feats)
    ranks = []
    for a, b, exclude in pairs:
        cand = [c for c in ids if c == b or c not in exclude]
        if len(cand) < 40:
            continue
        fa, ea = feats[a], emb.get(key_of(a))
        sc = []
        for c in cand:
            s = core_score(fa, feats[c])
            if w_clap and ea is not None:
                ec = emb.get(key_of(c))
                if ec is not None:
                    # kosinus w [-1,1] → [0,1]; miesza się z rdzeniem, nie zastępuje go
                    s = (1 - w_clap) * s + w_clap * float((np.dot(ea, ec) + 1) / 2)
            sc.append((s, c))
        sc.sort(reverse=True)
        r = [c for _, c in sc].index(b) + 1
        ranks.append(1 - (r - 1) / len(cand))
    return (float(np.mean(ranks)) if ranks else float("nan")), len(ranks)


def corpus_pairs(feats, limit=300):
    mixes = json.loads(MIXES.read_text())
    out = []
    for m in mixes:
        ids = [t.get("id") for t in (m.get("tracklist") or []) if t.get("id")]
        s = set(ids)
        for i in range(len(ids) - 1):
            if ids[i] in feats and ids[i + 1] in feats:
                out.append((ids[i], ids[i + 1], s))
    rng = np.random.default_rng(23)
    if len(out) > limit:
        out = [out[i] for i in rng.choice(len(out), limit, replace=False)]
    return out


def janek_data():
    repo = FileAnalysisRepository("experiments_priv/2026-07-30_rebuild/processed")
    feats = {}
    for a in (repo.get(t) for t in repo.list_track_ids()):
        g = grid_for(a.track.source_path)
        fr = getattr(a, "features", None) or []
        rms = [f.rms for f in fr if getattr(f, "rms", None) is not None]
        if g and a.track.key_estimate:
            feats[N(a.track.source_path)] = {
                "bpm": g["bpm"], "camelot": a.track.key_estimate,
                "conf": a.track.key_confidence or 0.0,
                "energy": float(np.mean(rms)) if rms else 0.10}
    pairs = []
    for cue in CUES:
        _, e = parse_cue(cue)
        order = [N(x.path) for x in e]
        order = [p for i, p in enumerate(order)
                 if p in feats and (i == 0 or p != order[i - 1])]
        seen = set()
        for i in range(len(order) - 1):
            seen.add(order[i])
            pairs.append((order[i], order[i + 1], set(seen) - {order[i + 1]}))
    return feats, pairs


def main() -> int:
    print("wczytuję cechy i wektory brzmienia…", flush=True)
    cfe = load_features(None)
    cemb = unit(json.loads(
        (ROOT / "data/reports/corpus_embeddings_full.json").read_text())["tracks"])
    jfe, jpairs = janek_data()
    # Osadzenia biblioteki są kluczowane ścieżką WZGLĘDNĄ wobec ~/Music
    # ("DEBIUTY/Artysta - Tytuł.aiff"), a analizy trzymają ścieżkę pełną.
    # Złączenie wprost dawało ZERO trafień i cicho zerowało pół pomiaru —
    # ta sama pułapka co przy Rekordboksie. Łączymy po nazwie pliku.
    jemb_raw = json.loads(
        (ROOT / "data/reports/library_embeddings.json").read_text())["tracks"]
    jemb = unit({N(pathlib.Path(k).name): v for k, v in jemb_raw.items()})
    cpairs = corpus_pairs(cfe)

    have_c = sum(1 for a, b, _ in cpairs if key_of(a) in cemb and key_of(b) in cemb)
    have_j = sum(1 for a, b, _ in jpairs if key_of(a) in jemb and key_of(b) in jemb)
    print(f"korpus: {len(cpairs)} par, brzmienie znane dla {have_c}")
    print(f"Janek : {len(jpairs)} par, brzmienie znane dla {have_j}\n")

    print(f"{'waga brzmienia':>16} │ {'korpus':>8} │ {'Janek':>8} │ ocena")
    print("─" * 56)
    base_c = base_j = None
    for w in (0.0, 0.15, 0.30, 0.45, 0.60):
        pc, nc = percentile(cpairs, cfe, cemb, w)
        pj, nj = percentile(jpairs, jfe, jemb, w)
        if w == 0.0:
            base_c, base_j = pc, pj
            verdict = "stan dzisiejszy"
        else:
            dc, dj = pc - base_c, pj - base_j
            verdict = (f"korpus {dc:+.3f} · Janek {dj:+.3f}"
                       + ("  ✓ pomaga obu" if dc > 0.005 and dj > 0.005 else
                          "  ✗ psuje Janka" if dj < -0.005 else
                          "  ~ bez wpływu"))
        print(f"{w:>16.2f} │ {pc:>8.4f} │ {pj:>8.4f} │ {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
