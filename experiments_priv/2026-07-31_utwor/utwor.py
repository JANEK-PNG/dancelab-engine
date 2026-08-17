"""Utwór rysowany z liczb — Sigur Rós × Bon Iver × left-field house.

Nie ma tu ani jednej próbki. Każdy dźwięk powstaje z sinusów, szumu i filtrów,
bo o to Janek poprosił: „nie masz silnika do robienia muzyki, ale wiesz, jak
muzyka wygląda — więc ją narysuj".

Trzy rzeczy, które trzymają to razem, wzięte z tego, co ci dwaj naprawdę robią:

  1. GŁOS JAKO TEKSTURA, NIE LEAD. Jónsi śpiewa w zmyślonym języku, Vernon
     przepuszcza swój głos przez sprzęt, który go rozstraja — u obu głos niesie
     harmonię i nie niesie treści. Tutaj robi to filtr formantowy: trzy rezonanse
     przesuwające się między samogłoskami na stosie rozstrojonych pił. Ucho czyta
     to jako głos, mimo że nikt nie śpiewał.

  2. HARMONIA WOLNA, ROZWIĄZANIA PÓŹNE. Jeden akord na cztery takty, a zawieszenie
     schodzi dopiero w ostatnim. To jest sedno Sigur Rós — akord stoi o takt
     dłużej, niż się spodziewasz.

  3. ZNIEKSZTAŁCENIE JAKO KOMPOZYCJA. Bitcrush i clipping u Bon Ivera nie są
     wykończeniem, tylko powodem, dla którego dźwięk tam jest. Warstwa zgnieciona
     leży POD czystą przez cały czas i wychodzi na wierzch w kulminacji.

Czwarta rzecz jest Janka i zmierzona na jego setach: wchodzi w utwory tam, gdzie
opierają się na perkusji i schodzą z basu — 71 % jego wejść przeciw 18 % losowych
momentów. Więc ten kawałek ma czterdziestosekundowe wejście na samej perkusji,
bez dołu. Jest zbudowany pod jego własną rękę.
"""

from __future__ import annotations

import numpy as np
import soundfile as sf
from scipy.signal import butter, lfilter, sosfilt

SR = 44100
BPM = 122.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT

rng = np.random.default_rng(11)


def t_of(n: int) -> np.ndarray:
    return np.arange(n) / SR


def adsr(n: int, a: float, d: float, s: float, r: float) -> np.ndarray:
    """Obwiednia. Ataki są tu długie — nic nie zaczyna się nagle poza perkusją."""
    A, D, R = int(a * SR), int(d * SR), int(r * SR)
    S = max(0, n - A - D - R)
    return np.concatenate([
        np.linspace(0, 1, A, endpoint=False) ** 2,
        np.linspace(1, s, D, endpoint=False),
        np.full(S, s),
        np.linspace(s, 0, n - A - D - S) ** 2,
    ])[:n]


def formant(x: np.ndarray, vowels: list[tuple[float, float, float]],
            morph: np.ndarray) -> np.ndarray:
    """Filtr formantowy — to on zamienia stos pił w coś, co ucho czyta jako głos.

    Trzy rezonanse na częstotliwościach samogłoski. `morph` w [0,1] przechodzi
    między pierwszą a drugą samogłoską, więc barwa oddycha zamiast stać.
    """
    out = np.zeros_like(x)
    for k in range(3):
        f = vowels[0][k] + (vowels[1][k] - vowels[0][k]) * morph
        # pasmo liczone kawałkami, bo środkowa częstotliwość się rusza
        step = 2048
        y = np.zeros_like(x)
        for i in range(0, len(x), step):
            j = min(i + step, len(x))
            fc = float(np.clip(f[i:j].mean(), 120, 4200))
            bw = fc * 0.16
            sos = butter(2, [max(60, fc - bw) / (SR / 2),
                             min(SR / 2 - 200, fc + bw) / (SR / 2)],
                         btype="bandpass", output="sos")
            y[i:j] = sosfilt(sos, x[i:j])
        out += y * (1.0, 0.65, 0.35)[k]
    return out


