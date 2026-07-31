"""Where a record sits in the style space of 5040 real DJ sets.

The DJ's own library cannot answer "what do you like to play" on its own. 72 % of his
files carry no genre tag at all, and of what Rekordbox has, 53 % says "electronic" or
"dance" — true, and far too coarse to choose with. Clustering his 296 records blind
gives groups nobody has a name for.

The corpus does have names. 5040 mixes carry MixesDB categories written by people
describing actual sets — House 1555, Techno 1547, Tech House 1410, Drum & Bass 507,
Disco 113 — and every one of the 12 668 corpus tracks with a CLAP vector belongs to
mixes that carry them. So a style becomes a place in embedding space: the centroid of
the records that DJs actually played in sets they called that.

This is the corpus finally reaching the product. Until now the only thing that ever
crossed from 44 % of the codebase into the engine was the BPM and harmony lifts.

The vocabulary is measured, but which of those names the DJ adopts stays his call —
the engine says "these 78 records of yours sit where sets called Tech House sit", not
"this is Tech House".
"""

from __future__ import annotations

import argparse
import json
import pathlib
import unicodedata as U
from collections import Counter, defaultdict

import numpy as np

CORPUS = pathlib.Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")
EMB = pathlib.Path("data/reports/corpus_embeddings_full.json")
LIB = pathlib.Path("data/reports/library_embeddings.json")

# Categories that name a sound rather than a person, a show or a room. Frequency
# alone cannot tell them apart — "Eddie Halliwell" and "Boiler Room" are as common as
# "Minimal" — so this list is a judgement and is written down to be argued with
# rather than hidden in a threshold.
GENRES = [
    "House", "Techno", "Tech House", "Progressive House", "Trance",
    "Drum & Bass", "Progressive Trance", "Deep House", "Minimal",
    "Deep Tech House", "Disco", "Electro", "Psytrance", "Dubstep",
    "Breakbeat", "Hardcore", "Ambient", "Downtempo", "Funk", "Garage",
    "Hard Trance", "Hardstyle", "Acid", "Electronica", "UK Garage",
]

# What this toolchain produced, and sample packs — not music, and they cluster
# beautifully on their own. Thirteen of the DJ's 296 embedded "records" were our own
# Demucs stems, twenty more were a sample library.
NOT_MUSIC = ("drums", "bass", "other", "vocals", "instrumental", "acapella")


def norm(s: str) -> str:
    return U.normalize("NFC", str(s)).lower()


def is_music(path: str) -> bool:
    stem = pathlib.Path(path).stem.lower()
    return (stem not in NOT_MUSIC
            and "mergefx" not in stem
            and "looperman" not in stem
            and "sample" not in stem
            and "DanceLab_Stem_Export" not in path)


