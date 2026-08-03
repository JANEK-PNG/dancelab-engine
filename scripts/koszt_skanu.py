"""Ile trwa pierwsze uruchomienie — liczba, na której ma stanąć UX.

Specyfikacja UX zakłada, że po wskazaniu bazy program „skanuje bibliotekę".
Nigdzie nie policzyliśmy, ile to jest w minutach, a od 2026-08-03 doszedł
kolejny koszt: brzmienie (CLAP) jest teraz składnikiem oceny przejścia, więc
biblioteka usera musi zostać osadzona, inaczej ten składnik nic nie wnosi.

Mierzymy na PRAWDZIWYCH plikach z biblioteki, nie na korpusie — bo korpus to
webm dekodowany wolną ścieżką (108 s/utwór) i dałby liczbę nie z tego świata.

Trzy koszty, każdy osobno, bo każdy inaczej się skaluje i inaczej wygląda w UX:

  1. DEKOD — wczytanie pliku. Rośnie z długością utworu.
  2. ANALIZA — sztywna siatka + tonacja + energia. To jest to, co daje BPM,
     Camelot i łuk energii.
  3. BRZMIENIE — pięć okien po 10 s przez CLAP na MPS. Nie zależy od długości
     utworu (okna są stałe), więc skaluje się liniowo z liczbą płyt.

Wynik przeliczamy na biblioteki różnej wielkości i na warianty wielowątkowe,
żeby dało się zdecydować, co robić od razu, a co w tle po pierwszym secie.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile
import time

import numpy as np
import soundfile as sf

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

SR_A = 22050          # analiza
SR_C = 48000          # CLAP
WINDOW_SEC, N_WINDOWS = 10, 5


def sample_library(n: int) -> list[pathlib.Path]:
    import unicodedata as U
    from pyrekordbox import Rekordbox6Database

    out = []
    for c in Rekordbox6Database().get_content():
        if not c.FolderPath:
            continue
        p = pathlib.Path(U.normalize("NFC", c.FolderPath))
        if p.suffix.lower() in (".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a") and p.exists():
            out.append(p)
    rng = np.random.default_rng(3)
    if len(out) > n:
        out = [out[i] for i in rng.choice(len(out), n, replace=False)]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    args = ap.parse_args()

    from dancelab.core.rigid_grid import fit_rigid_grid
    from dancelab.features.key import estimate_key

    files = sample_library(args.n)
    print(f"próbka: {len(files)} utworów z biblioteki\n", flush=True)

    print("ładuję CLAP…", flush=True)
    import torch
    from transformers import ClapModel, ClapProcessor
    mid = "laion/clap-htsat-unfused"
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    t0 = time.time()
    model = ClapModel.from_pretrained(mid).to(dev).eval()
    proc = ClapProcessor.from_pretrained(mid)
    load_s = time.time() - t0
    print(f"  model na {dev}, ładowanie {load_s:.1f} s (raz na uruchomienie)\n", flush=True)

    dec, ana, snd, mins = [], [], [], []
    for i, p in enumerate(files, 1):
        try:
            t = time.time()
            tmp = tempfile.mktemp(suffix=".wav")
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(p),
                            "-ac", "1", "-ar", str(SR_A), tmp],
                           check=True, capture_output=True, timeout=180)
            y, sr = sf.read(tmp, dtype="float32")
            pathlib.Path(tmp).unlink(missing_ok=True)
            dec.append(time.time() - t)
            mins.append(len(y) / sr / 60)

            t = time.time()
            fit_rigid_grid(y, sr)
            estimate_key(y, sr)
            w = sr
            n = (len(y) // w) * w
            if n:
                np.sqrt((y[:n].reshape(-1, w) ** 2).mean(axis=1))
            ana.append(time.time() - t)

            t = time.time()
            import librosa
            wav = librosa.resample(y, orig_sr=sr, target_sr=SR_C)
            win = WINDOW_SEC * SR_C
            starts = ([0] if wav.size <= win else
                      np.linspace(0, wav.size - win, N_WINDOWS, dtype=int))
            clips = [wav[s:s + win].astype(np.float32) for s in starts]
            inputs = proc(audio=clips, sampling_rate=SR_C, return_tensors="pt")
            inputs = {k: v.to(dev) for k, v in inputs.items()}
            with torch.no_grad():
                model.get_audio_features(**inputs).pooler_output.mean(dim=0).cpu().numpy()
            snd.append(time.time() - t)
            print(f"  {i}/{len(files)} {p.name[:34]:34s} "
                  f"dekod {dec[-1]:4.1f}s · analiza {ana[-1]:4.1f}s · brzmienie {snd[-1]:4.1f}s",
                  flush=True)
        except Exception as exc:                                   # noqa: BLE001
            print(f"  {i}: {type(exc).__name__} — pomijam", flush=True)

    if not ana:
        print("nie udało się nic zmierzyć")
        return 1

    d, a, s = float(np.median(dec)), float(np.median(ana)), float(np.median(snd))
    print(f"\nmediana na utwór ({np.median(mins):.1f} min audio):")
    print(f"  dekod      {d:5.2f} s")
    print(f"  analiza    {a:5.2f} s   (BPM, tonacja, energia)")
    print(f"  brzmienie  {s:5.2f} s   (CLAP, 5 okien po 10 s)")
    print(f"  RAZEM      {d + a + s:5.2f} s")

    print(f"\nco to znaczy dla UX (jeden wątek → 6 wątków):")
    for n in (500, 1000, 1837, 5000):
        one = n * (d + a + s) / 60
        six = one / 6
        bez = n * (d + a) / 60 / 6
        print(f"  {n:5d} utworów: {one:6.0f} min  →  {six:5.0f} min na 6 wątkach"
              f"   (bez brzmienia {bez:4.0f} min)")
    udzial = s / (d + a + s) * 100
    print(f"\n  brzmienie to {udzial:.0f}% całego kosztu skanu")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
