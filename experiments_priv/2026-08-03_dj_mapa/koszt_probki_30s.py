"""ILE KOSZTUJE NAS 30-SEKUNDOWA PRÓBKA — mierzone na pełnych analizach.

Po co (Janek 13.08): „mieliśmy bazę sampli przeanalizowanych i chcieliśmy
poprawić nasz silnik pełną analizą utworów". Każdy pomiar w mapie ma
`analiza_wersja = deezer-preview-30s`, czyli tempo, tonacja i energia
policzone z 30 sekund. Rekordbox po pełnym Analyze ma te same utwory
policzone Z CAŁOŚCI. Nakładka tych dwóch zbiorów to jedyny sposób, żeby
zmierzyć, ile tracimy na próbce — i gdzie dokładnie.

METODA (dwa poziomy dopasowania, bo to decyduje o wiarygodności):
  luźne  — jak w czytaj_rekordbox.py: nawiasy wycięte („(Original Mix)"),
           łapie więcej, ale myli remiks z oryginałem;
  ŚCISŁE — pełny tytuł z nawiasami; mniej par, za to prawie pewne.
Wyniki podajemy z obu, bo różnica między nimi mówi, ile w „rozbieżności"
jest naszego błędu, a ile pomyłek parowania.

NIC nie zapisujemy do mapy ani do master.db — to pomiar.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import unicodedata

TU = pathlib.Path(__file__).parent


def norm(s: str, luzne: bool) -> str:
    s = unicodedata.normalize("NFC", s or "").casefold()
    if luzne:
        s = re.sub(r"[\(\[].*?[\)\]]", " ", s)
    s = re.sub(r"[^0-9a-zà-ɏ]+", " ", s)
    return " ".join(s.split())


def wczytaj():
    rb = [json.loads(l) for l in
          (TU / "rekordbox_tonacje.jsonl").read_text().splitlines()]
    encje = {e["utwor_id"]: e for e in
             json.loads((TU / "encje_utwor.json").read_text())}
    return rb, encje


def pary(rb, encje, luzne: bool):
    """Pary (nasze 30 s, Rekordbox z całości) przy danym dopasowaniu."""
    if luzne:                       # rekordbox_tonacje.jsonl JEST luźne
        for d in rb:
            e = encje.get(d["klucz"])
            if e:
                yield e, d
        return
    # ścisłe: przelicz klucze po pełnym tytule i wymagaj identyczności
    for d in rb:
        e = encje.get(d["klucz"])
        if not e:
            continue
        # porównujemy nazwy MAPY z nazwami REKORDBOXA (nie mapy z mapą —
        # na tym się przejechałam raz, wychodziła zgodność 100%)
        if (norm(e.get("wykonawca", ""), False) == norm(d.get("rb_artysta", ""), False)
                and norm(e.get("tytul", ""), False) == norm(d.get("rb_tytul", ""), False)):
            yield e, d


def raport(rb, encje, luzne: bool) -> None:
    etyk = "LUŹNE (nawiasy wycięte)" if luzne else "ŚCISŁE (pełny tytuł)"
    kat = collections.Counter()
    ton_zg = ton_n = 0
    pasma = collections.defaultdict(lambda: [0, 0])   # tempo → [2× błędy, n]
    for e, d in pary(rb, encje, luzne):
        nasz, cal = e.get("bpm"), d.get("bpm_rb")
        if nasz and cal:
            dd, r = abs(nasz - cal), nasz / cal
            if dd <= 0.05:
                kat["tempo zgodne co do setnej"] += 1
            elif dd <= 1.0:
                kat["tempo zgodne (≤1 bpm)"] += 1
            elif abs(r - 2) < 0.03:
                kat["MY 2× ZA SZYBKO"] += 1
            elif abs(r - 0.5) < 0.03:
                kat["my 2× za wolno"] += 1
            else:
                kat["tempo rozbieżne"] += 1
            p = f"{int(cal // 20) * 20}–{int(cal // 20) * 20 + 19}"
            pasma[p][1] += 1
            if abs(r - 2) < 0.03 or abs(r - 0.5) < 0.03:
                pasma[p][0] += 1
        if e.get("tonacja") and d.get("tonacja"):
            ton_n += 1
            ton_zg += str(e["tonacja"]).upper() == str(d["tonacja"]).upper()
    n = sum(kat.values())
    print(f"\n═══ DOPASOWANIE {etyk} — {n} par z tempem ═══")
    for k, v in kat.most_common():
        print(f"   {k:30s} {v:5d}  ({v / n * 100:5.1f}%)")
    zg = kat["tempo zgodne co do setnej"] + kat["tempo zgodne (≤1 bpm)"]
    print(f"   → TEMPO z 30 s = tempo z całości: {zg}/{n} = {zg / n * 100:.1f}%")
    if ton_n:
        print(f"   → TONACJA z 30 s = tonacja z całości: "
              f"{ton_zg}/{ton_n} = {ton_zg / ton_n * 100:.1f}%")
    print("   błędy oktawy wg pasma tempa (wg Rekordboxa):")
    for p, (b, ile) in sorted(pasma.items(), key=lambda kv: int(kv[0].split("–")[0])):
        if ile >= 40:
            print(f"      {p:8s} n={ile:5d}   2× pomyłek {b:4d} = {b / ile * 100:4.1f}%")


def main() -> None:
    rb, encje = wczytaj()
    for luzne in (True, False):
        raport(rb, encje, luzne)


if __name__ == "__main__":
    main()
