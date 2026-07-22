"""DJ Style Harvester — mine per-DJ style profiles from the DJ-mix corpus.

The corpus (5040 mixes, 100k+ tracklist positions) was downloaded and aligned
but its per-DJ style signal was never extracted. This turns it into concrete,
rankable DJ style profiles: signature artists, signature tracks, genre palette,
and data volume — with NO dependency on CLAP, the model gate, or user taste.

Ranks DJs by data volume (sets, then tracks) so the richest profiles surface
first. Output: data/reports/dj_style_profiles/profiles.json + stdout summary.

Usage: python3 scripts/dj_style_harvester.py [--top N] [--min-sets K]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path("/Volumes/MY_PC/DanceLabCorpus/djmix-dataset.json")
OUT_DIR = ROOT / "data/reports/dj_style_profiles"

_DATE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*[-–]?\s*")
_INDEX = re.compile(r"^\[\d+\]\s*")
_ARTIST = re.compile(r"\s*([^-]+?)\s*-\s*(.+)")

# category tags that carry genre meaning (mixesdb uses "category:<x>")
GENRE_WORDS = {
    "techno", "house", "tech house", "deep house", "minimal", "disco", "electro",
    "ambient", "drum and bass", "dubstep", "trance", "breakbeat", "garage",
    "uk garage", "acid", "electronica", "progressive house", "melodic techno",
    "afro house", "downtempo", "idm", "jungle", "hardcore", "hard techno",
    "progressive trance", "tech trance", "psytrance", "big room", "future house",
    "bass", "grime", "funk", "soul", "hip hop", "nu disco", "italo",
}


def dj_of(title: str) -> str:
    """Extract the DJ/artist name from a mixesdb-style title."""
    t = _DATE.sub("", title or "")
    t = re.split(r"\s@\s|\bBoiler Room\b|\bEssential Mix\b|\blive at\b|\b@\b", t, flags=re.I)[0]
    t = re.split(r"\s[-–]\s", t)[0]
    return t.strip().strip("-–").strip()


def track_artist(raw_title: str) -> tuple[str, str] | None:
    title = _INDEX.sub("", raw_title or "")
    m = _ARTIST.match(title)
    if not m:
        return None
    artist = m.group(1).strip().lower()
    if not artist or artist in {"id", "??", "?", "unknown"}:
        return None
    return artist, title.strip()


def genres_from_tags(tags: list) -> list[str]:
    out = []
    for tg in tags or []:
        key = (tg.get("key", "") if isinstance(tg, dict) else str(tg))
        key = key.replace("category:", "").strip().lower()
        if key in GENRE_WORDS:
            out.append(key)
    return out


def build_profiles(mixes_by_dj: dict[str, list]) -> list[dict]:
    profiles = []
    for dj, mixes in mixes_by_dj.items():
        artists: Counter = Counter()
        tracks: Counter = Counter()
        genres: Counter = Counter()
        n_tracks = 0
        for mix in mixes:
            for g in genres_from_tags(mix.get("tags")):
                genres[g] += 1
            for tr in mix.get("tracklist") or []:
                raw = tr.get("title", "") if isinstance(tr, dict) else str(tr)
                n_tracks += 1
                parsed = track_artist(raw)
                if parsed:
                    artists[parsed[0]] += 1
                    tracks[parsed[1].lower()[:70]] += 1
        signature_tracks = [(t, c) for t, c in tracks.most_common(12) if c >= 2]
        profiles.append({
            "dj": dj,
            "n_sets": len(mixes),
            "n_tracks": n_tracks,
            "n_unique_tracks": len(tracks),
            "avg_tracks_per_set": round(n_tracks / max(len(mixes), 1), 1),
            "genres": genres.most_common(5),
            "signature_artists": artists.most_common(12),
            "signature_tracks": signature_tracks,
        })
    # rank by data volume: sets first, then total tracks
    profiles.sort(key=lambda p: (p["n_sets"], p["n_tracks"]), reverse=True)
    return profiles


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--min-sets", type=int, default=2)
    args = ap.parse_args()

    data = json.loads(CORPUS.read_text())
    by_dj: dict[str, list] = defaultdict(list)
    for mix in data:
        dj = dj_of(mix.get("title", ""))
        if dj and len(dj) > 2 and not dj[0].isdigit():
            by_dj[dj].append(mix)

    profiles = build_profiles({k: v for k, v in by_dj.items() if len(v) >= args.min_sets})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "dj-style-profiles-v1",
        "source": "djmix-dataset.json",
        "total_djs": len(by_dj),
        "profiled_djs": len(profiles),
        "profiles": profiles[: args.top],
    }
    (OUT_DIR / "profiles.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))

    print(f"DJ-ów w korpusie: {len(by_dj)} | sprofilowanych (≥{args.min_sets} setów): {len(profiles)}")
    print(f"zapisano top {min(args.top, len(profiles))} → {OUT_DIR/'profiles.json'}\n")
    print(f"{'#':>3}  {'sety':>4} {'tracki':>6}  DJ  ·  sygnatura")
    for i, p in enumerate(profiles[:15], 1):
        sig = " · ".join(a for a, _ in p["signature_artists"][:4])
        print(f"{i:>3}  {p['n_sets']:>4} {p['n_tracks']:>6}  {p['dj']}  ·  {sig}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