def voice_pad(freqs: list[float], n: int, detune: float = 0.006) -> np.ndarray:
    """Stos rozstrojonych pił przepuszczony przez samogłoski.

    Rozstrojenie i wolny dryf wysokości robią „chór", którego nie da się policzyć
    na głosy — dokładnie tak brzmi warstwa wokalna u obu tych artystów.
    """
    t = t_of(n)
    x = np.zeros(n)
    for f in freqs:
        for k in range(5):
            det = 1.0 + detune * (k - 2) / 2
            # dryf: powolny błądzący offset, nie vibrato — vibrato brzmi jak syntezator
            drift = np.cumsum(rng.normal(0, 0.00006, n))
            drift -= drift.mean()
            ph = 2 * np.pi * np.cumsum(np.full(n, f * det) * (1 + drift)) / SR
            # piła przez sumę harmonicznych — miękka, bez aliasu
            for h in range(1, 9):
                x += np.sin(h * ph) / (h * 1.6)
    x /= np.abs(x).max() + 1e-9
    ah = (700.0, 1220.0, 2600.0)
    oo = (330.0, 900.0, 2300.0)
    morph = 0.5 + 0.5 * np.sin(2 * np.pi * t / 19.0)
    return formant(x, [ah, oo], morph) * 0.9


def bowed(freqs: list[float], n: int) -> np.ndarray:
    """Smyczek na gitarze — wysokie składowe, wolne narastanie, szum włosia."""
    t = t_of(n)
    x = np.zeros(n)
    for f in freqs:
        for h in (1, 2, 3, 5, 8):
            amp = 1.0 / (h ** 1.3)
            wob = 1 + 0.0015 * np.sin(2 * np.pi * (0.7 + 0.11 * h) * t)
            x += amp * np.sin(2 * np.pi * f * h * t * wob)
    hair = rng.normal(0, 1, n)
    sos = butter(2, [2200 / (SR / 2), 7000 / (SR / 2)], btype="bandpass", output="sos")
    x += sosfilt(sos, hair) * 0.06
    return x / (np.abs(x).max() + 1e-9)


def reverb(x: np.ndarray, sec: float = 5.0, mix: float = 0.55) -> np.ndarray:
    """Splot z rozpadającym się szumem. Długi ogon, ale rzadko coś w nim gra."""
    n = int(sec * SR)
    ir = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 7, n))
    sos = butter(2, 5200 / (SR / 2), btype="lowpass", output="sos")
    ir = sosfilt(sos, ir)
    ir[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    wet = np.convolve(x, ir)[: len(x)]
    wet /= np.abs(wet).max() + 1e-9
    return (1 - mix) * x + mix * wet


def kick(n: int) -> np.ndarray:
    t = t_of(n)
    f = 45 + 95 * np.exp(-t / 0.018)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.19)
    click = rng.normal(0, 1, n) * np.exp(-t / 0.0016)
    return body + click * 0.28


def hat(n: int, open_: bool = False) -> np.ndarray:
    t = t_of(n)
    x = rng.normal(0, 1, n) * np.exp(-t / (0.09 if open_ else 0.014))
    sos = butter(4, 7000 / (SR / 2), btype="highpass", output="sos")
    return sosfilt(sos, x)


def clap(n: int) -> np.ndarray:
    t = t_of(n)
    x = np.zeros(n)
    for d in (0.0, 0.011, 0.021):      # trzy klaśnięcia, nie jedno
        i = int(d * SR)
        x[i:] += rng.normal(0, 1, n - i) * np.exp(-t[: n - i] / 0.013)
    x += rng.normal(0, 1, n) * np.exp(-t / 0.11) * 0.25
    sos = butter(2, [1100 / (SR / 2), 5200 / (SR / 2)], btype="bandpass", output="sos")
    return sosfilt(sos, x)


def crush(x: np.ndarray, bits: int = 6, hold: int = 5) -> np.ndarray:
    """Bitcrush plus obniżenie próbkowania — u Bon Ivera to jest instrument."""
    q = 2 ** (bits - 1)
    y = np.round(x * q) / q
    keep = y[::hold]
    return np.repeat(keep, hold)[: len(x)]


def place(dst: np.ndarray, src: np.ndarray, at: float, gain: float = 1.0) -> None:
    i = int(at * SR)
    j = min(i + len(src), len(dst))
    if j > i:
        dst[i:j] += src[: j - i] * gain


# ── harmonia ────────────────────────────────────────────────────────
# a-moll z zawieszeniami. Ostatni akord rozwiązuje się dopiero w czwartym takcie
# swojego czterotaktu — to jest ten późny oddech.
def hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


CHORDS = [
    [45, 57, 60, 64, 67],          # Am7
    [41, 53, 57, 60, 64],          # Fmaj7
    [48, 55, 60, 64, 62],          # Cadd9
    [43, 55, 60, 62, 65],          # Gsus4  (rozwiąże się niżej)
]
RESOLVE = [43, 55, 59, 62, 67]     # G


