"""Scalenie pomiarów z manifestu do tabel UTWORY i SZWY.

Dlaczego osobno od przeliczania: energia, groove i bas są normalizowane 0–1
percentylowo po CAŁEJ policzonej puli — normalizacja w trakcie biegu
zmieniałaby znaczenie liczb między wierszami zapisanymi wcześniej i później.

Co wypełnia:
  UTWORY: bpm, bpm_pewnosc, tonacja, tonacja_klasyczna, tonacja_pewnosc,
          energia, gestosc_groove, obecnosc_basu, dlugosc_s,
          analiza_wersja, analiza_data
  SZWY:   bpm_z/do, delta_bpm, delta_bpm_proc (względem WYCHODZĄCEGO),
          tonacja_z/do, zgodnosc_harmoniczna (słownik szkieletu),
          energia_z/do, delta_energii, analiza_wersja, analiza_data

Zgodność harmoniczną liczy silnik (`decision/harmonic.harmonic_relation`),
nie własna reimplementacja. Mapowanie na słownik szkieletu:
  exact → idealna · adjacent_same_mode → sasiednia ·
  relative_major_minor → wzgledna · cautious/risky → zadna ·
  unknown → puste pole (brak wiedzy to nie „żadna zgodność").

Czego NIE wypełnia: dlugosc_przejscia_s, typ_przejscia, bas_wstrzymany —
te wymagają audio miksu wokół szwu, nie próbek utworów.

Przed nadpisaniem robi kopie `*.przed_scaleniem.json`.

Użycie:
    .venv/bin/python scal_pomiary.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
KATALOG = pathlib.Path(__file__).resolve().parent
WERSJA = "deezer-preview-30s"
DATA = "2026-08-11"

MAPA_HARMONII = {"exact": "idealna", "adjacent_same_mode": "sasiednia",
                 "relative_major_minor": "wzgledna", "cautious": "zadna",
                 "risky": "zadna", "unknown": ""}


def percentyle(wartosci: dict[str, float]) -> dict[str, float]:
    """{id: surowa} → {id: pozycja 0–1 w policzonej puli}."""
    posortowane = sorted(wartosci.values())
    n = len(posortowane)
    if n < 2:
        return {k: 0.5 for k in wartosci}
    import bisect
    return {k: round(bisect.bisect_left(posortowane, v) / (n - 1), 3)
            for k, v in wartosci.items()}


def main() -> int:
    from dancelab.decision.harmonic import harmonic_relation

    pomiary = {}
    for linia in (KATALOG / "pomiar_utworow.jsonl").read_text().splitlines():
        w = json.loads(linia)
        if w.get("status") == "ok":
            pomiary[w["utwor_id"]] = w      # późniejszy wpis wygrywa
    print(f"pomiarów ok: {len(pomiary)}")

    # normalizacja 0–1 po całej puli — dopiero teraz, na komplecie
    for surowe, kolumna in (("energia_surowa", "energia"),
                            ("groove_surowy", "gestosc_groove"),
                            ("bas_surowy", "obecnosc_basu")):
        maja = {i: w[surowe] for i, w in pomiary.items()
                if w.get(surowe) is not None}
        znorm = percentyle(maja)
        for i, v in znorm.items():
            pomiary[i][kolumna] = v

    # UTWORY
    sciezka_u = KATALOG / "encje_utwor.json"
    shutil.copy2(sciezka_u, sciezka_u.with_suffix(".przed_scaleniem.json"))
    utwory = json.loads(sciezka_u.read_text())
    trafione = 0
    for x in utwory:
        w = pomiary.get(x["utwor_id"])
        if not w:
            continue
        trafione += 1
        x["bpm"] = round(w["bpm"], 1) if w.get("bpm") else ""
        x["bpm_pewnosc"] = round(w["bpm_pewnosc"], 2) if w.get("bpm_pewnosc") is not None else ""
        x["tonacja"] = w.get("tonacja") or ""
        x["tonacja_klasyczna"] = w.get("tonacja_klasyczna") or ""
        x["tonacja_pewnosc"] = round(w["tonacja_pewnosc"], 2) if w.get("tonacja_pewnosc") is not None else ""
        x["energia"] = w.get("energia", "")
        x["gestosc_groove"] = w.get("gestosc_groove", "")
        x["obecnosc_basu"] = w.get("obecnosc_basu", "")
        x["dlugosc_s"] = w.get("dlugosc_s") or ""
        x["analiza_wersja"] = WERSJA
        x["analiza_data"] = DATA
    sciezka_u.write_text(json.dumps(utwory, ensure_ascii=False, indent=1))
    print(f"UTWORY: wypełnione {trafione} z {len(utwory)}")

    # SZWY
    sciezka_s = KATALOG / "fakty_szew.json"
    shutil.copy2(sciezka_s, sciezka_s.with_suffix(".przed_scaleniem.json"))
    szwy = json.loads(sciezka_s.read_text())
    pelne = jednostronne = 0
    for sz in szwy:
        wz = pomiary.get(sz.get("utwor_z_id") or "")
        wdo = pomiary.get(sz.get("utwor_do_id") or "")
        if not wz and not wdo:
            continue
        if wz and wz.get("bpm"):
            sz["bpm_z"] = round(wz["bpm"], 1)
            sz["tonacja_z"] = wz.get("tonacja") or ""
            sz["energia_z"] = wz.get("energia", "")
        if wdo and wdo.get("bpm"):
            sz["bpm_do"] = round(wdo["bpm"], 1)
            sz["tonacja_do"] = wdo.get("tonacja") or ""
            sz["energia_do"] = wdo.get("energia", "")
        if wz and wdo and wz.get("bpm") and wdo.get("bpm"):
            pelne += 1
            delta = wdo["bpm"] - wz["bpm"]
            sz["delta_bpm"] = round(delta, 1)
            sz["delta_bpm_proc"] = round(100.0 * delta / wz["bpm"], 1)
            rel = harmonic_relation(wz.get("tonacja"), wdo.get("tonacja"))
            sz["zgodnosc_harmoniczna"] = MAPA_HARMONII.get(rel, "")
            if isinstance(wz.get("energia"), float) and isinstance(wdo.get("energia"), float):
                sz["delta_energii"] = round(wdo["energia"] - wz["energia"], 3)
            sz["analiza_wersja"] = WERSJA
            sz["analiza_data"] = DATA
        else:
            jednostronne += 1
    sciezka_s.write_text(json.dumps(szwy, ensure_ascii=False, indent=1))
    print(f"SZWY: pełne (obie strony) {pelne} · jednostronne {jednostronne} "
          f"· z {len(szwy)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
