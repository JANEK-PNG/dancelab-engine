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


def tempo_ladder(bpms: list[float],
                 max_pitch: float = MAX_PITCH) -> tuple[list[float], list[int]]:
    """The tempo each record enters at, and the one it hands over at.

    A DJ does not run an hour at one number. Each record is pitched onto the deck it
    is replacing — that is what beatmatching is — and then over its own solo it gets
    nudged back toward the tempo it was actually made at, until the next record has
    to be able to meet it there. So the set's tempo walks.

    Returns (keep, T): indices of the records that can follow one another, and for
    the k-th of those, `T[k]` is its entry tempo and `T[k+1]` the tempo it hands over
    at — so a record's whole trajectory lives between two numbers it can both reach.
    A record whose reachable band never touches the previous record's is left out:
    no shared tempo exists and no amount of fader would make one.

    The single-master renderer this replaces had no way to express any of that: it
    took one median and dragged everything onto it. On a set spanning 124 to 136 that
    meant five records pitched over four percent and one over eight, which is not a
    fader move, it is a different record.
    """
    keep: list[int] = []
    T: list[float] = []
    for i, b in enumerate(bpms):
        if not keep:
            keep.append(i)
            T.append(b)                       # the opener plays at its own tempo
            continue
        home = bpms[keep[-1]]                 # where the outgoing deck wants to be
        lo, hi = b * (1 - max_pitch), b * (1 + max_pitch)
        mine_lo, mine_hi = home * (1 - max_pitch), home * (1 + max_pitch)
        if hi < mine_lo or lo > mine_hi:      # the two bands never touch
            continue
        keep.append(i)
        # as close to the outgoing record's own tempo as the incoming one can reach
        T.append(min(max(min(max(home, lo), hi), mine_lo), mine_hi))
    if keep:
        T.append(bpms[keep[-1]])              # nothing follows the last one
    return keep, T


def tempo_schedule(t_in: float, t_out: float, blend_beats: int,
                   solo_beats: int) -> list[tuple[float, float, float]]:
    """One record's whole time on air, as (duration, tempo at start, tempo at end).

    The tempo only moves while the record is alone. During either blend it is pinned,
    because two decks sharing a blend share a tempo or they gallop — which is the
    whole point of the rigid grids. A phrase is counted in beats, so the solo's
    length in seconds follows from the ramp: beats = D * (t_in + t_out) / 120.
    """
    return [(blend_beats * 60.0 / t_in, t_in, t_in),
            (120.0 * solo_beats / (t_in + t_out), t_in, t_out),
            (blend_beats * 60.0 / t_out, t_out, t_out)]


# Measured on pure tones resampled at 1.0222, worst case 15 kHz: linear
# interpolation leaves rubbish 11 dB below the tone, 32 taps at 1024 fractional steps
# 64 dB below, and this 100 dB below. soxr_vhq reaches 120 dB but has no variable-rate
# mode, which is why this exists at all. The binding constraint was the fractional
# resolution, not the filter: at 1024 steps the offset is quantised to half a
# thousandth of a sample, which is 60 dB of phase error at 15 kHz on its own.
TAPS, SUBSTEPS = 64, 65536
_TABLES: dict[float, np.ndarray] = {}


def _kernel_table(cutoff: float, taps: int = TAPS, beta: float = 12.0,
                  substeps: int = SUBSTEPS) -> np.ndarray:
    """Kaiser-windowed sinc, precomputed for every fractional sample offset.

    Reading a record at a moving speed means asking for source positions that fall
    between samples, and the answer has to be band-limited or it is the same linear
    interpolation that cost 4 dB at 18 kHz. `cutoff` below 1 lowers the passband when
    the record is being sped up, which is where a plain interpolator aliases.
    """
    key = round(cutoff, 6)
    if key not in _TABLES:
        half = taps // 2
        m = np.arange(-half + 1, half + 1)[None, :]
        f = (np.arange(substeps + 1) / substeps)[:, None]
        x = m - f
        w = np.i0(beta * np.sqrt(np.maximum(0.0, 1.0 - (x / half) ** 2))) / np.i0(beta)
        k = np.sinc(x * key) * w
        _TABLES[key] = (k / k.sum(axis=1, keepdims=True)).astype(np.float32)
    return _TABLES[key]


