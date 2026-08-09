"""Etap 4 edytora cue: pady z ekranu → hot cue w Rekordboksie.

Czysta warstwa przygotowania (bez UI, bez dotykania bazy przy budowaniu
planu). Trzy rzeczy, których nie robi żadna istniejąca funkcja:

1. **Scalenie**: propozycje silnika + Twoje edycje (nakładka `cue_edycje`)
   → jeden plan do zapisu. Zapisujemy to, co WIDZISZ na ekranie.
2. **Tłumaczenie tożsamości**: plan podglądu mówi o utworach naszymi
   identyfikatorami, a baza Rekordboksa o swoich (ContentID). Mapujemy po
   ścieżce pliku (NFC, jak wszędzie w projekcie). Utwór, którego w kolekcji
   nie ma, jest POMIJANY IMIENNIE — nigdy zgadywany.
3. **Bezpieczeństwo rozstrzyga wyżej**: sam zapis robi
   `ingestion.rekordbox_cue_writer.write_plan` (odmowa przy otwartym
   Rekordboksie, backup, weryfikacja, auto-przywrócenie). Tutaj tylko
   przygotowanie i policzenie kolizji z TWOIMI padami.
"""

from __future__ import annotations

import pathlib
import unicodedata

from dancelab.decision.cue_export_models import (
    CuePlan,
    PlannedCue,
    TrackCuePlan,
    pad_index_to_kind,
)

PADY = "ABCDEFGH"


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", str(s))


def mapa_content_id() -> dict[str, str]:
    """{ścieżka pliku (NFC): ContentID} z kolekcji Rekordboksa."""
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()
    try:
        return {_nfc(r.FolderPath or ""): str(r.ID)
                for r in db.session.query(tables.DjmdContent).all()
                if r.FolderPath}
    finally:
        db.close()


def zbuduj_plan_do_zapisu(plan_podgladu: CuePlan, edycje: dict, by_id: dict,
                          kolejnosc: list[str], content_ids: dict[str, str],
                          ) -> tuple[CuePlan, list[str], list[str]]:
    """(plan dla Rekordboksa, ContentID w kolejności setu, pominięte imiennie).

    Pozycja pada bierze się z tego, co na ekranie: propozycja silnika albo
    Twoje przesunięcie. Pad ręczny (litera bez propozycji) też jedzie."""
    from dancelab.tui.cue_edycje import efektywne_pady

    tracks: list[TrackCuePlan] = []
    ids_setu: list[str] = []
    pominiete: list[str] = []
    for tid in kolejnosc:
        analiza = by_id.get(tid)
        if analiza is None:
            continue
        sciezka = _nfc(analiza.track.source_path)
        cid = content_ids.get(sciezka)
        if cid is None:
            pominiete.append(pathlib.Path(sciezka).stem[:40])
            continue
        ids_setu.append(cid)
        pady = efektywne_pady(plan_podgladu, edycje, tid)
        cues = []
        for litera, p in sorted(pady.items()):
            if litera not in PADY:
                continue
            cues.append(PlannedCue(
                content_id=cid,
                position_ms=int(p["position_ms"]),
                kind=pad_index_to_kind(PADY.index(litera) + 1),
                pad_label=litera,
                comment=p.get("comment") or "",
                cue_type=p.get("typ") or "mix_in",
                confident=bool(p.get("confident")),
            ))
        if cues:
            tracks.append(TrackCuePlan(
                content_id=cid,
                track_title=pathlib.Path(sciezka).stem[:60],
                cues=cues))
    return (plan_podgladu.model_copy(update={"tracks": tracks}),
            ids_setu, pominiete)


def policz_kolizje(plan: CuePlan, istniejace: dict[str, list]) -> dict:
    """Ile padów wejdzie, a ile ustąpi TWOIM cue (polityka: nigdy nie
    nadpisujemy tego, co DJ ustawił sam)."""
    from dancelab.decision.cue_conflict import resolve_conflicts
    from dancelab.decision.cue_export_models import ConflictAction

    rozwiazany, raport = resolve_conflicts(
        plan, istniejace, action=ConflictAction.skip)
    return {"plan": rozwiazany,
            "do_zapisu": raport.cues_to_write,
            "pominiete_kolizje": sum(len(t.cues) for t in plan.tracks)
            - raport.cues_to_write}
