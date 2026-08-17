"""Odczyt tonacji i tempa z master.db Rekordboxa dla utworów mapy DJ-ów.

ZASADY (twarde, z rejestru):
- pracujemy WYŁĄCZNIE na kopii master.db (oryginału nie dotykamy),
- pierwszy test to zapytanie-bzdura: utwór, którego NIE MA — musi wrócić nic,
- dopasowanie po ZNORMALIZOWANEJ nazwie (artysta ORAZ tytuł, NFC, casefold),
  nigdy po ścieżce; brak dopasowania = brak wpisu, nie zgadujemy.

Wyjście: rekordbox_tonacje.jsonl — {klucz, artysta, tytul, tonacja, bpm_rb}.
"""

from __future__ import annotations

import json
import pathlib
import re
import shutil
import sys
import unicodedata

BAZA = pathlib.Path.home() / "Library/Pioneer/rekordbox/master.db"
TU = pathlib.Path(__file__).parent
KOPIA = TU / "master_kopia.db"
WYJSCIE = TU / "rekordbox_tonacje.jsonl"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "").casefold()
    s = re.sub(r"[\(\[].*?[\)\]]", " ", s)          # (original mix) itp.
    s = re.sub(r"[^0-9a-zÀ-ɏ]+", " ", s)  # interpunkcja won
    return " ".join(s.split())


def wczytaj_rekordbox() -> list[dict]:
    # Kopia obok skryptu: Rekordbox może w tym czasie pisać do oryginału.
    shutil.copy2(BAZA, KOPIA)
    for boczny in (".db-wal", ".db-shm"):
        src = BAZA.with_suffix(boczny)
        if src.exists():
            shutil.copy2(src, KOPIA.with_suffix(boczny))
    from pyrekordbox import Rekordbox6Database

    db = Rekordbox6Database(KOPIA)
    wiersze = []
    for c in db.get_content():
        tonacja = c.Key.ScaleName if c.Key is not None else None
        wiersze.append({
            "artysta": c.Artist.Name if c.Artist is not None else "",
            "tytul": c.Title or "",
            "tonacja": tonacja,
            "bpm_rb": (c.BPM or 0) / 100.0 or None,
            # Janek 13.08: „nie wszystko było przeanalizowane". Bez tego
            # znacznika mieszamy tonacje POLICZONE przez Rekordboxa z tymi,
            # które przyszły ze znaczników pliku — i cała porównywarka kłamie.
            "analiza": int(c.Analysed or 0),
            "ma_anlz": bool(c.AnalysisDataPath),
        })
    db.close()
    return wiersze


def main() -> None:
    wiersze = wczytaj_rekordbox()
    print(f"master.db (kopia): {len(wiersze)} utworów")

    indeks: dict[tuple[str, str], dict] = {}
    for w in wiersze:
        k = (norm(w["artysta"]), norm(w["tytul"]))
        if k[1]:
            indeks.setdefault(k, w)

    # BRAMKA 1: zapytanie-bzdura — nie ma prawa nic wrócić.
    bzdura = indeks.get((norm("Zenon Nieistniejący"), norm("Utwór Widmo 999")))
    if bzdura is not None:
        sys.exit("BZDURA ZWRÓCIŁA WYNIK — indeks skażony, STOP")
    print("bramka-bzdura: OK (nic nie wróciło)")

    encje = json.loads((TU / "encje_utwor.json").read_text())
    trafienia, braki = 0, 0
    with WYJSCIE.open("w") as f:
        for e in encje:
            k = (norm(e.get("wykonawca", "")), norm(e.get("tytul", "")))
            w = indeks.get(k)
            if w is None or not w["tonacja"]:
                braki += 1
                continue
            trafienia += 1
            f.write(json.dumps({
                "klucz": e["utwor_id"], "artysta": e.get("wykonawca"),
                "tytul": e.get("tytul"), "tonacja": w["tonacja"],
                "bpm_rb": w["bpm_rb"], "analiza": w["analiza"],
                "ma_anlz": w["ma_anlz"],
                # nazwy PO STRONIE REKORDBOXA — bez nich nie da się później
                # sprawdzić ostrzej, czy to na pewno to samo nagranie
                "rb_artysta": w["artysta"], "rb_tytul": w["tytul"],
                }, ensure_ascii=False) + "\n")
    print(f"mapa: trafienia z tonacją {trafienia} · bez dopasowania {braki}")
    print(f"zapisano: {WYJSCIE.name}")


if __name__ == "__main__":
    main()
