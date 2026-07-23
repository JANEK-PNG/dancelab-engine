"""Artist similarity graph crawler — snowball from a seed via Last.fm.

Grows an artist-similarity graph (Janek's idea: 10 similar to Four Tet, each
10 similar, N levels deep) from REAL data — Last.fm `artist.getSimilar`, which
returns ranked neighbours with a match score. NOT from a language model's guess:
this keeps the "measure, don't guess" discipline (ADR-005).

BFS with dedup + a hard node cap, because the electronic neighbourhood saturates
(the same names recur by depth ~3). Resumable via the on-disk graph. Each edge
keeps Last.fm's match score so downstream code can weight similarity honestly.

Setup: get a free key at https://www.last.fm/api/account/create , then either
  export LASTFM_API_KEY=...   or   pass --api-key ...

Usage:
  python3 scripts/artist_graph_crawler.py --seed "Four Tet" --breadth 10 \
      --depth 5 --max-nodes 1500
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data/reports/artist_graph"
API = "https://ws.audioscrobbler.com/2.0/"


def get_similar(artist: str, api_key: str, limit: int) -> list[dict]:
    """Return [{name, match}] from Last.fm, or [] on any failure (keep crawling)."""
    q = urllib.parse.urlencode({
        "method": "artist.getsimilar", "artist": artist, "api_key": api_key,
        "format": "json", "limit": str(limit), "autocorrect": "1",
    })
    try:
        with urllib.request.urlopen(f"{API}?{q}", timeout=20) as resp:
            data = json.loads(resp.read())
    except Exception as exc:  # network / rate-limit / bad artist — skip, don't die
        print(f"  ! {artist}: {type(exc).__name__}", flush=True)
        return []
    out = []
    for a in (data.get("similarartists", {}).get("artist") or []):
        name = a.get("name")
        if name:
            out.append({"name": name, "match": float(a.get("match") or 0.0)})
    return out


def crawl(seed: str, api_key: str, breadth: int, depth: int, max_nodes: int) -> dict:
    nodes: dict[str, dict] = {}          # name -> {depth, first_seen_via}
    edges: list[dict] = []               # {source, target, match}
    seen: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(seed, 0)])
    nodes[seed] = {"depth": 0, "via": None}
    seen.add(seed.lower())

    while queue and len(nodes) < max_nodes:
        artist, d = queue.popleft()
        if d >= depth:
            continue
        neighbours = get_similar(artist, api_key, breadth)
        for n in neighbours:
            edges.append({"source": artist, "target": n["name"], "match": round(n["match"], 4)})
            key = n["name"].lower()
            if key not in seen:
                seen.add(key)
                nodes[n["name"]] = {"depth": d + 1, "via": artist}
                if len(nodes) < max_nodes:
                    queue.append((n["name"], d + 1))
        print(f"[{len(nodes)}/{max_nodes}] depth {d} · {artist} → {len(neighbours)}", flush=True)
        time.sleep(0.25)  # be polite to the API

    return {
        "schema_version": "artist-graph-v1",
        "source": "last.fm artist.getSimilar",
        "seed": seed,
        "params": {"breadth": breadth, "depth": depth, "max_nodes": max_nodes},
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": [{"name": k, **v} for k, v in nodes.items()],
        "edges": edges,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="Four Tet")
    ap.add_argument("--breadth", type=int, default=10)
    ap.add_argument("--depth", type=int, default=5)
    ap.add_argument("--max-nodes", type=int, default=1500)
    ap.add_argument("--api-key", default=os.environ.get("LASTFM_API_KEY", ""))
    args = ap.parse_args()

    if not args.api_key:
        raise SystemExit(
            "No Last.fm API key. Get one free at "
            "https://www.last.fm/api/account/create then: export LASTFM_API_KEY=..."
        )

    graph = crawl(args.seed, args.api_key, args.breadth, args.depth, args.max_nodes)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = args.seed.lower().replace(" ", "_")
    out = OUT_DIR / f"graph_{slug}.json"
    out.write_text(json.dumps(graph, ensure_ascii=False, indent=2))
    print(f"\ngraf: {graph['node_count']} artystów, {graph['edge_count']} krawędzi → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
