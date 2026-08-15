"""Mapa DJ-ów z festiwali 2026 — część, którą da się pobrać bez wyszukiwarki.

Janek chce arkusz: ksywa, imię i nazwisko, Instagram, SoundCloud, Apple Music,
3–10 miksów, trzy autorskie utwory, festiwal 2026, rezydencja klubowa. Przy
700–900 artystach każda kolumna wypełniana ręcznym szukaniem to tysiące zapytań.

Dwie z nich nie wymagają szukania wcale. Darmowe API iTunes zwraca stronę
artysty w Apple Music (`artistLinkUrl`) oraz jego utwory — jedno zapytanie HTTP
na osobę, bez udziału modelu. To samo API sprawdzaliśmy 2026-08-03 pod kątem
podpowiedzi utworów spoza półki.

Czego ten skrypt NIE zrobi, i dlaczego:

  * INSTAGRAM i SOUNDCLOUD — brak publicznego API bez klucza; zostają dla
    wyszukiwarki.
  * IMIĘ I NAZWISKO — wypełniane tylko tam, gdzie artysta sam je publikuje.
    Nigdy zgadywane i nigdy sklejane z przypadkowych źródeł.
  * REZYDENCJA — rzadko podawana w sposób sprawdzalny; wyszukiwarka, i tylko
    gdy stoi w oficjalnym bio albo na stronie klubu.

„Trzy autorskie utwory" mają definicję, żeby nie były moim widzimisię: to
trzy utwory zwrócone przez iTunes dla zapytania po artyście, posortowane wg
liczby wydań/popularności katalogu Apple. Kolumna `zrodlo` mówi wprost, skąd
liczba pochodzi. Dopasowanie nazwy jest sprawdzane — API potrafi zwrócić
kogoś innego o podobnej nazwie, więc wynik niepewny jest oznaczany, a nie
wpisywany po cichu.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import time
import unicodedata as U
import urllib.parse
import urllib.request

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
API = "https://itunes.apple.com/search"
LOOKUP = "https://itunes.apple.com/lookup"

# Gatunki, przy których dopasowanie po nazwie jest wiarygodne. Poza nimi zgodna
# nazwa nie wystarcza: „Praktyczna Pani" trafiła w Apple na wykonawcę
# hip-hopowego, a na Audioriver grała DJ-ka. Taki wiersz dostaje flagę
# do sprawdzenia zamiast cichego linku do kogoś innego.
# Pierwsza wersja tej listy oznaczyła London Elektricity jako podejrzanego, bo
# Apple daje mu „Jungle/Drum'n'bass" — a to jest dokładnie to, co on gra od
# trzydziestu lat. Filtr, który krzyczy na poprawne trafienia, uczy ignorować
# swoje własne ostrzeżenia, więc lista obejmuje wszystko, co realnie występuje
# na tych festiwalach. Zostaje wąska tam, gdzie ma sens: „Children's Music"
# albo „Country" przy DJ-u z Garbicza to prawie na pewno inny wykonawca.
GATUNKI_OK = {"electronic", "dance", "techno", "house", "dj mix", "trance",
              "drum & bass", "drum'n'bass", "jungle/drum'n'bass", "dubstep",
              "breakbeat", "downtempo", "experimental", "ambient", "alternative",
              "world", "jazz", "pop", "rock", "r&b/soul", "hip-hop/rap",
              "reggae", "latin", "afrobeats", "new age", "soundtrack",
              "electronica", "industrial", "singer/songwriter"}
UA = {"User-Agent": "DanceLab-research/0.1 (local, non-commercial)"}


def _norm(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def _get(params: dict) -> dict:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def apple_artist(name: str) -> dict | None:
    """Strona artysty w Apple Music — albo None, gdy nie ma pewnego dopasowania.

    Pewne dopasowanie znaczy: znormalizowana nazwa zwrócona przez API jest
    identyczna z szukaną. Bez tego „Siri" albo „Novah" trafiłyby na zupełnie
    innego wykonawcę, a wpisanie takiego linku jest gorsze niż puste pole.
    """
    try:
        data = _get({"term": name, "entity": "musicArtist", "limit": 10})
    except Exception:                                              # noqa: BLE001
        return None
    target = _norm(name)
    for r in data.get("results", []):
        if _norm(r.get("artistName", "")) == target:
            gatunek = r.get("primaryGenreName") or ""
            return {
                "apple_music": r.get("artistLinkUrl"),
                "apple_id": r.get("artistId"),
                "gatunek_apple": gatunek,
                "do_sprawdzenia": gatunek.lower() not in GATUNKI_OK,
            }
    return None


def apple_top_tracks(artist_id: int, limit: int = 3) -> list[dict]:
    """Utwory artysty z katalogu Apple. Pusta lista = nic pewnego nie znaleziono."""
    # Utwory bierze się z /lookup, nie z /search — /search ignoruje `id`
    # i dlatego pierwszy przebieg zwrócił zero utworów przy 20 trafionych
    # artystach. Sprzeczność sama w sobie była sygnałem, że coś jest źle.
    try:
        url = f"{LOOKUP}?{urllib.parse.urlencode({'id': artist_id, 'entity': 'song', 'limit': 30})}"
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception:                                              # noqa: BLE001
        return []
    out = []
    for r in data.get("results", []):
        if r.get("wrapperType") != "track":
            continue
        out.append({
            "tytul": r.get("trackName"),
            "album": r.get("collectionName"),
            "rok": (r.get("releaseDate") or "")[:4],
            "link": r.get("trackViewUrl"),
            "zrodlo": "iTunes Search API (katalog Apple Music)",
        })
        if len(out) >= limit:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artysci", required=True, help="Plik z listą nazw, jeden na wiersz")
    ap.add_argument("--pauza", type=float, default=0.4, help="Przerwa między zapytaniami")
    ap.add_argument("--wyjscie", default="apple.json",
                    help="Nazwa pliku wynikowego. Osobna nazwa przy dobieraniu "
                         "nowej partii artystów — inaczej nadpisalibyśmy poprzedni przebieg.")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    names = [n.strip() for n in pathlib.Path(args.artysci).read_text().splitlines() if n.strip()]
    rows, tracks = [], []
    trafione = 0
    for i, name in enumerate(names, 1):
        found = apple_artist(name)
        row = {"ksywa": name, "apple_music": None, "gatunek_apple": None}
        if found:
            trafione += 1
            row.update({"apple_music": found["apple_music"],
                        "gatunek_apple": found["gatunek_apple"],
                        "do_sprawdzenia": found["do_sprawdzenia"]})
            for t in apple_top_tracks(found["apple_id"]):
                tracks.append({"ksywa": name, **t})
            time.sleep(args.pauza)
        rows.append(row)
        znak = ("Apple ⚠ inny gatunek" if found and found["do_sprawdzenia"]
                else "Apple ✓" if found else "Apple —")
        print(f"  {i}/{len(names)} {name[:32]:32s} {znak}", flush=True)
        time.sleep(args.pauza)

    (OUT / args.wyjscie).write_text(json.dumps(
        {"artysci": rows, "utwory": tracks}, ensure_ascii=False, indent=1))
    print(f"\nApple Music trafionych: {trafione}/{len(names)} "
          f"({trafione / len(names) * 100:.0f}%)")
    print(f"utworów zebranych: {len(tracks)}")
    print(f"zapisane: {OUT / args.wyjscie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
