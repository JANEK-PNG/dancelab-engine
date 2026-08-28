"""Bieżący set — jedno miejsce dla obu skór.

Do tej pory plan setu żył osobno w każdej skórze: TUI zapisywało go przez
`plan_store`, okno nie zapisywało wcale. Skutek był taki, że zamknięcie
terminala i otwarcie okna znaczyło zaczynanie od zera, a zapis cue z okna byłby
zapisem, którego terminal nigdy nie widział i nie mógł zrecenzować.

Ten moduł niczego nowego nie liczy. Opakowuje `tui.plan_store` w dwie operacje,
których potrzebuje most, i dokłada jedną rzecz: **wskaźnik na plan bieżący**,
żeby obie skóry wiedziały, o którym pliku mowa, bez przekazywania sobie ścieżek.

Czego tu celowo NIE MA: własnego formatu zapisu. `plan_store` trzyma przy każdej
pozycji `track_id` **oraz ścieżkę**, bo id jest hashem ścieżki — po przeniesieniu
pliku tylko ścieżka ratuje dopasowanie. Własny format by to zgubił.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

from dancelab.tui import plan_store

#: Który plan jest „ten, nad którym pracuję". Leży obok planów, bo to ich
#: dotyczy, i jest jednym plikiem, żeby obie skóry czytały to samo.
WSKAZNIK = plan_store.PLANS_DIR / "biezacy.json"


def zapisz(order: list[str], by_id: dict, *, nazwa: str, parametry: dict,
           plan_silnika: list[str] | None = None,
           edycje: list | None = None) -> pathlib.Path:
    """Zapisz set i oznacz go jako bieżący. Zwraca ścieżkę pliku."""
    sciezka = plan_store.save_plan(
        order, by_id, name=nazwa, params=parametry,
        engine_order=plan_silnika or [], edits=edycje or [])
    WSKAZNIK.parent.mkdir(parents=True, exist_ok=True)
    WSKAZNIK.write_text(json.dumps({"plan": str(sciezka)}, ensure_ascii=False),
                        encoding="utf-8")
    return sciezka


def sciezka_biezacego(*, musi_istniec: bool = True) -> pathlib.Path | None:
    """Plan, nad którym pracujemy, albo None.

    ``musi_istniec=False`` zwraca ścieżkę także wtedy, gdy pliku już nie ma —
    bo „nigdy nie zbudowałeś setu" i „set był, ale plik zniknął" to dwie różne
    sytuacje i użytkownik ma prawo je odróżnić.
    """
    if not WSKAZNIK.exists():
        return None
    try:
        p = pathlib.Path(json.loads(WSKAZNIK.read_text(encoding="utf-8"))["plan"])
    except (OSError, ValueError, KeyError):
        return None
    return p if (p.exists() or not musi_istniec) else None


def wczytaj(by_id: dict, sciezka: str | pathlib.Path | None = None
            ) -> dict[str, Any]:
    """Wczytaj plan i dopasuj go do bieżącej puli.

    Zwraca kolejność ORAZ notki dopasowania — utwór, którego nie ma już w puli,
    jest pomijany z głośną notką, nigdy podmieniany. To zachowanie pochodzi z
    `plan_store.match_order` i jest tu przekazane bez zmian.
    """
    cel = (pathlib.Path(sciezka) if sciezka
           else sciezka_biezacego(musi_istniec=False))
    if cel is None:
        return {"kolejnosc": [], "notki": [], "plan": None,
                "powod": "nie ma bieżącego planu — zbuduj set"}
    if not cel.exists():
        return {"kolejnosc": [], "notki": [], "plan": str(cel),
                "powod": f"plan zniknął z dysku: {cel.name}"}

    rec = plan_store.read_plan(cel)
    kolejnosc, notki = plan_store.match_order(rec, by_id)
    return {
        "kolejnosc": kolejnosc,
        "notki": notki,
        "plan": str(cel),
        "nazwa": rec.get("nazwa"),
        "zapisano": rec.get("zapisano"),
        "parametry": rec.get("parametry") or {},
        "zapisanych": len(rec.get("kolejnosc") or []),
    }


def lista() -> list[dict]:
    """Zapisane plany, najnowsze pierwsze — z zaznaczeniem, który jest bieżący."""
    biezacy = sciezka_biezacego()
    wpisy = plan_store.list_plans()
    for w in wpisy:
        w["biezacy"] = biezacy is not None and w["path"] == str(biezacy)
    return wpisy
