"""Czy realny set to JEDEN łuk, czy kilka bloków? Pomiar na sesjach Janka.

POWÓD. `set_builder._set_arc_target_profile` dla łuku "build" wystawia JEDNĄ
szeroką wspinaczkę (wykładnik 1,15 od percentyla 15 do 85), a `_arc_profile_
candidates` dokłada twardą regułę „nie schodź niżej niż o `_BUILD_MAX_DROP_
FRACTION`". To jest MODEL, nie pomiar — nigdy nie sprawdziliśmy, czy realne
sety tak wyglądają. Zanim dołożymy brief wieloblokowy, trzeba wiedzieć, czy
jeden łuk jest po prostu ZŁY.

DANE. `DjmdSongHistory` z Rekordboxa: kolejność z `TrackNo` (tak samo jak
`validate_on_my_history.py` i `pomiar_1_2_historia.py` — nie zmieniać bez
powodu). Energia utworu liczona DOKŁADNIE tak, jak liczy ją silnik przy
budowie setu (`set_builder.track_energy` = średni RMS), żeby testować model
na jego własnej mierze.

UCZCIWE OGRANICZENIE. Średni RMS niesie też głośność masteringu, nie samą
energię muzyczną. Nie unieważnia to testu — silnik układa sety na TEJ SAMEJ
liczbie, więc jeśli realne sety nie układają się w jego łuk na jego własnej
mierze, to jest wynik o modelu, nie o RMS-ie. Ale nie wolno z tego czytać
„tak wygląda energia na parkiecie".

Użycie:
    .venv/bin/python experiments_priv/2026-08-10_ksztalt_setu/ksztalt_realnych_setow.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import unicodedata

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
KATALOG = pathlib.Path(__file__).resolve().parent
PULA = KORZEN / "experiments_priv/2026-07-30_rebuild/processed"

MIN_UTWOROW = 8          # krótsza sesja nie ma kształtu
MIN_POKRYCIE = 0.60      # poniżej tego krzywa jest dziurawa i nic nie mówi


def nfc(tekst: str) -> str:
    return unicodedata.normalize("NFC", tekst)


def energie_puli() -> dict[str, float]:
    """{nazwa pliku NFC: energia} — ta sama miara, której używa set_builder."""
    from dancelab.decision.set_builder import track_energy
    from dancelab.storage.repositories import FileAnalysisRepository

    repo = FileAnalysisRepository(PULA)
    out: dict[str, float] = {}
    for tid in repo.list_track_ids():
        a = repo.get(tid)
        sciezka = str(a.track.source_path or "")
        if not sciezka.startswith("/"):
            continue
        e = track_energy(a)
        if e > 0:
            out[nfc(pathlib.Path(sciezka).name)] = e
    return out


def sesje() -> list[tuple[str, list[str]]]:
    """[(nazwa sesji, [nazwa pliku NFC…])] w kolejności grania."""
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()
    nazwy_plikow = {str(c.ID): nfc(getattr(c, "FileNameL", None) or "")
                    for c in db.get_content()}
    kolejnosc: dict[str, list[str]] = {}
    for row in (db.session.query(tables.DjmdSongHistory)
                .order_by(tables.DjmdSongHistory.TrackNo).all()):
        kolejnosc.setdefault(row.HistoryID, []).append(str(row.ContentID))
    etykiety = {h.ID: h.Name for h in db.session.query(tables.DjmdHistory).all()}
    out = []
    for hid, ids in kolejnosc.items():
        pliki = [nazwy_plikow.get(i, "") for i in ids]
        out.append((etykiety.get(hid, hid), pliki))
    return out


def znormalizuj(wartosci: list[float]) -> list[float]:
    lo, hi = min(wartosci), max(wartosci)
    rozpietosc = max(hi - lo, 1e-9)
    return [(w - lo) / rozpietosc for w in wartosci]


def cel_build(n: int) -> list[float]:
    """Kopia kształtu z `_set_arc_target_profile` dla arc='build', 0→1."""
    if n == 1:
        return [0.0]
    return [(i / (n - 1)) ** 1.15 for i in range(n)]


def dopasuj_bloki(krzywa: list[float], ile_blokow: int) -> float:
    """Średni błąd bezwzględny najlepszego podziału na `ile_blokow` poziomów.

    Każdy blok = jedna stała wartość (jego średnia). Szukamy podziału
    minimalizującego błąd — programowanie dynamiczne, bo n jest małe.
    """
    import numpy as np

    n = len(krzywa)
    x = np.asarray(krzywa, dtype=float)
    # koszt[i][j] = suma błędów bezwzględnych odcinka [i, j)
    koszt = np.full((n + 1, n + 1), np.inf)
    for i in range(n):
        for j in range(i + 1, n + 1):
            odc = x[i:j]
            koszt[i][j] = float(np.abs(odc - odc.mean()).sum())
    naj = np.full((ile_blokow + 1, n + 1), np.inf)
    naj[0][0] = 0.0
    for b in range(1, ile_blokow + 1):
        for j in range(1, n + 1):
            for i in range(j):
                if naj[b - 1][i] + koszt[i][j] < naj[b][j]:
                    naj[b][j] = naj[b - 1][i] + koszt[i][j]
    return float(naj[ile_blokow][n] / n)


def test_permutacyjny(krzywa: list[float], ile_blokow: int,
                      powtorzen: int = 300) -> tuple[float, float, float]:
    """(błąd realny, mediana błędu po przetasowaniu, p).

    KONTROLA UCZCIWOŚCI. Model blokowy ma swobodne parametry, więc dopasuje się
    do CZEGOKOLWIEK — porównanie go ze sztywnym łukiem samo w sobie niczego nie
    dowodzi. Tasujemy więc TE SAME wartości energii i dopasowujemy bloki tak
    samo. Jeśli realna kolejność da wyraźnie mniejszy błąd niż przetasowana,
    to znaczy, że struktura siedzi w KOLEJNOŚCI, a nie w swobodzie modelu.
    Test niczego nie zakłada o rozkładzie energii — bierze go dokładnie takim,
    jaki jest, i pyta wyłącznie o układ.
    """
    import numpy as np

    rng = np.random.default_rng(20260810)   # stałe ziarno — wynik powtarzalny
    realny = dopasuj_bloki(krzywa, ile_blokow)
    losowe = []
    for _ in range(powtorzen):
        losowe.append(dopasuj_bloki(list(rng.permutation(krzywa)), ile_blokow))
    lepszych = sum(1 for x in losowe if x <= realny)
    return realny, float(np.median(losowe)), (lepszych + 1) / (powtorzen + 1)


def main() -> int:
    import numpy as np
    from scipy.stats import spearmanr

    energie = energie_puli()
    print(f"pula z energią: {len(energie)} plików\n")

    wiersze = []
    for nazwa, pliki in sesje():
        if len(pliki) < MIN_UTWOROW:
            continue
        wart = [energie.get(p) for p in pliki]
        znane = [w for w in wart if w is not None]
        pokrycie = len(znane) / len(wart)
        if pokrycie < MIN_POKRYCIE or len(znane) < MIN_UTWOROW:
            continue
        krzywa = znormalizuj(znane)
        n = len(krzywa)
        rho = float(spearmanr(range(n), krzywa).statistic)
        cel = cel_build(n)
        blad_luk = float(np.mean(np.abs(np.asarray(krzywa) - np.asarray(cel))))
        blad_1 = dopasuj_bloki(krzywa, 1)
        blad_2 = dopasuj_bloki(krzywa, 2)
        blad_3 = dopasuj_bloki(krzywa, 3)
        spadki = sum(1 for i in range(1, n) if krzywa[i] < krzywa[i - 1] - 0.08)
        # SPRAWIEDLIWE PORÓWNANIE: oba modele bez ANI JEDNEGO swobodnego
        # parametru — nasz łuk kontra płaska linia w połowie skali.
        blad_plaski = float(np.mean(np.abs(np.asarray(krzywa) - 0.5)))
        realny2, los2, p2 = test_permutacyjny(krzywa, 2)
        wiersze.append(dict(sesja=nazwa, n=n, pokrycie=pokrycie, rho=rho,
                            blad_luk=blad_luk, blad_plaski=blad_plaski,
                            blad_1=blad_1, blad_2=blad_2, blad_3=blad_3,
                            spadki=spadki, perm_realny=realny2,
                            perm_losowy=los2, perm_p=p2))

    if not wiersze:
        print("brak sesji spełniających próg")
        return 1

    print(f"{'sesja':26} {'n':>3} {'pokr':>5} {'rho':>6} "
          f"{'łuk':>6} {'1 blok':>7} {'2 bloki':>8} {'3 bloki':>8} {'spadki':>7}")
    for w in wiersze:
        print(f"{w['sesja'][:26]:26} {w['n']:3} {w['pokrycie']:5.0%} "
              f"{w['rho']:+6.2f} {w['blad_luk']:6.3f} {w['blad_1']:7.3f} "
              f"{w['blad_2']:8.3f} {w['blad_3']:8.3f} {w['spadki']:7}")

    n_ses = len(wiersze)
    print(f"\n--- {n_ses} sesji, {sum(w['n'] for w in wiersze)} utworów ---")
    print(f"mediana rho (pozycja vs energia): "
          f"{np.median([w['rho'] for w in wiersze]):+.3f}")
    print(f"sesji rosnących (rho > +0,3):  "
          f"{sum(1 for w in wiersze if w['rho'] > 0.3)}/{n_ses}")
    print(f"sesji bez kierunku (|rho| ≤ 0,3): "
          f"{sum(1 for w in wiersze if abs(w['rho']) <= 0.3)}/{n_ses}")
    print(f"sesji malejących (rho < −0,3):  "
          f"{sum(1 for w in wiersze if w['rho'] < -0.3)}/{n_ses}")
    print("\n== TEST 1: modele BEZ swobodnych parametrów (sprawiedliwy) ==")
    for etykieta, klucz in (("nasz łuk build", "blad_luk"),
                            ("płaska linia 0,5", "blad_plaski")):
        print(f"  mediana błędu — {etykieta:17}: "
              f"{np.median([w[klucz] for w in wiersze]):.3f}")
    plaski_lepszy = sum(1 for w in wiersze
                        if w["blad_plaski"] < w["blad_luk"])
    print(f"  płaska linia opisuje sesję lepiej niż nasz łuk: "
          f"{plaski_lepszy}/{n_ses}")

    print("\n== TEST 2: modele Z dopasowaniem (NIE porównywać z łukiem) ==")
    for etykieta, klucz in (("1 blok", "blad_1"), ("2 bloki", "blad_2"),
                            ("3 bloki", "blad_3")):
        print(f"  mediana błędu — {etykieta:17}: "
              f"{np.median([w[klucz] for w in wiersze]):.3f}")

    print("\n== TEST 3: permutacyjny — czy struktura siedzi w KOLEJNOŚCI ==")
    print(f"  mediana błędu 2 bloków, kolejność realna:      "
          f"{np.median([w['perm_realny'] for w in wiersze]):.3f}")
    print(f"  mediana błędu 2 bloków, kolejność przetasowana: "
          f"{np.median([w['perm_losowy'] for w in wiersze]):.3f}")
    istotne = sum(1 for w in wiersze if w["perm_p"] < 0.05)
    print(f"  sesji, w których realna kolejność bije tasowanie (p < 0,05): "
          f"{istotne}/{n_ses}")
    print(f"  mediana p: {np.median([w['perm_p'] for w in wiersze]):.3f}")

    print(f"\nmediana spadków >8% na sesję: "
          f"{np.median([w['spadki'] for w in wiersze]):.1f} "
          f"(nasz łuk zabrania ich w ogóle)")

    (KATALOG / "wynik_ksztalt.json").write_text(
        json.dumps(wiersze, ensure_ascii=False, indent=2))
    print(f"\nzapisane: {KATALOG / 'wynik_ksztalt.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
