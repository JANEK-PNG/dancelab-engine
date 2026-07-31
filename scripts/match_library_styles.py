"""What style is each of the DJ's records, according to Discogs.

The number this exists to produce is the match rate. Everything upstream — the corpus
style space, the CLAP centroids, the two-thirds ceiling — was an attempt to guess a
record's style from its sound because we had no way to look it up. If enough of the
library can simply be found in a database of records, the guessing stops.

Titles come from Rekordbox rather than from filenames. Rekordbox holds a real Artist
and Title per track, where the files hold `01 Chiggy Chiggy (Rohaan Extended Remix)`
and worse.

Candidates come from an inverted index built only over the words that appear in this
library, so the scan is one pass over the dump table and the memory is proportional to
the library rather than to Discogs.
"""

from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys
import unicodedata as U
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from discogs_style_db import same_record, tokens          # noqa: E402


def library_from_rekordbox() -> list[tuple[str, str]]:
    from pyrekordbox import Rekordbox6Database

    out, seen = [], set()
    for c in Rekordbox6Database().get_content():
        if not c.FolderPath:
            continue
        try:
            artist = c.Artist.Name if c.Artist else None
        except Exception:                                   # noqa: BLE001
            artist = None
        title = c.Title
        if not artist or not title:
            continue
        k = U.normalize("NFC", f"{artist}|{title}").lower()
        if k not in seen:
            seen.add(k)
            out.append((artist, title))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/Volumes/MY_PC/DanceLabStyleDB/"
                                    "styles_masters.sqlite3")
    ap.add_argument("--show", type=int, default=25)
    args = ap.parse_args()

    lib = library_from_rekordbox()
    print(f"biblioteka: {len(lib)} utworów z wykonawcą i tytułem", flush=True)

    wanted: set[str] = set()
    for _, t in lib:
        wanted |= tokens(t)
    print(f"różnych słów w tytułach: {len(wanted)}", flush=True)

    db = sqlite3.connect(args.db)
    index: dict[str, list[int]] = defaultdict(list)
    rowsdata: dict[int, tuple] = {}
    n = 0
    for rid, artist, title, genres, styles in db.execute(
            "SELECT rowid, artist, title, genres, styles FROM tracks"):
        n += 1
        tt = tokens(title)
        hit = tt & wanted
        if not hit:
            continue
        rowsdata[rid] = (artist, title, genres, styles)
        for t in hit:
            index[t].append(rid)
    print(f"przejrzane {n:,} pozycji Discogs · kandydatów w indeksie "
          f"{len(rowsdata):,}", flush=True)

    found, styles_count, misses, examples = 0, Counter(), [], []
    for artist, title in lib:
        cand: set[int] = set()
        for t in tokens(title):
            cand |= set(index.get(t, ()))
        best = None
        for rid in cand:
            a2, t2, _, st = rowsdata[rid]
            if same_record(artist, title, a2, t2):
                best = (a2, t2, st)
                break
        if best and best[2]:
            found += 1
            for s in best[2].split("|"):
                if s:
                    styles_count[s] += 1
            if len(examples) < args.show:
                examples.append((artist, title, best[2].replace("|", ", ")))
        else:
            misses.append((artist, title))

    print(f"\nZNALEZIONE ZE STYLEM: {found} z {len(lib)} "
          f"({found / max(len(lib), 1) * 100:.1f}%)\n")
    print("style w bibliotece DJ-a, wg Discogs:")
    for s, c in styles_count.most_common(20):
        print(f"  {c:5d}  {s}")
    print("\nprzykłady dopasowań:")
    for a, t, s in examples:
        print(f"  {a[:24]:24s} {t[:34]:34s} → {s[:44]}")
    print(f"\nnietrafione ({len(misses)}), pierwsze 12:")
    for a, t in misses[:12]:
        print(f"  {a[:26]:26s} {t[:44]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
