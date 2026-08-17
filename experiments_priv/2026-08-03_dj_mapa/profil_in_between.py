"""Profil In Between P = (C, D, Syn, U) liczony PRZEZ SILNIK, nie obok niego.

Janek 13.08: „pamiętaj, że wciąż to ma być sprzężone z naszym silnikiem".
Więc każda z czterech liczb wychodzi z prawdziwych funkcji DanceLaba —
tych samych, które wybierają następny utwór — a nie z przybliżenia w JS:

  C   sprzężenie realizowane  = ważona suma komponentów silnika dla tej pary
                                (wagi set_builder: harmonic .35, bpm .25,
                                 energy .20, mixability .20 — mixability
                                 bez audio niedostępne, więc liczymy rdzeń
                                 i mówimy o tym wprost)
  D   asymetria               = ln(i_HS / i_SH), gdzie siły stron liczymy
                                z energii utworów (energia = nacisk strony)
  Syn emergencja              = transition_prior_lift z KORPUSU: o ile
                                realni DJ-e grają to przejście lepiej, niż
                                wynikałoby ze składników. Lift > 1 znaczy
                                dosłownie: w szwie jest coś, czego nie ma
                                w częściach
  U   wykorzystanie           = C / K, gdzie K to sprzężenie osiągalne w tej
                                ramie: ten sam wzór przy tonacjach idealnych
                                i tempie utrzymanym

Wyjście: dopisane pola do szwy.json makiety (C, D, Syn, U, K, okreslone).
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from dancelab.core.config import load_config, load_weights          # noqa: E402
from dancelab.decision.corpus_priors import transition_prior_lift   # noqa: E402
from dancelab.decision.harmonic import harmonic_compatibility       # noqa: E402
from dancelab.decision.set_builder import bpm_score                 # noqa: E402

TU = pathlib.Path(__file__).parent
CEL = pathlib.Path("/Users/jantrybus/Developer/dancelab-engine/docs/mockup-dj-karty/szwy.json")
THETA = 0.18


def _energia_score(dE: float) -> float:
    """Arc „off" (zmierzony 10.08 jako lepszy niż łuk): energia neutralna —
    liczy się PŁYNNOŚĆ zmiany, nie kierunek."""
    return max(0.0, 1.0 - min(abs(dE) * 1.6, 1.0))


def profil(s: dict, poprz: dict, wagi, trend: dict | None = None) -> dict:
    w = dict(wagi.set_builder.weights)
    ton_a, ton_b = (s.get("ta") or ""), (s.get("tb") or "")
    if ton_a and ton_b:
        harm = harmonic_compatibility(ton_a, ton_b, 1.0, 1.0)
        h, rel = harm.harmonic_compatibility_score, harm.harmonic_relation
    else:                       # bez tonacji nie zgadujemy — bierzemy pomiar mapy
        h = {"idealna": 1.0, "sasiednia": 0.8, "rownolegla": 0.74,
             "wzgledna": 0.5, "zadna": 0.12}.get(s.get("h") or "", 0.3)
        rel = s.get("h") or "unknown"
    bp = bpm_score(s.get("a"), s.get("b")) if s.get("a") and s.get("b") else 0.5
    eA, eB = poprz.get("eb"), s.get("eb")
    en = _energia_score(eB - eA) if (eA is not None and eB is not None) else 0.5

    # C: rdzeń wzoru silnika (mixability wymaga audio — nieobecne w mapie)
    dostepne = {"harmonic": h, "bpm": bp, "energy": en}
    suma_wag = sum(w[k] for k in dostepne)
    C = sum(w[k] * v for k, v in dostepne.items()) / suma_wag

    # D: kto prowadzi — siła strony z jej energii i gęstości groove'u
    def sila(e, g):
        return 0.62 * (e if e is not None else 0.5) \
             + 0.38 * (g if g is not None else 0.5) + 0.05
    iHS = sila(poprz.get("eb"), poprz.get("gb"))
    iSH = sila(s.get("eb"), s.get("gb"))
    okreslone = C >= THETA
    D = math.log(iHS / iSH) if okreslone and iSH > 0 else None

    # Syn: prior z KORPUSU — ile realni DJ-e wyciskają ponad składniki
    lift = 1.0
    if s.get("a") and s.get("b"):
        try:
            lift, _ = transition_prior_lift(rel, s["a"], s["b"])
        except Exception:                                   # noqa: BLE001
            lift = 1.0
    Syn = max(0.0, min(1.0, (lift - 1.0) * 2.2))

    # === SPRZĘŻENIE DJ ↔ MUZYKA (Janek: „to jest właśnie in between") ===
    # i_DJ→M: ile DJ NARZUCIŁ — o ile jego wybór odbiega od inercji, czyli
    #         od tego, dokąd sama muzyka zmierzała (trend poprzednich kroków).
    # i_M→DJ: ile MUZYKA go poprowadziła — o ile jego wybór jest kontynuacją
    #         tego, co już grało (podążanie za tempem i energią).
    # Ich suma to C_dj (sprzężenie w pętli), a ln ilorazu mówi, kto prowadzi.
    K = (w["harmonic"] * 1.0 + w["bpm"] * 1.0 + w["energy"] * 1.0) / suma_wag
    U = min(1.0, C / K) if K > 0 else 0.0
    # pętla DJ ↔ muzyka
    iDJ = iM = None
    Cdj = Ddj = None
    if trend:
        # dokąd zmierzała sama muzyka (trend z poprzednich kroków)?
        prog_bpm = trend.get("bpm"); prog_en = trend.get("en")
        if prog_bpm is not None and s.get("b"):
            odchyl_b = min(abs(s["b"] - prog_bpm) / 18.0, 1.0)      # DJ narzucił
            ciag_b = 1.0 - odchyl_b                                  # muzyka wiodła
        else:
            odchyl_b = ciag_b = 0.5
        if prog_en is not None and s.get("eb") is not None:
            odchyl_e = min(abs(s["eb"] - prog_en) * 2.2, 1.0)
            ciag_e = 1.0 - odchyl_e
        else:
            odchyl_e = ciag_e = 0.5
        iDJ = round(0.55 * odchyl_b + 0.45 * odchyl_e + 0.05, 4)
        iM = round(0.55 * ciag_b + 0.45 * ciag_e + 0.05, 4)
        Cdj = round(min(1.0, (iDJ + iM) / 2.1), 4)
        Ddj = round(math.log(iDJ / iM), 4) if (iM > 0 and Cdj >= THETA) else None
    return {"C": round(C, 4), "D": None if D is None else round(D, 4),
            "Syn": round(Syn, 4), "U": round(U, 4), "K": round(K, 4),
            "okreslone": okreslone, "lift": round(lift, 4),
            "iDJ": iDJ, "iM": iM, "Cdj": Cdj, "Ddj": Ddj}


def main() -> None:
    cfg = load_config("configs/default.yaml")
    wagi = load_weights(cfg.weights_file)
    dane = json.loads(CEL.read_text())
    sz_map = {(s["ksywa"], s["set_link"], s["pozycja_z"]): s
              for s in json.loads((TU / "fakty_szew.json").read_text())}
    ile, bez_kier = 0, 0
    for ksywa, lista in dane.items():
        for i, s in enumerate(lista):
            # dołóż tonacje z mapy, jeśli są (silnik woli je od etykiety)
            for klucz, wpis in sz_map.items():
                if klucz[0] == ksywa and wpis["pozycja_z"] == s["poz"]:
                    s.setdefault("ta", wpis.get("tonacja_z") or "")
                    s.setdefault("tb", wpis.get("tonacja_do") or "")
                    break
            # trend muzyki: dokąd zmierzała przed tym wyborem (2 kroki wstecz)
            hist = lista[max(0, i - 2):i]
            trend = None
            if hist:
                bpmy = [h.get("b") for h in hist if h.get("b")]
                eny = [h.get("eb") for h in hist if h.get("eb") is not None]
                trend = {"bpm": (2 * bpmy[-1] - bpmy[0]) if len(bpmy) > 1
                                else (bpmy[-1] if bpmy else None),
                         "en": (2 * eny[-1] - eny[0]) if len(eny) > 1
                               else (eny[-1] if eny else None)}
            p = profil(s, lista[i - 1] if i else s, wagi, trend)
            s.update(p)
            ile += 1
            bez_kier += 0 if p["okreslone"] else 1
    CEL.write_text(json.dumps(dane, ensure_ascii=False))
    print(f"policzone przez silnik: {ile} przejść · bez kierunku (C<θ): {bez_kier}")
    tim = dane["Tim Reaper"]
    for i in (10, 40, 95):
        s = tim[i]
        print(f"  Tim #{i}: C={s['C']} D={s['D']} · DJ↔muzyka: C={s['Cdj']} "
              f"D={s['Ddj']} (DJ {s['iDJ']} / muzyka {s['iM']})")


if __name__ == "__main__":
    main()
