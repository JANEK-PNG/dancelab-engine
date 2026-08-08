"""Edycje padów w edytorze cue (etap 2) — czysty stan, zero UI, zero zapisu.

Model: propozycje silnika są NIEZMIENNE (żyją w CuePlan z podglądu);
edycje DJ-a to osobna warstwa nakładana na wierzch. Dzięki temu:
* propozycja silnika nigdy nie znika — po przesunięciu pada UI pokazuje
  kropkę „silnik proponował…" (uczciwość: widać, o ile się różnicie);
* Z cofa po jednym kroku (historia to migawki warstwy edycji);
* zapis (etap 4) dostanie po prostu listę efektywnych padów.

Pozycje zawsze w milisekundach, przesunięcia w uderzeniach liczonych
z tempa NASZEJ siatki (60000/BPM · N) — pad ląduje na bicie, nie „gdzieś".
"""

from __future__ import annotations

import copy

PADY = "ABCDEFGH"


def nowe() -> dict:
    return {"nadpisania": {}, "zdjete": [], "historia": []}


def _klucz(tid: str, pad: str) -> str:
    return f"{tid}|{pad}"


def _migawka(edycje: dict) -> None:
    edycje["historia"].append(
        (copy.deepcopy(edycje["nadpisania"]), list(edycje["zdjete"])))


def cofnij(edycje: dict) -> bool:
    """Z: wróć do stanu sprzed ostatniej operacji. False = nie ma czego."""
    if not edycje["historia"]:
        return False
    nadpisania, zdjete = edycje["historia"].pop()
    edycje["nadpisania"] = nadpisania
    edycje["zdjete"] = zdjete
    return True


def przesun(edycje: dict, tid: str, pad: str, uderzenia: int, bpm: float,
            silnik_ms: int | None, biezaca_ms: int) -> int:
    """Przesuń pad o N uderzeń. Zwraca nową pozycję w ms (nie schodzi <0)."""
    _migawka(edycje)
    delta = int(round(uderzenia * 60000.0 / max(bpm, 1.0)))
    nowa = max(biezaca_ms + delta, 0)
    edycje["nadpisania"][_klucz(tid, pad)] = {
        "position_ms": nowa, "silnik_ms": silnik_ms}
    k = _klucz(tid, pad)
    if k in edycje["zdjete"]:
        edycje["zdjete"].remove(k)
    return nowa


def postaw(edycje: dict, tid: str, pad: str, position_ms: int) -> None:
    """Nowy pad ręczny (litera bez istniejącego pada)."""
    _migawka(edycje)
    edycje["nadpisania"][_klucz(tid, pad)] = {
        "position_ms": max(int(position_ms), 0), "silnik_ms": None}
    k = _klucz(tid, pad)
    if k in edycje["zdjete"]:
        edycje["zdjete"].remove(k)


def zdejmij(edycje: dict, tid: str, pad: str) -> None:
    """X: zdejmij pad (silnikowy trafia na listę zdjętych, ręczny znika)."""
    _migawka(edycje)
    k = _klucz(tid, pad)
    edycje["nadpisania"].pop(k, None)
    if k not in edycje["zdjete"]:
        edycje["zdjete"].append(k)


def efektywne_pady(plan, edycje: dict, tid: str) -> dict[str, dict]:
    """Pady utworu po nałożeniu edycji: {litera: {position_ms, typ, zrodlo,
    silnik_ms, confident, comment}}. `zrodlo`: silnik | reka."""
    wynik: dict[str, dict] = {}
    for t in plan.tracks:
        if t.content_id != tid:
            continue
        for c in t.cues:
            wynik[c.pad_label] = {
                "position_ms": c.position_ms, "typ": c.cue_type,
                "zrodlo": "silnik", "silnik_ms": c.position_ms,
                "confident": c.confident, "comment": c.comment}
    for klucz, wpis in edycje["nadpisania"].items():
        t_id, pad = klucz.rsplit("|", 1)
        if t_id != tid:
            continue
        bazowy = wynik.get(pad, {})
        wynik[pad] = {
            "position_ms": wpis["position_ms"],
            "typ": bazowy.get("typ", "reczny"),
            "zrodlo": "reka",
            "silnik_ms": wpis.get("silnik_ms"),
            "confident": False,
            "comment": bazowy.get("comment", "")}
    for klucz in edycje["zdjete"]:
        t_id, pad = klucz.rsplit("|", 1)
        if t_id == tid:
            wynik.pop(pad, None)
    return wynik
