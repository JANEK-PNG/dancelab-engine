"""Where the missing half of the library goes.

Discogs answers 54.1 % of this library and 88 % of it has an artist Discogs knows,
so thirty points sit between what we get and what is there. Guessing at that gap is
how the whole style question went wrong twice already, so this counts it.

Every miss lands in exactly one bucket, and the buckets are chosen so each one
implies a different decision:

  * not music — samples, loops, our own stem exports, the DJ's own recorded sets.
    Nothing to find. Should never have been in the denominator.
  * artist unknown to Discogs — the record is not in the database at all. A real
    ceiling; no amount of matching work recovers it.
  * artist known, and the title carries a remix or edit marker — likely a version
    Discogs does not carry. Also a ceiling, but a different one: the original is
    usually there, so we could fall back to the original's style.
  * artist known, plain title — a record that ought to be findable and is not.
    This is the only bucket that is our fault, and the only one worth work.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sqlite3
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from discogs_style_db import same_record, tokens              # noqa: E402
from match_library_styles import library_from_rekordbox       # noqa: E402

NOT_MUSIC = re.compile(
    r"loopmasters|rekordbox|demo track|sample|oneshot|looperman|mergefx|"
    r"\blifter\b|\bimpact\b|^snare$|^kick$|^noise|^boom|open deck|premier",
    re.I)
VERSION = re.compile(r"\b(remix|rmx|edit|vip|bootleg|rework|refix|flip|mashup|"
                     r"dub|version|re-?version)\b", re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="/Volumes/MY_PC/DanceLabStyleDB/"
                                    "styles_releases.sqlite3")
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args()

    lib = library_from_rekordbox()
    print(f"biblioteka: {len(lib)} pozycji", flush=True)

    want_t: set[str] = set()
    want_a: set[str] = set()
    for a, t in lib:
        want_t |= tokens(t)
        want_a |= tokens(a)

    db = sqlite3.connect(args.db)
    by_title: dict[str, list[int]] = defaultdict(list)
    by_artist: dict[str, list[int]] = defaultdict(list)
    rows: dict[int, tuple] = {}
    n = 0
    for rid, artist, title, styles in db.execute(
            "SELECT rowid, artist, title, styles FROM tracks"):
        n += 1
        if n % 5_000_000 == 0:
            print(f"  {n:,} …", flush=True)
        ta = tokens(artist)
        if not (ta & want_a):
            continue
        tt = tokens(title)
        rows[rid] = (artist, title, styles)
        for x in ta & want_a:
            by_artist[x].append(rid)
        for x in tt & want_t:
            by_title[x].append(rid)
    print(f"przejrzane {n:,} pozycji Discogs\n", flush=True)

    buckets: Counter = Counter()
    samples: dict[str, list] = defaultdict(list)
    for a, t in lib:
        if NOT_MUSIC.search(a) or NOT_MUSIC.search(t):
            buckets["nie muzyka"] += 1
            samples["nie muzyka"].append((a, t))
            continue
        cand: set[int] = set()
        for x in tokens(t):
            cand |= set(by_title.get(x, ()))
        if any(same_record(a, t, rows[r][0], rows[r][1]) and rows[r][2] for r in cand):
            buckets["znalezione ze stylem"] += 1
            continue
        known = any(by_artist.get(x) for x in tokens(a))
        if not known:
            key = "artysty nie ma w Discogs"
        elif VERSION.search(t):
            key = "jest artysta, tytuł to wersja (remix/edit/VIP)"
        else:
            key = "jest artysta, zwykły tytuł — NASZ BŁĄD"
        buckets[key] += 1
        samples[key].append((a, t))

    total = sum(buckets.values())
    print(f"{'':52s}  ile   udział")
    for k, c in buckets.most_common():
        print(f"  {k:50s} {c:5d}  {c / total * 100:5.1f}%")

    for k in ("jest artysta, zwykły tytuł — NASZ BŁĄD",
              "jest artysta, tytuł to wersja (remix/edit/VIP)",
              "artysty nie ma w Discogs"):
        if not samples.get(k):
            continue
        print(f"\n{k} — przykłady:")
        for a, t in samples[k][:args.show]:
            print(f"  {a[:26]:26s} {t[:46]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
