"""A style for every record, from the Discogs dump rather than from a tag.

The corpus gave us a style vocabulary but it is somebody else's: 81 % of its 5040
mixes are House, Techno, Tech House, Progressive or Trance, while UK Garage has 12
mixes, Breakbeat 21, Bassline 23 and UK Bass none at all — so this DJ's records land
on whichever of six centroids is nearest, which is a nearest neighbour and not a
description. And reading style from the files themselves is worse: 72 % carry no
genre tag, and 53 % of what Rekordbox holds says "electronic" or "dance".

Discogs publishes its whole database monthly under CC0, and a release carries both
`genres` and `styles` — where the styles are at the resolution a DJ actually uses:
UK Garage, Bassline, Breakbeat, Jungle, Grime, Deep House, Tech House. So a record
does not have to sound like anything: it has to be *found*. No embedding, no
centroid, no two-thirds ceiling.

The dump is 32 GB unpacked, so nothing is ever held in memory: the gzip is parsed as
a stream and each release is discarded as soon as its rows are written.

Discogs describes a RELEASE, not a track, so a track inherits the styles of the record
it came out on. For a two-track twelve-inch that is what a DJ would say anyway; for a
compilation it is the compilation's style, which is why the release format is kept.

Matching is the real work, not downloading. A library says `01 Chiggy Chiggy (Rohaan
Extended Remix)` where Discogs says `Chiggy Chiggy (Rohaan Remix)`, macOS writes
`Selvática` differently from Rekordbox, and half the files carry a track number in
front. So the key is normalised hard: accents folded, leading track numbers removed,
the mix-suffix noise dropped, everything else reduced to sorted word tokens.
"""

from __future__ import annotations

import argparse
import gzip
import pathlib
import re
import sqlite3
import unicodedata as U
from xml.etree import ElementTree as ET

# Suffixes that a shop, a DAW or a DJ adds and which never distinguish two records.
NOISE = re.compile(
    r"\b(original|extended|radio|club|vocal|instrumental|dub)?\s*"
    r"(mix|edit|version|remaster(ed)?|vip)\b", re.I)
LEADING_NUM = re.compile(r"^\s*[\[(]?\d{1,3}[\])._\- ]+\s*")
BRACKETS = re.compile(r"[\[(][^\])]*[\])]")


def tokens(s: str) -> set[str]:
    """What is left of a name once every way of writing it down is stripped off."""
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c)).lower()
    s = LEADING_NUM.sub("", s)
    s = BRACKETS.sub(" ", s)
    s = NOISE.sub(" ", s)
    s = re.sub(r"\bfeat\.?\b.*$", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    # Single letters are noise; a single digit is not. Dropping it made `Wiggler 2`
    # identical to `Wiggler`, which is a different record by the same artist.
    return {t for t in s.split() if len(t) > 1 or t.isdigit()}


def key(artist: str, title: str) -> str:
    """A single indexable string. Exact equality is a first pass, not the matcher."""
    return f"{' '.join(sorted(tokens(artist)))}|{' '.join(sorted(tokens(title)))}"


def same_record(a1: str, t1: str, a2: str, t2: str) -> bool:
    """Whether two ways of writing a record name the same one.

    Exact key equality answers 4 of 7 real cases from this DJ's own library, and the
    three it misses are all the same shape — one side carries words the other does
    not. `CHROMA 010 BRILLO` against `Brillo` is a catalogue number inside the title;
    `Kettama, Fred again.., SICARIA` against `KETTAMA & Fred again..` is a third
    artist the shop listed and the label did not. Neither is a different record.

    So the title matches when one side's words contain the other's, and the artists
    match when they share anyone at all. Subset rather than equality is also why the
    lookup cannot be a plain index on the key — it needs the token index built in
    `main`, with this as the scorer over the candidates it returns.
    """
    T1, T2 = tokens(t1), tokens(t2)
    A1, A2 = tokens(a1), tokens(a2)
    if not T1 or not T2 or not (A1 & A2):
        return False
    if T1 == T2:
        return True
    short, long_ = (T1, T2) if len(T1) < len(T2) else (T2, T1)
    if not short < long_:
        return False
    # Subset alone is too generous: it merges `Baby` into `Baby Beat`, two records by
    # the same artist. A number among the extra words is not enough on its own either
    # — that lets `Wiggler` swallow `Wiggler 2`. What a catalogue number actually
    # looks like is a number AND a series name: `CHROMA 010 BRILLO` against `Brillo`
    # brings both, a sequel brings only the digit and another title only the word.
    extra = long_ - short
    return (any(t.isdigit() for t in extra)
            and any(not t.isdigit() for t in extra))


def rows(path: pathlib.Path, only_electronic: bool = True):
    """Stream (key, artist, title, genres, styles, year, release_id) out of the dump."""
    with gzip.open(path, "rb") as fh:
        for _, el in ET.iterparse(fh, events=("end",)):
            if el.tag != "release":
                continue
            genres = [g.text for g in el.findall("./genres/genre") if g.text]
            styles = [s.text for s in el.findall("./styles/style") if s.text]
            if only_electronic and "Electronic" not in genres:
                el.clear()
                continue
            names = [a.text for a in el.findall("./artists/artist/name") if a.text]
            main = ", ".join(names)
            year = (el.findtext("released") or "")[:4]
            rid = el.get("id") or ""
            for tr in el.findall("./tracklist/track"):
                title = tr.findtext("title")
                if not title:
                    continue
                # a track on a compilation carries its own artist; a track on an EP
                # inherits the release's, and Various is never an answer
                own = [a.text for a in tr.findall("./artists/artist/name") if a.text]
                who = ", ".join(own) if own else main
                if who.strip().lower() in ("", "various", "various artists"):
                    continue
                yield (key(who, title), who, title,
                       "|".join(genres), "|".join(styles), year, rid)
            el.clear()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default="/Volumes/MY_PC/DanceLabStyleDB/"
                                      "discogs_20260701_releases.xml.gz")
    ap.add_argument("--db", default="/Volumes/MY_PC/DanceLabStyleDB/styles.sqlite3")
    ap.add_argument("--all-genres", action="store_true",
                    help="Nie filtruj do Electronic (baza urośnie kilkukrotnie)")
    ap.add_argument("--limit", type=int, default=0, help="Przerwij po N wierszach")
    args = ap.parse_args()

    db = sqlite3.connect(args.db)
    db.executescript("""
        PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
        CREATE TABLE IF NOT EXISTS tracks(
            k TEXT, artist TEXT, title TEXT, genres TEXT, styles TEXT,
            year TEXT, release_id TEXT);
    """)
    n = 0
    batch = []
    for row in rows(pathlib.Path(args.dump), not args.all_genres):
        batch.append(row)
        n += 1
        if len(batch) >= 50_000:
            db.executemany("INSERT INTO tracks VALUES (?,?,?,?,?,?,?)", batch)
            db.commit()
            batch.clear()
            print(f"  {n:,} wierszy", flush=True)
        if args.limit and n >= args.limit:
            break
    if batch:
        db.executemany("INSERT INTO tracks VALUES (?,?,?,?,?,?,?)", batch)
    db.commit()
    print(f"indeksuję {n:,} wierszy …", flush=True)
    db.execute("CREATE INDEX IF NOT EXISTS ix_k ON tracks(k)")
    db.commit()
    db.close()
    print(f"gotowe: {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
