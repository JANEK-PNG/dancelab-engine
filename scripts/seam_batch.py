"""Run the seam measurement across a whole recorded set, and say what it found.

One seam proves a method; a set is where a DJ's habits become visible. This walks
the .cue, locks every record onto the mix's clock, measures each handover, and
reduces it to the few numbers a DJ would recognise: how long the blend ran, was
the incoming bass held back and for how long, did the outgoing record thin out
before it left.

A seam that cannot be locked is dropped and counted, never estimated. The whole
point of the exercise is that these numbers came from the recording rather than
from a plausible story about it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from cue_parse import parse_cue
from seam_align import align, load_mono as load_env_mono, onset_env
import seam_decompose as S

MIN_ANCHORS = 2
LOCK_TOLERANCE = 0.4          # seconds; anchors must name the same origin


def _try_window(mix_path, track_env, t0, t1, splits=4) -> dict | None:
    """Strict consensus in one window: several stretches must name one instant."""
    if t1 - t0 < 25:
        return None
    edges = np.linspace(t0, t1, splits + 1)
    found = []
    for i in range(splits):
        a, b = float(edges[i]), float(edges[i + 1])
        if b - a < 8:
            continue
        r = align(onset_env(load_env_mono(mix_path, a, b)), track_env)
        if r is None:          # the stretched track is shorter than this window
            continue
        r["origin"] = a - r["track_sec"] / r["rate"]
        found.append(r)
    if len(found) < MIN_ANCHORS:
        return None
    med = float(np.median([r["origin"] for r in found]))
    agree = [r for r in found if abs(r["origin"] - med) < LOCK_TOLERANCE]
    if len(agree) < MIN_ANCHORS:
        return None
    return {"origin": float(np.median([r["origin"] for r in agree])),
            "rate": float(np.median([r["rate"] for r in agree])),
            "anchors": f"{len(agree)}/{len(found)}", "window": [t0, t1],
            "spread_ms": float(max(abs(r["origin"] - med) for r in agree) * 1000)}


def lock(mix_path, track_path, marker, next_marker) -> dict | None:
    """Where this record sits on the mix's clock, or None if it cannot be proven.

    Only one thing makes a lock trustworthy: independent stretches of the mix,
    searched separately, naming the same start instant to within a few hundred
    milliseconds. That test is kept strict and never relaxed — a lock accurate to
    a second is worthless when the question is when a hand moved.

    What varies instead is *where* we look. The obvious window — this marker to
    the next — is clean only if the record played alone, and on this material the
    DJ often cuts back and forth between two decks, so half the window belongs to
    someone else. Several candidate stretches are tried and the tightest lock
    wins. A record that passes nowhere is reported as unlocked, not estimated;
    two seam measurements were lost that way rather than invented.

    Rejected alternatives, both measured: voting across anchors in origin space
    survives contamination but lands 1-4 s out, and constraining the search to
    the marker's neighbourhood picks a neighbouring bar. Neither is precise
    enough to time a hand.
    """
    end = next_marker if next_marker else marker + 240
    track_env = onset_env(load_env_mono(track_path))
    candidates = [(marker + 8, end - 5), (marker + 8, marker + 95),
                  (marker + 40, marker + 170), (end - 95, end + 35)]
    got = [g for lo, hi in candidates
           if (g := _try_window(mix_path, track_env, lo, hi)) is not None]
    return min(got, key=lambda g: g["spread_ms"]) if got else None


# A knob that is down reads around 0.2-0.8 against the deck's own mid, and one
# that is up reads 0.9-1.5, so the two states separate cleanly — but only once the
# ratio is read over a few seconds. Frame by frame it crosses any threshold a
# dozen times, which chopped a confirmed sixteen-second bass cut into pieces of
# four. The knob is a hand, so it is measured on the timescale of a hand.
TILT_CUT = 0.7
TILT_SMOOTH_SEC = 3.0


def describe(bands, floors, t) -> dict:
    """Reduce three gain curves to the gestures a DJ has names for.

    Presence is judged against the noise floor, but *EQ* is judged by comparing a
    deck's bass to its own mid. Thresholding bass against the floor proved far too
    fragile: on the one seam checked by ear the incoming bass sat at 0.29-0.39
    against a floor of 0.30, so a measurement the DJ confirmed as sixteen seconds
    came out as six. A within-deck ratio does not care where the floor sits, and
    the deck-separation error largely cancels because it is the same record on
    both sides of the fraction.
    """
    t = np.asarray(t)
    step = float(np.median(np.diff(t))) if len(t) > 1 else 0.0
    out = {}

    def gain(band, deck):
        return np.asarray(bands[band]["a" if deck == "A" else "b"])

    b_on = gain("środek", "B") > floors["środek"]
    a_on = gain("środek", "A") > floors["środek"]
    if not b_on.any() or not a_on.any():
        return {"blend_sec": None, "reason": "jeden z decków nigdy nie przekroczył podłogi"}
    b_in = float(t[np.argmax(b_on)])
    a_out = float(t[len(a_on) - 1 - np.argmax(a_on[::-1])])
    out |= {"b_in_sec": b_in, "a_out_sec": a_out, "blend_sec": max(a_out - b_in, 0.0)}
    overlap = (t >= b_in) & (t <= a_out)
    if not overlap.any():
        return out

    def tilt_down(deck):
        """Where this deck's bass is pushed below its own mid — the EQ knob.

        Only frames where the deck's mid is above the floor count: with the record
        barely audible the ratio is a division of two noise values and says
        nothing about anybody's hand.
        """
        bass, mid = gain("bas", deck), gain("środek", deck)
        audible = mid > floors["środek"]
        ratio = np.where(audible, bass / np.maximum(mid, 1e-6), np.nan)
        w = max(3, int(round(TILT_SMOOTH_SEC / step)) | 1) if step else 3
        pad = np.pad(ratio, w // 2, mode="edge")
        smooth = np.array([np.nanmedian(pad[i:i + w]) if not np.isnan(pad[i:i + w]).all()
                           else np.nan for i in range(len(ratio))])
        return audible & (smooth < TILT_CUT)

    def runs(mask):
        """Contiguous stretches as (start_index, length), longest first."""
        idx = np.flatnonzero(np.diff(np.concatenate(([0], mask.view(np.int8), [0]))))
        return sorted(zip(idx[::2], idx[1::2] - idx[::2]), key=lambda r: -r[1])

    # A move is one continuous stretch with the knob down, so the longest run is
    # the measurement. Summing every frame below the line instead counts a knob
    # that wobbled all through the blend as if it had been held down once, which
    # on the seam checked by ear inflated sixteen seconds to twenty-two.
    held = runs(tilt_down("B") & overlap)
    out["b_bass_held_sec"] = float(held[0][1] * step) if held else 0.0
    if held:
        out["b_bass_held_at_sec"] = float(t[held[0][0]])

    # Thinning is the run that the outgoing record leaves on: found by walking
    # back from the exit to the last moment its bass was still up, so a single
    # flickering frame at the very end cannot erase the whole gesture.
    thin, up = tilt_down("A") & overlap, ~tilt_down("A") & overlap
    last = int(len(t) - 1 - np.argmax(overlap[::-1]))
    up_idx = np.flatnonzero(up[:last + 1])
    out["a_thinned_sec"] = float((last - up_idx[-1]) * step) if len(up_idx) else 0.0
    if not thin[max(last - 1, 0):last + 1].any():
        out["a_thinned_sec"] = 0.0        # it left with its bass in
    return out


def source_bass_check(y_b, lock_b, seam) -> dict:
    """Did the record have any bass to close in the first place?

    Without this the headline lies. Plenty of dance records open on drums and a
    voice with no low end at all, and a deck whose bass was never there measures
    exactly like a deck whose bass was pulled down — one is the DJ, the other is
    the pressing. Measured on this material the difference was not marginal: of
    eighteen holds, three were the record.

    The comparison is the *band* 30-300 Hz, not Demucs's bass stem. A mixer's low
    knob cuts a band, and what mostly lives in that band is the kick, which stem
    separation files under drums — checking the bass stem called a confirmed hand
    movement "no bass in the record".
    """
    held = seam.get("b_bass_held_sec") or 0.0
    if held < 4:
        return {}
    t0 = seam.get("b_bass_held_at_sec") or seam["b_in_sec"]
    low = np.where((S._CENTRES >= 30) & (S._CENTRES < 300))[0]
    mid = np.where((S._CENTRES >= 300) & (S._CENTRES < 3000))[0]

    def tilt(sig):
        E = S.sub_energy(sig)
        return E[low].sum() / max(E[mid].sum(), 1e-12)

    here = tilt(S.warp(y_b, lock_b["origin"], lock_b["rate"], t0, t0 + held))
    whole = tilt(y_b[: S.SR * 180])
    ratio = float(here / max(whole, 1e-12))
    return {"b_source_bass_ratio": ratio,
            "b_bass_hold_is_hand": bool(ratio >= 0.85),
            "b_bass_hold_verdict": ("ręka" if ratio >= 0.85 else
                                    "utwór sam nie ma tam basu" if ratio < 0.5
                                    else "niepewne")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cue")
    ap.add_argument("--out-dir", default="experiments_priv/seams")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    mix, entries = parse_cue(args.cue)
    out_dir = Path(args.out_dir) / Path(args.cue).stem.replace(" ", "_")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"{mix.name}: {len(entries)} wpisów, {len(entries)-1} szwów\n", flush=True)

    # Lock every record first: a seam needs both neighbours, and a record's own
    # solo stretch is the only place the search has a clean signal to lock onto.
    # Locking is by far the slowest step and depends only on the recording, so it
    # is cached: re-running to fix a measurement must not cost twenty minutes of
    # re-deriving facts that cannot have changed.
    cache = out_dir / "locks.json"
    if cache.exists():
        locks = json.loads(cache.read_text())
        print(f"  zamki z cache ({sum(x is not None for x in locks)}/{len(locks)})\n",
              flush=True)
    else:
        locks = []
        for i, e in enumerate(entries):
            nxt = entries[i + 1].marker_sec if i + 1 < len(entries) else None
            got = lock(str(mix), e.path, e.marker_sec, nxt)
            locks.append(got)
            state = (f"origin {got['origin']:8.2f}s rate {got['rate']:.4f} "
                     f"{got['anchors']} ±{got['spread_ms']:.0f}ms") if got else "BRAK ZAMKA"
            print(f"  [{i+1:2d}] {state}   {Path(e.path).name[:44]}", flush=True)
        cache.write_text(json.dumps(locks))

    seams, skipped = [], []
    pairs = list(range(len(entries) - 1))[: args.limit or None]
    for i in pairs:
        a, b = entries[i], entries[i + 1]
        la, lb = locks[i], locks[i + 1]
        if not la or not lb:
            skipped.append({"i": i + 1, "why": "brak zamka"})
            continue
        ya, yb = S.load_mono(a.path), S.load_mono(b.path)
        a_end = la["origin"] + (len(ya) / S.SR) / la["rate"]
        t0, t1 = lb["origin"] - 20, min(a_end + 15, lb["origin"] + 200)
        if t1 - t0 < 30:
            skipped.append({"i": i + 1, "why": "okno za krótkie"})
            continue

        Em = S.sub_energy(S.load_mono(str(mix), t0, t1))
        bands = S.fit_gains(Em,
                            S.sub_energy(S.warp(ya, la["origin"], la["rate"], t0, t1)),
                            S.sub_energy(S.warp(yb, lb["origin"], lb["rate"], t0, t1)))
        times = [t0 + x for x in bands["bas"]["t"]]

        # Noise floor per seam, not borrowed: these two records, this stretch.
        n0, n1 = max(t0 - 90, 0), max(t0 - 15, 1)
        floors = {}
        if n1 - n0 > 30:
            present = S.sub_energy(S.warp(ya, la["origin"], la["rate"], n0, n1))
            nf = S.noise_floor(str(mix), yb, present, n0, n1,
                               (n0 - 200, n0 - 40), lb["rate"], n_draws=6)
            floors = {k: v["median"] for k, v in nf.items()}
        if not floors:
            skipped.append({"i": i + 1, "why": "brak okna na test zerowy"})
            continue

        seam = {"i": i + 1,
                "from": f"{a.performer} — {a.title}", "to": f"{b.performer} — {b.title}",
                "window": [t0, t1], "floors": floors,
                **describe(bands, floors, times)}
        seam |= source_bass_check(yb, lb, seam)
        (out_dir / f"seam_{i+1:02d}.json").write_text(json.dumps(
            {**seam, "bands": {k: {**v, "t": times} for k, v in bands.items()},
             "deck_a": la | {"path": a.path}, "deck_b": lb | {"path": b.path}}))
        if seam.get("blend_sec") is None:
            # Both records are locked and the fit ran, but one of them never rose
            # above its own noise floor here — so there is no handover to time.
            skipped.append({"i": i + 1, "why": seam.get("reason", "brak nakładania")})
            print(f"  szew {i+1:2d}: bez nakładania nad podłogą   "
                  f"{a.title[:22]} → {b.title[:22]}", flush=True)
            continue
        seams.append(seam)
        print(f"  szew {i+1:2d}: blend {seam['blend_sec']:5.1f}s  "
              f"bas B wstrzymany {seam.get('b_bass_held_sec') or 0:5.1f}s  "
              f"A wychudzony {seam.get('a_thinned_sec') or 0:5.1f}s   "
              f"{a.title[:22]} → {b.title[:22]}", flush=True)

    (out_dir / "summary.json").write_text(json.dumps(
        {"mix": str(mix), "seams": seams, "skipped": skipped}, ensure_ascii=False))
    print(f"\n  zmierzone {len(seams)}, pominięte {len(skipped)}")
    for s in skipped:
        print(f"    szew {s['i']}: {s['why']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
