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

import librosa

import seam_decompose as S
from cue_parse import parse_cue
from grid_cache import grid_for

MAX_PITCH = 0.08          # what a pitch fader reaches before it stops being a mix
BLEND_BEATS = 128
SOLO_BEATS = 160
BASS_OPEN_AT = 0.97       # his median: the low end changes hands at the handover
LOW_HZ, HIGH_HZ = 200.0, 3000.0


def entry_point(y: np.ndarray, g: dict, bars: int = 4,
                need_sec: float = 0.0) -> float | None:
    """Where this record wants to be brought in: drums up, low end down.

    Measured on the DJ's own sets, 71 % of his entries land on a moment where the
    record leans on its drums and away from its bass relative to how it usually
    sounds, against 18 % of moments picked at random. Snapped to a phrase because
    nothing else would survive being mixed into.
    """
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
    # A record must have enough left after its entry to fill its whole slot. Without
    # this the warp simply returns zeros past the end of the file, which put 13.5
    # seconds of silence into the middle of a set.
    if need_sec:
        latest = span - need_sec
        # max() used to floor this at the first beat, which turned "this record is
        # too short for its slot" into "start at the beginning" — and the warp then
        # padded past the end of the file with exact digital silence. Measured: a
        # 2:30 record in a 3:03 slot contributed 36 s of nothing, 20 % of the slot.
        if latest < g["first"]:
            return None
    else:
        latest = min(span * 0.45, 150.0)
    best, best_score = g["first"], -1e9
    t = g["first"]
    while t + phrase < min(min(span * 0.45, 150.0), latest):
        lo, md = energy(low, t, t + phrase), energy(mid, t, t + phrase)
        # and it has to be playing there: the rule looks for drums up and bass down,
        # which a near-silent breakdown satisfies perfectly while sounding like a
        # hole. A third of the record's own average is the floor.
        if md > 0.33 * ref_mid:
            score = (md / (ref_mid + 1e-12)) - (lo / (ref_low + 1e-12))
            if score > best_score:
                best, best_score = t, score
        t += phrase
    return min(best, latest)


def load_stereo(path: str) -> np.ndarray:
    """Both channels, kept apart. Shape (2, n).

    Everything upstream analyses in mono, which is right — a beat grid and an entry
    point are properties of the music, not of its width. The render is not analysis.
    Folding to mono there cost the whole set its stereo image: channel correlation
    came out at exactly 1.000 against 0.935 in the DJ's own recording, with the side
    signal 240 dB down instead of 15. Nothing centred and nothing wide is precisely
    what he kept calling flat.
    """
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    y = data.T
    if y.shape[0] == 1:
        y = np.repeat(y, 2, axis=0)
    if sr != S.SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=S.SR, res_type="soxr_vhq")
    return y[:2].astype(np.float32)


def warp_stereo(y: np.ndarray, origin: float, rate: float, t0: float,
                t1: float) -> np.ndarray:
    return np.stack([S.warp(ch, origin, rate, t0, t1, hq=True) for ch in y])


