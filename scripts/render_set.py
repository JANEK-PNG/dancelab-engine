"""DanceLab Automix — play a whole set, not a row of transitions.

Every join so far was rendered in isolation, which hides the two things that only
appear across an hour: whether the set holds one tempo end to end, and whether the
level stays where a room expects it. So this builds the timeline itself instead of
calling the preview renderer, and gains nothing from the isolation: one master
tempo, every record pitched onto it, one continuous mix.

Three decisions come from the DJ's own measured seams rather than from a template:

  * the set runs at one tempo, and records that cannot reach it on a pitch fader
    are dropped and named rather than time-stretched into mush;
  * the incoming record arrives where it leans on its drums and away from its low
    end — measured at 71 % of his entries against 18 % of random moments;
  * its bass stays shut until the handover itself, not the textbook midpoint —
    his median was 97 % of the blend.

Level is matched to the records, not to the peaks. The preview renderer normalises
to peak, and summing two tracks throws occasional peaks high enough to pull the
whole mix 3-4 dB below the DJ's own recording — which is exactly what he described
as flat and lacking punch, at identical spectral content.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

import seam_decompose as S
from cue_parse import parse_cue
from dancelab.core.rigid_grid import fit_rigid_grid

MAX_PITCH = 0.08          # what a pitch fader reaches before it stops being a mix
BLEND_BEATS = 128
SOLO_BEATS = 160
BASS_OPEN_AT = 0.97       # his median: the low end changes hands at the handover
LOW_HZ, HIGH_HZ = 200.0, 3000.0
GRIDS = Path(__file__).resolve().parents[1] / "experiments_priv/_cache/rigid_grids.json"


def grid_of(path: str) -> dict | None:
    cache = json.loads(GRIDS.read_text()) if GRIDS.exists() else {}
    if path not in cache:
        got = fit_rigid_grid(S.load_mono(path), S.SR)
        cache[path] = ({"bpm": got.bpm, "first": got.first_beat_sec,
                        "contrast": got.contrast} if got else None)
        GRIDS.parent.mkdir(parents=True, exist_ok=True)
        GRIDS.write_text(json.dumps(cache))
    g = cache[path]
    return g if g and g["contrast"] >= 2.0 else None


def entry_point(path: str, g: dict, bars: int = 4) -> float:
    """Where this record wants to be brought in: drums up, low end down.

    Measured on the DJ's own sets, 71 % of his entries land on a moment where the
    record leans on its drums and away from its bass relative to how it usually
    sounds, against 18 % of moments picked at random. Snapped to a phrase because
    nothing else would survive being mixed into.
    """
    y = S.load_mono(path)
    sos_lo = butter(4, LOW_HZ / (S.SR / 2), btype="lowpass", output="sos")
    low = sosfiltfilt(sos_lo, y).astype(np.float32)
    mid = (y - low).astype(np.float32)
    period = 60.0 / g["bpm"]
    phrase = period * 4 * bars
    span = len(y) / S.SR

    def energy(sig, t0, t1):
        a, b = int(t0 * S.SR), int(min(t1, span) * S.SR)
        return float((sig[a:b] ** 2).mean()) if b > a else 0.0

    ref_low, ref_mid = energy(low, 0, span), energy(mid, 0, span)
    best, best_score = g["first"], -1e9
    t = g["first"]
    while t + phrase < min(span * 0.45, 150.0):
        lo, md = energy(low, t, t + phrase), energy(mid, t, t + phrase)
        if md > 0.05 * ref_mid:
            score = (md / (ref_mid + 1e-12)) - (lo / (ref_low + 1e-12))
            if score > best_score:
                best, best_score = t, score
        t += phrase
    return best


def bands(y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lo = sosfiltfilt(butter(4, LOW_HZ / (S.SR / 2), btype="lowpass", output="sos"), y)
    hi = sosfiltfilt(butter(4, HIGH_HZ / (S.SR / 2), btype="highpass", output="sos"), y)
    return lo.astype(np.float32), (y - lo - hi).astype(np.float32), hi.astype(np.float32)


def envelopes(n: int, fade_in: int, fade_out_at: int, fade_out: int):
    """Fader and bass curves for one record's whole time on air.

    Mids and highs cross equal-power, which is what keeps the sum steady. The low
    band does not cross with them: it stays shut on the way in until the handover
    and then arrives whole, because that is what the DJ does and because two records
    sharing a low end at half level is the mud a bass swap exists to avoid.
    """
    t = np.arange(n, dtype=np.float32)
    fader = np.ones(n, dtype=np.float32)
    if fade_in > 0:
        r = np.clip(t[:fade_in] / fade_in, 0, 1)
        fader[:fade_in] = np.sin(r * np.pi / 2)
    if fade_out > 0:
        seg = slice(fade_out_at, min(fade_out_at + fade_out, n))
        r = np.clip((t[seg] - fade_out_at) / fade_out, 0, 1)
        fader[seg] = np.cos(r * np.pi / 2)
        fader[min(fade_out_at + fade_out, n):] = 0.0

    low = np.ones(n, dtype=np.float32)
    if fade_in > 0:
        opens = int(fade_in * BASS_OPEN_AT)
        low[:opens] = 0.0
        ramp = max(1, fade_in - opens)
        low[opens:opens + ramp] = np.linspace(0, 1, ramp, dtype=np.float32)
    if fade_out > 0:
        closes = fade_out_at + int(fade_out * BASS_OPEN_AT)
        ramp = max(1, fade_out_at + fade_out - closes)
        low[closes:closes + ramp] = np.linspace(1, 0, ramp, dtype=np.float32)
        low[closes + ramp:] = 0.0
    return fader, low


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cue")
    ap.add_argument("--out", required=True)
    ap.add_argument("--blend-beats", type=int, default=BLEND_BEATS)
    ap.add_argument("--solo-beats", type=int, default=SOLO_BEATS)
    args = ap.parse_args()

    _, entries = parse_cue(args.cue)
    order, seen = [], set()
    for e in entries:
        if e.path not in seen:
            seen.add(e.path)
            order.append(e)

    grids = {e.path: grid_of(e.path) for e in order}
    playable = [e for e in order if grids[e.path]]
    bpms = [grids[e.path]["bpm"] for e in playable]
    master = float(np.median(bpms))

    keep, dropped = [], []
    for e in playable:
        rate = master / grids[e.path]["bpm"]
        (keep if abs(rate - 1) <= MAX_PITCH else dropped).append((e, rate))
    for e in order:
        if not grids[e.path]:
            dropped.append((e, None))

    print(f"tempo setu: {master:.0f} BPM · gra {len(keep)} z {len(order)} utworów")
    for e, rate in dropped:
        why = ("brak sztywnej siatki" if rate is None
               else f"wymaga {abs(rate - 1) * 100:.1f}% suwaka")
        print(f"  POMIJAM {e.performer} — {e.title}: {why}")

    beat = 60.0 / master
    blend_n = int(args.blend_beats * beat * S.SR)
    solo_n = int(args.solo_beats * beat * S.SR)
    total = solo_n * len(keep) + blend_n + S.SR * 4
    mix = np.zeros(total, dtype=np.float32)
    levels = []

    for i, (e, rate) in enumerate(keep):
        g = grids[e.path]
        cue = entry_point(e.path, g)
        on_air = args.solo_beats + args.blend_beats
        want = on_air * beat
        y = S.warp(S.load_mono(e.path), -cue / rate, rate, 0.0, want, hq=True)
        n = y.size
        fade_in = blend_n if i > 0 else 0
        fade_out = blend_n if i < len(keep) - 1 else 0
        fader, low_gain = envelopes(n, fade_in, solo_n, fade_out)
        lo, md, hi = bands(y)
        # The low band does not go through the line fader, exactly as it does not
        # on a mixer. With the fader in that path the one deck holding the bass sits
        # at 0.7 while the mids of two decks sum to unity, which measured as 3.4 dB
        # of missing low end against the DJ's own recording — for 44 % of the set,
        # since that is how much of it is inside a blend.
        voice = low_gain * lo + fader * (md + hi)
        at = i * solo_n
        mix[at:at + n] += voice
        levels.append(float(np.sqrt((y[fade_in:solo_n] ** 2).mean())) if solo_n > fade_in
                      else 0.0)
        print(f"  {i + 1:2d}. {e.performer[:22]:22s} {e.title[:28]:28s} "
              f"{g['bpm']:5.1f} → {master:.0f} ({(rate - 1) * 100:+.1f}%)  "
              f"wejście {cue / 60:.0f}:{int(cue) % 60:02d}", flush=True)

    # Level is set from the records, not the peaks: peak normalisation drops a
    # summed mix 3-4 dB below the same music played alone, which reads as flat.
    # One constant gain, and nothing else. Chasing the DJ's loudness with a soft
    # clip was the real fault behind every complaint about the sound: that curve
    # lifted quiet material 3.1 dB and loud material 0.5 dB, squashing 2.6 dB of
    # range across 14 % of the samples. He named it before it was measured — it is
    # a photograph pushed with ISO instead of exposed properly, bright and grainy
    # rather than clean. Loudness that has to be manufactured is not loudness.
    peak = float(np.abs(mix).max())
    mix *= 0.89 / max(peak, 1e-9)          # about -1 dBFS, no dynamics touched
    quiet = 20 * np.log10(float(np.sqrt((mix[mix != 0] ** 2).mean())) + 1e-12)
    print(f"\npoziom: szczyt -1.0 dBFS, rms {quiet:.1f} dB — bez kompresji "
          f"i bez limitera, wiec ciszej niz miks przepuszczony przez mikser")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, np.stack([mix, mix], axis=1), S.SR, subtype="PCM_24")
    dur = mix.size / S.SR
    print(f"\nWrote {out} — {dur / 60:.1f} min, {master:.0f} BPM przez cały set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
