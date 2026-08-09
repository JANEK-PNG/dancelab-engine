"""Grupy brzmieniowe DJ-ów — rodziny wyliczone z POMIARU, nie z opinii.

Decyzja Janka 09.08 („zróbmy grupowanie tych DJ-ów") poprzedzona pomiarem
dwóch odrzuconych pomysłów:
* gatunek — pole `genres` jest puste w 100% naszych profili DJ-skich;
  dopisanie go 284 nazwiskom byłoby zgadywaniem;
* miejsce/event — w tytułach miksów mamy Boiler Room (301) i Warehouse
  Project (61), ale to jest ŹRÓDŁO NASZEGO SCRAPINGU, nie tożsamość
  artysty; grupowanie po tym kłamałoby.

Zostaje rzecz zmierzona: centroid brzmienia (CLAP) każdego DJ-a. Klastrujemy
go k-średnimi z ustalonym ziarnem (ten sam podział przy każdym uruchomieniu)
i NAZYWAMY GRUPĘ JEJ NAJBARDZIEJ TYPOWYMI CZŁONKAMI — żadnych wymyślonych
etykiet gatunkowych, bo tych nie zmierzyliśmy.
"""

from __future__ import annotations

ZIARNO = 7
GRUP = 8


def grupuj(djs: dict, k: int = GRUP, ziarno: int = ZIARNO
           ) -> list[tuple[str, list[tuple[str, int, float | None]]]]:
    """[(etykieta grupy, [(DJ, n_wektorów, mediana skoku)])].

    Grupy malejąco po liczebności, w środku najbardziej typowi najpierw
    (najbliżej środka grupy). Bez scikit-learn albo przy zbyt małej próbce
    zwracamy JEDNĄ grupę „wszyscy" — nigdy zmyślonego podziału."""
    nazwy = sorted(djs)
    if len(nazwy) < k * 2:
        return [("wszyscy DJ-e", _wiersze(nazwy, djs))]
    try:
        import numpy as np
        from sklearn.cluster import KMeans
    except ImportError:
        return [("wszyscy DJ-e (brak biblioteki do grupowania)",
                 _wiersze(nazwy, djs))]

    X = np.array([djs[n]["centroid"] for n in nazwy], dtype=float)
    X /= (np.linalg.norm(X, axis=1, keepdims=True) + 1e-12)
    model = KMeans(n_clusters=k, n_init=10, random_state=ziarno).fit(X)

    grupy: list[tuple[str, list[tuple[str, int, float | None]]]] = []
    for numer in range(k):
        indeksy = [i for i, lab in enumerate(model.labels_) if lab == numer]
        if not indeksy:
            continue
        srodek = model.cluster_centers_[numer]
        srodek = srodek / (float(np.linalg.norm(srodek)) + 1e-12)
        # najbardziej typowy = najbliżej środka grupy
        indeksy.sort(key=lambda i: -float(X[i] @ srodek))
        czlonkowie = [nazwy[i] for i in indeksy]
        etykieta = "brzmi jak: " + " · ".join(czlonkowie[:3])
        grupy.append((etykieta, _wiersze(czlonkowie, djs)))
    grupy.sort(key=lambda g: -len(g[1]))
    return grupy


def _wiersze(nazwy, djs) -> list[tuple[str, int, float | None]]:
    return [(n, int(djs[n]["n_tracks"]), djs[n].get("cos_median"))
            for n in nazwy]


def opis(dj: str, n: int, skok: float | None) -> str:
    """Wiersz DJ-a: liczba wektorów i mediana skoku (im niżej, tym odważniej
    ten DJ przeskakuje między utworami — zmierzone na jego setach)."""
    if skok is None:
        return f"{dj}  ({n} wekt.)"
    odwaga = "odważny" if skok < 0.70 else ("gładki" if skok > 0.80 else "")
    return f"{dj}  ({n} wekt., skok {skok:.2f}{'  ' + odwaga if odwaga else ''})"