def load_style_space(min_tracks: int = 60):
    """One centroid per style, from the tracks DJs played in sets called that."""
    emb = json.loads(EMB.read_text())["tracks"]
    mixes = json.loads(CORPUS.read_text())

    per_track: dict[str, Counter] = defaultdict(Counter)
    for m in mixes:
        cats = [t["key"].replace("Category:", "")
                for t in (m.get("tags") or []) if isinstance(t, dict) and t.get("key")]
        styles = [c for c in cats if c in GENRES]
        if not styles:
            continue
        for t in (m.get("tracklist") or []):
            tid = t.get("id") if isinstance(t, dict) else None
            if tid in emb:
                per_track[tid].update(styles)

    # A track played in twenty House sets and one Techno set is evidence about House.
    # Counting it for both would blur every centroid toward the middle, and the three
    # biggest categories overlap so heavily that the middle is where they all end up.
    members: dict[str, list[str]] = defaultdict(list)
    for tid, counts in per_track.items():
        top, n = counts.most_common(1)[0]
        if n >= 2 and n >= 0.5 * sum(counts.values()):
            members[top].append(tid)

    # Everything in this corpus is electronic dance music, so every vector shares a
    # large common direction, and raw cosine is dominated by it. Two effects, both
    # measured: style centroids come out 0.90 similar to each other and look useless,
    # and any recording long enough to average toward the middle — the DJ's own
    # fifty-minute set, for one — reads as the nearest track to every style at once.
    #
    # Subtracting the common direction fixes the reading, not the content: held-out
    # prediction of a corpus track's own style is 66.6 % raw and 65.5 % centred,
    # against 33.2 % for always guessing the commonest. The discrimination was there
    # the whole time; the cosine was hiding it. That number is also the honest limit
    # of this vocabulary — two thirds, on labels that are themselves noisy, because a
    # set tagged Techno still contains records that are not.
    all_ids = [i for ids in members.values() for i in ids]
    common = np.array([emb[i] for i in all_ids], dtype=np.float64)
    common /= np.linalg.norm(common, axis=1, keepdims=True) + 1e-12
    common = common.mean(axis=0)

    names, cents = [], []
    for style, ids in sorted(members.items(), key=lambda kv: -len(kv[1])):
        if len(ids) < min_tracks:
            continue
        X = np.array([emb[i] for i in ids], dtype=np.float64)
        X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-12
        c = (X - common).mean(axis=0)
        names.append(style)
        cents.append(c / (np.linalg.norm(c) + 1e-12))
    return names, np.array(cents), {k: len(v) for k, v in members.items()}, common


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-tracks", type=int, default=60)
    ap.add_argument("--out", default="experiments_priv/2026-07-31_style/style_space.json")
    args = ap.parse_args()

    names, cents, sizes, common = load_style_space(args.min_tracks)
    print(f"przestrzeń stylu z korpusu: {len(names)} stylów\n")
    for n, c in zip(names, cents):
        print(f"  {sizes[n]:5d} utworów  {n}")

    # How far apart are these centroids really? Styles a DJ hears as different can
    # sit on top of each other in an embedding, and a vocabulary of names that all
    # point at the same place is worse than no vocabulary.
    print("\npodobieństwo między stylami (im bliżej 1, tym mniej się różnią):")
    sim = cents @ cents.T
    worst = [(sim[i, j], names[i], names[j])
             for i in range(len(names)) for j in range(i + 1, len(names))]
    for s, a, b in sorted(worst, reverse=True)[:6]:
        print(f"  {s:.3f}  {a} ↔ {b}")
    print(f"  mediana wszystkich par: {np.median([s for s, _, _ in worst]):.3f}")

    lib = json.loads(LIB.read_text())["tracks"]
    paths = [p for p in lib if is_music(p)]
    print(f"\nbiblioteka DJ-a: {len(lib)} osadzeń, {len(paths)} to muzyka "
          f"({len(lib) - len(paths)} to nasze stemy, sample i loopy)")
    L = np.array([lib[p] for p in paths], dtype=np.float64)
    L /= np.linalg.norm(L, axis=1, keepdims=True) + 1e-12
    L -= common                       # read in the same space the centroids live in
    L /= np.linalg.norm(L, axis=1, keepdims=True) + 1e-12
    scores = L @ cents.T
    best = scores.argmax(axis=1)
    print("\ngdzie leży biblioteka DJ-a w tej przestrzeni:")
    for style, n in Counter(names[b] for b in best).most_common():
        near = [paths[i] for i in np.argsort(-scores[:, names.index(style)])[:3]]
        print(f"  {n:4d}  {style}")
        for p in near:
            print(f"           {pathlib.Path(p).stem[:52]}")

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "schema_version": "style-space-v1",
        "source": "MixesDB categories over 5040 corpus mixes; CLAP centroids",
        "styles": names,
        "member_counts": {n: sizes[n] for n in names},
        "centroids": [c.tolist() for c in cents],
        "common_direction": common.tolist(),
    }))
    print(f"\nzapisane: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
