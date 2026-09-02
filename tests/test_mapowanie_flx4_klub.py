"""Mapowanie 1:1 FLX4 ↔ klub (Janek 29.08): sprawdzian LICZBOWY, nie deklaracja.

Cztery liczby na górze panelu klubu (jest / inaczej / brak / pułapka) muszą
zgadzać się z parami w `mapowanie.json`: każda kontrolka „jest/inaczej/
pułapka" ma ≥1 parę (poza jawnymi wyjątkami), żadna „brak" nie ma pary,
a każda kontrolka FLX4 jest albo sparowana, albo nazwana jako bez
odpowiednika — dokładnie jedno z dwojga.
"""

import json
import pathlib

KORZEN = pathlib.Path(__file__).resolve().parents[1]
MAPA = json.loads((KORZEN / "docs/sprzet-klubowy/mapowanie.json").read_text(encoding="utf-8"))
KONTR = json.loads((KORZEN / "docs/sprzet-klubowy/kontrolki.json").read_text(encoding="utf-8"))
UKLAD = json.loads((KORZEN / "docs/sprzet-klubowy/uklad.json").read_text(encoding="utf-8"))

STAN = {k["nazwa"]: k["stan"] for u in KONTR["urzadzenia"] for s in u["sekcje"] for k in s["kontrolki"]}
URZ_KLUCZA = {k["nazwa"]: u["id"] for u in KONTR["urzadzenia"] for s in u["sekcje"] for k in s["kontrolki"]}
FLX4 = set(MAPA["flx4_kontrolki"])
PARY = MAPA["pary"]


def test_pary_wskazuja_istniejace_kontrolki_po_obu_stronach():
    for p in PARY:
        assert p["flx4"] in FLX4, p
        assert p["klub"] in STAN, p
        assert p["urzadzenie"] in ("cdj_l", "cdj_p", "djm", "flx4"), p
        # urządzenie pary zgadza się z urządzeniem, pod którym klub opisuje kontrolkę
        oczekiwane = {"cdj": ("cdj_l", "cdj_p"), "djm": ("djm",), "flx4": ("flx4",)}[URZ_KLUCZA[p["klub"]]]
        assert p["urzadzenie"] in oczekiwane, p


def test_relacja_pary_to_stan_z_kontrolki_json_chyba_ze_jawnie_nadpisany():
    for p in PARY:
        if p.get("nadpisuje_stan"):
            assert p.get("uwaga"), f"nadpisanie bez powodu: {p}"
            continue
        assert p["relacja"] == STAN[p["klub"]], p


def test_cztery_liczby_klubu_zgadzaja_sie_z_mapowaniem():
    sparowane = {p["klub"] for p in PARY}
    wyjatki = {x["klub"] for x in MAPA["klub_bez_kontrolki_flx4"]}
    for klucz, stan in STAN.items():
        if stan == "brak":
            assert klucz not in sparowane, f"„{klucz}” ma stan brak, a jest sparowane"
        else:
            assert klucz in sparowane or klucz in wyjatki, f"„{klucz}” ({stan}) bez pary"
    for x in MAPA["klub_bez_kontrolki_flx4"]:
        assert x["klub"] in STAN and STAN[x["klub"]] != "brak" and x.get("powod")


def test_kazda_kontrolka_flx4_jest_sparowana_albo_nazwana_bez_odpowiednika():
    sparowane = {p["flx4"] for p in PARY}
    bez = {x["id"] for x in MAPA["flx4_bez_odpowiednika"]}
    assert sparowane & bez == set(), sparowane & bez
    assert sparowane | bez == FLX4, FLX4 - (sparowane | bez)
    for x in MAPA["flx4_bez_odpowiednika"]:
        assert x.get("powod"), x


def test_decki_sa_symetryczne():
    """d1 → lewy CDJ, d2 → prawy; co ma jeden deck, ma i drugi."""
    for p in PARY:
        if p["flx4"].startswith("d1_"):
            blizniak = dict(p, flx4="d2_" + p["flx4"][3:],
                            urzadzenie="cdj_p" if p["urzadzenie"] == "cdj_l" else p["urzadzenie"])
            assert blizniak in PARY, blizniak
    for p in PARY:
        if p["flx4"] in ("load1", "browse"):
            assert p["urzadzenie"] == "cdj_l" or p["flx4"] == "browse"


def test_kazdy_klubowy_klucz_pary_jest_narysowany():
    """Para na kontrolkę, której rysunek nie ma, byłaby podświetleniem pustki."""
    narysowane = {e["k"] for u in UKLAD["urzadzenia"] for e in (u.get("elementy") or [])}
    for p in PARY:
        if p["urzadzenie"] != "flx4":
            assert p["klub"] in narysowane, p["klub"]
