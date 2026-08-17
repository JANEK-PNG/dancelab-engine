"""Drugi katalog dla mapy: Bandcamp — muzyka, której sklepy nie znają.

PO CO. Deezer nie znał 12 932 utworów mapy; zwiad 11.08 zmierzył, że Bandcamp
zna ~20% z nich (12/60) — to jest podziemie wydające na taśmach i winylach.
Ekstrapolacja: ~2 600 dodatkowych utworów z tempem, tonacją, energią
i wektorem → pokrycie mapy ~7 100 → ~9 700.

INSTRUMENT, nazwany uczciwie: Deezer daje 30 s WYBRANE przez wydawcę;
tu wycinamy 30 s ZE ŚRODKA pełnego strumienia. Prawie ten sam instrument,
ale nie identyczny — każdy wiersz niesie `wersja: bandcamp-30s`, a wektory
dostają pole `zrodlo`, żeby przed użyciem obu naraz w MODELU dało się
zrobić test przecieku źródła (reguła po AUC 0,889). Do kolumn tabeli
różnica jest niegroźna.

RYTUAŁ jak zawsze: test-bzdurą na starcie; dopasowanie przyjęte tylko przy
zgodzie znormalizowanego wykonawcy I tytułu; pobierz → policz → SKASUJ,
jeden plik naraz; wznawialne po utwor_id; tylko zapytania o katalog.

Wyniki dopisują się do `pomiar_utworow.jsonl` (świeższy wpis wygrywa przy
scalaniu — wiersz „ok" z Bandcampa nadpisze dawny „brak_w_katalogu")
i do `wektory_mapy.jsonl`.

Użycie:
    .venv/bin/python przelicz_bandcamp.py [--ile N]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
import time
import unicodedata
import urllib.request

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
sys.path.insert(0, str(KORZEN / "scripts"))
KATALOG = pathlib.Path(__file__).resolve().parent
MANIFEST = KATALOG / "pomiar_utworow.jsonl"
WEKTORY = KATALOG / "wektory_mapy.jsonl"
TMP = KATALOG / "_cache_audio"
SZUKAJ = "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic"
UA = {"User-Agent": "DanceLab/1.0 (prywatne badanie lokalne)"}
UA_JSON = {**UA, "Content-Type": "application/json"}
WERSJA = "bandcamp-30s"
DATA = "2026-08-11"


def norm(tekst: str) -> str:
    t = unicodedata.normalize("NFKD", tekst or "").encode("ascii", "ignore").decode()
    t = t.lower()
    t = re.sub(r"\((original|extended|club|radio)[^)]*\)", " ", t)
    t = re.sub(r"\b(original|extended)\s+mix\b", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def pasuje(nw, nt, iw, it) -> bool:
    nw, nt, iw, it = norm(nw), norm(nt), norm(iw), norm(it)
    if not nw or not nt or not iw or not it:
        return False
    w_ok = nw in iw or iw in nw or bool(set(nw.split()) & set(iw.split()))
    t_ok = nt == it or nt in it or it in nt
    return w_ok and t_ok


def szukaj_utworu(wyk: str, tyt: str) -> str | None:
    dane = json.dumps({"search_text": f"{wyk} {tyt}"[:100], "search_filter": "t",
                       "full_page": False, "fan_id": None}).encode()
    req = urllib.request.Request(SZUKAJ, headers=UA_JSON, data=dane)
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode())
    for w in (d.get("auto") or {}).get("results", []):
        if w.get("type") != "t":
            continue
        if pasuje(wyk, tyt, w.get("band_name", ""), w.get("name", "")):
            return w.get("item_url_path")
    return None


def strumien(url_utworu: str) -> tuple[str | None, float]:
    req = urllib.request.Request(url_utworu, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", "replace")
    m = re.search(r'data-tralbum="([^"]+)"', html)
    if not m:
        return None, 0.0
    dane = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&"))
    tr = (dane.get("trackinfo") or [{}])[0]
    return (tr.get("file") or {}).get("mp3-128"), float(tr.get("duration") or 0)


def ffmpeg_bin() -> str:
    kandydat = pathlib.Path.home() / ".local/bin/ffmpeg"
    if kandydat.exists():
        return str(kandydat)
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ile", type=int, default=0)
    ap.add_argument("--bez-wektorow", action="store_true")
    args = ap.parse_args()

    print("test zapytaniem-bzdurą:", flush=True)
    for wyk, tyt in (("Xqzvw Blorptak", "Grumblefish Zzzyx"),
                     ("Vrblgh Qq", "Snorfblat 999")):
        if szukaj_utworu(wyk, tyt) is not None:
            print("  ⛔ zapora nie trzyma — nie ruszam")
            return 1
        time.sleep(0.4)
    print("  ✓ trzyma", flush=True)

    braki, bc_zrobione = {}, set()
    for linia in MANIFEST.read_text().splitlines():
        w = json.loads(linia)
        if w.get("status") == "brak_w_katalogu":
            braki[w["utwor_id"]] = w
        if w.get("wersja") == WERSJA:
            bc_zrobione.add(w["utwor_id"])
    praca = [w for uid, w in braki.items() if uid not in bc_zrobione]
    if args.ile:
        praca = praca[: args.ile]
    print(f"do sprawdzenia w Bandcampie: {len(praca)}", flush=True)

    from dancelab.core.config import load_config
    from dancelab.core.pipeline import analyze_track
    cfg = load_config()

    model = procesor = urzadzenie = None
    if not args.bez_wektorow:
        import torch
        from library_e_embeddings import MODEL_ID, embed_track  # noqa: F401
        from transformers import ClapModel, ClapProcessor
        urzadzenie = "mps" if torch.backends.mps.is_available() else "cpu"
        model = ClapModel.from_pretrained(MODEL_ID).to(urzadzenie).eval()
        procesor = ClapProcessor.from_pretrained(MODEL_ID)

    TMP.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_bin()
    ok = brak = zle = 0
    t0 = time.time()
    with MANIFEST.open("a") as mf, WEKTORY.open("a") as wf:
        for n, x in enumerate(praca, 1):
            uid = x["utwor_id"]
            wpis = {"utwor_id": uid, "wykonawca": x["wykonawca"],
                    "tytul": x["tytul"], "wersja": WERSJA, "data": DATA}
            pelny = TMP / f"bc_{n}.mp3"
            ciety = TMP / f"bc_{n}_30s.mp3"
            try:
                url = szukaj_utworu(x["wykonawca"], x["tytul"])
                if not url:
                    wpis["status"] = "brak_bandcamp"
                    brak += 1
                else:
                    adres, dl = strumien(url)
                    if not adres or dl < 45:
                        wpis["status"] = "brak_strumienia"
                        brak += 1
                    else:
                        req = urllib.request.Request(adres, headers=UA)
                        with urllib.request.urlopen(req, timeout=90) as r, \
                                pelny.open("wb") as fh:
                            fh.write(r.read())
                        start = max((dl - 30) / 2, 0)
                        subprocess.run(
                            [ff, "-y", "-loglevel", "error", "-ss",
                             f"{start:.1f}", "-t", "30", "-i", str(pelny),
                             "-acodec", "copy", str(ciety)], check=True)
                        a = analyze_track(ciety, cfg, title=x["tytul"],
                                          artist=x["wykonawca"])
                        rms = [f.rms for f in a.features if f.rms is not None]
                        ons = [f.onset_density for f in a.features
                               if f.onset_density is not None]
                        bas = [f.bass_energy for f in a.features
                               if f.bass_energy is not None]
                        sr = lambda xs: sum(xs) / len(xs) if xs else None
                        bg = a.beatgrid
                        wpis.update(
                            status="ok",
                            bpm=a.track.bpm_estimate,
                            bpm_pewnosc=(bg.quality_score if bg and
                                         bg.quality_score is not None
                                         else (0.9 if bg and bg.reliable else 0.3)),
                            tonacja=a.track.key_estimate,
                            tonacja_klasyczna=a.track.key_name,
                            tonacja_pewnosc=a.track.key_confidence,
                            energia_surowa=sr(rms), groove_surowy=sr(ons),
                            bas_surowy=sr(bas), dlugosc_s=int(dl),
                            bandcamp_url=url)
                        if model is not None:
                            from library_e_embeddings import embed_track
                            wek = embed_track(ciety, model, procesor, urzadzenie)
                            wf.write(json.dumps({"utwor_id": uid,
                                                 "zrodlo": WERSJA,
                                                 "wektor": wek}) + "\n")
                            wf.flush()
                        ok += 1
            except Exception as exc:  # noqa: BLE001 — jeden utwór ≠ koniec biegu
                wpis["status"] = f"blad:{type(exc).__name__}"
                zle += 1
            finally:
                pelny.unlink(missing_ok=True)
                ciety.unlink(missing_ok=True)   # audio nie zostaje NIGDY
            mf.write(json.dumps(wpis, ensure_ascii=False) + "\n")
            mf.flush()
            time.sleep(0.6)
            if n % 200 == 0:
                zostalo = (time.time() - t0) / n * (len(praca) - n) / 3600
                print(f"  {n}/{len(praca)} · policzone {ok} · brak {brak} · "
                      f"błędy {zle} · ~{zostalo:.1f} h", flush=True)
    print(f"KONIEC: policzone {ok} · brak {brak} · błędy {zle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