def read_at(x: np.ndarray, pos: np.ndarray, cutoff: float) -> np.ndarray:
    """The record sampled at arbitrary fractional positions `pos`, band-limited."""
    table = _kernel_table(cutoff)
    i = np.floor(pos).astype(np.int64)
    kf = np.rint((pos - i) * SUBSTEPS).astype(np.int64)
    over = kf == SUBSTEPS
    i[over] += 1
    kf[over] = 0
    out = np.zeros(pos.size, dtype=np.float32)
    half = TAPS // 2
    for j, m in enumerate(range(-half + 1, half + 1)):
        out += table[kf, j] * x[np.clip(i + m, 0, x.size - 1)]
    return out


def source_positions(schedule, bpm: float, cue: float) -> np.ndarray:
    """Where in the record each output sample comes from, as the tempo moves.

    The playback rate is tempo/bpm, so the position is its running integral. A linear
    tempo ramp integrates in closed form, which keeps this exact rather than a sum of
    small steps that would drift.
    """
    out, src = [], cue * S.SR
    for dur, ta, tb in schedule:
        n = int(round(dur * S.SR))
        if n <= 0:
            continue
        t = np.arange(n, dtype=np.float64) / S.SR
        # tempo T(t) = ta + (tb-ta)*t/dur ; position = src + ∫ T/bpm dt
        adv = (ta * t + (tb - ta) * t * t / (2.0 * dur)) / bpm * S.SR
        out.append(src + adv)
        src += (ta + tb) / 2.0 * dur / bpm * S.SR
    return np.concatenate(out) if out else np.zeros(0)


