"""ETAP 6 — czy BRAK DANYCH o utworze przewiduje, że silnik się pomyli.

ZGODA JANKA: 2026-08-17, wprost („masz zgodę na pomiar") — pomiar na jego
bibliotece i historii grania. Zakaz z 11.08 pozostaje regułą domyślną; to jest
jednorazowe zawieszenie na ten jeden pomiar.

DLACZEGO NA BIBLIOTECE, NIE NA KORPUSIE
---------------------------------------
Trzy mechanizmy odmowy padły na korpusie (pewność modelu, nowość zapytania,
nowość kandydata — etapy 3 i 5). Czwarty kandydat — „silnik wie o tym utworze
mało" — ma wariancję WYŁĄCZNIE tutaj: w korpusie każdy utwór ma komplet cech
z jednego źródła, a w bibliotece Janka 81% historii to strumienie Apple Music,
gdzie klatki cech niosą tylko RMS, tonacja jest z Rekordboxa, a wektora
brzmienia w analizie nie ma.

PYTANIE
-------
Ranking silnika PRODUKCYJNEGO (`transition_score`, wagi z configs, tryb smart,
arc=off — dokładnie to, co jedzie w produkcie) na prawdziwych następstwach
z historii grania: utwór B, który Janek NAPRAWDĘ załadował po A, kontra 200
kandydatów z jego puli. Czy DEFICYT DANYCH o zapytaniu A przewiduje pozycję B?

DEFICYT (0–4, liczony dla utworu; sygnał dostępny W CHWILI PREDYKCJI):
  +1  brak tonacji albo tonacja bez zmierzonej pewności (po zmianie 17.08
      strumienie mają key_confidence=None — i to jest deficyt, nie ozdoba)
  +1  siatka bitów niewiarygodna albo jej brak
  +1  klatki cech bez treści (tylko RMS — bez flux/onset/bass)
  +1  brak wektora brzmienia w analizie

HIGIENA
-------
* master.db kopiowany do scratchpadu, czytamy WYŁĄCZNIE kopię (wzorzec
  z `czytaj_rekordbox.py`); żadnego zapisu gdziekolwiek.
* Pary przez filtr odstępu 90–600 s (D3 z OBALONE.md: załadowanie ≠ zagranie).
* Strumienie mapowane po ContentID (analiza `rb{ID}`), pliki po ścieżce NFC.
* Pula kandydatów po scaleniu duplikatów (`tui.duplikaty`), 200 na parę,
  deterministycznie.

POPRAWKA PRZYRZĄDU (przed policzeniem JAKIEJKOLWIEK korelacji)
--------------------------------------------------------------
Pierwsza definicja deficytu (0–4 addytywnie) padła na własnej bramce M3:
w zapisanych analizach wektora nie ma NIGDZIE (leży w osobnych plikach),
siatka jest wiarygodna w 99,96%, a pewność tonacji 1,0 pochodzi sprzed
zmiany z 17.08. Realna oś deficytu jest JEDNA i binarna:

    STRUMIEŃ (klatki tylko RMS, tonacja z RB)  vs  PLIK (pełne cechy).

Bramka zatrzymała bieg PRZED rankingiem, więc to jest naprawa przyrządu,
nie dopasowanie do wyniku.

PROGI ZAREJESTROWANE PRZED BIEGIEM (po poprawce, nadal przed rankingiem)
------------------------------------------------------------------------
  M1: zapytania-STRUMIENIE mają medianę pozycji prawdy o ≥ +15 miejsc
      (z 200) GORSZĄ niż zapytania-PLIKI, wewnątrz KAŻDEJ warstwy klasy
      prawdy (B=strumień i B=plik osobno — bez tego mierzylibyśmy klasę B,
      czyli pułapkę „model rozpoznaje źródło", AUC 0,889 z 02.08).
      Istotność: test permutacyjny na różnicy median, p < 0,05, łącznie.
  M2 (kontrola): ten sam test na POZYCJI LOSOWEJ musi być czysty.
  RAPORTOWANE BEZ PROGU: efekt klasy PRAWDY (B) — też jest sygnałem odmowy,
      dostępnym w predykcji (znamy klasę kandydatów), ale nie jest progiem.
"""

from __future__ import annotations

import json
import pathlib
import shutil
import statistics
import sys
import unicodedata as U
from collections import Counter, defaultdict

import numpy as np

KATALOG = pathlib.Path(__file__).parent
ROOT = KATALOG.parents[1]
sys.path.insert(0, str(KATALOG))

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
BAZA = pathlib.Path.home() / "Library/Pioneer/rekordbox/master.db"
SCRATCH = pathlib.Path("/private/tmp/claude-501/-Users-jantrybus-Desktop-AI/"
                       "ae2e7309-426b-47ac-a3e6-2b2cdb758053/scratchpad")
KOPIA = SCRATCH / "master_etap6.db"

N_KAND = 200
PLAY_LO, PLAY_HI = 90.0, 600.0
MIN_TRACKS = 5

nfc = lambda s: U.normalize("NFC", str(s or ""))  # noqa: E731


