"""Wektory brzmienia (CLAP) dla policzonych utworów mapy DJ-ów.

PO CO. Teza tripletów Janka w wersji, która ma sens: B jest pomostem
BRZMIENIOWYM między A i C — „BPM może być ten sam w folku i hard techno,
a to dwa osobne gatunki; chodzi o synergię" (Janek, 2026-08-11). Test na
tempie i energii dał zero (45,8% vs 46,2% losu) — właściwy test wymaga
przestrzeni brzmienia.

JAK. Bierzemy utwory ze statusem `ok` w manifeście pomiarów. NIE szukamy
ponownie po nazwie — używamy zapisanego `deezer_id` (dopasowanie już
zaudytowane), a świeży adres próbki bierzemy z `api.deezer.com/track/{id}`,
bo stare adresy CDN wygasają. Ten sam model co w bibliotece Janka
(laion/clap-htsat-unfused), więc wektory są porównywalne z resztą projektu —
ale NIE wolno ich mieszać z wektorami z pełnych plików w jednym zbiorze
(przeciek źródła, AUC 0,889): tu wszystko jest z próbek 30 s i zostaje
w obrębie mapy.

Zasady jak zawsze: pobierz → policz → SKASUJ audio, jeden plik naraz,
wysyłamy wyłącznie identyfikatory katalogu.

Wynik: `wektory_mapy.jsonl` — {utwor_id, deezer_id, wektor}. Wznawialne.

Użycie:
    .venv/bin/python policz_wektory_mapy.py [--ile N]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.request

KORZEN = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORZEN / "src"))
sys.path.insert(0, str(KORZEN / "scripts"))
KATALOG = pathlib.Path(__file__).resolve().parent
MANIFEST = KATALOG / "pomiar_utworow.jsonl"
WYJSCIE = KATALOG / "wektory_mapy.jsonl"
TMP = KATALOG / "_cache_audio"
UA = "DanceLab/1.0 (prywatne badanie lokalne)"


def swiezy_preview(deezer_id: int) -> str | None:
    req = urllib.request.Request(f"https://api.deezer.com/track/{deezer_id}",
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as odp:
        return json.loads(odp.read().decode()).get("preview") or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ile", type=int, default=0)
    args = ap.parse_args()

    praca = []
    widziane = set()
    for linia in MANIFEST.read_text().splitlines():
        w = json.loads(linia)
        if w.get("status") == "ok" and w.get("deezer_id") and \
                w["utwor_id"] not in widziane:
            widziane.add(w["utwor_id"])
            praca.append((w["utwor_id"], w["deezer_id"]))
    zrobione = set()
    if WYJSCIE.exists():
        for linia in WYJSCIE.read_text().splitlines():
            try:
                zrobione.add(json.loads(linia)["utwor_id"])
            except Exception:
                pass
    praca = [p for p in praca if p[0] not in zrobione]
    if args.ile:
        praca = praca[: args.ile]
    print(f"do policzenia wektorów: {len(praca)}", flush=True)

    import torch
    from library_e_embeddings import MODEL_ID, embed_track
    from transformers import ClapModel, ClapProcessor
    urzadzenie = "mps" if torch.backends.mps.is_available() else "cpu"
    model = ClapModel.from_pretrained(MODEL_ID).to(urzadzenie).eval()
    procesor = ClapProcessor.from_pretrained(MODEL_ID)

    TMP.mkdir(parents=True, exist_ok=True)
    ok = zle = 0
    t0 = time.time()
    with WYJSCIE.open("a") as out:
        for n, (uid, did) in enumerate(praca, 1):
            plik = TMP / f"{did}.mp3"
            try:
                adres = swiezy_preview(did)
                if not adres:
                    zle += 1
                    continue
                req = urllib.request.Request(adres, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=45) as r, \
                        plik.open("wb") as fh:
                    fh.write(r.read())
                wektor = embed_track(plik, model, procesor, urzadzenie)
                out.write(json.dumps({"utwor_id": uid, "deezer_id": did,
                                      "wektor": wektor}) + "\n")
                out.flush()
                ok += 1
            except Exception as exc:  # noqa: BLE001 — jeden utwór ≠ koniec biegu
                zle += 1
                if zle <= 5:
                    print(f"  ⚠ {uid}: {type(exc).__name__} {exc}", flush=True)
            finally:
                plik.unlink(missing_ok=True)   # audio nie zostaje NIGDY
            time.sleep(0.25)
            if n % 200 == 0:
                tempo = (time.time() - t0) / n
                print(f"  {n}/{len(praca)} · wektory {ok} · błędy {zle} · "
                      f"~{tempo * (len(praca) - n) / 3600:.1f} h do końca",
                      flush=True)
    print(f"\nKONIEC: wektory {ok} · błędy {zle} → {WYJSCIE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
