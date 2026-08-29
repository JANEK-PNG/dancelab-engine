"""Czy trzy poprzednie utwory niosą informację, której para nie ma.

Pięć cech kontekstu z PLAN.md, mierzonych wobec 158 ocen ucha. Zgodność
liczona WEWNĄTRZ playlisty — na wspólnej kupie każda cecha dostałaby punkty
za samo rozpoznanie, że playlista jest potasowana.
"""

from __future__ import annotations

import collections
import csv
import json
import pathlib

import numpy as np
from scipy.stats import spearmanr

TU = pathlib.Path(__file__).parent
ROOT = TU.parents[1]
OCENY = ROOT / "experiments_priv/2026-08-17_ocena_papierowa"
PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
OKNO = 3
ZIARNO = 20260829
PERMUTACJE = 10_000


def kolo_kwintowe(a: str | None, b: str | None) -> bool:
    """Czy krok jest harmonicznie zgodny wg koła Camelota (±1 albo zmiana trybu)."""
    if not a or not b or len(a) < 2 or len(b) < 2:
        return True                      # nie wiemy = nie oskarżamy
    try:
        na, ma = int(a[:-1]), a[-1].upper()
        nb, mb = int(b[:-1]), b[-1].upper()
    except ValueError:
        return True
    if na == nb:
        return True
    krok = min((na - nb) % 12, (nb - na) % 12)
    return krok <= 1 and ma == mb


def srednie_rho_w_playlistach(w: np.ndarray, ucho: np.ndarray,
                              plej: np.ndarray) -> float:
    rhos = []
    for nazwa in np.unique(plej):
        m = plej == nazwa
        if w[m].std() < 1e-12 or ucho[m].std() < 1e-12:
            continue
        rhos.append(float(spearmanr(w[m], ucho[m]).statistic))
    return float(np.mean(rhos)) if rhos else float("nan")


def p_permutacyjne(w: np.ndarray, ucho: np.ndarray, plej: np.ndarray,
                   obs: float) -> float:
    """Permutacja ocen WEWNĄTRZ playlisty — zachowuje strukturę playlist."""
    g = np.random.default_rng(ZIARNO)
    licznik = 0
    for _ in range(PERMUTACJE):
        perm = ucho.copy()
        for nazwa in np.unique(plej):
            m = plej == nazwa
            perm[m] = g.permutation(perm[m])
        if abs(srednie_rho_w_playlistach(w, perm, plej)) >= abs(obs) - 1e-12:
            licznik += 1
    return licznik / PERMUTACJE


