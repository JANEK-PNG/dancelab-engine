"""Wypełnianie kolumn analizy dźwięku w mapie DJ-ów — z katalogu, nie z dysku.

DECYZJA JANKA 2026-08-10: „kompletnie zapomnij o muzyce, którą mam na dysku".
Cała tabela liczona JEDNYM instrumentem — 30-sekundową próbką z katalogu
Deezer — więc porównania utwór-do-utworu są spójne same z siebie. Lekcja
o przecieku źródła (AUC 0,889, patrz dancelab-pro-ml) mówi to samo od strony
metodologii: nie mieszać źródeł w jednej tabeli.

ZASADY (zgoda Janka 02.08, te same co przy personach):
  pobierz → policz → SKASUJ audio, jeden plik naraz, wysyłamy wyłącznie
  zapytania o katalog, nic o użytkowniku.

NAJWIĘKSZE RYZYKO: złe dopasowanie nazwy do katalogu (zmierzone na próbie:
„AY AY" trafiło w inny utwór, 124 vs 105 BPM). Dlatego dopasowanie jest
przyjmowane TYLKO, gdy znormalizowany wykonawca i tytuł zgadzają się po obu
stronach. Wątpliwe dopasowanie = puste pole, nie zgadywanie.

PIERWSZY TEST = ZAPYTANIE-BZDURA (twarda reguła po wpadce NTS +71%):
zapytanie, które NIE powinno nic zwrócić. Jeśli zwraca — dopasowanie po
nazwach jest jedyną zaporą i musi być włączone zawsze.

Wyniki idą do manifestu JSONL (wznawialne po utwor_id); scalanie do
`encje_utwor.json` robi osobny skrypt `scal_pomiary.py`, bo energia,
groove i bas są normalizowane 0–1 percentylowo po CAŁEJ policzonej puli.

Użycie:
    .venv/bin/python przelicz_utwory.py --bzdura        # sam test zapory
    .venv/bin/python przelicz_utwory.py --ile 50        # próba
    .venv/bin/python przelicz_utwory.py                 # pełny bieg
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
KATALOG = pathlib.Path(__file__).resolve().parent
MANIFEST = KATALOG / "pomiar_utworow.jsonl"
TMP = KATALOG / "_cache_audio"
UA = "DanceLab/1.0 (prywatne badanie lokalne)"
WERSJA = "deezer-preview-30s"
DATA = "2026-08-10"


def norm(tekst: str) -> str:
    """Do porównań: bez akcentów, bez interpunkcji, bez dopisków wydania."""
    t = unicodedata.normalize("NFKD", tekst or "").encode("ascii", "ignore").decode()
    t = t.lower()
    t = re.sub(r"\((original|extended|club|radio)[^)]*\)", " ", t)
    t = re.sub(r"\b(original|extended)\s+mix\b", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def pasuje(nasz_w: str, nasz_t: str, ich_w: str, ich_t: str) -> bool:
    """Zapora przed cudzym utworem: wykonawca I tytuł muszą się zgadzać."""
    nw, nt, iw, it = norm(nasz_w), norm(nasz_t), norm(ich_w), norm(ich_t)
    if not nw or not nt or not iw or not it:
        return False
    # wykonawca: jeden zawiera drugiego (feat./kolejność bywa różna)
    w_ok = nw in iw or iw in nw or bool(set(nw.split()) & set(iw.split()))
    # tytuł: rdzeń identyczny albo jeden zawiera drugi w całości
    t_ok = nt == it or nt in it or it in nt
    return w_ok and t_ok


def szukaj(w: str, t: str) -> dict | None:
    q = f"{w} {t}"[:120]
    url = "https://api.deezer.com/search?" + urllib.parse.urlencode(
        {"q": q, "limit": 5})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as odp:
        dane = json.loads(odp.read().decode()).get("data", [])
    for d in dane:
        if not d.get("preview"):
            continue
        if pasuje(w, t, (d.get("artist") or {}).get("name", ""),
                  d.get("title", "")):
            return d
    return None


def test_bzdura() -> bool:
    """Zapytanie, które NIE powinno przejść zapory. Prawda = zapora trzyma."""
    smieci = [("Xqzvw Blorptak", "Grumblefish Zzzyx Nocturne"),
              ("Vrblgh Qqmwx", "Snorfblat Overture 999")]
    for w, t in smieci:
        wynik = szukaj(w, t)
        if wynik is not None:
            print(f"  ⛔ BZDURA PRZESZŁA: {w} - {t} → "
                  f"{wynik.get('artist', {}).get('name')} - {wynik.get('title')}")
            return False
        time.sleep(0.35)
    print("  ✓ zapora trzyma — na zapytania-bzdury nic nie przechodzi")
    return True


def lista_pracy() -> list[dict]:
    """Utwory potrzebne do szwów, czyste, najczęściej grane najpierw."""
    u = json.loads((KATALOG / "encje_utwor.json").read_text())
    s = json.loads((KATALOG / "fakty_szew.json").read_text())
    uid = {x["utwor_id"]: x for x in u}

    def czysty(x):
        w, t = (x.get("wykonawca") or "").strip(), (x.get("tytul") or "").strip()
        if not w or not t or t in ("?", "ID") or w in ("?", "ID"):
            return False
        # "Unknown - Untitled" to BRAK tożsamości, nie tożsamość — dopasuje się
        # do dowolnego wydawnictwa o tej nazwie (złapane w próbie 50).
        if norm(w) in ("unknown", "unknown artist", "various", "various artists", "va"):
            return False
        if norm(t) in ("unknown", "untitled") or norm(t).startswith("untitled"):
            return False
        return not re.search(r"\?{2,}|^id\b|unreleased", t.lower())

    potrzebne = set()
    for sz in s:
        for k in ("utwor_z_id", "utwor_do_id"):
            i = sz.get(k) or ""
            if i in uid and czysty(uid[i]):
                potrzebne.add(i)
    zrobione = set()
    if MANIFEST.exists():
        for linia in MANIFEST.read_text().splitlines():
            try:
                zrobione.add(json.loads(linia)["utwor_id"])
            except Exception:
                pass
    praca = [uid[i] for i in potrzebne if i not in zrobione]
    praca.sort(key=lambda x: -x.get("wystapien", 0))
    return praca


def policz(plik: pathlib.Path, cfg, tytul: str, wykonawca: str) -> dict:
    from dancelab.core.pipeline import analyze_track

    a = analyze_track(plik, cfg, title=tytul, artist=wykonawca)
    rms = [f.rms for f in a.features if f.rms is not None]
    onset = [f.onset_density for f in a.features if f.onset_density is not None]
    bas = [f.bass_energy for f in a.features if f.bass_energy is not None]
    bg = a.beatgrid
    sr = lambda xs: sum(xs) / len(xs) if xs else None
    return {
        "bpm": a.track.bpm_estimate,
        "bpm_pewnosc": (bg.quality_score if bg and bg.quality_score is not None
                        else (0.9 if bg and bg.reliable else 0.3)),
        "tonacja": a.track.key_estimate,
        "tonacja_klasyczna": a.track.key_name,
        "tonacja_pewnosc": a.track.key_confidence,
        "energia_surowa": sr(rms),
        "groove_surowy": sr(onset),
        "bas_surowy": sr(bas),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ile", type=int, default=0, help="0 = wszystko")
    ap.add_argument("--bzdura", action="store_true")
    args = ap.parse_args()

    print("test zapytaniem-bzdurą:")
    if not test_bzdura():
        print("zapora NIE trzyma — nie ruszam dalej")
        return 1
    if args.bzdura:
        return 0

    from dancelab.core.config import load_config
    cfg = load_config()
    praca = lista_pracy()
    if args.ile:
        praca = praca[: args.ile]
    print(f"do policzenia: {len(praca)} utworów", flush=True)
    TMP.mkdir(parents=True, exist_ok=True)

    ok = brak = zle = 0
    t0 = time.time()
    with MANIFEST.open("a") as mf:
        for n, x in enumerate(praca, 1):
            wpis = {"utwor_id": x["utwor_id"], "wykonawca": x["wykonawca"],
                    "tytul": x["tytul"], "wersja": WERSJA, "data": DATA}
            try:
                hit = szukaj(x["wykonawca"], x["tytul"])
                if hit is None:
                    wpis["status"] = "brak_w_katalogu"
                    brak += 1
                else:
                    plik = TMP / f"{hit['id']}.mp3"
                    try:
                        req = urllib.request.Request(
                            hit["preview"], headers={"User-Agent": UA})
                        with urllib.request.urlopen(req, timeout=45) as r, \
                                plik.open("wb") as fh:
                            fh.write(r.read())
                        wpis.update(policz(plik, cfg, x["tytul"], x["wykonawca"]))
                        wpis["status"] = "ok"
                        wpis["dlugosc_s"] = int(hit.get("duration") or 0) or None
                        wpis["deezer_id"] = hit["id"]
                        wpis["deezer_artysta"] = (hit.get("artist") or {}).get("name")
                        wpis["deezer_tytul"] = hit.get("title")
                        ok += 1
                    finally:
                        plik.unlink(missing_ok=True)   # audio nie zostaje NIGDY
            except Exception as exc:  # noqa: BLE001 — jeden utwór ≠ koniec biegu
                wpis["status"] = f"blad:{type(exc).__name__}"
                zle += 1
            mf.write(json.dumps(wpis, ensure_ascii=False) + "\n")
            mf.flush()
            time.sleep(0.35)
            if n % 100 == 0:
                tempo = (time.time() - t0) / n
                zostalo = tempo * (len(praca) - n) / 3600
                print(f"  {n}/{len(praca)} · policzone {ok} · brak {brak} · "
                      f"błędy {zle} · ~{zostalo:.1f} h do końca", flush=True)
    print(f"\nKONIEC: policzone {ok} · brak w katalogu {brak} · błędy {zle}")
    print(f"manifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
