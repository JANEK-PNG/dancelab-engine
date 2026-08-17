"""Wisłoujście — line-up 2026 i PEŁNY PROGRAM, prosto ze strony festiwalu.

Wisłoujście (Twierdza Wisłoujście, Gdańsk, 21-23.08.2026, IX edycja) różni się
od dwóch poprzednich festiwali dwiema rzeczami, które warto zapisać:

  * LINE-UP JEST WYŁĄCZNIE POLSKI. To deklaracja organizatora, nie nasz wniosek.
    Dla mapy DJ-ów znaczy to, że Wisłoujście dokłada warstwę, której Garbicz
    i Audioriver nie mają — polski underground bez zagranicznych nazwisk.
  * SCENA NIESIE GATUNEK. Cztery parkiety, każdy opisany przez festiwal wprost:
    Twierdza — techno i melodic, Szaniec — tech-house, disco, electro,
    Raj — house, downtempo, electronica, Bastion — industrial, acid, rave.
    Nigdzie indziej `scena` nie mówiła tyle o tym, CO ktoś zagra.

Strona ładuje wszystko javascriptem, więc ani WebFetch, ani czytnik nic nie
widzą. Ale `js/lineup.js` i `js/timetable.js` pobierają dwa zwykłe pliki:
`data/lineup.json` i `data/schedule.json`. Drugi z nich to **pełny timetable
z godzinami start-koniec, per scena, per dzień** — najlepsze dane programowe,
jakie mieliśmy dla któregokolwiek festiwalu.

Program NIE jest listą nagrań: festiwal odbędzie się dopiero 21 sierpnia.
To jest zapis PLANU, i tak go trzymamy — osobno od `miksy.json`, w którym
leżą rzeczy, których da się posłuchać.
"""

from __future__ import annotations

import json
import pathlib
import re
import urllib.request

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
BAZA = "https://wisloujscie.com/data"

SCENY = {"twierdza": "Twierdza", "raj": "Raj",
         "szaniec": "Szaniec", "bastion": "Bastion"}

# Charakter parkietu wg samego festiwalu — to jest jego opis, nie nasza ocena.
CHARAKTER = {
    "Twierdza": "techno, progressive, melodic — dziedziniec fortecy",
    "Bastion": "industrial, acid, rave — surowo, w lesie",
    "Raj": "house, downtempo, electronica — między drzewami, strefa chillout",
    "Szaniec": "tech-house, disco, electro — drewniana, kameralna",
}


def _js(sciezka: str):
    req = urllib.request.Request(f"{BAZA}/{sciezka}", headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def rola_z_slotu(i: int, ile: int, start: str) -> str:
    """Miejsce w programie da się tu wyliczyć, bo znamy CAŁY program sceny.

    To jedyny festiwal w bazie, przy którym `rola` nie jest wyłuskana z opisu,
    tylko wynika z pozycji w timetable — i dlatego jest pewna.
    """
    godz = int(start.split(":")[0])
    if 4 <= godz <= 9:
        return "wschod-slonca"
    if i == 0:
        return "otwarcie"
    if i == ile - 1:
        return "zamkniecie"
    if 0 <= godz <= 3:
        return "noc"
    if godz >= 22:
        return "peak"
    return ""


def main() -> int:
    lineup = _js("lineup.json")
    plan = _js("schedule.json")

    # ── program ──
    program, artysci = [], {}
    for dzien in plan["days"]:
        data = dzien.get("date") or ""
        for klucz, scena in SCENY.items():
            sloty = [s for s in dzien.get(klucz, []) if not s.get("placeholder")]
            for i, s in enumerate(sloty):
                nazwa = (s.get("name") or "").strip()
                if not nazwa:
                    continue
                program.append({
                    "ksywa": nazwa, "wydarzenie": "Wisłoujście", "typ": "festiwal",
                    "scena": scena, "charakter_sceny": CHARAKTER[scena],
                    "data": data, "dzien": dzien.get("label") or "",
                    "start": s.get("start"), "koniec": s.get("end"),
                    "czas": f"{s.get('start')}-{s.get('end')}",
                    "rola": rola_z_slotu(i, len(sloty), s.get("start") or "00:00"),
                    "format": ("b2b" if re.search(r"\bb2b\b", nazwa, re.I) else "dj-set"),
                })
                artysci.setdefault(nazwa, set()).add(scena)

    for a in lineup.get("artists", []):
        nazwa = (a.get("name") or "").strip()
        if nazwa:
            artysci.setdefault(nazwa, set()).add(
                SCENY.get(a.get("stage", ""), ""))

    (OUT / "wisloujscie_program.json").write_text(
        json.dumps(program, ensure_ascii=False, indent=1))

    # ── dopisanie do listy festiwalowej ──
    fest = json.loads((OUT / "festiwale.json").read_text())
    klucze = {v["ksywa"] for v in fest.values()}
    dodani = 0
    for nazwa, sceny in sorted(artysci.items()):
        opis = "Wisłoujście 21-23.08"
        if nazwa in klucze:
            for v in fest.values():
                if v["ksywa"] == nazwa and opis not in v["wystapienia"]:
                    v["wystapienia"].append(opis)
            continue
        fest[nazwa] = {"ksywa": nazwa, "wystapienia": [opis]}
        dodani += 1
    (OUT / "festiwale.json").write_text(json.dumps(fest, ensure_ascii=False, indent=1))

    print(f"artystów Wisłoujścia: {len(artysci)}  (nowych w bazie: {dodani})")
    print(f"slotów w programie:   {len(program)}")
    for s in SCENY.values():
        n = sum(1 for p in program if p["scena"] == s)
        print(f"  {s:10s} {n:3d} slotów")
    print(f"dni: {[d.get('label') for d in plan['days']]}")
    print(f"zapisane: {OUT / 'wisloujscie_program.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