def bands(y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lo = sosfiltfilt(butter(4, LOW_HZ / (S.SR / 2), btype="lowpass", output="sos"),
                     y, axis=-1)
    hi = sosfiltfilt(butter(4, HIGH_HZ / (S.SR / 2), btype="highpass", output="sos"),
                     y, axis=-1)
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
    ap.add_argument("cue", nargs="?", help="rekordbox .cue of a recorded set")
    ap.add_argument("--tracks", help="Text file of paths, one per line, in play order")
    ap.add_argument("--out", required=True)
    ap.add_argument("--blend-beats", type=int, default=BLEND_BEATS)
    ap.add_argument("--solo-beats", type=int, default=SOLO_BEATS)
    ap.add_argument("--no-eq", action="store_true",
                    help="Never touch the samples: one gain per deck, original audio, "
                         "no band split anywhere in the signal path")
    args = ap.parse_args()

    # Two ways in: replay a set the DJ recorded, or play an order the engine chose.
    # Everything downstream is identical, which is the point — the difference
    # between copying him and proposing is upstream of the mixing.
    if args.tracks:
        from types import SimpleNamespace

        order = []
        for line in Path(args.tracks).read_text().splitlines():
            if not line.strip():
                continue
            stem = Path(line).stem
            who, _, what = stem.partition(" - ")
            order.append(SimpleNamespace(path=line.strip(), performer=who,
                                         title=what or stem))
    elif args.cue:
        _, entries = parse_cue(args.cue)
        order, seen = [], set()
        for e in entries:
            if e.path not in seen:
                seen.add(e.path)
                order.append(e)
    else:
        ap.error("podaj plik .cue albo --tracks")

    grids = {e.path: grid_for(e.path) for e in order}
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

    # A record also has to last long enough for its slot, and that is decided here,
    # from the file's duration, rather than inside the render loop — the loop placed
    # each record at its index in the queue, so a record refused down there kept its
    # slot, and five refusals put five holes of seventy seconds into a set that
    # still reported its full length.
    #
    # "Long enough" is not the whole slot, though, and demanding it threw away five
    # good records over as little as nine seconds. A record's last blend plays under
    # the next one, so material missing from that tail is never heard: measured on
    # the previous render, five records running out early left one second of silence
    # in fifty minutes, all of it at the very end. So a record only has to reach the
    # point where its successor takes over. What it owes is its slot minus the blend
    # that covers it.
    beat = 60.0 / master
    want = (args.solo_beats + 2 * args.blend_beats) * beat
    covered = args.blend_beats * beat
    short: list = []
    long_enough = []
    for e, rate in keep:
        span = sf.info(e.path).duration
        owed = max(want - covered, 0.0) * rate
        (short.append((e, span, owed)) if span - owed < grids[e.path]["first"]
         else long_enough.append((e, rate)))
    keep = long_enough

    print(f"tempo setu: {master:.0f} BPM · gra {len(keep)} z {len(order)} utworów")
    for e, rate in dropped:
        why = ("brak sztywnej siatki" if rate is None
               else f"wymaga {abs(rate - 1) * 100:.1f}% suwaka")
        print(f"  POMIJAM {e.performer} — {e.title}: {why}")
    for e, have, need in short:
        print(f"  POMIJAM {e.performer} — {e.title}: {have / 60:.1f} min materiału, "
              f"slot potrzebuje {need / 60:.1f} min")

    # Layout, and the first version had it wrong in a way that mattered more than
    # anything it was being compared against. Records were spaced solo_beats apart
    # while each blend ran blend_beats, so with 160 and 128 the two overlapped for
    # four fifths of the set and nothing ever played alone for more than fourteen
    # seconds. A permanent crossfade is not a set.
    #
    # A record enters, blends with the one leaving for blend_beats, plays alone for
    # solo_beats, and is still on air through the next blend. So the spacing between
    # entries is blend + solo, and each record is on air for solo + two blends.
    blend_n = int(args.blend_beats * beat * S.SR)
    solo_n = int(args.solo_beats * beat * S.SR)
    step_n = blend_n + solo_n
    total = step_n * len(keep) + blend_n + S.SR * 4
    mix = np.zeros((2, total), dtype=np.float32)
    levels = []  # solo-section RMS per record; sets the final gain

    # Position comes from how many records have actually been placed, never from the
    # queue index. The duration check above should mean nothing is refused here, but
    # a refusal that silently moved every later record a slot down the timeline is
    # the kind of hole a listener notices and a summary line does not.
    placed = 0
    for e, rate in keep:
        g = grids[e.path]
        # One read of the file, not three. The grid fit, the entry search and the
        # render each used to open it separately; on a fifty-minute set that is
        # twenty-four records read three times over for no gain.
        source = load_stereo(e.path)
        cue = entry_point(source.mean(axis=0), g,
                          need_sec=max(want - covered, 0.0) * rate)
        if cue is None:
            print(f"  POMIJAM {e.performer} — {e.title}: nie ma gdzie wejść",
                  flush=True)
            continue
        y = warp_stereo(source, -cue / rate, rate, 0.0, want)
        n = y.shape[1]
        fade_in = blend_n if placed > 0 else 0
        fade_out = blend_n if placed < len(keep) - 1 else 0
        # A record starts leaving when the NEXT one arrives, which is one spacing
        # after it arrived itself — never "however long it has been playing". The
        # opening record has no fade-in, so measuring from its own entry sent it out
        # a whole blend early: it reached silence at 2:08 and the second record
        # started from zero at 2:08, a butt splice with a hole in front of it.
        fader, low_gain = envelopes(n, fade_in, step_n, fade_out)
        if args.no_eq:
            # The DJ's test: analysis may split the audio all it likes, but nothing
            # that reaches the speakers is ever rebuilt from the pieces. One gain on
            # the untouched file. The cost is musical, not technical — both records
            # keep their bass through the blend, which is the mud a bass swap exists
            # to prevent — and that is the point of hearing them side by side.
            voice = fader[None, :] * y
        else:
            lo, md, hi = bands(y)
            # The low band does not go through the line fader, exactly as it does
            # not on a mixer. With the fader in that path the one deck holding the
            # bass sits at 0.7 while the mids of two decks sum to unity, measured as
            # 3.4 dB of missing low end for the 44 % of a set inside a blend.
            voice = low_gain[None, :] * lo + fader[None, :] * (md + hi)
        at = placed * step_n
        mix[:, at:at + n] += voice
        levels.append(float(np.sqrt((y[:, fade_in:fade_in + solo_n] ** 2).mean())))
        print(f"  {placed + 1:2d}. {e.performer[:22]:22s} {e.title[:28]:28s} "
              f"{g['bpm']:5.1f} → {master:.0f} ({(rate - 1) * 100:+.1f}%)  "
              f"wejście {cue / 60:.0f}:{int(cue) % 60:02d}", flush=True)
        placed += 1

    # The buffer is allocated generously and the last record ends where it ends, so
    # trim the tail rather than shipping a set that fades into fourteen seconds of
    # nothing.
    loud = np.abs(mix).max(axis=0)
    live = np.flatnonzero(loud > 1e-4)
    if live.size:
        mix = mix[:, : min(int(live[-1]) + S.SR, mix.shape[1])]

    # One constant gain, and nothing else. Chasing the DJ's loudness with a soft
    # clip was the real fault behind every complaint about the sound: that curve
    # lifted quiet material 3.1 dB and loud material 0.5 dB, squashing 2.6 dB of
    # range across 14 % of the samples. He named it before it was measured — it is
    # a photograph pushed with ISO instead of exposed properly, bright and grainy
    # rather than clean. Loudness that has to be manufactured is not loudness.
    # And check the result rather than trusting the layout. A hole is the one fault
    # a summary line cannot show — a set with ten minutes of silence in it still
    # reports its full length, because length is measured to the last sample that
    # made a sound. Measured on the render, in one-second blocks.
    loud = np.abs(mix).max(axis=0)
    whole = (loud.size // S.SR) * S.SR
    quietblk = (loud[:whole].reshape(-1, S.SR).max(axis=1) < 1e-3 if whole
                else np.zeros(0, dtype=bool))
    run = gap = 0
    for q in quietblk:
        run = run + 1 if q else 0
        gap = max(gap, run)
    print(f"cisza: najdluzsza przerwa {gap} s"
          + ("" if gap <= 2 else "  <-- DZIURA W SECIE"))

    peak = float(np.abs(mix).max())
    mix *= 0.89 / max(peak, 1e-9)          # about -1 dBFS, no dynamics touched
    quiet = 20 * np.log10(float(np.sqrt((mix[mix != 0] ** 2).mean())) + 1e-12)
    print(f"\npoziom: szczyt -1.0 dBFS, rms {quiet:.1f} dB — bez kompresji "
          f"i bez limitera, wiec ciszej niz miks przepuszczony przez mikser")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, mix.T, S.SR, subtype="PCM_24")
    dur = mix.shape[1] / S.SR
    print(f"\nWrote {out} — {dur / 60:.1f} min, {master:.0f} BPM przez cały set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
