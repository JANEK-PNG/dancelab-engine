"""Dowód, nie opinia: ten sam utwór — lossless Janka kontra plik z korpusu.

Zarzut Janka był słuszny: nazwałem korpus „niską jakością" bez pomiaru,
a jedyny twardy przypadek złej jakości (64 kbps AAC / 32 kHz) był NASZYM
błędem eksportu, nie plikami z dysku. Tu jest pomiar.

Porównujemy trzy pary tego samego nagrania. Dla każdej strony:

  * co mówi kontener (kodek, próbkowanie, bitrate — z ffmpeg),
  * gdzie naprawdę kończy się pasmo (f95/f99 — częstotliwość, poniżej której
    leży 95%/99% energii; kodeki stratne ucinają górę),
  * ile energii żyje nad 14 i 16 kHz względem całości,
  * uśrednione widmo obu wersji na jednym obrazku.

I werdykt per ZASTOSOWANIE, bo „jakość" bez celu to puste słowo: co innego
znaczy „za słabe" dla ucha na klubowym systemie, a co innego dla siatki bitów
liczonej z pasma stopy poniżej 160 Hz.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from scipy.signal import welch

DIR = pathlib.Path("experiments_priv/2026-08-01_jakosc_korpusu")
PAPER, INK = "#efece4", "#141414"

PAIRS = [
    ("Robotman — Never (DBX Mix)",
     None,  # sciezke lossless znajdziemy po nazwie
     "/Volumes/MY_PC/DanceLabCorpus/tracks/BUb8CBEKaNI.webm"),
    ("G-Man — Quo Vadis",
     None,
     "/Volumes/MY_PC/DanceLabCorpus/tracks/r_M8xiUd9kU.webm"),
    ("Herbert — Got To Be Movin'",
     None,
     "/Volumes/MY_PC/DanceLabCorpus/tracks/c3FNi8kQwAY.webm"),
]
HINTS = ["Robotman - Never", "Quo Vadis", "Got To Be Movin"]


def find_local(hint: str) -> str | None:
    import unicodedata as U
    from pyrekordbox import Rekordbox6Database
    for c in Rekordbox6Database().get_content():
        if not c.FolderPath:
            continue
        p = pathlib.Path(c.FolderPath)
        name = U.normalize("NFC", p.stem).lower()
        if (p.suffix.lower() in (".aiff", ".aif", ".wav", ".flac") and p.exists()
                and U.normalize("NFC", hint).lower().split(" - ")[-1][:12] in name):
            return str(p)
    return None


def codec_info(path: str) -> str:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path],
                       capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        ln = ln.strip()
        if ln.startswith("Stream") and "Audio" in ln:
            return ln.split("Audio:", 1)[1].strip()[:90]
    return "?"


def load_mid(path: str, sec: float = 100000.0) -> tuple[np.ndarray, int]:
    """Środkowe 90 s, dekodowane ffmpegiem do wav — wspólny mianownik formatów."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        out = tmp.name
    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-i", path, "-ac", "1", "-ar", "44100", out], check=True)
    y, sr = sf.read(out, dtype="float64")
    pathlib.Path(out).unlink()
    return y, sr


def band_facts(y: np.ndarray, sr: int) -> dict:
    f, P = welch(y, sr, nperseg=8192)
    c = np.cumsum(P) / (P.sum() + 1e-18)
    tot = P.sum()
    # SUFIT kodeka, nie zawartość muzyki: najwyższa częstotliwość, przy której
    # widmo wciąż stoi 70 dB nad własnym maksimum podłogi — kodek stratny tnie
    # górę twardo i to widać jako urwisko, niezależnie od sekcji utworu.
    Pn = P / (P.max() + 1e-18)
    above = np.where(Pn > 1e-7)[0]
    cutoff = float(f[above[-1]]) if above.size else 0.0
    return {
        "f": f, "P": P, "cutoff": cutoff,
        "f95": float(f[np.searchsorted(c, 0.95)]),
        "f99": float(f[np.searchsorted(c, 0.99)]),
        "gt14k": float(P[f > 14000].sum() / tot),
        "gt16k": float(P[f > 16000].sum() / tot),
    }


def main() -> int:
    fig, axes = plt.subplots(len(PAIRS), 1, figsize=(13, 4 * len(PAIRS)),
                             facecolor=PAPER, gridspec_kw={"hspace": 0.45})
    for k, ((label, _, corpus), hint) in enumerate(zip(PAIRS, HINTS)):
        local = find_local(hint)
        if not local:
            print(f"{label}: nie znalazłem lokalnego pliku, pomijam")
            continue
        print(f"\n═ {label}")
        print(f"  Janek : {codec_info(local)}")
        print(f"  korpus: {codec_info(corpus)}")
        yl, sr = load_mid(local)
        yc, _ = load_mid(corpus)
        bl, bc = band_facts(yl, sr), band_facts(yc, sr)
        for who, b in (("Janek ", bl), ("korpus", bc)):
            print(f"  {who}: SUFIT {b['cutoff'] / 1000:5.1f} kHz · f99 {b['f99'] / 1000:4.1f} kHz"
                  f" · >14k {b['gt14k'] * 100:.2f}% · >16k {b['gt16k'] * 100:.3f}%")

        ax = axes[k] if len(PAIRS) > 1 else axes
        for who, b, col in (("lossless Janka", bl, INK),
                            ("korpus (webm/opus)", bc, "#e0483c")):
            ax.semilogy(b["f"] / 1000, b["P"] / b["P"].max() + 1e-12,
                        label=who, lw=1.1, color=col, alpha=0.85)
        ax.set_xlim(0, 22)
        ax.set_ylim(1e-9, 2)
        ax.set_title(label, color=INK, fontsize=11, loc="left", family="monospace")
        ax.set_xlabel("częstotliwość [kHz]", fontsize=8)
        ax.legend(fontsize=8)
        ax.set_facecolor(PAPER)
        for spx in ax.spines.values():
            spx.set_color(INK)
        ax.tick_params(colors=INK, labelsize=8)
    fig.savefig(DIR / "porownanie_widm.png", dpi=150, facecolor=PAPER,
                bbox_inches="tight")
    print(f"\n{DIR / 'porownanie_widm.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
