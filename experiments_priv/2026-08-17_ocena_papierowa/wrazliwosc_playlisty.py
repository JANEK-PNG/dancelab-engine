"""Czy H1 stoi na jednej playliście?

OCENA C dostała same piątki (średnia 5,0) i jest w grupie silnika. Jeśli po
jej wyjęciu różnica znika, to nie jest wynik o silniku, tylko o jednej
playliście. Ten sam test robimy po kolei dla każdej z dziesięciu.

To NIE zmienia progów z 18.08 — to sprawdzenie, na czym werdykt stoi.
"""

import csv
import itertools
import pathlib

import numpy as np

TU = pathlib.Path(__file__).parent


def main() -> int:
    import json
    przydzial = json.loads((TU / "PRZYDZIAL_NIE_OTWIERAC.json")
                           .read_text(encoding="utf-8"))["przydzial"]
    oceny: dict[str, list[float]] = {}
    for p in sorted(TU.glob("SESJA_*_transition_ratings.csv")):
        for r in csv.DictReader(p.open(encoding="utf-8")):
            plej = r["pair_id"].rsplit("_", 1)[0].replace("_", " ")
            oceny.setdefault(plej, []).append(float(r["dj_mixability_rating"]))
    srednie = {k: float(np.mean(v)) for k, v in oceny.items()}

    def licz(bez: str | None) -> tuple[float, float, int]:
        naz = sorted(k for k in srednie if k != bez)
        wart = np.array([srednie[n] for n in naz])
        kontrola = frozenset(i for i, n in enumerate(naz)
                             if przydzial[n] != "SILNIK")

        def delta(k: frozenset) -> float:
            m = np.array([i in k for i in range(len(naz))])
            return float(wart[~m].mean() - wart[m].mean())

        obs = delta(kontrola)
        wsz = [delta(frozenset(k))
               for k in itertools.combinations(range(len(naz)), len(kontrola))]
        return obs, sum(1 for d in wsz if d >= obs - 1e-12) / len(wsz), len(wsz)

    d0, p0, n0 = licz(None)
    print(f"{'bez playlisty':>16} {'grupa':>18} {'delta':>7} {'p':>8} {'ukladow':>8}")
    print(f"{'— (komplet)':>16} {'':>18} {d0:7.3f} {p0:8.4f} {n0:8d}")
    for nazwa in sorted(srednie):
        d, p, n = licz(nazwa)
        grupa = przydzial[nazwa]
        print(f"{nazwa:>16} {grupa:>18} {d:7.3f} {p:8.4f} {n:8d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