def historia_par():
    """Pary A→B z kopii bazy + odstęp w sekundach. Zero dotykania oryginału."""
    shutil.copy2(BAZA, KOPIA)
    for boczny in (".db-wal", ".db-shm"):
        src = BAZA.with_suffix(boczny)
        if src.exists():
            shutil.copy2(src, KOPIA.with_suffix(boczny))
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database(KOPIA)
    sciezka_cid = {str(r.ID): nfc(r.FolderPath) for r in
                   db.session.query(tables.DjmdContent).all()}
    gry = defaultdict(list)
    for r in (db.session.query(tables.DjmdSongHistory)
              .order_by(tables.DjmdSongHistory.TrackNo).all()):
        gry[str(r.HistoryID)].append((r.TrackNo, str(r.ContentID), r.created_at))
    db.close()

    pary = []
    for hid, rows in gry.items():
        if len(rows) < MIN_TRACKS:
            continue
        rows = sorted(rows)
        for (na, ca, ta), (nb, cb, tb) in zip(rows, rows[1:]):
            try:
                odstep = (tb - ta).total_seconds()
            except Exception:  # noqa: BLE001
                continue
            if PLAY_LO <= odstep <= PLAY_HI:
                pary.append((ca, cb, hid))
    return pary, sciezka_cid


def ubogi(a) -> bool:
    """True = silnik wie o utworze mało (klatki bez treści — tylko RMS)."""
    klatki = getattr(a, "features", None) or []
    return not any(getattr(f, "spectral_flux", None) is not None
                   or getattr(f, "onset_density", None) is not None
                   or getattr(f, "bass_energy", None) is not None
                   for f in klatki[:8])