def main() -> int:
    from dancelab.storage.repositories import FileAnalysisRepository
    from dancelab.tui.duplikaty import scal

    dane = json.loads((OCENY / "playlisty_dane.json").read_text(encoding="utf-8"))
    potrzebne = {t["track_id"] for lista in dane.values() for t in lista}
    repo = FileAnalysisRepository(PROCESSED)
    widok, _ = scal([repo.get(t) for t in repo.list_track_ids()])
    by_id = {a.track.track_id: a for a in widok if a.track.track_id in potrzebne}

    rms = {}
    for tid, a in by_id.items():
        v = [f.rms for f in a.features if f.rms is not None]
        rms[tid] = float(np.mean(v)) if v else None
    mediana_rms = float(np.median([v for v in rms.values() if v is not None]))
    rms = {k: (v if v is not None else mediana_rms) for k, v in rms.items()}

    oceny = {}
    for p in sorted(OCENY.glob("SESJA_*_transition_ratings.csv")):
        for r in csv.DictReader(p.open(encoding="utf-8")):
            oceny[(r["track_id_a"], r["track_id_b"])] = int(r["dj_mixability_rating"])

    stare = json.loads((ROOT / "experiments_priv/2026-08-29_rozdzielczosc_punktacji"
                        / "skladowe.json").read_text(encoding="utf-8"))

    wiersze = []
    for nazwa, lista in dane.items():
        ids = [t["track_id"] for t in lista]
        for i in range(1, len(ids)):
            para = (ids[i - 1], ids[i])
            if para not in oceny:
                continue
            okno = ids[max(0, i - OKNO):i]          # do trzech poprzednich
            b = ids[i]
            e_okno = np.array([rms[t] for t in okno])
            e_b = rms[b]
            rozrzut = float(e_okno.std()) if len(e_okno) > 1 else 0.0
            skok = abs(e_b - float(e_okno.mean())) / (rozrzut + 1e-6) if rozrzut > 1e-9 \
                else abs(e_b - float(e_okno.mean())) / (mediana_rms + 1e-9)

            bpm = [by_id[t].track.bpm_estimate or 0.0 for t in okno]
            bpm_b = by_id[b].track.bpm_estimate or 0.0
            dryf = abs(bpm_b - float(np.mean(bpm))) / (float(np.mean(bpm)) + 1e-9)

            ciag = [rms[t] for t in okno] + [e_b]
            zmiany = np.diff(ciag)
            zygzak = int(sum(1 for j in range(1, len(zmiany))
                             if zmiany[j] * zmiany[j - 1] < 0))

            style = [by_id[t].track.style_label for t in okno
                     if by_id[t].track.style_label]
            st_b = by_id[b].track.style_label
            if not style or not st_b:
                obcosc = 0.5                        # nie wiemy = neutralnie
            else:
                dominujacy = collections.Counter(style).most_common(1)[0][0]
                obcosc = 0.0 if st_b == dominujacy else 1.0

            kroki = [ids[j] for j in range(max(0, i - OKNO), i + 1)]
            niezgodne = sum(
                0 if kolo_kwintowe(by_id[kroki[j]].track.key_estimate,
                                   by_id[kroki[j + 1]].track.key_estimate) else 1
                for j in range(len(kroki) - 1))

            wiersze.append({
                "playlista": nazwa, "ucho": oceny[para],
                "skok_energii": skok, "dryf_tempa": dryf,
                "zygzak_energii": float(zygzak), "obcosc_stylu": obcosc,
                "niezgodnosc_tonacji": float(niezgodne),
            })

    plej = np.array([w["playlista"] for w in wiersze])
    ucho = np.array([float(w["ucho"]) for w in wiersze])
    print(f"przejść z pełnym oknem: {len(wiersze)} (pierwsze przejście każdej "
          f"playlisty ma okno krótsze, ale liczone)\n")

    # dzisiejsza punktacja jako punkt odniesienia
    stary = np.array(stare["po priorze"])
    stary_plej = np.array(stare["playlista"])
    stary_ucho = np.array(stare["ucho"])
    baza = srednie_rho_w_playlistach(stary, stary_ucho, stary_plej)
    nasycone = stary >= 0.9999

    print(f"{'cecha':<24} {'rho w playl.':>13} {'p':>8} {'rho w nasyconych':>18}")
    print(f"{'dzisiejsza punktacja':<24} {baza:>+13.3f} {'—':>8} "
          f"{srednie_rho_w_playlistach(stary[nasycone], stary_ucho[nasycone], stary_plej[nasycone]):>+18.3f}")
    wyniki = {}
    for cecha in ("skok_energii", "dryf_tempa", "zygzak_energii",
                  "obcosc_stylu", "niezgodnosc_tonacji"):
        w = np.array([x[cecha] for x in wiersze])
        rho = srednie_rho_w_playlistach(w, ucho, plej)
        p = p_permutacyjne(w, ucho, plej, rho)
        # ta sama cecha, ale tylko na przejściach, gdzie silnik dziś jest ślepy
        rho_nas = srednie_rho_w_playlistach(w[nasycone], ucho[nasycone],
                                            plej[nasycone])
        wyniki[cecha] = {"rho": rho, "p": p, "rho_nasycone": rho_nas}
        print(f"{cecha:<24} {rho:>+13.3f} {p:>8.4f} {rho_nas:>+18.3f}")

    (TU / "wynik.json").write_text(
        json.dumps({"baza_rho_w_playlistach": baza, "cechy": wyniki},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nprogi z PLAN.md: |rho| ≥ 0,20 przy p < 0,01 · "
          "|rho w nasyconych| ≥ 0,15 · połączenie ≥ 0,50")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
