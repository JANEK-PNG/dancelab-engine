"""Zły jest nasz ŁUK czy nasza MIARA energii? Trzy miary na tych samych setach.

PROBLEM. Nagrane sety Janka nie układają się w nasz łuk „build" mierzony
średnim RMS — ale to ma DWA możliwe wyjaśnienia i mylenie ich byłoby błędem:

  (a) model łuku jest zły — sety naprawdę nie rosną;
  (b) miara jest zła — RMS nie widzi energii, którą słyszy sala.

Rozróżniamy je tak: liczymy krzywą setu TRZEMA różnymi miarami i patrzymy,
czy któraś pokazuje wspinaczkę. Jeśli żadna — wina jest po stronie modelu.
Jeśli któraś pokazuje — wina jest po stronie miary i to JĄ trzeba zmienić,
a łuku nie ruszać.

MIARY:
  * `rms`   — średni RMS szerokopasmowy; dokładnie to, czego dziś używa
              `set_builder.track_energy`. Miara podsądna.
  * `bas`   — energia w paśmie 40–150 Hz. Dla parkietu to stopa i bas, czyli
              to, po czym Janek sam rozpoznaje moment wejścia
              (zmierzona reguła: wchodzi tam, gdzie utwór opiera się na
              perkusji i schodzi z basu).
  * `gora`  — energia powyżej 4 kHz. Blachy i hi-haty rosną w miksach
              klubowych wraz z natężeniem, a nie zależą od poziomu basu.

UWAGA O NAGRANIU. To zapis z miksera, więc poziom niesie także ruchy faderów
Janka — czyli to, co realnie wyszło na salę. Dla tego pomiaru jest to zaleta,
nie wada: nie mierzymy masteringu płyt, tylko wyjście.

Użycie:
    .venv/bin/python experiments_priv/2026-08-10_ksztalt_setu/czy_miara_czy_model.py
"""

from __future__ import annotations

import json
import pathlib
import sys

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
KATALOG = pathlib.Path(__file__).resolve().parent
NAGRANIA = pathlib.Path.home() / "Music/rekordbox/Recording/Jan Trybus"

PASMA = {"bas": (40.0, 150.0), "gora": (4000.0, 20000.0)}


def krzywe_trzema_miarami(wav: pathlib.Path, granice: list[float]) -> dict:
    """{'rms': [...], 'bas': [...], 'gora': [...]} — wartość na utwór."""
    import numpy as np
    import soundfile as sf

    info = sf.info(str(wav))
    sr = info.samplerate
    krance = [*granice, info.frames / sr]
    n = len(granice)
    sumy = {k: [0.0] * n for k in ("rms", *PASMA)}
    liczby = [0] * n

    okno = sr * 5
    czest = np.fft.rfftfreq(okno, 1.0 / sr)
    maski = {k: (czest >= lo) & (czest < hi) for k, (lo, hi) in PASMA.items()}

    idx = 0
    pozycja = 0.0
    with sf.SoundFile(str(wav)) as f:
        for blok in f.blocks(blocksize=okno, dtype="float32", always_2d=True):
            mono = blok.mean(axis=1)
            czas = len(mono) / sr
            srodek = pozycja + czas / 2
            while idx + 1 < len(krance) and srodek >= krance[idx + 1]:
                idx += 1
            if len(mono) == okno:
                widmo = np.abs(np.fft.rfft(mono)) ** 2
                for k, maska in maski.items():
                    sumy[k][idx] += float(np.sqrt(widmo[maska].mean()))
                sumy["rms"][idx] += float(np.sqrt(np.mean(mono ** 2)))
                liczby[idx] += 1
            pozycja += czas
    return {k: [sumy[k][i] / liczby[i] if liczby[i] else 0.0 for i in range(n)]
            for k in sumy}


def main() -> int:
    import numpy as np
    from scipy.stats import spearmanr

    from ksztalt_nagranych_setow import wczytaj_cue
    from ksztalt_realnych_setow import cel_build, test_permutacyjny, znormalizuj

    wyniki = []
    for cue in sorted(NAGRANIA.glob("*/*.cue")):
        wav = cue.with_suffix(".wav")
        if not wav.exists():
            continue
        utwory = wczytaj_cue(cue)
        if len(utwory) < 5:
            continue
        print(f"→ {cue.parent.name}/{cue.stem} ({len(utwory)} utworów)…",
              flush=True)
        krzywe = krzywe_trzema_miarami(wav, [t for _n, t in utwory])
        wpis = {"set": f"{cue.parent.name}/{cue.stem}", "n": len(utwory)}
        for miara, surowe in krzywe.items():
            k = znormalizuj(surowe)
            n = len(k)
            _realny, _losowy, p = test_permutacyjny(k, 2)
            wpis[miara] = dict(
                rho=float(spearmanr(range(n), k).statistic),
                blad_luk=float(np.mean(np.abs(np.asarray(k)
                                              - np.asarray(cel_build(n))))),
                blad_plaski=float(np.mean(np.abs(np.asarray(k) - 0.5))),
                perm_p=p,
                spadki=sum(1 for i in range(1, n) if k[i] < k[i - 1] - 0.08),
                krzywa=[round(x, 3) for x in k])
        wyniki.append(wpis)

    print()
    print(f"{'set':22} {'miara':6} {'rho':>7} {'łuk':>7} {'płaski':>7} "
          f"{'p(bloki)':>9} {'spadki':>7}")
    for w in wyniki:
        for miara in ("rms", "bas", "gora"):
            d = w[miara]
            znak = " ←ROŚNIE" if d["rho"] > 0.5 else ""
            print(f"{w['set'][:22]:22} {miara:6} {d['rho']:+7.3f} "
                  f"{d['blad_luk']:7.3f} {d['blad_plaski']:7.3f} "
                  f"{d['perm_p']:9.3f} {d['spadki']:7}{znak}")

    print("\nODCZYT:")
    rosnace = [(w["set"], m) for w in wyniki for m in ("rms", "bas", "gora")
               if w[m]["rho"] > 0.5]
    if rosnace:
        print("  któraś miara pokazuje wspinaczkę → winna MIARA, nie łuk:")
        for s, m in rosnace:
            print(f"    {s} · {m}")
    else:
        print("  ŻADNA z trzech miar nie pokazuje wspinaczki (rho > 0,5)")
        print("  → to nie jest wina miary; nasz model łuku jest po prostu zły")
    lepszy_plaski = sum(1 for w in wyniki for m in ("rms", "bas", "gora")
                        if w[m]["blad_plaski"] < w[m]["blad_luk"])
    print(f"  płaska linia bije nasz łuk w {lepszy_plaski} przypadkach "
          f"na {len(wyniki) * 3}")
    bloki = sum(1 for w in wyniki for m in ("rms", "bas", "gora")
                if w[m]["perm_p"] < 0.05)
    print(f"  struktura blokowa istotna w {bloki} przypadkach "
          f"na {len(wyniki) * 3}")

    (KATALOG / "wynik_miary.json").write_text(
        json.dumps(wyniki, ensure_ascii=False, indent=2))
    print(f"\nzapisane: {KATALOG / 'wynik_miary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
