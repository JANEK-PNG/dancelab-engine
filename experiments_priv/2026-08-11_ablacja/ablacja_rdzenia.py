"""Audyt ablacyjny rdzenia — silnik ma udowodnić każdy swój gram.

PROJEKT JANKA (2026-08-11, zatwierdzony): „zacznijmy od mega okrojonej wersji,
np. tylko z BPM, i dodawajmy stopniowo. Jak różnica po dodaniu kolejnych
elementów będzie znikoma, to zaznaczamy na czerwono i myślimy, czy wywalamy".

ŁAWKA — WYŁĄCZNIE MAPA DJ-ÓW (twarda reguła: żadnych lokalnych utworów).
Zadanie: realne przejście A→B z setu spiętego po linku; kandydaci = policzone
utwory TEGO SAMEGO setu bez A (prawdziwy B wśród nich, minimum 5 kandydatów).
Miara: percentyl prawdziwego B w rankingu (1,0 = pierwsze miejsce), top-1,
top-5. Pula z tego samego setu jest NAJTRUDNIEJSZA (set jest spójny z doboru)
— przewagi będą małe; liczy się różnica MIĘDZY szczeblami, nie wartość.

UCZCIWOŚĆ INSTRUMENTU: oceny liczy DOKŁADNIE produkcyjne
`set_builder.transition_score` (tryb smart, arc="off" — nowy domyślny),
na obiektach analiz zbudowanych z kolumn mapy: tempo, tonacja Camelot
z pewnością, energia/groove/bas jako 30 stałych klatek ze zmierzonych
średnich, wektor brzmienia z próbki 30 s. Ograniczenie nazwane wprost:
mixability widzi tyle, ile niosą stałe klatki (bez wokalu, bez przebiegu) —
wynik czyta się „ile mixability dokłada NA TYM, co mapa widzi".

DRABINKA (kumulacyjnie, wagi produkcyjne dla włączonych, zero dla reszty):
  los → naiwne |ΔBPM| (spoza silnika: czy oktawowa maszyneria bpm_score
  w ogóle zarabia) → bpm → +harmonia → +priorsy korpusu → +energia
  (arc off ⇒ oczekiwane 0 Z KONSTRUKCJI) → +mixability → +brzmienie (0,6).

PROGI CZERWONEJ FLAGI — ZAREJESTROWANE PRZED URUCHOMIENIEM:
  szczebel jest CZERWONY, gdy względem poprzedniego
  Δmediana < 0,005 ORAZ Δtop-1 < 0,5 pp ORAZ Δtop-5 < 1,0 pp.

Użycie:
    .venv/bin/python ablacja_rdzenia.py [--proba N]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
KATALOG = pathlib.Path(__file__).resolve().parent
MAPA = KORZEN / "experiments_priv/2026-08-03_dj_mapa"
MIN_KANDYDATOW = 5

PROG_MEDIANA = 0.005
PROG_TOP1 = 0.5     # punkty procentowe
PROG_TOP5 = 1.0


def zbuduj_analizy():
    from dancelab.core.models import AnalysisResult, FeatureFrame, Track

    utw = {u["utwor_id"]: u for u in
           json.loads((MAPA / "encje_utwor.json").read_text())}
    surowe = {}
    for linia in (MAPA / "pomiar_utworow.jsonl").read_text().splitlines():
        w = json.loads(linia)
        if w.get("status") == "ok":
            surowe[w["utwor_id"]] = w
    wektory = {}
    for linia in (MAPA / "wektory_mapy.jsonl").read_text().splitlines():
        w = json.loads(linia)
        wektory[w["utwor_id"]] = w["wektor"]

    analizy = {}
    for uid, s in surowe.items():
        u = utw.get(uid, {})
        if not s.get("bpm"):
            continue
        rms = s.get("energia_surowa")
        onset = s.get("groove_surowy")
        bas = s.get("bas_surowy")
        analizy[uid] = AnalysisResult(
            engine_version="deezer-preview-30s",
            track=Track(
                track_id=uid,
                title=u.get("tytul") or None,
                artist=u.get("wykonawca") or None,
                bpm_estimate=float(s["bpm"]),
                key_estimate=s.get("tonacja") or None,
                key_confidence=(float(s["tonacja_pewnosc"])
                                if s.get("tonacja_pewnosc") is not None else None),
                sound_embedding=wektory.get(uid),
            ),
            features=[
                FeatureFrame(
                    track_id=uid, timestamp_sec=float(t),
                    rms=rms, onset_density=onset, bass_energy=bas,
                )
                for t in range(30)
            ],
        )
    return analizy


def przypadki(analizy):
    szwy = json.loads((MAPA / "fakty_szew.json").read_text())
    sety = defaultdict(dict)
    for s in szwy:
        if s.get("utwor_z_id"): sety[s["set_link"]][s["pozycja_z"]] = s["utwor_z_id"]
        if s.get("utwor_do_id"): sety[s["set_link"]][s["pozycja_do"]] = s["utwor_do_id"]
    out = []
    for link, poz in sety.items():
        policzone = [u for u in set(poz.values()) if u in analizy]
        for p in sorted(poz):
            a, b = poz.get(p), poz.get(p + 1)
            if not a or not b or a not in analizy or b not in analizy:
                continue
            kand = [x for x in policzone if x != a]
            if b in kand and len(kand) >= MIN_KANDYDATOW:
                out.append((a, b, kand))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--proba", type=int, default=0)
    args = ap.parse_args()

    import numpy as np
    from dancelab.core.config import WeightGroup, load_weights
    from dancelab.decision.corpus_priors import priors_available
    from dancelab.decision.set_builder import transition_score

    if not priors_available():
        print("UWAGA: brak pliku priorsów — szczebel '+priorsy' zmierzy zero "
              "z powodu braku pliku, nie braku wartości. Przerwij i sprawdź.")

    analizy = zbuduj_analizy()
    print(f"analiz z mapy: {len(analizy)}")
    lawka = przypadki(analizy)
    if args.proba:
        lawka = lawka[: args.proba]
    print(f"przypadków na ławce: {len(lawka)}")

    prod = load_weights("configs/descriptor_weights.yaml")
    pw = dict(prod.set_builder.weights)   # produkcyjne proporcje

    def wagi(h=0.0, b=0.0, e=0.0, m=0.0, priors=0.0, sound=0.0):
        return prod.model_copy(update={
            "set_builder": WeightGroup(
                status="ablation", weights={
                    "harmonic": h, "bpm": b, "energy": e, "mixability": m}),
            "corpus_priors_weight": priors,
            "sound_affinity_weight": sound,
        })

    SZCZEBLE = [
        ("bpm",         wagi(b=pw["bpm"])),
        ("+harmonia",   wagi(h=pw["harmonic"], b=pw["bpm"])),
        ("+priorsy",    wagi(h=pw["harmonic"], b=pw["bpm"], priors=1.0)),
        ("+energia",    wagi(h=pw["harmonic"], b=pw["bpm"], e=pw["energy"],
                             priors=1.0)),
        ("+mixability", wagi(h=pw["harmonic"], b=pw["bpm"], e=pw["energy"],
                             m=pw["mixability"], priors=1.0)),
        ("+brzmienie",  wagi(h=pw["harmonic"], b=pw["bpm"], e=pw["energy"],
                             m=pw["mixability"], priors=1.0, sound=0.6)),
    ]

    energie = {uid: (a.features[0].rms or 0.0) for uid, a in analizy.items()}
    zakres = (max(energie.values()) - min(energie.values())) or 1.0

    rng = np.random.default_rng(20260811)

    def oceny_przypadku(a, kand, w):
        out = {}
        for x in kand:
            s, _rel, _rea = transition_score(
                analizy[a], analizy[x], w, "off",
                energie[a], energie[x], zakres)
            out[x] = s
        return out

    wyniki = {}
    # podłogi i baseline spoza silnika
    for nazwa in ("los", "naiwne |dBPM|"):
        rekordy = []
        for a, b, kand in lawka:
            if nazwa == "los":
                o = {x: rng.random() for x in kand}
            else:
                ba = analizy[a].track.bpm_estimate
                o = {x: -abs(analizy[x].track.bpm_estimate - ba) for x in kand}
            posort = sorted(kand, key=lambda x: (-o[x], x))
            m = posort.index(b)
            rekordy.append((1.0 - m / (len(kand) - 1), m == 0, m < 5))
        wyniki[nazwa] = rekordy
        print(f"  policzone: {nazwa}", flush=True)

    for nazwa, w in SZCZEBLE:
        rekordy = []
        for a, b, kand in lawka:
            o = oceny_przypadku(a, kand, w)
            posort = sorted(kand, key=lambda x: (-o[x], x))
            m = posort.index(b)
            rekordy.append((1.0 - m / (len(kand) - 1), m == 0, m < 5))
        wyniki[nazwa] = rekordy
        print(f"  policzone: {nazwa}", flush=True)

    print(f"\n{'szczebel':16} {'mediana':>8} {'top-1':>7} {'top-5':>7}   werdykt")
    kolejnosc = ["los", "naiwne |dBPM|"] + [n for n, _ in SZCZEBLE]
    podsum = {}
    poprzedni = None
    for nazwa in kolejnosc:
        r = wyniki[nazwa]
        med = float(np.median([x[0] for x in r]))
        t1 = 100 * float(np.mean([x[1] for x in r]))
        t5 = 100 * float(np.mean([x[2] for x in r]))
        podsum[nazwa] = dict(mediana=med, top1=t1, top5=t5)
        werdykt = ""
        if poprzedni and nazwa not in ("los", "naiwne |dBPM|"):
            dm = med - podsum[poprzedni]["mediana"]
            d1 = t1 - podsum[poprzedni]["top1"]
            d5 = t5 - podsum[poprzedni]["top5"]
            czerwony = (dm < PROG_MEDIANA and d1 < PROG_TOP1 and d5 < PROG_TOP5)
            werdykt = (f"Δmed {dm:+.3f} · Δt1 {d1:+.1f}pp · Δt5 {d5:+.1f}pp"
                       + ("   ⛔ CZERWONA FLAGA" if czerwony else "   ✓ zarabia"))
        print(f"{nazwa:16} {med:8.3f} {t1:6.1f}% {t5:6.1f}%   {werdykt}")
        poprzedni = nazwa

    (KATALOG / "wynik_ablacji.json").write_text(
        json.dumps(dict(przypadkow=len(lawka), progi=dict(
            mediana=PROG_MEDIANA, top1=PROG_TOP1, top5=PROG_TOP5),
            szczeble=podsum), ensure_ascii=False, indent=1))
    print(f"\nzapisane: {KATALOG / 'wynik_ablacji.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
