"""Buduje `data/reports/dj_anchors.json` — podpisy brzmienia i prowadzenia DJ-ów.

To jest most między badaniami a produktem. Badania (experiments_priv) mają
tracklisty miksów Boiler Room / Warehouse Project i wektory CLAP z 30-sekundowych
próbek. Produkt („graj jak X") potrzebuje z tego trzech rzeczy na DJ-a:

  centroid   środek brzmienia tego, co grywa (kotwica selekcji),
  contour    kolejne skoki podobieństwa sąsiadów w jego NAJDŁUŻSZYM miksie
             (sposób prowadzenia — zmierzone 03.08, że styl to rozkład i jego
             kształt, nie średnia; celowanie w medianę gasi rozrzut),
  statystyki mediana/kwartyle skoków — do raportowania „jak blisko podeszliśmy".

Progi uczciwości:
  * DJ wchodzi do pliku tylko z >=12 wektorami — mniejsza próbka to nie podpis,
    tylko anegdota;
  * pozycje nie-muzyczne (Commentary/Interlude — zmierzone 4,3% zbioru) odpadają;
  * każdy wpis niesie źródło: wektory z PRÓBEK WERSJI ZMIKSOWANYCH (30 s), nie
    z pełnych plików — kto porówna z wektorami biblioteki, ma o tym wiedzieć
    (przeciek źródła wektora, 02.08, AUC 0,889).

Uruchamiać po każdej rozbudowie korpusu miksów. Produkt tylko CZYTA wynik.
"""

from __future__ import annotations

import json
import pathlib
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRACKLISTS = ROOT / "experiments_priv/2026-08-03_applemix/tracklisty.json"
EMBEDDINGS = ROOT / "data/reports/applemix_embeddings.json"
OUT = ROOT / "data/reports/dj_anchors.json"

MIN_TRACKS = 12
SCHEMA = "dj-anchors-v1"
NON_MUSIC = ("Commentary", "Interlude", "Skit")


def main() -> int:
    albums = json.loads(TRACKLISTS.read_text())["albums"]
    vec_raw = json.loads(EMBEDDINGS.read_text())["tracks"]

    per_dj: dict[str, list[dict]] = defaultdict(list)
    for album in albums.values():
        artists = album.get("artist") or []
        artists = artists if isinstance(artists, list) else [artists]
        if len(artists) != 1:
            continue                      # b2b to wspólny podpis dwóch osób — pomijamy
        tracks = []
        for t in album.get("tracks") or []:
            rec = vec_raw.get(t.get("id") or "")
            if not rec:
                continue
            name = rec.get("track") or ""
            if any(name.startswith(p) for p in NON_MUSIC):
                continue
            tracks.append(rec)
        if tracks:
            per_dj[str(artists[0])].append(
                {"name": album.get("name", "?"), "tracks": tracks})

    out: dict[str, dict] = {}
    for dj, mixes in sorted(per_dj.items()):
        vectors = [t["vector"] for m in mixes for t in m["tracks"]]
        if len(vectors) < MIN_TRACKS:
            continue
        V = np.asarray(vectors, dtype=np.float64)
        V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-12
        centroid = V.mean(axis=0)
        centroid /= np.linalg.norm(centroid) + 1e-12

        longest = max(mixes, key=lambda m: len(m["tracks"]))
        L = np.asarray([t["vector"] for t in longest["tracks"]], dtype=np.float64)
        L /= np.linalg.norm(L, axis=1, keepdims=True) + 1e-12
        contour = [round(float(L[i] @ L[i + 1]), 4) for i in range(len(L) - 1)]

        out[dj] = {
            "n_tracks": len(vectors),
            "n_mixes": len(mixes),
            "mixes": [m["name"][:80] for m in mixes],
            "centroid": [round(float(x), 6) for x in centroid],
            "contour": contour,
            "contour_mix": longest["name"][:80],
            "cos_median": round(float(np.median(contour)), 3) if contour else None,
            "cos_q25": round(float(np.percentile(contour, 25)), 3) if contour else None,
            "cos_q75": round(float(np.percentile(contour, 75)), 3) if contour else None,
        }

    OUT.write_text(json.dumps({
        "schema_version": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "wektory CLAP z 30-sekundowych próbek WERSJI ZMIKSOWANYCH "
                  "(Apple Music, Boiler Room + Warehouse Project); nie porównywać "
                  "wprost z wektorami z pełnych plików bez świadomości różnicy źródła",
        "min_tracks": MIN_TRACKS,
        "djs": out,
    }, ensure_ascii=False))

    print(f"DJ-ów w pliku: {len(out)} (próg {MIN_TRACKS} wektorów)")
    for dj, d in sorted(out.items(), key=lambda kv: -kv[1]["n_tracks"])[:15]:
        print(f"  {d['n_tracks']:4d} wekt. · {d['n_mixes']} miksów · "
              f"mediana skoku {d['cos_median']}  {dj}")
    print(f"\nzapisane: {OUT} ({OUT.stat().st_size/1024:.0f} kB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
