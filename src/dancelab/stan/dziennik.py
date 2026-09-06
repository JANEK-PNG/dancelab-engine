"""Dziennik decyzji DJ-a przy oknie — akceptacje i odrzucenia propozycji.

Pytanie Q14 z rejestru (01.08): „logujemy Twoje akceptacje/odrzucenia
propozycji silnika?" — jedyny ruch, przy którym używanie produktu samo go
uczy. Decyzja Janka 01.09: logujemy. Dane zbierają się wyłącznie do przodu,
więc każde zdarzenie jest dopisaniem; niczego nie nadpisujemy i nie kasujemy.

Od 02.09 to JEDYNY pisarz dla obu skór (Janek: „połącz elementy wspólne").
Do tego dnia terminal pisał sam (`tui/app.py::_log_verdict`) do
`tui_edycje.jsonl` i `tui_werdykt_*.json`, a okno tutaj do
`gui_dziennik.jsonl`. Te pliki zostają NIETKNIĘTE jako archiwum — dane są
tylko do przodu. Nowe zdarzenia obu skór idą do `dziennik.jsonl` z polem
`skora` („tui" | „gui"); werdykty zachowują prefiks skóry w nazwie pliku,
żeby dotychczasowe globy czytelników dalej działały.

Zasady uczciwości (ADR-005):
- pad silnika, którego DJ nie oglądał, NIE jest „zaakceptowany" — przeszedł
  domyślnie i tak ma być opisany (pole `propozycje_widziane` per utwór);
- edycja utworu, dla którego propozycji nie pokazano, nie dostaje pól
  kontekstu — nieznane zostaje nieznane, nie zerem;
- awaria zapisu dziennika nie blokuje edycji (dziennik to dodatek), ale
  wraca do widoku jako ostrzeżenie, nie znika po cichu.

Katalog jest zakotwiczony w korzeniu repo, nie w bieżącym katalogu procesu.
`WERDYKTY_DIR` terminala jest względne i działa tylko dlatego, że wszystko
startuje z korzenia — dla danych zbieranych „tylko do przodu" jedno
uruchomienie skądinąd rozwidliłoby historię po cichu.
"""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

from dancelab.stan.sciezki import KORZEN
from dancelab.storage.atomic import write_text_atomic

KATALOG = KORZEN / "experiments_priv" / "2026-08-04_werdykty"

#: Wspólny strumień zdarzeń obu skór (od 02.09). Archiwa sprzed scalenia:
#: `tui_edycje.jsonl` (terminal, 04.08–02.09), `gui_dziennik.jsonl` (okno,
#: 01.09–02.09) — czytelnik historii ma złożyć trzy pliki, nie jeden.
PLIK_ZDARZEN = "dziennik.jsonl"

#: Dozwolone znaczniki skóry — literówka w nazwie rozwidliłaby historię.
SKORY = ("tui", "gui")


def zrodlo_kandydata(meta: dict[str, dict[str, Any]], tid: str) -> dict[str, Any]:
    """Skąd wziął się utwór wstawiony do setu — z listy silnika czy z ręki DJ-a.

    `meta` to rangi z OTWARTEGO panelu kandydatów (tid → ranga/score/tryb).
    Wybór bez wpisu jest uczciwie opisany jako własny, nie zgadywany — dzień
    po dodaniu wstawiania z Biblioteki da się policzyć, ile podmian kończy
    się wyborem z NASZYCH kandydatów. Jedna definicja dla obu skór.
    """
    wpis = meta.get(tid)
    return dict(wpis) if wpis else {"zrodlo": "reka_dj"}


def dopisz(typ: str, *, skora: str, **pola: Any) -> str | None:
    """Dopisz jedno zdarzenie do strumienia; błąd ZWRÓĆ zamiast rzucać.

    `skora` jest WYMAGANA i słowna: zdarzenie bez niej byłoby nie do
    przypisania po scaleniu strumieni. Zwrócony opis idzie do widoku jako
    ostrzeżenie — edycja, której zdarzenie dotyczy, już się udała i nie wolno
    jej wywracać przez dziennik.
    """
    if skora not in SKORY:
        return f"dziennik: nieznana skóra {skora!r} — zdarzenie {typ!r} nie zapisane"
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "skora": skora,
           "typ": typ, **pola}
    try:
        KATALOG.mkdir(parents=True, exist_ok=True)
        with (KATALOG / PLIK_ZDARZEN).open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return None
    except OSError as exc:
        return f"dziennik nie zapisał zdarzenia {typ!r}: {exc}"


def zapisz_werdykt(rec: dict[str, Any], *, skora: str
                   ) -> tuple[str | None, str | None]:
    """Werdykt końcowy do osobnego pliku `<skora>_werdykt_<czas>.json`.

    Kształt rekordu jest sprawą skóry (terminal: plan_silnika/stan_dja/edycje;
    okno: utwory/pady/miara) — pisarz jest jeden, pola `skora` i `ts` stempluje
    sam. Zwraca (ścieżka, błąd) — dokładnie jedno z dwojga jest ustawione.
    """
    if skora not in SKORY:
        return None, f"werdykt: nieznana skóra {skora!r} — nie zapisałem"
    rec = {"skora": skora, "ts": time.strftime("%Y-%m-%d %H:%M:%S"), **rec}
    try:
        KATALOG.mkdir(parents=True, exist_ok=True)
        plik = KATALOG / f"{skora}_werdykt_{time.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex}.json"
        # default=str: jeden niezapisywalny typ (np. w wagach) nie ma prawa
        # zgubić całego werdyktu — wartość zostaje czytelnym napisem.
        write_text_atomic(plik, json.dumps(rec, ensure_ascii=False, indent=1,
                                          default=str), overwrite=False)
        return str(plik), None
    except OSError as exc:
        return None, f"werdyktu nie zapisałem: {exc}"
