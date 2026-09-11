"""Search bridge check: does artist+title search find the right Apple Music song?

    .venv/bin/python experiments_priv/2026-09-10_isrc_most/szukanie.py

Rule and threshold are fixed in PROGI_szukanie.md (written before this ran):
exact normalized title, at least one shared artist, duration within 3 s,
exactly one candidate. Precision is measured on local files whose catalog id
is already known from their ISRC (the ground truth); >= 98 % or the rule does
not ship. Artist and title come from the file tag, then Rekordbox, then the
analysis. Prints counts only; per-file detail goes to wynik_szukanie.json
(gitignored). Needs the MusicKit config; only catalog endpoints are called.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import unicodedata

TU = pathlib.Path(__file__).resolve().parent
ROOT = TU.parents[1]
sys.path.insert(0, str(ROOT / "src"))

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
_SPLIT = re.compile(r"\s*(?:,|&|/|;|\bfeat\.?\b|\bft\.?\b|\bvs\.?\b|\bwith\b)\s*", re.I)


def norm(s: str | None) -> str:
    """NFKD without accents, lower case, no version brackets, no 'feat. …', letters/digits only."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[\(\[].*?[\)\]]", " ", s)
    s = re.sub(r"\b(feat|ft)\b\.?.*$", " ", s)
    return " ".join(re.findall(r"[a-z0-9]+", s))


def artists(s: str | None) -> set[str]:
    """Split an artist credit into normalized names."""
    return {norm(p) for p in _SPLIT.split(s or "") if norm(p)}


def match(file_meta: dict, songs: list[dict]) -> dict | None:
    """The single candidate passing the pre-registered rule, else None."""
    t, a, dur = norm(file_meta["title"]), artists(file_meta["artist"]), file_meta["duration"]
    if not t or not a or not dur:
        return None
    ok = []
    for s in songs:
        at = s.get("attributes") or {}
        if norm(at.get("name")) != t:
            continue
        if not (a & artists(at.get("artistName"))):
            continue
        ms = at.get("durationInMillis")
        if not ms or abs(ms / 1000 - dur) > 3:
            continue
        ok.append(s)
    return ok[0] if len(ok) == 1 else None


def local_meta() -> list[dict]:
    """Local files on disk with artist/title/duration from tag → Rekordbox → analysis."""
    from dancelab.ingestion.analysis_enrichment import load_rekordbox_meta_map
    from dancelab.ingestion.tags import read_audio_tags

    rb, _ = load_rekordbox_meta_map()
    out: dict[str, dict] = {}
    for f in PROCESSED.glob("*.json"):
        t = (json.loads(f.read_text()).get("track")) or {}
        sp = t.get("source_path") or ""
        if not sp or sp.startswith("apple-music:") or not pathlib.Path(sp).exists():
            continue
        key = unicodedata.normalize("NFC", sp)
        if key in out:
            continue
        tag = read_audio_tags(sp)
        rb_art, rb_tit = rb.get(key, ("", ""))
        out[key] = {"path": key,
                    "artist": tag.artist or rb_art or t.get("artist"),
                    "title": tag.title or rb_tit or t.get("title") or pathlib.Path(sp).stem,
                    "duration": t.get("duration_sec")}
    return list(out.values())


def main() -> None:
    """Measure precision on ISRC-known files, then apply to the rest if it passes."""
    from dancelab.ingestion.apple_music_api import AppleMusicClient
    from dancelab.ingestion.isrc_bridge import load_bridge

    bridge, _ = load_bridge()
    storefront = json.loads((ROOT / "data/reports/apple_library.json").read_text())["storefront"]
    client = AppleMusicClient.from_config()
    files = local_meta()

    def search(m: dict) -> dict | None:
        first = sorted(artists(m["artist"]))[:1]
        if not first or not norm(m["title"]):
            return None
        term = f"{first[0]} {norm(m['title'])}"[:120]
        page = client.get(f"/v1/catalog/{storefront}/search",
                          {"term": term, "types": "songs", "limit": "15"})
        songs = ((page.get("results") or {}).get("songs") or {}).get("data") or []
        return match(m, songs)

    znane = [m for m in files if m["path"] in bridge]
    rest = [m for m in files if m["path"] not in bridge]
    detail = {"known": [], "rest": []}
    hit = wrong = same_isrc = 0
    for m in znane:
        s = search(m)
        truth = bridge[m["path"]]
        row = {"path": pathlib.Path(m["path"]).name, "truth": truth["catalog_id"],
               "found": s and s["id"]}
        if s:
            if str(s["id"]) == str(truth["catalog_id"]):
                hit += 1
            else:
                wrong += 1
                if (s.get("attributes") or {}).get("isrc", "").replace("-", "").upper() == truth["isrc"]:
                    same_isrc += 1
                    row["same_isrc_other_id"] = True
        detail["known"].append(row)
    found = hit + wrong
    precision = hit / found if found else 0.0
    print(f"sprawdzian: plików z id z ISRC {len(znane)} | dopasowań {found} "
          f"(pokrycie {found / len(znane):.0%}) | trafnych {hit}, innych {wrong} "
          f"(z tym samym ISRC {same_isrc}) | precyzja {precision:.1%} (próg 98 %)")
    zdane = found > 0 and precision >= 0.98
    print("próg:", "ZDANY" if zdane else "NIE ZDANY")
    if zdane:
        dop = 0
        for m in rest:
            s = search(m)
            detail["rest"].append({"path": m["path"], "found": s and s["id"]})
            dop += bool(s)
        print(f"zastosowanie: {len(rest)} plików bez tożsamości → dopasowanych {dop}")
    (TU / "wynik_szukanie.json").write_text(json.dumps(
        {"precision": precision, "zdane": zdane, **detail}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