def warp_ladder(y: np.ndarray, bpm: float, cue: float, schedule) -> np.ndarray:
    """Render one record whose tempo moves — one continuous read, no seams.

    An earlier version resampled the trajectory in two-second spans and stitched
    them. It was transparent between the joins and wrong at every one of them:
    measured against a single-span render of the same constant tempo, the difference
    was exactly zero everywhere except at the seams, where it peaked at 0.39 against
    a signal peak of 0.95 — sub-sample misalignment landing on a kick. soxr 1.1 has
    no variable-rate mode, so rather than hide seams behind crossfades there are
    none: the source position of every output sample is computed in closed form and
    the record is read there directly.
    """
    pos = source_positions(schedule, bpm, cue)
    fastest = max(max(a, b) for _, a, b in schedule) / bpm
    cutoff = min(1.0, 1.0 / fastest)          # anti-alias only when speeding up
    return np.stack([read_at(ch, pos, cutoff) for ch in y])


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
    dropped = [(e, "brak sztywnej siatki") for e in order if not grids[e.path]]

    # The set walks its tempo instead of running on one number. See `tempo_ladder`:
    # the single master this replaces took a median and dragged every record onto it,
    # which on a set spanning 124 to 136 pitched five records over four percent and
    # one over eight.
    idx, T = tempo_ladder([grids[e.path]["bpm"] for e in playable])
    for j, e in enumerate(playable):
        if j not in idx:
            dropped.append((e, f"{grids[e.path]['bpm']:.0f} BPM — nie ma tempa, "
                               f"które osiągnęłyby oba sąsiednie utwory"))
    keep = [(playable[j], T[k], T[k + 1]) for k, j in enumerate(idx)]

    # A record also has to last long enough, and that is decided here, from the
    # file's duration, rather than inside the render loop — the loop placed each
    # record at its index in the queue, so a record refused down there kept its slot,
    # and five refusals put five holes of seventy seconds into a set that still
    # reported its full length.
    #
    # "Long enough" is not the whole slot: a record's last blend plays under the next
    # one, so material missing from that tail is never heard. Measured on an earlier
    # render, five records running out early left one second of silence in fifty
    # minutes, all of it at the very end. What a record owes is its time on air minus
    # the blend that covers it — both now counted in ITS OWN seconds, because with a
    # moving tempo the mix's seconds and the record's are no longer the same thing.
    short: list = []
    long_enough = []
    for e, t_in, t_out in keep:
        bpm = grids[e.path]["bpm"]
        sched = tempo_schedule(t_in, t_out, args.blend_beats, args.solo_beats)
        owed = sum(d * (a + b) / 2.0 for d, a, b in sched[:2]) / bpm
        span = sf.info(e.path).duration
        (short.append((e, span, owed)) if span - owed < grids[e.path]["first"]
         else long_enough.append((e, t_in, t_out)))
    keep = long_enough

    lo_t, hi_t = (min(t for _, t, _ in keep), max(t for _, _, t in keep)) if keep \
        else (0.0, 0.0)
    print(f"tempo setu: {lo_t:.2f}–{hi_t:.2f} BPM (drabinka) · "
          f"gra {len(keep)} z {len(order)} utworów")
    for e, why in dropped:
        print(f"  POMIJAM {e.performer} — {e.title}: {why}")
    for e, have, need in short:
        print(f"  POMIJAM {e.performer} — {e.title}: {have / 60:.1f} min materiału, "
              f"potrzeba {need / 60:.1f} min")

    # Layout, and the first version had it wrong in a way that mattered more than
    # anything it was being compared against. Records were spaced solo_beats apart
    # while each blend ran blend_beats, so with 160 and 128 the two overlapped for
    # four fifths of the set and nothing ever played alone for more than fourteen
    # seconds. A permanent crossfade is not a set.
    #
    # A record enters, blends with the one leaving for blend_beats, plays alone for
    # solo_beats, and is still on air through the next blend. So the spacing between
    # entries is blend + solo, and each record is on air for solo + two blends.
    # Spacing is no longer one number times an index. Each blend lasts blend_beats at
    # the tempo THAT handover happens at, and each solo lasts solo_beats spread over
    # a ramp, so every span has its own length in seconds and positions have to be
    # accumulated. A uniform grid cannot describe a set that changes tempo.
    schedules = [tempo_schedule(t_in, t_out, args.blend_beats, args.solo_beats)
                 for _, t_in, t_out in keep]
    starts, at = [], 0.0
    for s in schedules:
        starts.append(at)
        at += s[0][0] + s[1][0]              # next record arrives after blend + solo
    total = int((at + schedules[-1][2][0] + 4.0) * S.SR) if schedules else S.SR
    mix = np.zeros((2, total), dtype=np.float32)
    levels = []  # solo-section RMS per record; sets the final gain

    # Position comes from how many records have actually been placed, never from the
    # queue index. The duration check above should mean nothing is refused here, but
    # a refusal that silently moved every later record a slot down the timeline is
    # the kind of hole a listener notices and a summary line does not.
    placed = 0
    for k, (e, t_in, t_out) in enumerate(keep):
        g = grids[e.path]
        sched = schedules[k]
        blend_in_d, solo_d, blend_out_d = (d for d, _, _ in sched)
        # One read of the file, not three. The grid fit, the entry search and the
        # render each used to open it separately; on a fifty-minute set that is
        # twenty-four records read three times over for no gain.
        source = load_stereo(e.path)
        owed = sum(d * (a + b) / 2.0 for d, a, b in sched[:2]) / g["bpm"]
        cue = entry_point(source.mean(axis=0), g, need_sec=owed)
        if cue is None:
            print(f"  POMIJAM {e.performer} — {e.title}: nie ma gdzie wejść",
                  flush=True)
            continue
        y = warp_ladder(source, g["bpm"], cue, sched)
        n = y.shape[1]
        blend_n = int(blend_in_d * S.SR)
        solo_n = int(solo_d * S.SR)
        step_n = blend_n + solo_n
        fade_in = blend_n if placed > 0 else 0
        fade_out = int(blend_out_d * S.SR) if k < len(keep) - 1 else 0
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
        at = int(starts[k] * S.SR)
        n = min(n, total - at)
        mix[:, at:at + n] += voice[:, :n]
        levels.append(float(np.sqrt((y[:, fade_in:fade_in + solo_n] ** 2).mean())))
        drift = "" if abs(t_out - t_in) < 0.05 else f" → {t_out:.1f}"
        print(f"  {placed + 1:2d}. {e.performer[:20]:20s} {e.title[:26]:26s} "
              f"{g['bpm']:5.1f} → {t_in:.1f}{drift:>7s} "
              f"({(t_in / g['bpm'] - 1) * 100:+5.1f}%)  "
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
    print(f"\nWrote {out} — {dur / 60:.1f} min, drabinka tempa "
          f"{lo_t:.2f}–{hi_t:.2f} BPM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
