"""Kształt DWÓCH REALNIE ZAGRANYCH setów Janka — energia liczona z nagrania.

DLACZEGO OSOBNY POMIAR. `ksztalt_realnych_setow.py` czyta `DjmdSongHistory`,
czyli ZAŁADOWANIA utworu na deck. W samym 2026-02-24 takich „sesji" jest
kilkanaście — to przekopywanie biblioteki w domu, nie występ. Wniosek o
kształcie setu wyciągnięty z przekopywania byłby błędem, więc ten skrypt
używa jedynych danych bez tej wady: dwóch nagranych setów Janka (WAV + .cue
z Rekordboksa).

CO TU JEST PRAWDZIWE. Energia liczona z NAGRANIA, czyli z tego, co realnie
poszło z miksera — razem z tym, jak Janek prowadził fadery. Granice utworów
z `INDEX 01` w arkuszu cue, czyli z zapisu Rekordboxa, nie z naszej detekcji.

CZEGO TO NIE JEST. Dwa sety to dwa sety. To ground truth, ale nie próba
statystyczna — wynik wolno czytać jako „tak wyglądają TE sety", nie „tak
wyglądają sety w ogóle".

Audio NIE jest odtwarzane — czytamy próbki blokami i liczymy RMS.

Użycie:
    .venv/bin/python experiments_priv/2026-08-10_ksztalt_setu/ksztalt_nagranych_setow.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
KATALOG = pathlib.Path(__file__).resolve().parent
NAGRANIA = pathlib.Path.home() / "Music/rekordbox/Recording/Jan Trybus"


def czas_z_cue(tekst: str) -> float:
    """`INDEX 01 HH:MM:SS` → sekundy.

    PUŁAPKA, kosztowała jeden fałszywy wynik. Norma arkusza cue (Red Book) mówi
    `MM:SS:FF`, gdzie FF to klatki 1/75 s. **Rekordbox pisze tu HH:MM:SS.**
    Sprawdzone wprost: ostatni znacznik w „Open Deck" to `00:46:45` przy
    nagraniu długim na 52,2 min — jako MM:SS:FF dałoby to 46,6 SEKUNDY, czyli
    wszystkie 19 granic w pierwszej minucie zamiast na przestrzeni całego setu.
    Odczytane po normie krzywe wyglądały jak muzyka (0,00 0,56 0,00 0,60…),
    a były artefaktem pustych odcinków.
    """
    a, b, c = (int(x) for x in tekst.split(":"))
    return a * 3600 + b * 60 + c


def wczytaj_cue(sciezka: pathlib.Path) -> list[tuple[str, float]]:
    """[(tytuł, początek w sekundach)] w kolejności grania."""
    utwory: list[tuple[str, float]] = []
    tytul = None
    for linia in sciezka.read_text(errors="replace").splitlines():
        t = linia.strip()
        if t.startswith("TRACK "):
            tytul = None
        elif t.startswith("TITLE ") and tytul is None and utwory != []:
            tytul = t[6:].strip().strip('"')
        elif t.startswith("TITLE ") and tytul is None:
            tytul = t[6:].strip().strip('"')
        elif t.startswith("INDEX 01 "):
            utwory.append((tytul or "?", czas_z_cue(t.split()[-1])))
            tytul = None
    # pierwszy TITLE w pliku to tytuł CAŁEGO setu, nie utworu — odpada,
    # bo stoi przed pierwszym TRACK i nie ma po nim INDEX-u.
    return utwory


def energia_per_utwor(wav: pathlib.Path,
                      granice: list[float]) -> list[float]:
    """Średni RMS każdego odcinka między znacznikami — czytane blokami."""
    import numpy as np
    import soundfile as sf

    info = sf.info(str(wav))
    sr = info.samplerate
    dlugosc = info.frames / sr
    krance = [*granice, dlugosc]
    sumy = [0.0] * len(granice)
    liczby = [0] * len(granice)

    idx = 0
    pozycja = 0.0
    with sf.SoundFile(str(wav)) as f:
        for blok in f.blocks(blocksize=sr * 5, dtype="float32", always_2d=True):
            mono = blok.mean(axis=1)
            czas_bloku = len(mono) / sr
            srodek = pozycja + czas_bloku / 2
            while idx + 1 < len(krance) and srodek >= krance[idx + 1]:
                idx += 1
            sumy[idx] += float(np.sqrt(np.mean(mono ** 2)))
            liczby[idx] += 1
            pozycja += czas_bloku
    return [sumy[i] / liczby[i] if liczby[i] else 0.0 for i in range(len(granice))]


def main() -> int:
    import numpy as np
    from scipy.stats import spearmanr

    from ksztalt_realnych_setow import (cel_build, dopasuj_bloki,
                                        test_permutacyjny, znormalizuj)

    wyniki = []
    for cue in sorted(NAGRANIA.glob("*/*.cue")):
        wav = cue.with_suffix(".wav")
        if not wav.exists():
            print(f"pominięte (brak WAV): {cue.name}")
            continue
        utwory = wczytaj_cue(cue)
        if len(utwory) < 5:
            print(f"pominięte (za mało utworów w cue): {cue.name}")
            continue
        print(f"→ {cue.parent.name}/{cue.stem}: {len(utwory)} utworów, "
              f"licze energie z nagrania…", flush=True)
        ener = energia_per_utwor(wav, [t for _n, t in utwory])
        krzywa = znormalizuj(ener)
        n = len(krzywa)
        rho = float(spearmanr(range(n), krzywa).statistic)
        blad_luk = float(np.mean(np.abs(np.asarray(krzywa)
                                        - np.asarray(cel_build(n)))))
        blad_plaski = float(np.mean(np.abs(np.asarray(krzywa) - 0.5)))
        realny, losowy, p = test_permutacyjny(krzywa, 2)
        spadki = sum(1 for i in range(1, n) if krzywa[i] < krzywa[i - 1] - 0.08)
        wyniki.append(dict(set=f"{cue.parent.name}/{cue.stem}", n=n, rho=rho,
                           blad_luk=blad_luk, blad_plaski=blad_plaski,
                           blad_2=realny, perm_losowy=losowy, perm_p=p,
                           spadki=spadki,
                           krzywa=[round(x, 4) for x in krzywa],
                           tytuly=[t for t, _ in utwory]))

    if not wyniki:
        print("brak nagranych setów do policzenia")
        return 1

    print()
    for w in wyniki:
        print(f"== {w['set']} — {w['n']} utworów ==")
        print(f"  rho (pozycja vs energia):        {w['rho']:+.3f}")
        print(f"  błąd naszego łuku build:         {w['blad_luk']:.3f}")
        print(f"  błąd płaskiej linii 0,5:         {w['blad_plaski']:.3f}"
              f"   {'← płaska LEPSZA' if w['blad_plaski'] < w['blad_luk'] else ''}")
        print(f"  2 bloki, kolejność realna:       {w['blad_2']:.3f}")
        print(f"  2 bloki, kolejność przetasowana: {w['perm_losowy']:.3f}"
              f"  (p = {w['perm_p']:.3f})")
        print(f"  spadki >8%:                      {w['spadki']} "
              f"(nasz łuk zabrania ich w ogóle)")
        ksztalt = " ".join(f"{x:.2f}" for x in w["krzywa"])
        print(f"  krzywa: {ksztalt}\n")

    (KATALOG / "wynik_nagrania.json").write_text(
        json.dumps(wyniki, ensure_ascii=False, indent=2))
    print(f"zapisane: {KATALOG / 'wynik_nagrania.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