def main() -> int:
    from dancelab.core.config import load_weights
    from dancelab.decision.mixability import precompute_mixability_inputs
    from dancelab.decision.set_builder import transition_score
    from dancelab.storage.repositories import FileAnalysisRepository
    from dancelab.tui.duplikaty import scal
    from etap5_nowosc import los, spearman

    print("wczytuję analizy…")
    repo = FileAnalysisRepository(PROCESSED)
    wszystkie = [repo.get(t) for t in repo.list_track_ids()]
    widok, scalone = scal(wszystkie)
    by_id = {a.track.track_id: a for a in widok}
    by_path = {nfc(a.track.source_path): a for a in widok
               if a.track.source_path and not str(a.track.source_path)
               .startswith("apple-music:")}
    print(f"analiz {len(wszystkie)} → po scaleniu {len(widok)} "
          f"(scalono {scalone})")

    pary_cid, sciezka_cid = historia_par()
    print(f"par w historii po filtrze {PLAY_LO:.0f}–{PLAY_HI:.0f} s: "
          f"{len(pary_cid)}")

    def analiza_cid(cid: str):
        a = by_id.get(f"rb{cid}")
        if a is not None:
            return a
        return by_path.get(sciezka_cid.get(cid, ""))

    pary = []
    for ca, cb, hid in pary_cid:
        a, b = analiza_cid(ca), analiza_cid(cb)
        if a is not None and b is not None and a.track.track_id != b.track.track_id:
            pary.append((a, b, hid))
    print(f"pary z analizą po OBU stronach: {len(pary)}")

    rozklad = Counter((ubogi(a), ubogi(b)) for a, b, _ in pary)
    print("rozkład (A ubogie, B ubogie):",
          {f"A{'u' if ka else 'P'}/B{'u' if kb else 'P'}": v
           for (ka, kb), v in sorted(rozklad.items())})
    if min(rozklad.get((True, x), 0) + rozklad.get((False, x), 0)
           for x in (True, False)) < 40:
        print("⛔ za mało par w którejś warstwie klasy prawdy")
        return 2

    W = load_weights("configs/descriptor_weights.yaml")
    pula = sorted(by_id)
    print("liczę rankingi (produkcyjny transition_score, 200 kandydatów)…")

    nowe = los("etap6")
    wiersze = []
    pre_cache = {}
    for nr, (a, b, hid) in enumerate(pary):
        g = los(f"etap6|{hid}|{nr}")
        kand_id = [pula[i] for i in g.choice(len(pula), size=N_KAND + 20,
                                             replace=False)]
        kand_id = [k for k in kand_id
                   if k not in (a.track.track_id, b.track.track_id)][:N_KAND - 1]
        kandydaci = [by_id[k] for k in kand_id] + [b]
        pre = precompute_mixability_inputs([a] + kandydaci)
        wyniki = []
        for k in kandydaci:
            r = transition_score(a, k, W, arc="off", energy_a=0.5, energy_b=0.5,
                                 energy_range=1.0, planner_mode="smart",
                                 mixability_precomputation=pre)
            s = r[0] if isinstance(r, tuple) else r
            wyniki.append(float(s))
        kolej = np.argsort(-np.asarray(wyniki), kind="stable")
        poz_b = int(np.where(kolej == len(kandydaci) - 1)[0][0]) + 1
        wiersze.append({
            "a_ubogi": ubogi(a), "b_ubogi": ubogi(b),
            "pozycja": poz_b,
            "pozycja_losowa": int(nowe.integers(1, len(kandydaci) + 1)),
        })
        if nr % 200 == 0:
            print(f"  {nr}/{len(pary)}")

    def roznica_median(klucz_poz):
        """Różnica median (A ubogie − A pełne) wewnątrz warstw klasy B,
        ważona liczebnością; do tego permutacyjne p (5000 tasowań)."""
        def stat(ws):
            tot = wag = 0.0
            for kb in (True, False):
                u = [w[klucz_poz] for w in ws if w["b_ubogi"] == kb and w["a_ubogi"]]
                p_ = [w[klucz_poz] for w in ws if w["b_ubogi"] == kb and not w["a_ubogi"]]
                if len(u) >= 10 and len(p_) >= 10:
                    n = len(u) + len(p_)
                    tot += (statistics.median(u) - statistics.median(p_)) * n
                    wag += n
            # ZŁAPANE W AUDYCIE: pierwsza wersja zwracała tu 0.0 i wynik
            # wyglądał jak zmierzone zero. Brak mierzalnej warstwy to inna
            # odpowiedź niż zero — to brak pomiaru.
            return (tot / wag) if wag else None
        real = stat(wiersze)
        if real is None:
            return None, None
        g = los("permutacje-etap6")
        licznik = 0
        flagi = [w["a_ubogi"] for w in wiersze]
        for _ in range(5000):
            tas = list(g.permutation(flagi))
            kopia = [dict(w, a_ubogi=t) for w, t in zip(wiersze, tas)]
            if abs(stat(kopia)) >= abs(real):
                licznik += 1
        return real, (licznik + 1) / 5001

    d_real, p_real = roznica_median("pozycja")
    d_los, p_los = roznica_median("pozycja_losowa")

    if d_real is None:
        print("\n⛔ M1 NIEMIERZALNE: żadna warstwa klasy prawdy nie ma obu "
              "grup zapytań ≥10.\n   Sesje Janka są jednorodne (strumienie "
              "ALBO pliki) — komórki krzyżowe mają 5 i 9 par.")
        (KATALOG / "etap6_wynik.json").write_text(json.dumps({
            "par": len(wiersze),
            "rozklad": {f"A{'u' if ka else 'P'}/B{'u' if kb else 'P'}": v
                        for (ka, kb), v in sorted(rozklad.items())},
            "werdykt": {"M1": "NIEMIERZALNE — sesje jednorodne klasowo",
                        "M2": None},
            "mediany": {f"B{'u' if kb else 'P'}/A{'u' if ka else 'P'}":
                        statistics.median([w["pozycja"] for w in wiersze
                                           if w["b_ubogi"] == kb and w["a_ubogi"] == ka] or [0])
                        for kb in (True, False) for ka in (True, False)},
            "mediana_ogolem": statistics.median(w["pozycja"] for w in wiersze),
        }, ensure_ascii=False), encoding="utf-8")
        print("zapisano: etap6_wynik.json")
        return 0

    print(f"\nM1: mediana pozycji, A-STRUMIEŃ minus A-PLIK "
          f"(wewnątrz warstw B) = {d_real:+.1f} miejsc · p = {p_real:.4f}")
    print(f"M2: kontrola na pozycji losowej = {d_los:+.1f} · p = {p_los:.4f}")

    print("\nmediany pozycji (warstwa × klasa zapytania):")
    for kb in (False, True):
        for ka in (False, True):
            grupa = [w["pozycja"] for w in wiersze
                     if w["b_ubogi"] == kb and w["a_ubogi"] == ka]
            if grupa:
                print(f"  B={'ubogie' if kb else 'pełne '} · "
                      f"A={'ubogie' if ka else 'pełne '}: "
                      f"{statistics.median(grupa):6.0f} · n={len(grupa)}")
    # efekt klasy PRAWDY — bez progu, ale to też sygnał odmowy
    for kb in (False, True):
        grupa = [w["pozycja"] for w in wiersze if w["b_ubogi"] == kb]
        print(f"  klasa PRAWDY B={'ubogie' if kb else 'pełne '}: mediana "
              f"{statistics.median(grupa):6.0f} · n={len(grupa)}")

    m1 = d_real >= 15 and p_real < 0.05
    m2 = p_los >= 0.05
    print(f"\n═══ WERDYKT (progi sprzed biegu) ═══")
    print(f"  M1 ubóstwo zapytania przewiduje błąd: {'ZDANY' if m1 else 'NIEZDANY'}")
    print(f"  M2 kontrola czysta:                   {'ZDANY' if m2 else 'NIEZDANY'}")

    (KATALOG / "etap6_wynik.json").write_text(json.dumps({
        "par": len(wiersze),
        "rozklad": {f"A{'u' if ka else 'P'}/B{'u' if kb else 'P'}": v
                    for (ka, kb), v in sorted(rozklad.items())},
        "M1_roznica_median": d_real, "M1_p": p_real,
        "M2_roznica": d_los, "M2_p": p_los,
        "werdykt": {"M1": bool(m1), "M2": bool(m2)},
    }, ensure_ascii=False), encoding="utf-8")
    print("zapisano: etap6_wynik.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
