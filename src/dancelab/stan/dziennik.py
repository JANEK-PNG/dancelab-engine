"""Dziennik decyzji DJ-a przy oknie — akceptacje i odrzucenia propozycji.

Pytanie Q14 z rejestru (01.08): „logujemy Twoje akceptacje/odrzucenia
propozycji silnika?" — jedyny ruch, przy którym używanie produktu samo go
uczy. Decyzja Janka 01.09: logujemy. Dane zbierają się wyłącznie do przodu,
więc każde zdarzenie jest dopisaniem; niczego nie nadpisujemy i nie kasujemy.

Terminal loguje od 04.08 (`tui/app.py::_log_verdict`), okno do dziś nie
logowało nic — ten moduł jest jego drogą. Zapisy lądują w tym samym katalogu
co werdykty terminala, żeby całą historię decyzji dało się czytać z jednego
miejsca.

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

from dancelab.stan.sciezki import KORZEN

KATALOG = KORZEN / "experiments_priv" / "2026-08-04_werdykty"

#: Strumień zdarzeń okna (odpowiednik `tui_edycje.jsonl` terminala).
PLIK_ZDARZEN = "gui_dziennik.jsonl"


def zrodlo_kandydata(meta: dict[str, dict[str, Any]], tid: str) -> dict[str, Any]:
    """Skąd wziął się utwór wstawiony do setu — z listy silnika czy z ręki DJ-a.

    `meta` to rangi z OTWARTEGO panelu kandydatów (tid → ranga/score/tryb).
    Wybór bez wpisu jest uczciwie opisany jako własny, nie zgadywany — dzień
    po dodaniu wstawiania z Biblioteki da się policzyć, ile podmian kończy
    się wyborem z NASZYCH kandydatów. Jedna definicja dla obu skór.
    """
    wpis = meta.get(tid)
    return dict(wpis) if wpis else {"zrodlo": "reka_dj"}


def dopisz(typ: str, **pola: Any) -> str | None:
    """Dopisz jedno zdarzenie do strumienia; błąd ZWRÓĆ zamiast rzucać.

    Zwrócony opis idzie do widoku jako ostrzeżenie — edycja, której zdarzenie
    dotyczy, już się udała i nie wolno jej wywracać przez dziennik.
    """
    rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "typ": typ, **pola}
    try:
        KATALOG.mkdir(parents=True, exist_ok=True)
        with (KATALOG / PLIK_ZDARZEN).open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return None
    except OSError as exc:
        return f"dziennik nie zapisał zdarzenia {typ!r}: {exc}"


def zapisz_werdykt(rec: dict[str, Any]) -> tuple[str | None, str | None]:
    """Werdykt końcowy do osobnego pliku (jak `tui_werdykt_*.json`).

    Zwraca (ścieżka, błąd) — dokładnie jedno z dwojga jest ustawione.
    """
    try:
        KATALOG.mkdir(parents=True, exist_ok=True)
        plik = KATALOG / f"gui_werdykt_{time.strftime('%Y%m%d_%H%M%S')}.json"
        # default=str: jeden niezapisywalny typ (np. w wagach) nie ma prawa
        # zgubić całego werdyktu — wartość zostaje czytelnym napisem.
        plik.write_text(json.dumps(rec, ensure_ascii=False, indent=1,
                                   default=str), encoding="utf-8")
        return str(plik), None
    except OSError as exc:
        return None, f"werdyktu nie zapisałem: {exc}"
