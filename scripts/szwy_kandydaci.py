"""Z tracklist robi KANDYDATÓW NA SZEW — czyli to, po co w ogóle je zbieramy.

Surowe znaczniki z komentarzy nie są jeszcze szwami. Na secie Marlona
Hoffstadta z Boiler Room wypadło 130 znaczników „ID", z czego trzy na
sekundach 5:31, 5:32 i 5:32. To nie są trzy przejścia — to trzy osoby pytające
o ten sam utwór. Gęstość komentarzy mierzy hype, nie muzykę.

Skupienie zamienia ten szum w informację o dwóch wymiarach:

  * GDZIE — środek skupiska to moment, w którym ludzie usłyszeli zmianę;
  * ILU — liczba osób, które zapytały niezależnie. To jest miara pewności,
    której pojedynczy komentarz nie daje.

Dwa progi i powód każdego z nich:

  * OKNO 25 s. Ludzie nie reagują natychmiast — klikają „ID" kilkanaście
    sekund po tym, jak utwór wszedł. Węższe okno rozbija jedno przejście na
    kilka, szersze skleja sąsiednie utwory w szybkim secie.
  * ODSTĘP 45 s między szwami. Poniżej tego w secie klubowym nie ma miejsca
    na przejście; takie skupiska to ta sama zmiana widziana dwa razy.

Czego NIE robimy: nie twierdzimy, że kandydat na szew JEST szwem. To jest
miejsce do posłuchania — DanceLab liczy szew z dźwięku, a nie z komentarzy.
Te dane mówią, GDZIE słuchać.
"""

from __future__ import annotations

import json
import pathlib
import statistics

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")

OKNO_MS = 25_000        # ile trwa reakcja publiczności na zmianę
ODSTEP_MS = 45_000      # minimalny odstęp między dwoma osobnymi szwami


def skup(pozycje: list[dict]) -> list[dict]:
    """Znaczniki → kandydaci na szew. Wejście musi być posortowane po czasie."""
    zt = [p for p in pozycje if p.get("ms") is not None]
    if not zt:
        return []
    zt.sort(key=lambda p: p["ms"])
    grupy: list[list[dict]] = [[zt[0]]]
    for p in zt[1:]:
        if p["ms"] - grupy[-1][-1]["ms"] <= OKNO_MS:
            grupy[-1].append(p)
        else:
            grupy.append([p])

    kandydaci = []
    for g in grupy:
        # Mediana, nie średnia: jeden spóźniony komentarz nie ma przesuwać
        # całego skupiska.
        ms = int(statistics.median(p["ms"] for p in g))
        nazwane = [p for p in g if p["tytul"] != "ID" and p["tytul"]]
        kandydaci.append({
            "ms": ms,
            "czas": (f"{ms // 3600000}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d}"
                     if ms >= 3600000 else f"{ms // 60000}:{ms // 1000 % 60:02d}"),
            "glosow": len(g),
            "osob": len({p.get("autor") for p in g if p.get("autor")}) or len(g),
            "nazwa": (f"{nazwane[0]['wykonawca']} — {nazwane[0]['tytul']}".strip(" —")
                      if nazwane else ""),
            "rozstrzygniety": bool(nazwane),
        })

    # Sklejamy skupiska bliższe niż odstęp — to ta sama zmiana widziana dwa razy.
    scalone: list[dict] = []
    for k in kandydaci:
        if scalone and k["ms"] - scalone[-1]["ms"] < ODSTEP_MS:
            poprzedni = scalone[-1]
            poprzedni["glosow"] += k["glosow"]
            poprzedni["osob"] += k["osob"]
            if not poprzedni["nazwa"] and k["nazwa"]:
                poprzedni["nazwa"] = k["nazwa"]
                poprzedni["rozstrzygniety"] = True
            continue
        scalone.append(k)
    return scalone


def main() -> int:
    d = json.loads((OUT / "tracklisty.json").read_text())
    wynik, wszystkie = [], []
    for w in d:
        k = skup(w["tracklista"])
        if not k:
            continue
        dl = w.get("dlugosc_min")
        wynik.append({
            "ksywa": w.get("ksywa"), "tytul": w.get("tytul"),
            "wydarzenie": w.get("wydarzenie"), "data": w.get("data"),
            "dlugosc_min": dl, "link": w.get("link"),
            "szwow": len(k),
            "szwow_na_godzine": round(len(k) / (dl / 60), 1) if dl else None,
            "rozstrzygnietych": sum(1 for x in k if x["rozstrzygniety"]),
            "szwy": k,
        })
        wszystkie += k

    p = OUT / "szwy_kandydaci.json"
    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))

    gest = [w["szwow_na_godzine"] for w in wynik if w["szwow_na_godzine"]]
    print(f"setów z kandydatami na szew: {len(wynik)}")
    print(f"kandydatów razem: {len(wszystkie)}  "
          f"(surowych znaczników było {sum(len(x['tracklista']) for x in d)})")
    print(f"  z nazwą utworu:      {sum(1 for k in wszystkie if k['rozstrzygniety'])}")
    print(f"  potwierdzonych >=2 osobami: {sum(1 for k in wszystkie if k['osob'] >= 2)}")
    if gest:
        print(f"  szwów na godzinę: mediana {statistics.median(gest):.1f}, "
              f"od {min(gest):.1f} do {max(gest):.1f}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
