"""Składa NAZWY z RA z CZASAMI z komentarzy — czyli robi z tego szew.

Żadne z tych źródeł samo nie wystarcza i to jest sedno:

  * RA podaje CO zagrano i w jakiej kolejności. Spisane przez redakcję, więc
    nazwy są pewne. Godzin nie ma w ogóle.
  * Komentarze SoundCloud są przypięte do sekundy nagrania, więc mówią KIEDY
    coś się zmieniło. Ale w większości mówią tylko „ID" — bez nazwy.

Szew to nazwa PLUS moment. Osobno mamy połowę odpowiedzi dwa razy.

JAK TO SIĘ SKŁADA, na przykładzie RA.517 (Awesome Tapes From Africa):

    RA           —:—   Onyame Nkrabea Nwomkro — Owerehoni      poz. 1
    RA           —:—   Issa Bagayogo          — Kouloun        poz. 2
    RA           —:—   Penny Penny            — Shichangani    poz. 3
    KOMENTARZ   0:09   Onyame Nkrabea Nwomkro — Owerehon
    KOMENTARZ   4:20   Issa Bagayogo          — Kouloun
    KOMENTARZ   9:47   Penny Penny            — Shichangani
    KOMENTARZ  29:05   —                      — ID

Trzy pierwsze komentarze nazywają utwory, które stoją na liście RA. To są
KOTWICE: pozycja i czas naraz. Czwarty mówi tylko „ID" — ale skoro znamy
kolejność z RA i mamy kotwice po obu stronach, wiemy, KTÓRY to utwór.

TRZY STOPNIE PEWNOŚCI CZASU, i nigdy ich nie mieszamy:

  * `zmierzony`   — ktoś nazwał ten utwór w komentarzu o tej sekundzie;
  * `z_kotwic`    — czas wyliczony z pozycji między dwiema kotwicami. To jest
                    OSZACOWANIE, nie pomiar, i tak jest oznaczone;
  * `bez_czasu`   — utwór z listy RA, do którego nic nie sięga.

Dopasowanie musi być MONOTONICZNE: czas rośnie razem z pozycją na liście.
Bez tego jedna pomyłka nazwy przestawia całą resztę setu — a set grany
w kolejności to jedyne założenie, które tu wolno przyjąć.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import unicodedata as U
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tracklisty as T                                             # noqa: E402

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
API = "https://api-v2.soundcloud.com"

# Poniżej tego udziału wspólnych słów uznajemy, że to nie ten sam utwór.
# 0.5 wybrane po obejrzeniu trafień: „Shichangani (Remix" kontra
# „Shichangani (Remix)" ma zostać, „Kouloun" kontra „Koulou Kan" nie.
PROG = 0.5


def _tokeny(s: str) -> set[str]:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return {t for t in s.split() if len(t) > 2}


def podobne(a: str, b: str) -> float:
    ta, tb = _tokeny(a), _tokeny(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def resolve(url: str, cid: str) -> tuple[int | None, int | None]:
    u = (f"{API}/resolve?url={urllib.parse.quote(url, safe='')}"
         f"&client_id={cid}")
    try:
        req = urllib.request.Request(u, headers={"User-Agent": T.UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read().decode("utf-8"))
        return d.get("id"), d.get("duration")
    except Exception:                                              # noqa: BLE001
        return None, None


def kotwice(lista: list[dict], komentarze: list[dict]) -> list[tuple[int, int]]:
    """(pozycja na liście RA, czas w ms). Wyłącznie trafienia monotoniczne.

    Komentarz może nazywać utwór spoza kolejności — ktoś pisze o kawałku
    z połowy setu, słuchając końcówki. Wymuszenie rosnącej pozycji przy
    rosnącym czasie odsiewa takie wtręty; koszt to kilka utraconych kotwic,
    zysk to brak przestawienia całego setu.
    """
    pary = []
    for c in komentarze:
        if c["tytul"] == "ID" or c["ms"] is None:
            continue
        opis = f"{c['wykonawca']} {c['tytul']}"
        naj, naji = 0.0, None
        for i, t in enumerate(lista):
            s = podobne(opis, f"{t['wykonawca']} {t['tytul']}")
            if s > naj:
                naj, naji = s, i
        if naji is not None and naj >= PROG:
            pary.append((naji, c["ms"], naj))
    pary.sort(key=lambda x: x[1])

    # Najdłuższy rosnący podciąg po pozycji — klasycznie, bo par jest mało.
    n = len(pary)
    if not n:
        return []
    dp = [1] * n
    skad = [-1] * n
    for i in range(n):
        for j in range(i):
            if pary[j][0] < pary[i][0] and dp[j] + 1 > dp[i]:
                dp[i], skad[i] = dp[j] + 1, j
    i = max(range(n), key=lambda x: dp[x])
    out = []
    while i != -1:
        out.append((pary[i][0], pary[i][1]))
        i = skad[i]
    return out[::-1]


def zloz(lista: list[dict], komentarze: list[dict],
         dlugosc_ms: int | None) -> list[dict]:
    kot = kotwice(lista, komentarze)
    wynik = []
    for i, t in enumerate(lista):
        czas_ms, pewnosc = None, "bez_czasu"
        dokladne = next((ms for poz, ms in kot if poz == i), None)
        if dokladne is not None:
            czas_ms, pewnosc = dokladne, "zmierzony"
        elif len(kot) >= 2:
            # Dwie kotwice obejmujące tę pozycję → interpolacja liniowa.
            # Poza skrajnymi kotwicami NIE ekstrapolujemy: zgadywanie w tył
            # od pierwszej i w przód od ostatniej myli się najbardziej.
            lewa = max((k for k in kot if k[0] < i), default=None)
            prawa = min((k for k in kot if k[0] > i), default=None)
            if lewa and prawa and prawa[0] > lewa[0]:
                frakcja = (i - lewa[0]) / (prawa[0] - lewa[0])
                czas_ms = int(lewa[1] + frakcja * (prawa[1] - lewa[1]))
                pewnosc = "z_kotwic"
        wynik.append({
            "pozycja": i + 1,
            "wykonawca": t["wykonawca"], "tytul": t["tytul"],
            "ms": czas_ms,
            "czas": T.czas(czas_ms) if czas_ms is not None else "",
            "pewnosc_czasu": pewnosc,
        })
    return wynik


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-pozycji", type=int, default=5)
    ap.add_argument("--wyjscie", default="szwy_zlozone.json")
    args = ap.parse_args()

    cid = T.client_id()
    if not cid:
        print("Brak client_id.")
        return 1

    pod = json.loads((OUT / "ra_podcasty.json").read_text())
    cele = [p for p in pod
            if p["pozycji"] >= args.min_pozycji and "soundcloud.com" in (p["link"] or "")]
    print(f"podcastów z tracklistą RA i linkiem SoundCloud: {len(cele)}")

    p = OUT / args.wyjscie
    wynik, zrobione = [], set()
    if p.exists():
        wynik = json.loads(p.read_text())
        zrobione = {w["link"] for w in wynik}
        print(f"wznawiam — mam już {len(zrobione)}")

    for i, x in enumerate(cele, 1):
        if x["link"] in zrobione:
            continue
        tid, dur = resolve(x["link"], cid)
        if not tid:
            continue
        kom = T.komentarze(tid, cid, dur)
        sklad = zloz(x["tracklista"], kom, dur)
        zm = sum(1 for s in sklad if s["pewnosc_czasu"] == "zmierzony")
        wynik.append({
            "ksywa": x["ksywa"], "tytul": x["tytul"], "data": x["data"],
            "link": x["link"], "strona": x["strona"],
            "utworow": len(sklad), "kotwic": zm,
            "z_kotwic": sum(1 for s in sklad if s["pewnosc_czasu"] == "z_kotwic"),
            "komentarzy": len(kom),
            "sklad": sklad,
        })
        if i % 20 == 0:
            print(f"  {i}/{len(cele)} — złożonych {len(wynik)}", flush=True)
            p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
        time.sleep(0.25)

    p.write_text(json.dumps(wynik, ensure_ascii=False, indent=1))
    utw = sum(w["utworow"] for w in wynik)
    zm = sum(w["kotwic"] for w in wynik)
    zk = sum(w["z_kotwic"] for w in wynik)
    print(f"\nsetów złożonych: {len(wynik)}")
    print(f"utworów razem:   {utw}")
    print(f"  czas ZMIERZONY (kotwica):   {zm:5d}  ({zm / max(utw,1) * 100:.1f}%)")
    print(f"  czas z KOTWIC (oszacowany): {zk:5d}  ({zk / max(utw,1) * 100:.1f}%)")
    print(f"  bez czasu:                  {utw - zm - zk:5d}")
    print(f"  setów z >=2 kotwicami:      "
          f"{sum(1 for w in wynik if w['kotwic'] >= 2)}")
    print(f"zapisane: {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
