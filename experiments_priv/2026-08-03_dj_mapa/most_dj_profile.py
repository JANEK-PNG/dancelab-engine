"""Most danych: mapa DJ-ów → data/reports/dj_profile.json dla zakładki DJ-e.

Krok przewidziany w spec 2026-08-12 (karty DJ-ów): karta w TUI ma pokazywać
te same POMIARY co makieta GUI. Liczymy z fakty_szew + encje_utwor:
zakres temp (p10/mediana/p90), % szwów zgodnych harmonicznie, mediana
skoku tempa, mediany energii/groove'u/basu, liczności, edycje wydarzeń.

Zasady: tylko agregaty (zero identyfikatorów utworów — filozofia
SeamProfile), pola bez pomiaru = None, nigdy zgadywane. Profil pełny
dopiero od 10 pełnych szwów — poniżej „profil w budowie".
"""

from __future__ import annotations

import json
import pathlib
import statistics

TU = pathlib.Path(__file__).parent
CEL = pathlib.Path("/Users/jantrybus/Developer/dancelab-engine/data/reports/dj_profile.json")
MIN_PELNYCH = 10


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> None:
    sz = json.loads((TU / "fakty_szew.json").read_text())
    enc = {e["utwor_id"]: e for e in
           json.loads((TU / "encje_utwor.json").read_text())}

    wg_dj: dict[str, list[dict]] = {}
    for s in sz:
        wg_dj.setdefault(s["ksywa"], []).append(s)

    med = lambda l, r=2: round(statistics.median(l), r) if l else None
    profile: dict[str, dict] = {}
    for ksywa, moje in wg_dj.items():
        pelne = [s for s in moje if s.get("bpm_z") and s.get("bpm_do")]
        sety = {s["set_link"] for s in moje}
        edycje = sorted({f"{s['wydarzenie']} {str(s['data'])[:4]}"
                         for s in moje if s.get("wydarzenie")})
        wpis: dict = {"sety": len(sety), "szwy": len(moje),
                      "szwy_pelne": len(pelne), "edycje": edycje}
        if len(pelne) >= MIN_PELNYCH:
            bpmy = sorted([s["bpm_z"] for s in pelne]
                          + [s["bpm_do"] for s in pelne])
            harm = [s for s in pelne if s.get("zgodnosc_harmoniczna")]
            ok = [s for s in harm if s["zgodnosc_harmoniczna"]
                  in ("idealna", "sasiednia", "rownolegla")]
            en, gr, bas = [], [], []
            widziane: set[str] = set()
            for s in moje:
                for uid in (s.get("utwor_z_id"), s.get("utwor_do_id")):
                    if uid and uid not in widziane:
                        widziane.add(uid)
                        u = enc.get(uid, {})
                        for lst, pole in ((en, "energia"),
                                          (gr, "gestosc_groove"),
                                          (bas, "obecnosc_basu")):
                            v = num(u.get(pole))
                            if v is not None:
                                lst.append(v)
            delty = [abs(s["delta_bpm"]) for s in pelne
                     if s.get("delta_bpm") is not None]
            wpis.update(
                bpm_lo=round(bpmy[int(len(bpmy) * 0.1)]),
                bpm_med=round(statistics.median(bpmy)),
                bpm_hi=round(bpmy[int(len(bpmy) * 0.9)]),
                harm_proc=(round(100 * len(ok) / len(harm)) if harm else None),
                skok_bpm=med(delty, 1),
                energia=med(en), groove=med(gr), bas=med(bas),
                utwory_zmierzone=len(en) or None,
            )
        profile[ksywa] = wpis

    CEL.parent.mkdir(parents=True, exist_ok=True)
    CEL.write_text(json.dumps(
        {"zrodlo": "mapa DJ-ów (fakty_szew + encje_utwor)",
         "stan": "2026-08-12", "min_pelnych": MIN_PELNYCH,
         "djs": profile}, ensure_ascii=False, indent=1))
    pelnych = sum(1 for p in profile.values() if "bpm_med" in p)
    print(f"DJ-ów w profilu: {len(profile)} · z pełnym profilem: {pelnych}")
    print(f"zapisano: {CEL}")
    # kontrola: Tim Reaper musi się zgadzać z karty_pilot3.json
    tr = profile.get("Tim Reaper", {})
    print("Tim Reaper:", tr.get("bpm_lo"), tr.get("bpm_med"),
          tr.get("bpm_hi"), tr.get("harm_proc"), tr.get("skok_bpm"))


if __name__ == "__main__":
    main()
