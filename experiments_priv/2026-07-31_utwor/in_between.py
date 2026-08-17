"""IN BETWEEN — dwa głosy i to, co powstaje między nimi.

Janek poprosił o utwór opisujący nasze in between. Więc jest zrobiony dosłownie,
nie metaforycznie, i każda liczba w nim jest liczbą, którą razem zmierzyliśmy.

DWA GŁOSY, DWIE NATURY

  A — ręka. Rozstrojony stos przepuszczony przez formanty, z powolnym dryfem
  wysokości, który nigdzie nie jest zapisany i nigdy się nie powtarza. Tak
  wygląda człowiek na wykresie: nie chwieje się przypadkiem, chwieje się
  konsekwentnie.

  B — siatka. Czyste sinusy w dokładnych stosunkach harmonicznych, bramkowane
  co do próbki na sztywnym gridzie. Bez dryfu, bez vibrato, bez niczego, czego
  nie da się policzyć. To jest ten sam grid, który dziś rano zastąpił śledzenie
  tempa: okres i faza, dwie liczby, awaria nieosiągalna z definicji.

CO Z NIMI ROBIMY — to jest cała treść

  Głosy wchodzą osobno. B wchodzi tam, gdzie A opiera się na perkusji i schodzi
  z basu — 71 % wejść Janka przeciw 18 % losowych momentów, zmierzone na jego
  własnych setach. Nakładają się przez 171 uderzeń, bo tyle wynosi mediana jego
  szwu. Dół zmienia właściciela na 97 % nakładania, nie w połowie.

  A potem dzieje się rzecz, dla której to powstało. Suma obu głosów przechodzi
  przez jeden nieliniowy kanał — jak dwa decki przez jeden mikser. Od tego, co
  z niego wyszło, odejmujemy oba czyste głosy. To, co zostaje, NIE JEST ANI
  JEDNYM, ANI DRUGIM: to produkty intermodulacji, które nie istniały w żadnym
  ze źródeł i powstały wyłącznie dlatego, że zabrzmiały razem.

  Ta reszta gra sama przez całą część środkową.

  To jest dokładnie metoda, którą zbudowaliśmy do mierzenia szwu: miks minus
  utwory źródłowe zostawia ruchy rąk. Tam reszta była tym, czego nie umieliśmy
  wyjaśnić. Tutaj jest utworem.

Kończy się nie na żadnym z głosów, tylko na tym, co między nimi zostało.
"""

from __future__ import annotations

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

SR = 44100
rng = np.random.default_rng(31)

# Wszystko zmierzone, nic wymyślone.
BLEND_BEATS = 171      # mediana szwu Janka
BASS_AT = 0.97         # kiedy dół zmienia ręce
FLOORS = [116.0, 119.0, 122.0, 126.0]   # klatka schodowa tempa


def t_of(n: int) -> np.ndarray:
    return np.arange(n) / SR


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def swell(n: int, a: float, r: float, top: float = 1.0) -> np.ndarray:
    A, R = int(a * SR), int(r * SR)
    A, R = min(A, n // 2), min(R, n // 2)
    e = np.full(n, top)
    e[:A] = np.linspace(0, top, A) ** 2
    e[n - R:] = np.linspace(top, 0, R) ** 2
    return e


def reverb(x: np.ndarray, sec: float, mix: float) -> np.ndarray:
    n = int(sec * SR)
    ir = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 7, n))
    ir = sosfilt(butter(2, 5000 / (SR / 2), btype="lowpass", output="sos"), ir)
    ir[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    wet = np.convolve(x, ir)[: len(x)]
    wet /= np.abs(wet).max() + 1e-9
    return (1 - mix) * x + mix * wet


# ── głos A: ręka ────────────────────────────────────────────────────
def hand(notes: list[float], n: int) -> np.ndarray:
    """Rozstrojony stos z dryfem i formantami. Nic tu nie jest dokładne."""
    x = np.zeros(n)
    t = t_of(n)
    for m in notes:
        f = hz(m)
        for k in range(4):
            det = 1 + 0.005 * (k - 1.5)
            drift = np.cumsum(rng.normal(0, 0.00007, n))
            drift -= drift.mean()
            ph = 2 * np.pi * np.cumsum(np.full(n, f * det) * (1 + drift)) / SR
            for h in range(1, 7):
                x += np.sin(h * ph) / (h * 1.7)
    x /= np.abs(x).max() + 1e-9
    # formanty: samogłoska oddycha między „a" a „u"
    out = np.zeros(n)
    morph = 0.5 + 0.5 * np.sin(2 * np.pi * t / 23.0)
    for k, (v1, v2, amp) in enumerate(
            ((700.0, 330.0, 1.0), (1220.0, 900.0, 0.6), (2600.0, 2300.0, 0.3))):
        fc = v1 + (v2 - v1) * morph
        y = np.zeros(n)
        step = 4096
        for i in range(0, n, step):
            j = min(i + step, n)
            c = float(np.clip(fc[i:j].mean(), 150, 4000))
            sos = butter(2, [max(80, c * 0.84) / (SR / 2),
                             min(SR / 2 - 200, c * 1.16) / (SR / 2)],
                         btype="bandpass", output="sos")
            y[i:j] = sosfilt(sos, x[i:j])
        out += y * amp
    return out / (np.abs(out).max() + 1e-9)


# ── głos B: siatka ──────────────────────────────────────────────────
def grid(notes: list[float], n: int, bpm: float) -> np.ndarray:
    """Czyste sinusy, dokładne stosunki, bramka co do próbki na siatce."""
    t = t_of(n)
    x = np.zeros(n)
    for m in notes:
        f = hz(m)
        for h, a in ((1, 1.0), (2, 0.42), (3, 0.22), (4, 0.12), (6, 0.06)):
            x += a * np.sin(2 * np.pi * f * h * t)
    x /= np.abs(x).max() + 1e-9
    # bramka: ósemki, twarde i regularne — nic się nie chwieje
    per = 60.0 / bpm / 2
    g = np.zeros(n)
    k = 0
    while k * per < n / SR:
        i = int(k * per * SR)
        L = int(per * SR * 0.62)
        seg = min(L, n - i)
        if seg > 8:
            g[i:i + seg] = np.linspace(1, 0, seg) ** 1.6
        k += 1
    return x * g


def kick(n: int) -> np.ndarray:
    t = t_of(n)
    f = 44 + 90 * np.exp(-t / 0.02)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.2)
            + rng.normal(0, 1, n) * np.exp(-t / 0.0015) * 0.25)