def main() -> int:
    cycle = 4 * 4 * BAR            # cztery akordy po cztery takty ≈ 31,5 s
    # Osiem obrotów, żeby zdążyło się wydarzyć wszystko, co jest w układzie:
    # wejście na perkusji, wejście stopy, wejście basu, cisza i ściana po niej.
    total = int(np.ceil(cycle * 8)) + 26
    n = int(total * SR)
    L = np.zeros(n)
    R = np.zeros(n)

    # ── warstwa harmoniczna ──
    seg = int(4 * BAR * SR)
    pos = 0.0
    k = 0
    while pos + 4 * BAR < total - 8:
        ch = CHORDS[k % 4]
        # późne rozwiązanie: ostatni takt czwartego akordu schodzi na G
        env = adsr(seg, 2.4, 1.2, 0.85, 2.6)
        pad = voice_pad([hz(m) for m in ch], seg) * env
        bow = bowed([hz(m + 12) for m in ch[1:4]], seg) * adsr(seg, 3.4, 1.0, 0.7, 3.0)

        if k % 4 == 3:
            tail = int(BAR * SR)
            res = voice_pad([hz(m) for m in RESOLVE], tail) * adsr(tail, 0.9, 0.5, 0.8, 1.2)
            pad[-tail:] = pad[-tail:] * np.linspace(1, 0.15, tail) + res * 0.85

        # zgnieciona kopia leży pod czystą przez cały czas
        low = 0.20 + 0.55 * min(1.0, pos / (total * 0.62))
        voice = pad + crush(pad, bits=6, hold=6) * low * 0.42

        wide = reverb(voice, 5.4, 0.5)
        place(L, wide, pos, 0.30)
        place(R, np.roll(wide, 380), pos, 0.30)      # rozjazd = szerokość
        place(L, reverb(bow, 6.0, 0.62), pos, 0.16)
        place(R, reverb(bow, 6.0, 0.62), pos, 0.14)
        pos += 4 * BAR
        k += 1

    # ── perkusja ──
    # Wejście na samej perkusji przez pierwsze 40 s, bez dołu — reguła Janka.
    DRUMS_IN, KICK_IN, BASS_IN = 6.0, 40.0, 78.0
    BREAK_A, BREAK_B = 168.0, 196.0                  # cisza przed ścianą
    beat = 0
    tt = 0.0
    while tt < total - 6:
        bar_i = int(tt / BAR)
        inbreak = BREAK_A <= tt < BREAK_B
        if tt >= KICK_IN and not inbreak:
            place(L, kick(int(0.30 * SR)), tt, 0.52)
            place(R, kick(int(0.30 * SR)), tt, 0.52)
        if tt >= DRUMS_IN:
            h = hat(int(0.10 * SR), open_=(beat % 4 == 2))
            place(L, h, tt + BEAT / 2, 0.10 if inbreak else 0.20)
            place(R, np.roll(h, 90), tt + BEAT / 2, 0.09 if inbreak else 0.18)
        if tt >= DRUMS_IN + 8 * BAR and beat % 4 == 2 and not inbreak:
            c = reverb(clap(int(0.35 * SR)), 2.6, 0.42)
            place(L, c, tt, 0.16)
            place(R, np.roll(c, 220), tt, 0.16)
        # bas — sinus pod stopą, wchodzi późno i zostaje rzadki
        if tt >= BASS_IN and not inbreak and beat % 2 == 0:
            ch = CHORDS[(bar_i // 4) % 4]
            m = int(0.55 * SR)
            b = np.sin(2 * np.pi * hz(ch[0] - 12) * t_of(m)) * adsr(m, 0.01, 0.1, 0.5, 0.4)
            place(L, b, tt, 0.34)
            place(R, b, tt, 0.34)
        tt += BEAT
        beat += 1

    # ── poziom: jedna stała, bez kompresji, tak jak w automiksie ──
    mix = np.stack([L, R])
    # miękkie wejście i wyjście całości
    fi, fo = int(3.5 * SR), int(7.0 * SR)
    mix[:, :fi] *= np.linspace(0, 1, fi) ** 1.5
    mix[:, -fo:] *= np.linspace(1, 0, fo) ** 1.5
    mix *= 0.89 / (np.abs(mix).max() + 1e-9)

    out = "experiments_priv/2026-07-31_utwor/utwor.wav"
    sf.write(out, mix.T, SR, subtype="PCM_24")
    print(f"{out} — {mix.shape[1] / SR / 60:.1f} min, {BPM:.0f} BPM")
    print(f"korelacja kanałów {np.corrcoef(mix[0], mix[1])[0, 1]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
