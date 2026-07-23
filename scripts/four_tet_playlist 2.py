"""End-to-end 'Four Tet-like' playlist from the user's own library.

Uses EVERYTHING we have, no UI:
  1. CLAP library embeddings  → pick tracks that SOUND like the Four Tet anchor
  2. engine analyze_track     → real BPM / Camelot key / energy for the shortlist
  3. engine build_set (harmonic/energy 'build' arc) → mixable ORDER

Output: an .m3u the user can import into Rekordbox + a readable JSON/summary.

Usage: PYTHONPATH=src python3 scripts/four_tet_playlist.py \
    [--anchor "four tet"] [--pool 16] [--arc build]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

LIBRARY_ROOT = Path("/Users/jantrybus/Music")
EMB = ROOT / "data/reports/library_embeddings.json"
OUT_M3U = ROOT / "data/reports/four_tet_playlist.m3u"
OUT_XML = ROOT / "data/reports/four_tet_playlist.rekordbox.xml"
OUT_JSON = ROOT / "data/reports/four_tet_playlist.json"
CACHE_DIR = ROOT / "data/reports/library_analysis_cache"


def artist_of(rel: str) -> str:
    """Best-effort artist from a library filename ('Artist - Title.ext')."""
    name = rel.split("/")[-1].rsplit(".", 1)[0]
    name = re.sub(r"^\[\d+\]\s*|^\d+[\s._-]+", "", name)  # strip leading index
    return re.split(r"\s-\s", name)[0].strip().lower() or name.lower()


def album_of(path: Path) -> str | None:
    """Album from audio tags (compilations!). None when untagged — then uncapped.

    Handles both easy keys ('album') and raw ID3 frames ('TALB' — AIFF/ID3
    files don't get the easy mapping).
    """
    try:
        import mutagen
        f = mutagen.File(str(path), easy=True)
        if not (f and f.tags):
            return None
        raw = f.tags.get("album") or f.tags.get("TALB")
        if raw is None:
            return None
        if hasattr(raw, "text") and raw.text:
            val = str(raw.text[0])
        elif isinstance(raw, (list, tuple)) and raw:
            val = str(raw[0])
        else:
            val = str(raw)
        val = val.strip().lower()
        return val or None
    except Exception:
        return None


def rank_by_sound(anchor_sub: str, pool: int, max_per_artist: int,
                  max_per_album: int) -> list[tuple[str, float]]:
    data = json.loads(EMB.read_text())["tracks"]
    names = list(data)
    V = np.array([data[n] for n in names])
    anchor_idx = [i for i, n in enumerate(names) if anchor_sub.lower() in n.lower()]
    if not anchor_idx:
        raise SystemExit(f"anchor '{anchor_sub}' not in library embeddings")
    anchor = V[anchor_idx].mean(axis=0)
    anchor /= np.linalg.norm(anchor)
    sims = V @ anchor
    order = np.argsort(-sims)
    picked: list[tuple[str, float]] = []
    reserve: list[tuple[str, float]] = []  # 2nd-from-album — extreme-case only
    seen_vecs: list[np.ndarray] = []
    artist_count: dict[str, int] = {}
    album_count: dict[str, int] = {}
    for i in order:
        if any(float(V[i] @ sv) > 0.999 for sv in seen_vecs):  # near-identical dup
            continue
        art = artist_of(names[i])
        if artist_count.get(art, 0) >= max_per_artist:  # artist diversity
            continue
        # album rule (Janek): 1/10 tracks, "max 2 w ekstremalnych przypadkach",
        # NEVER 3+ — craft rule: no DJ wants to be caught playing one record
        alb = album_of(LIBRARY_ROOT / names[i])
        if alb and album_count.get(alb, 0) >= max_per_album:
            if album_count.get(alb, 0) == max_per_album:  # exactly the 2nd → reserve
                reserve.append((names[i], float(sims[i])))
                album_count[alb] = album_count[alb] + 1  # 3rd+ never enters anything
            continue
        picked.append((names[i], float(sims[i])))
        seen_vecs.append(V[i])
        artist_count[art] = artist_count.get(art, 0) + 1
        if alb:
            album_count[alb] = album_count.get(alb, 0) + 1
        if len(picked) >= pool:
            break
    return picked, reserve


def cached_analyze(abs_path: Path, cfg, analyze_track):
    """Analyse once, reuse forever (keyed by path+mtime+size). Kills the 8-min re-runs."""
    from dancelab.core.models import AnalysisResult
    st = abs_path.stat()
    key = hashlib.md5(f"{abs_path}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()
    cf = CACHE_DIR / f"{key}.json"
    if cf.is_file():
        return AnalysisResult.model_validate_json(cf.read_text())
    res = analyze_track(abs_path, cfg)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cf.write_text(res.model_dump_json(), encoding="utf-8")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anchor", default="four tet")
    ap.add_argument("--pool", type=int, default=22)
    ap.add_argument("--minutes", type=float, default=60.0, help="target set length; 0 = no trim")
    ap.add_argument("--max-per-artist", type=int, default=1, help="artist diversity cap")
    ap.add_argument("--max-per-album", type=int, default=0,
                    help="album/compilation cap; 0 = auto: 1 per ~10 tracks, hard max 4")
    ap.add_argument("--arc", default="build")
    args = ap.parse_args()

    # Janek's rule: 1 per album per ~10 tracks of playlist, absolute cap 4
    max_album = args.max_per_album or max(1, min(4, int(round(args.minutes / 60))))

    from dancelab.core.config import load_config, load_weights
    from dancelab.core.pipeline import analyze_track

    shortlist, reserve = rank_by_sound(args.anchor, args.pool, args.max_per_artist, max_album)
    print(f"(dywersyfikacja: max {args.max_per_artist}/artystę, max {max_album}/album)", flush=True)
    print(f"CLAP shortlist ({len(shortlist)} tracków najbliższych '{args.anchor}'):", flush=True)
    for rel, sim in shortlist:
        print(f"  {sim:.3f}  {rel.split('/')[-1][:60]}", flush=True)

    cfg = load_config(str(ROOT / "configs/default.yaml"))
    weights = load_weights(str(ROOT / "configs/descriptor_weights.yaml"))

    meta: dict[str, dict] = {}

    def analyze_into(rel: str, sim: float):
        """Analyse one candidate; None for failures and non-tracks (>15 min)."""
        abs_path = LIBRARY_ROOT / rel
        try:
            res = cached_analyze(abs_path, cfg, analyze_track)
        except Exception as exc:
            print(f"  skip {rel.split('/')[-1][:40]}: {type(exc).__name__}", flush=True)
            return None
        if (res.track.duration_sec or 0) > 900:
            print(f"  pominięto >15 min (miks, nie track): {rel.split('/')[-1][:40]}", flush=True)
            return None
        meta[res.track.track_id] = {
            "rel": rel, "abs": str(abs_path), "sim": round(sim, 3),
            "title": res.track.title, "artist": res.track.artist,
            "bpm": round(res.track.bpm_estimate, 1) if res.track.bpm_estimate else None,
            "key": res.track.key_estimate,
            "dur": res.track.duration_sec,
        }
        return res

    print("\nanaliza silnika (BPM/klucz/energia)…", flush=True)
    analyses = [a for a in (analyze_into(rel, sim) for rel, sim in shortlist) if a]
    print(f"  zanalizowano {len(analyses)} tracków", flush=True)

    # tempo window vs the anchor's BPM (octave-folded): a craft floor — a set of
    # Four-Tet-likes should not be glued with ±30% jumps
    from dancelab.decision._common import nearest_bpm_variant

    anchor_meta = max(meta.values(), key=lambda m: m["sim"], default=None)
    anchor_bpm = anchor_meta.get("bpm") if anchor_meta else None

    def tempo_ok(a) -> bool:
        b = a.track.bpm_estimate
        if not (b and anchor_bpm):
            return True  # unknown → let the engine judge downstream
        folded = nearest_bpm_variant(anchor_bpm, b)
        return abs(folded - anchor_bpm) / anchor_bpm <= 0.18

    if args.minutes and args.minutes > 0:
        target = args.minutes * 60
        by_sim = sorted(analyses, key=lambda a: -meta[a.track.track_id]["sim"])
        keep, total, outliers = [], 0.0, []
        for a in by_sim:
            if total >= target:
                break
            if tempo_ok(a):
                keep.append(a)
                total += meta[a.track.track_id].get("dur") or 0.0
            else:
                outliers.append(a)
        # extreme clause (Janek): a 2nd track from an album may enter INSTEAD of
        # a tempo outlier — never a 3rd, and only when the set runs short
        if total < 0.85 * target and reserve:
            print("  klauzula ekstremalna: dopuszczam 2. z albumu zamiast outliera tempa", flush=True)
            for rel, sim in reserve:
                if total >= target:
                    break
                a = analyze_into(rel, sim)
                if a and tempo_ok(a):
                    keep.append(a)
                    total += meta[a.track.track_id].get("dur") or 0.0
                    print(f"    + {rel.split('/')[-1][:52]}", flush=True)
        if outliers:
            names_out = ", ".join(
                f"{meta[o.track.track_id]['title'] or meta[o.track.track_id]['rel'].split('/')[-1][:30]}"
                f" ({meta[o.track.track_id]['bpm']})" for o in outliers)
            print(f"  odrzucone outliery tempa (>±18% od kotwicy): {names_out}", flush=True)
        if total < 0.85 * target:
            print(f"  UWAGA: set krótszy niż cel ({total/60:.0f} min) — wolę krótszy niż śmieciowe przejścia", flush=True)
        analyses = keep
        print(f"  cel {args.minutes:.0f} min → {len(analyses)} tracków "
              f"(suma {total/60:.1f} min surowej długości)", flush=True)

    from dancelab.decision.set_builder import build_set

    plan = build_set(analyses, weights, arc=args.arc)
    order = plan.track_order
    by_id = {a.track.track_id: a for a in analyses}
    trans = list(plan.transitions)  # engine already scored every A→B — surface it

    # mix profile per adjacent pair: mixability → transition_strategy (best effort)
    profiles: dict[int, dict] = {}
    try:
        from dancelab.core.models import MixabilityInput
        from dancelab.decision.mixability import compute_mixability
        from dancelab.decision.transition_strategy import classify_transition_strategy
        for i in range(len(order) - 1):
            a, b = by_id.get(order[i]), by_id.get(order[i + 1])
            if not (a and b):
                continue
            mix = compute_mixability(
                MixabilityInput(track_a=a, track_b=b),
                weights.mixability, weights.mixability_conflict,
            )
            strat = classify_transition_strategy(a, b, mix)
            profiles[i] = {
                "mix_score": round(mix.mixability_score, 2),
                "profile": getattr(strat.recommended_transition_strategy, "value",
                                    str(strat.recommended_transition_strategy)),
                "risk": (mix.risks[0] if mix.risks else None),
            }
    except Exception as exc:
        print(f"  (profil miksu pominięty: {type(exc).__name__}: {exc})", flush=True)

    lines = ["#EXTM3U"]
    rows = []
    for pos, tid in enumerate(order, 1):
        m = meta.get(tid, {})
        lines.append(f"#EXTINF:-1,{m.get('artist') or '?'} - {m.get('title') or m.get('rel','?').split('/')[-1]}")
        lines.append(m.get("abs", ""))
        t = trans[pos - 1] if pos - 1 < len(trans) else None
        p = profiles.get(pos - 1, {})
        rows.append({"pos": pos, **m,
                     "to_next": ({"harmonic": t.harmonic_relation, "key": f"{t.key_from}->{t.key_to}",
                                  "bpm_delta_pct": t.bpm_delta_pct, "energy_delta": t.energy_delta,
                                  "score": round(t.transition_score, 2),
                                  "reason": (t.reasoning[0] if t.reasoning else None), **p} if t else None)})
    OUT_M3U.write_text("\n".join(lines), encoding="utf-8")

    # Rekordbox XML — the engine's native exporter (playlist + hot cues from
    # transition windows; NEVER writes BPM/beatgrid — the hard invariant)
    try:
        from dancelab.core.models import TransitionWindowInput
        from dancelab.decision.transition_windows import detect_transition_windows
        from dancelab.export.rekordbox import build_rekordbox_xml, write_rekordbox_xml

        windows = {
            an.track.track_id: detect_transition_windows(
                TransitionWindowInput(track_id=an.track.track_id, segments=an.segments,
                                      feature_frames=an.features, beatgrid=an.beatgrid),
                weights.transition_window, top_k=cfg.analysis.transition_top_n).windows
            for an in analyses
        }
        xml = build_rekordbox_xml(analyses, set_plan=plan, windows_by_track=windows,
                                  playlist_name="Four Tet like — DanceLab",
                                  export_beatgrid=False)
        write_rekordbox_xml(xml, OUT_XML)
        print(f"Rekordbox XML: {OUT_XML}", flush=True)
    except Exception as exc:
        print(f"(XML pominięty: {type(exc).__name__}: {exc})", flush=True)

    total_min = sum((r.get("dur") or 0.0) for r in rows) / 60
    c = plan.set_coherence
    OUT_JSON.write_text(json.dumps({
        "anchor": args.anchor, "arc": args.arc, "minutes": round(total_min, 1),
        "n_in_set": len(order), "n_dropped": len(plan.dropped_track_ids),
        "set_coherence": c.model_dump() if c else None, "order": rows,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== FOUR-TET-LIKE SET ({len(order)} tracków · ~{total_min:.0f} min · arc {args.arc}) ===")
    for r in rows:
        bpm = f"{r.get('bpm')}" if r.get("bpm") else "?"
        print(f"{r['pos']:>2}. [{str(r.get('key') or '?'):>3} {bpm:>5}bpm  vibe {r.get('sim',0):.2f}]  "
              f"{(r.get('artist') or '?')} – {(r.get('title') or '?')[:40]}")
        tn = r.get("to_next")
        if tn:
            risk = f" ⚠ {tn['risk']}" if tn.get("risk") else ""
            print(f"      ↓ {tn['key']} {tn['harmonic']} · ΔBPM {tn.get('bpm_delta_pct')}% · "
                  f"score {tn['score']} · {tn.get('profile','?')} (mix {tn.get('mix_score','?')}){risk}")
    if c:
        print(f"\nspójność setu: {c.overall:.2f}  (łuk energii {c.arc_adherence:.2f} · ciągłość tempa {c.tempo_continuity:.2f})")
    if plan.dropped_track_ids:
        print(f"silnik odrzucił {len(plan.dropped_track_ids)} track(ów) jako niepasujące")
    print(f"\n→ {OUT_M3U}  (import do Rekordbox)  ·  → {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