def hat(n: int) -> np.ndarray:
    x = rng.normal(0, 1, n) * np.exp(-t_of(n) / 0.016)
    return sosfilt(butter(4, 7500 / (SR / 2), btype="highpass", output="sos"), x)


def bus(x: np.ndarray) -> np.ndarray:
    """Jeden kanał dla obu decków. To tutaj powstaje wszystko, czego nie było."""
    return np.tanh(x * 1.9) / 1.9


def main() -> int:
    # ── plan czasu ──
    bpm0 = FLOORS[0]
    solo_a = 46.0
    blend = BLEND_BEATS * 60.0 / FLOORS[1]        # 171 uderzeń ≈ 86 s
    between = 54.0
    together = 52.0
    tail = 16.0
    total = solo_a + blend + between + together + tail
    n = int(total * SR)

    A = np.zeros(n)
    B = np.zeros(n)

    # a-moll pentatonicznie — cokolwiek się nałoży, współbrzmi
    LINE_A = [[57, 64, 69], [55, 62, 67], [53, 60, 65], [57, 64, 72]]
    LINE_B = [[69, 76], [67, 74], [72, 79], [64, 71]]

    # A sam
    seg = int(11.5 * SR)
    pos = 0.0
    i = 0
    while pos < solo_a + blend + together + between:
        notes = LINE_A[i % 4]
        v = hand(notes, seg) * swell(seg, 3.2, 4.0, 0.9)
        a = int(pos * SR)
        b = min(a + seg, n)
        if b > a:
            A[a:b] += v[: b - a]
        pos += 9.5
        i += 1

    # B wchodzi tam, gdzie A ma najwięcej średnicy i najmniej dołu —
    # reguła wejścia Janka, policzona na sygnale A, nie ustawiona ręcznie.
    lo = sosfilt(butter(4, 200 / (SR / 2), btype="lowpass", output="sos"), A)
    mid = A - lo
    win = int(2.0 * SR)
    best, score = solo_a, -1e9
    for c in np.arange(solo_a - 12, solo_a + 12, 1.0):
        s = slice(int(c * SR), int(c * SR) + win)
        m = float((mid[s] ** 2).mean())
        l = float((lo[s] ** 2).mean())
        v = m / (float((mid ** 2).mean()) + 1e-12) - l / (float((lo ** 2).mean()) + 1e-12)
        if v > score:
            best, score = float(c), v
    print(f"B wchodzi w {best:.0f} s — tam, gdzie A opiera się na perkusji i schodzi z basu")

    pos = best
    i = 0
    while pos < best + blend + between + together:
        f = FLOORS[min(3, int((pos - best) / ((blend + between + together) / 4)))]
        s2 = int(9.0 * SR)
        v = grid(LINE_B[i % 4], s2, f) * swell(s2, 1.4, 2.6, 0.85)
        a = int(pos * SR)
        b = min(a + s2, n)
        if b > a:
            B[a:b] += v[: b - a]
        pos += 8.0
        i += 1

    A /= np.abs(A).max() + 1e-9
    B /= np.abs(B).max() + 1e-9

    # ── obwiednie szwu ──
    env_a = np.ones(n)
    env_b = np.zeros(n)
    bs, be = int(best * SR), int((best + blend) * SR)
    env_b[bs:be] = np.sin(np.linspace(0, np.pi / 2, be - bs))
    env_b[be:] = 1.0
    # A nie znika — cofa się i wraca w finale, bo to nie jest przejście, tylko rozmowa
    env_a[bs:be] = np.cos(np.linspace(0, np.pi / 2, be - bs)) * 0.55 + 0.45
    bt = int((best + blend + between) * SR)
    env_a[be:bt] *= np.linspace(1, 0.22, bt - be)
    env_a[bt:] = np.linspace(0.22, 1.0, n - bt)

    # dół oddany na 97 % szwu, nie w połowie
    hand_low = sosfilt(butter(4, 200 / (SR / 2), btype="lowpass", output="sos"), A)
    swap = int((best + blend * BASS_AT) * SR)
    low_a = np.ones(n)
    low_a[swap:] = np.linspace(1, 0, min(int(3 * SR), n - swap)).tolist() + \
        [0.0] * max(0, n - swap - int(3 * SR))

    va = A * env_a
    va = (va - hand_low) + hand_low * low_a
    vb = B * env_b

    # ── jeden kanał dla obu ──
    mix = bus(va * 0.72 + vb * 0.62)
    # RESZTA: to, czego nie było w żadnym ze źródeł
    residual = mix - (va * 0.72 + vb * 0.62)
    residual /= np.abs(residual).max() + 1e-9
    residual = reverb(residual, 5.5, 0.62)

    # część środkowa: grają tylko ruchy rąk
    body = mix.copy()
    a0, a1 = be, bt
    fade = int(4 * SR)
    body[a0:a1] *= 0.10
    body[a0:a0 + fade] *= np.linspace(1, 0.1, fade) / 0.1 * 0.1 + 0.9 * np.linspace(1, 0, fade)
    res_env = np.zeros(n)
    res_env[a0:a1] = 1.0
    res_env[a0:a0 + fade] = np.linspace(0, 1, fade)
    res_env[a1 - fade:a1] = np.linspace(1, 0.25, fade)
    res_env[a1:] = 0.25
    # Reszta jest z natury cienka — to produkty intermodulacji, nie ton. Przy
    # 0,85 wychodziła 9 dB pod resztą utworu i czytała się jak dziura zamiast
    # jak część. Podniesiona tak, żeby była o kilka decybeli ciszej, nie o dekadę.
    out = body + residual * res_env * 1.9

    # ── perkusja: wchodzi z siatką, znika w części środkowej ──
    tt = best
    k = 0
    beat = 60.0 / FLOORS[1]
    while tt < total - 4:
        f = FLOORS[min(3, int(max(0, tt - best) / ((blend + between + together) / 4)))]
        beat = 60.0 / f
        quiet = a0 / SR <= tt < a1 / SR
        if not quiet:
            i0 = int(tt * SR)
            kk = kick(int(0.3 * SR))
            j = min(i0 + len(kk), n)
            out[i0:j] += kk[: j - i0] * 0.34
        hh = hat(int(0.09 * SR))
        i0 = int((tt + beat / 2) * SR)
        j = min(i0 + len(hh), n)
        out[i0:j] += hh[: j - i0] * (0.05 if quiet else 0.13)
        tt += beat
        k += 1

    # ── stereo: ręka i siatka po dwóch stronach, reszta w środku ──
    # Ręka po jednej stronie, siatka po drugiej — a to, co między nimi, w środku.
    # Przy 0,16 korelacja kanałów wychodziła 0,98, czyli prawie mono.
    L = out + va * 0.34
    R = out + vb * 0.34
    mixs = np.stack([L, R])
    fi, fo = int(4 * SR), int(10 * SR)
    mixs[:, :fi] *= np.linspace(0, 1, fi) ** 1.5
    mixs[:, -fo:] *= np.linspace(1, 0, fo) ** 1.5
    mixs *= 0.89 / (np.abs(mixs).max() + 1e-9)

    p = "experiments_priv/2026-07-31_utwor/in_between.wav"
    sf.write(p, mixs.T, SR, subtype="PCM_24")
    print(f"{p} — {mixs.shape[1] / SR / 60:.1f} min")
    print(f"szew {blend:.0f} s = {BLEND_BEATS} uderzeń · dół oddany na {BASS_AT:.0%}")
    print(f"reszta (to, czego nie było w żadnym głosie): "
          f"{20 * np.log10(np.sqrt((residual[a0:a1] ** 2).mean()) + 1e-12):.1f} dB")
    print(f"korelacja kanałów {np.corrcoef(mixs[0], mixs[1])[0, 1]:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
