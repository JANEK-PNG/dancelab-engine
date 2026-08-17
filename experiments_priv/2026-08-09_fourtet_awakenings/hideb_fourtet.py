"""Test integracyjny tezy tripletów: set Four Teta z ukrytym co DRUGIM
utworem. Dla każdego ukrytego B model dostaje sąsiadów A i C i ma odnaleźć
PRAWDZIWY utwór wśród całego katalogu żniw (2777 dystraktorów).

Etap 1: cechy utworów seta — iTunes Search (entity=song, pewne dopasowanie
artysty i tytułu albo imienny brak) → preview → analiza silnika → kasacja
audio. Etap 2: hide-B co drugi + ranking. Wagi ręczne, α=1 (ustalenia v3).
"""

import json
import pathlib
import re
import sys
import time
import urllib.parse
from concurrent.futures import ProcessPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from dancelab.ingestion.artwork_sync import _http, _norm  # noqa: E402

KAT = pathlib.Path(__file__).parent
ANALIZY = KAT / "analizy"
AUDIO = KAT / "preview_tmp"
ANALIZY.mkdir(exist_ok=True)
AUDIO.mkdir(exist_ok=True)
TRACKLISTA = json.loads((KAT / "tracklista_mixesdb.json").read_text())["utwory"]

_CONFIG = None


def _init_worker():
    global _CONFIG
    from dancelab.core.config import load_config
    _CONFIG = load_config(str(ROOT / "configs/default.yaml"))


def _analizuj(tid, sciezka):
    from dancelab.core.pipeline import analyze_track
    out = ANALIZY / f"{tid}.json"
    try:
        wynik = analyze_track(sciezka, _CONFIG)
        out.write_text(wynik.model_dump_json())
        return tid, ""
    except Exception as exc:  # noqa: BLE001
        return tid, str(exc)[:150]


def szukaj_preview(artysta, tytul):
    czysty = re.sub(r"\s*\((Original|Extended|Instrumental)[^)]*\)", "",
                    tytul, flags=re.I)
    fraza = urllib.parse.quote(f"{artysta} {czysty}"[:120])
    url = (f"https://itunes.apple.com/search?term={fraza}"
           f"&media=music&entity=song&limit=10")
    wyniki = json.loads(_http(url)).get("results", [])
    glowny = artysta.split("&")[0].split("feat")[0]
    for w in wyniki:
        if (_norm(czysty) and _norm(czysty) in _norm(w.get("trackName", ""))
                and _norm(glowny) in _norm(w.get("artistName", ""))
                and w.get("previewUrl")):
            return w["previewUrl"]
    return None


def etap1_cechy():
    braki = []
    zadania = []
    for u in TRACKLISTA:
        tid = f"ft-{u['nr']}"
        if (ANALIZY / f"{tid}.json").exists() or u["artysta"] == "Unknown":
            continue
        try:
            prev = szukaj_preview(u["artysta"], u["tytul"])
        except Exception as exc:  # noqa: BLE001
            prev = None
            braki.append((u["nr"], f"iTunes: {exc}"))
        if not prev:
            braki.append((u["nr"], "brak pewnego preview w iTunes"))
        else:
            cel = AUDIO / f"{tid}.m4a"
            cel.write_bytes(_http(prev))
            zadania.append((tid, str(cel)))
        time.sleep(0.6)
    print(f"preview: {len(zadania)} pobranych · braki {len(braki)}",
          flush=True)
    with ProcessPoolExecutor(max_workers=4, initializer=_init_worker) as ex:
        futy = [ex.submit(_analizuj, tid, sc) for tid, sc in zadania]
        for f in futy:
            tid, blad = f.result()
            if blad:
                braki.append((tid, blad))
    for tid, sc in zadania:
        pathlib.Path(sc).unlink(missing_ok=True)
    (KAT / "hideb_braki.json").write_text(
        json.dumps(braki, ensure_ascii=False, indent=1))
    return braki


def cechy(katalog):
    feats = {}
    for p in katalog.glob("*.json"):
        d = json.loads(p.read_text())
        tr = d.get("track", {})
        frames = d.get("features") or []
        rms = [f.get("rms") for f in frames if f.get("rms") is not None]
        feats[p.stem] = {"bpm": tr.get("bpm_estimate"),
                         "camelot": tr.get("key_estimate"),
                         "energy": (sum(rms) / len(rms)) if rms else None}
    return feats


def etap2_hideb():
    import priors_validation as pv
    from dancelab.decision._common import nearest_bpm_variant

    ft = cechy(ANALIZY)
    zniwa = cechy(ROOT / "experiments_priv/2026-08-08_apple_mixy/analizy")
    feats = {**zniwa, **ft}
    sekwencja = [f"ft-{u['nr']}" for u in TRACKLISTA]
    pula = sorted(zniwa)          # 2777 dystraktorów z żniw
    wyniki = []
    for i in range(1, len(sekwencja) - 1, 2):     # co DRUGI ukryty
        a, b, c = sekwencja[i - 1], sekwencja[i], sekwencja[i + 1]
        if not all(t in feats for t in (a, b, c)):
            wyniki.append({"nr": i + 1, "status": "pominięty (brak cech)"})
            continue
        kandydaci = [b, *[t for t in pula if t != b]]
        fa, fc = feats[a], feats[c]

        def trip(t):
            return (pv.score_hand(fa, feats[t])
                    + pv.score_hand(feats[t], fc))

        def para(t):
            return pv.score_hand(fa, feats[t])

        r_trip = sorted(kandydaci, key=lambda t: -trip(t)).index(b) + 1
        r_para = sorted(kandydaci, key=lambda t: -para(t)).index(b) + 1
        u = TRACKLISTA[i]
        wyniki.append({"nr": u["nr"], "utwor": f"{u['artysta']} – {u['tytul']}",
                       "ranga_triplet": r_trip, "ranga_para": r_para,
                       "pula": len(kandydaci)})
    (KAT / "hideb_wynik.json").write_text(
        json.dumps(wyniki, ensure_ascii=False, indent=1))
    ocenione = [w for w in wyniki if "ranga_triplet" in w]
    for w in wyniki:
        if "ranga_triplet" in w:
            print(f"  {w['nr']:>2}. {w['utwor'][:44]:<44} "
                  f"triplet #{w['ranga_triplet']:<5} para #{w['ranga_para']}")
        else:
            print(f"  {w['nr']:>2}. {w['status']}")
    if ocenione:
        import statistics
        rt = [w["ranga_triplet"] for w in ocenione]
        rp = [w["ranga_para"] for w in ocenione]
        print(f"\nocenione: {len(ocenione)} ukrytych · pula {len(feats)-1}")
        print(f"TRIPLET: mediana rangi {statistics.median(rt):.0f} · "
              f"top10 {sum(1 for r in rt if r <= 10)} · "
              f"top100 {sum(1 for r in rt if r <= 100)}")
        print(f"PARA:    mediana rangi {statistics.median(rp):.0f} · "
              f"top10 {sum(1 for r in rp if r <= 10)} · "
              f"top100 {sum(1 for r in rp if r <= 100)}")


if __name__ == "__main__":
    etap1_cechy()
    etap2_hideb()
