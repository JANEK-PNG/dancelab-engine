"""Set na granie Janka — 135–140 BPM, brzmienie UK bass/garage/breaks.

Brief (03.08): dwie godziny, energetycznie, 135–140 BPM, styl spójny —
UK garage / breaks / bass, dobrany do miksów z Warehouse Project i Boiler Room.

KOTWICA nie z tagów gatunkowych, tylko z BRZMIENIA — decyzja Janka z 31.07:
silnik nie twierdzi „to jest UK garage", twierdzi, że te płyty brzmią podobnie.
Tagi iTunes są tu zresztą bezużyteczne: wszystko wpada w „House" i „Techno".

Centroid liczony z utworów zagranych przez DJ-ów z tego świata w miksach,
które Janek wskazał. Biblioteka szeregowana po podobieństwie do centroidu,
potem kolejność układa produkcyjny `transition_score`.

Reguły rzemieślnicze Janka trzymane: max 1 utwór na artystę, tempo w oknie,
zero utworów-nie-utworów.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import unicodedata as U

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from grid_cache import grid_for                                    # noqa: E402
from dancelab.core.config import load_config, load_weights          # noqa: E402
from dancelab.decision.set_builder import transition_score          # noqa: E402
from dancelab.storage.repositories import FileAnalysisRepository    # noqa: E402

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
LIB_EMB = ROOT / "data/reports/library_embeddings.json"
MIX_EMB = ROOT / "data/reports/applemix_embeddings.json"
TRACKLISTS = ROOT / "experiments_priv/2026-08-03_applemix/tracklisty.json"
N = lambda s: U.normalize("NFC", str(s))  # noqa: E731

ANCHOR_DJS = [
    "DJ EZ", "Mala", "Jamie xx", "Bicep", "salute", "Anz", "Ben UFO",
    "TSHA", "Bradley Zero", "Four Tet", "Daphni", "Barry Can't Swim",
    "Call Super", "Nautica", "larishka", "Overmono", "Interplanetary Criminal",
    "Bakey", "Main Phase", "Hamdi", "Skream", "Sherelle", "Yung Singh",
]


def anchor_centroid():
    """Środek brzmienia z miksów wskazanych DJ-ów. Zwraca (wektor, ile utworów, kto)."""
    alb = json.loads(TRACKLISTS.read_text())["albums"]
    vec = json.loads(MIX_EMB.read_text())["tracks"]
    used, who = [], {}
    for a in alb.values():
        arts = a.get("artist") or []
        arts = arts if isinstance(arts, list) else [arts]
        hit = next((s for s in ANCHOR_DJS
                    for x in arts if s.lower() == str(x).lower()), None)
        if hit is None:
            continue
        for t in (a.get("tracks") or []):
            r = vec.get(t.get("id") or "")
            if not r:
                continue
            nm = (r.get("track") or "")
            if nm.startswith("Commentary") or nm.startswith("Interlude"):
                continue                       # nie-muzyka, zmierzone 4,3% zbioru
            used.append(np.asarray(r["vector"], dtype=np.float32))
            who[hit] = who.get(hit, 0) + 1
    if not used:
        return None, 0, {}
    c = np.mean(used, axis=0)
    return c / (np.linalg.norm(c) + 1e-9), len(used), who


STEM_NAMES = {"drums", "bass", "other", "vocals", "no_vocals", "accompaniment"}
MAX_TRACK_SEC = 15 * 60          # dłuższe to nie utwory, tylko czyjeś sety


def _norm_title(stem: str) -> str:
    import re
    s = re.sub(r"^\d+\s+", "", stem)
    s = re.sub(r"\((original|extended|radio)[^)]*\)", "", s, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def library():
    repo = FileAnalysisRepository(PROCESSED)
    an = [repo.get(t) for t in repo.list_track_ids()]
    d = json.loads(LIB_EMB.read_text())
    root = N(d.get("library_root", ""))
    out = []
    for a in an:
        p = pathlib.Path(a.track.source_path)
        if not p.exists():
            continue
        g = grid_for(str(p))
        bpm = float(g["bpm"]) if g else float(a.track.bpm_estimate or 0)
        v = d["tracks"].get(N(str(p))[len(root):].lstrip("/"))
        if v is None or bpm <= 0:
            continue
        # Trzy filtry, każdy z realnego znaleziska (03.08):
        #  * „Janek.mp3" trwa 43 min i wskoczył na 1. miejsce z podobieństwem
        #    0,920 — bo to CAŁY SET w tym stylu, nie utwór;
        #  * `drums/bass/vocals/other` ×4 to nasze własne wyjście Demucsa,
        #    które wróciło do puli (rejestr 30.07, wciąż nienaprawione);
        #  * ten sam utwór leży w dwóch folderach (Got No _3, OBSESSION).
        if p.stem.strip().lower() in STEM_NAMES:
            continue
        if (a.track.duration_sec or 0) > MAX_TRACK_SEC:
            continue
        w = np.asarray(v, dtype=np.float32)
        out.append({"a": a, "bpm": bpm, "vec": w / (np.linalg.norm(w) + 1e-9),
                    "name": p.stem, "key": _norm_title(p.stem),
                    "artist": (a.track.artist or p.stem.split(" - ")[0])})
    seen, uniq = set(), []
    for t in out:
        if t["key"] in seen:
            continue
        seen.add(t["key"])
        uniq.append(t)
    return uniq


def energy(a):
    v = [f.rms for f in (getattr(a, "features", None) or [])
         if getattr(f, "rms", None) is not None]
    return float(np.mean(v)) if v else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=float, default=135.0)
    ap.add_argument("--hi", type=float, default=140.0)
    ap.add_argument("--minutes", type=float, default=120.0)
    ap.add_argument("--pool", type=int, default=45, help="ilu kandydatów po brzmieniu")
    ap.add_argument("--out")
    args = ap.parse_args()

    c, n, who = anchor_centroid()
    if c is None:
        print("brak wektorów kotwicy — najpierw policz miksy")
        return 1
    print(f"KOTWICA: {n} utworów z miksów")
    print("  " + " · ".join(f"{k} {v}" for k, v in
                            sorted(who.items(), key=lambda x: -x[1])[:8]))

    lib = library()
    win = [t for t in lib if args.lo <= t["bpm"] <= args.hi]
    print(f"\nbiblioteka: {len(lib)} utworów · w oknie {args.lo:.0f}–{args.hi:.0f}: {len(win)}")
    for t in win:
        t["sim"] = float(t["vec"] @ c)
    win.sort(key=lambda t: -t["sim"])
    pool = win[: args.pool]
    print(f"\nnajbliżej brzmienia kotwicy (z {len(win)}):")
    for t in pool[:12]:
        print(f"   {t['sim']:.3f}  {t['bpm']:5.1f}  {t['name'][:52]}")

    # ── kolejność: produkcyjny transition_score, max 1 na artystę
    cfg = load_config(str(ROOT / "configs/default.yaml"))
    W = load_weights(cfg.weights_file)
    E = {id(t): (energy(t["a"]) or 0.5) for t in pool}
    er = (max(E.values()) - min(E.values())) or 1.0

    # KLATKA SCHODOWA, NIGDY W DÓŁ — decyzja Janka z 2026-07-31. Start bierzemy
    # z dolnej połowy okna (najlepsze brzmienie spośród wolniejszych), a potem
    # tempo może stać albo rosnąć, nigdy spadać. Bez tego łańcuch zachłanny
    # startował od 140 i schodził do 135, czyli grał się od końca.
    lo_half = [t for t in pool if t["bpm"] <= (args.lo + args.hi) / 2] or pool
    need = args.minutes * 60
    order = [max(lo_half, key=lambda t: t["sim"])]
    used_art = {order[0]["artist"].lower()}
    total = order[0]["a"].track.duration_sec or 270
    while total < need and len(order) < len(pool):
        cur = order[-1]
        best, bs = None, -1e9
        for t in pool:
            if t in order or t["artist"].lower() in used_art:
                continue
            if t["bpm"] < cur["bpm"] - 0.05:        # nigdy w dół
                continue
            s, _, _ = transition_score(cur["a"], t["a"], W, "build",
                                       E[id(cur)], E[id(t)], er)
            s += 0.35 * t["sim"]              # brzmienie kotwicy dokłada się do wyboru
            if s > bs:
                best, bs = t, s
        if best is None:
            break
        order.append(best)
        used_art.add(best["artist"].lower())
        total += best["a"].track.duration_sec or 270

    print(f"\n{'='*74}\nSET · {len(order)} utworów · {total/60:.0f} min\n{'='*74}")
    print(f"{'#':>3} {'BPM':>6} {'ton':>4} {'brzm':>5}  utwór")
    for i, t in enumerate(order, 1):
        k = t["a"].track.key_estimate or "?"
        print(f"{i:>3} {t['bpm']:6.1f} {k:>4} {t['sim']:5.2f}  {t['name'][:56]}")
    if args.out:
        pathlib.Path(args.out).write_text(
            "\n".join(t["a"].track.source_path for t in order), encoding="utf-8")
        print(f"\nścieżki: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
