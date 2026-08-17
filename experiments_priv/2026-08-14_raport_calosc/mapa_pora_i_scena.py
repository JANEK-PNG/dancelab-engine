"""MAPA — co ci artyści realnie grali, z rozbiciem na porę i typ sceny.

Odpowiada na jedno wąskie, sprawdzalne pytanie produktowe:

    „Wasza scena o czwartej rano — te osoby faktycznie tam grają,
     te tylko wyglądają na pasujące."

To NIE jest uczenie maszynowe. To zapytanie do arkusza. Każde zdanie da się
sprawdzić klikając w link do setu.

UCZCIWOŚĆ POKRYCIA, wypisywana zawsze na górze: pole `rola` jest wypełnione
tylko dla części miksów. Artysta bez ani jednego opisanego setu NIE jest
„niepasujący" — jest NIEOPISANY, i tak musi być pokazany.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections import Counter, defaultdict

import openpyxl

KATALOG = pathlib.Path(__file__).parent
MAPA = KATALOG.parent / "2026-08-03_dj_mapa" / "mapa_djow_audioriver_garbicz.xlsx"

PORY = ("otwarcie", "popoludnie", "wschod-slonca", "poranek", "noc", "zamkniecie")


def wczytaj():
    wb = openpyxl.load_workbook(MAPA, read_only=True, data_only=True)
    ws = wb["Miksy"]
    it = ws.iter_rows(values_only=True)
    nag = list(next(it))
    idx = {k: nag.index(k) for k in
           ("ksywa", "tytuł", "wydarzenie", "typ", "scena", "rola",
            "data", "link", "pewność", "długość (min)")}
    wiersze = []
    for r in it:
        wiersze.append({k: (r[i] if i < len(r) else None) for k, i in idx.items()})
    return wiersze


def rok(w) -> int | None:
    d = str(w.get("data") or "")
    for kawalek in (d[:4],):
        if kawalek.isdigit():
            return int(kawalek)
    return None


def main() -> int:
    pora_szukana = sys.argv[1] if len(sys.argv) > 1 else "noc"
    od_roku = int(sys.argv[2]) if len(sys.argv) > 2 else 2023

    wiersze = wczytaj()
    print(f"MIKSÓW W MAPIE: {len(wiersze)}")

    # --- pokrycie, zanim jakakolwiek liczba ---
    z_rola = [w for w in wiersze if w["rola"]]
    z_scena = [w for w in wiersze if w["scena"]]
    z_data = [w for w in wiersze if rok(w)]
    print(f"\nPOKRYCIE — ile w ogóle da się powiedzieć")
    print(f"  z opisaną porą:   {len(z_rola):5d}  ({100*len(z_rola)/len(wiersze):4.1f}%)")
    print(f"  z opisaną sceną:  {len(z_scena):5d}  ({100*len(z_scena)/len(wiersze):4.1f}%)")
    print(f"  z datą:           {len(z_data):5d}  ({100*len(z_data)/len(wiersze):4.1f}%)")
    print(f"  ⇒ o {100-100*len(z_rola)/len(wiersze):.0f}% miksów NIE WIEMY, o której grały.")
    print("    Brak opisu to nie-wiem, a nie nie-grał.")

    swieze = [w for w in z_rola if (rok(w) or 0) >= od_roku]
    print(f"\nOKNO: od {od_roku} · miksów z porą w oknie: {len(swieze)}")
    print(f"rozkład pór w oknie: "
          f"{dict(Counter(str(w['rola']) for w in swieze).most_common())}")

    # --- kto realnie grał o tej porze ---
    grali = defaultdict(list)
    for w in swieze:
        if str(w["rola"]) == pora_szukana:
            grali[str(w["ksywa"])].append(w)
    print(f"\n{'='*66}")
    print(f"ARTYSCI, KTORZY REALNIE GRALI {pora_szukana.upper()} OD {od_roku}")
    print(f"{'='*66}")
    print(f"{'artysta':28s} {'setów':>6s}  sceny / wydarzenia")
    for ksywa, lista in sorted(grali.items(), key=lambda kv: -len(kv[1]))[:20]:
        sceny = [str(x["scena"] or x["wydarzenie"] or "?") for x in lista]
        opis = ", ".join(sorted(set(sceny))[:3])
        print(f"{ksywa[:28]:28s} {len(lista):6d}  {opis[:34]}")
    print(f"\nrazem artystow z potwierdzonym {pora_szukana}: {len(grali)}")

    # --- kto ma sety w oknie, ale NIGDY o tej porze ---
    wszyscy_w_oknie = defaultdict(list)
    for w in swieze:
        wszyscy_w_oknie[str(w["ksywa"])].append(str(w["rola"]))
    nigdy = {k: Counter(v) for k, v in wszyscy_w_oknie.items() if k not in grali}
    print(f"\n{'='*66}")
    print(f"MAJA OPISANE SETY, ALE ANI RAZU {pora_szukana.upper()}")
    print(f"{'='*66}")
    print("to jest mocne twierdzenie: wiemy, o której grali, i nigdy o tej porze")
    print(f"{'artysta':28s} {'setów':>6s}  co grali zamiast")
    for ksywa, licz in sorted(nigdy.items(), key=lambda kv: -sum(kv[1].values()))[:15]:
        zamiast = ", ".join(f"{p}×{n}" for p, n in licz.most_common(3))
        print(f"{ksywa[:28]:28s} {sum(licz.values()):6d}  {zamiast[:34]}")
    print(f"\nrazem: {len(nigdy)} artystów")

    # --- i ci, o których po prostu nie wiemy ---
    wszystkie_ksywy = {str(w["ksywa"]) for w in wiersze if w["ksywa"]}
    nieopisani = wszystkie_ksywy - set(wszyscy_w_oknie)
    print(f"\nNIEOPISANI (mają miksy, ale żaden z porą w oknie): {len(nieopisani)}")
    print("  => o nich NIE WOLNO powiedziec ani ze graja, ani ze nie graja.")

    wynik = {
        "pora": pora_szukana, "od_roku": od_roku,
        "pokrycie": {"miksow": len(wiersze), "z_pora": len(z_rola),
                     "z_scena": len(z_scena), "w_oknie": len(swieze)},
        "grali": {k: len(v) for k, v in sorted(grali.items(), key=lambda kv: -len(kv[1]))},
        "nigdy_o_tej_porze": {k: dict(v) for k, v in nigdy.items()},
        "nieopisani_liczba": len(nieopisani),
    }
    cel = KATALOG / f"mapa_pora_{pora_szukana}.json"
    cel.write_text(json.dumps(wynik, ensure_ascii=False), encoding="utf-8")
    print(f"\nzapisano: {cel.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
