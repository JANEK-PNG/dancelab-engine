"""Zapis i wczytywanie planów setów z TUI — plan przeżywa zamknięcie okna.

Brak z audytu 04.08: po zamknięciu TUI plan znikał, zostawało tylko to,
co poszło do Rekordboxa. Tu ląduje wszystko, co trzeba, by wrócić do pracy:
kolejność (z track_id ORAZ ścieżką — id to sha1 ścieżki, więc po przenosinach
pliku ratuje nas dopasowanie po ścieżce), parametry formularza, PIERWOTNY plan
silnika (do werdyktu „plan vs Twoje zmiany") i dziennik edycji.

Uczciwość przy wczytywaniu: utwór, którego nie ma już w puli, jest POMIJANY
z głośną notką — nigdy nie zgadujemy zamiennika. Uszkodzony plik planu jest
pokazywany na liście jako uszkodzony, nie ukrywany.

Katalog: `data/exports/tui_plany/` — dane osobiste, poza gitem (repo=kod+docs).
"""

from __future__ import annotations

import json
import pathlib
import time

PLANS_DIR = pathlib.Path("data/exports/tui_plany")


def save_plan(order, by_id, *, name: str, params: dict,
              engine_order, edits) -> pathlib.Path:
    """Zapisz bieżący stan setu; zwraca ścieżkę pliku."""
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    rec = {
        "zapisano": time.strftime("%Y-%m-%d %H:%M:%S"),
        "nazwa": name,
        "parametry": dict(params),
        "kolejnosc": [{"track_id": tid,
                       "path": by_id[tid].track.source_path}
                      for tid in order],
        "plan_silnika": list(engine_order or []),
        "edycje": list(edits or []),
    }
    path = PLANS_DIR / f"plan_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return path


def list_plans() -> list[dict]:
    """Zapisane plany, najnowsze pierwsze. Uszkodzony plik = widoczny, nie ukryty."""
    if not PLANS_DIR.exists():
        return []
    out = []
    for p in sorted(PLANS_DIR.glob("plan_*.json"), reverse=True):
        try:
            rec = json.loads(p.read_text())
            out.append({"path": str(p),
                        "zapisano": rec.get("zapisano", "?"),
                        "nazwa": rec.get("nazwa") or p.stem,
                        "n": len(rec.get("kolejnosc", []))})
        except Exception:  # noqa: BLE001 — pokaż problem, nie zamiataj
            out.append({"path": str(p), "zapisano": "?",
                        "nazwa": f"USZKODZONY: {p.name}", "n": 0})
    return out


def read_plan(path: str | pathlib.Path) -> dict:
    return json.loads(pathlib.Path(path).read_text())


def match_order(rec: dict, by_id: dict) -> tuple[list[str], list[str]]:
    """Dopasuj zapisany plan do bieżącej puli → (kolejność, notki).

    Najpierw po track_id; gdy plik zmienił ścieżkę (id = sha1 ścieżki),
    ratunek po ścieżce. Braki są pomijane Z NOTKĄ — nigdy zgadywane.
    """
    by_path = {a.track.source_path: tid for tid, a in by_id.items()}
    order: list[str] = []
    notes: list[str] = []
    for item in rec.get("kolejnosc", []):
        tid = item.get("track_id")
        if tid in by_id:
            order.append(tid)
            continue
        alt = by_path.get(item.get("path", ""))
        if alt is not None:
            order.append(alt)
            notes.append("dopasowany po ścieżce: "
                         f"{pathlib.Path(item['path']).stem[:40]}")
        else:
            notes.append("BRAK W PULI (pominięty): "
                         f"{pathlib.Path(item.get('path', '?')).stem[:40]}")
    return order, notes
