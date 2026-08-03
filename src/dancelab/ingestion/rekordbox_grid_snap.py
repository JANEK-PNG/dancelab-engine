"""Przyciągnij zaplanowane cue do siatki bitów Rekordboxa, nie do naszej.

Janek zobaczył to pierwszego dnia, kiedy cue trafiły do jego biblioteki: znacznik
stał 0,3 taktu od jedynki, którą rysuje Rekordbox („106.3 Bars"). Cue poza siatką
jest do miksowania bezużyteczne — pad wciśnięty na 0,3 taktu przed jedynką wchodzi
w takt krzywo i nic tego nie ratuje.

Przyczyna nie jest błędem rachunku. `cue_plan` przyciąga pozycje do NASZEJ siatki
i robi to poprawnie. Tylko że plik trafia do Rekordboxa, a Rekordbox ma własną
siatkę o własnej fazie — i to jego siatkę widzi DJ na ekranie i na CDJ-u. Dwie
poprawne siatki o różnej fazie dają cue pomiędzy bitami.

Więc na samym końcu, tuż przed zapisem, pozycje są przeliczane na siatkę
gospodarza. Nasza siatka zostaje tym, co WYBIERA miejsce (które przejście, który
takt); siatka Rekordboxa rozstrzyga, GDZIE dokładnie to miejsce leży.

Dwie rzeczy trzymają to uczciwie:

  * BRAK SIATKI = BRAK RUCHU. Utwór bez analizy Pioneera (pusty PQTZ) zostaje
    z pozycją, którą policzyliśmy, plus ostrzeżenie. Nie zmyślamy siatki (ADR-005).
  * RUCH JEST RAPORTOWANY. Każde przesunięcie większe niż jeden bit znaczy, że
    obie siatki różnią się fazą, a nie tylko zaokrągleniem — to jest informacja
    o utworze, nie szum, i ma trafić na ekran.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dancelab.decision.cue_export_models import CuePlan


@dataclass
class SnapReport:
    """Co przyciąganie zrobiło — do pokazania DJ-owi, nie do schowania."""

    moved: int = 0
    unchanged: int = 0
    no_grid: list[str] = field(default_factory=list)      # tytuły bez siatki RB
    big_moves: list[tuple[str, int]] = field(default_factory=list)  # (tytuł, ms)

    def render(self) -> str:
        lines = [f"Siatka Rekordboxa: przesunięto {self.moved} cue, "
                 f"{self.unchanged} już stało na miejscu."]
        for title in self.no_grid:
            lines.append(f"⚠ {title[:44]}: Rekordbox nie ma siatki — cue zostaje "
                         f"tam, gdzie policzył silnik")
        for title, ms in self.big_moves[:8]:
            lines.append(f"  {title[:40]:40s} przesunięte o {ms:+d} ms "
                         f"(siatki różnią się fazą)")
        return "\n".join(lines)


DEFAULT_SHARE = Path.home() / "Library/Pioneer/rekordbox/share"


def _anlz_dirs(db, content) -> list[Path]:
    """Gdzie szukać analizy Pioneera dla tego utworu.

    pyrekordbox liczy katalog analizy względem pliku bazy. Przy pracy na KOPII
    bazy — a na kopii pracujemy zawsze, zanim cokolwiek dotknie biblioteki —
    wskazuje to na katalog, w którym żadnych plików analizy nie ma. Więc obok
    ścieżki wyliczonej sprawdzamy też tę prawdziwą, złożoną z `AnalysisDataPath`
    i domyślnego katalogu Rekordboxa. Bez tego przyciąganie po cichu nie robi nic
    i cue wracają krzywe.
    """
    out: list[Path] = []
    try:
        out.append(Path(db.get_anlz_dir(content)))
    except Exception:                                              # noqa: BLE001
        pass
    rel = getattr(content, "AnalysisDataPath", None)
    if rel:
        out.append(DEFAULT_SHARE / str(rel).lstrip("/").rsplit("/", 1)[0])
    return [p for p in out if p.is_dir()]


def rekordbox_downbeats(db, content) -> list[int]:
    """Czasy jedynek (w ms) z analizy Pioneera. Pusta lista = nie ma siatki.

    Pusta lista jest odpowiedzią pełnoprawną: znaczy „Rekordbox nie przeanalizował
    tego utworu", a nie „utwór nie ma bitu".
    """
    from pyrekordbox.anlz import read_anlz_files

    files = {}
    for directory in _anlz_dirs(db, content):
        try:
            files = read_anlz_files(directory)
        except Exception:                                          # noqa: BLE001
            continue
        if files:
            break
    for anlz in files.values():
        for tag in anlz.tags:
            if "PQTZ" not in type(tag).__name__:
                continue
            entries = (tag.content or {}).get("entries") or []
            downs = [int(e.time) for e in entries if int(e.beat) == 1]
            if downs:
                return sorted(downs)
    return []


def _nearest(values: list[int], target: int) -> int:
    """Najbliższa wartość z posortowanej listy. Lista nigdy nie jest pusta."""
    import bisect

    i = bisect.bisect_left(values, target)
    if i == 0:
        return values[0]
    if i >= len(values):
        return values[-1]
    lo, hi = values[i - 1], values[i]
    return lo if target - lo <= hi - target else hi


def snap_plan_to_rekordbox_grid(plan: CuePlan, db, tables) -> tuple[CuePlan, SnapReport]:
    """Przesuń każde cue na najbliższą jedynkę z siatki Rekordboxa.

    Celem jest JEDYNKA, nie najbliższy bit. Cue typu mix in / mix out mają wchodzić
    na początek taktu — dlatego `cue_plan` szuka downbeatu w naszej siatce. Gdyby
    przyciągać do najbliższego bitu, cue z przykładu Janka wylądowałoby o jeden bit
    od jedynki zamiast o 1,2 — nadal krzywo, tylko mniej widocznie.
    """
    report = SnapReport()
    grids: dict[str, list[int]] = {}

    for track in plan.tracks:
        if track.content_id not in grids:
            content = db.get_content(ID=track.content_id)
            grids[track.content_id] = (
                rekordbox_downbeats(db, content) if content is not None else []
            )
        downbeats = grids[track.content_id]
        if not downbeats:
            if track.track_title not in report.no_grid:
                report.no_grid.append(track.track_title or track.content_id)
            continue

        for cue in track.cues:
            snapped = _nearest(downbeats, cue.position_ms)
            delta = snapped - cue.position_ms
            if delta == 0:
                report.unchanged += 1
                continue
            cue.position_ms = snapped
            cue.reasoning.append(f"przyciągnięte do siatki Rekordboxa ({delta:+d} ms)")
            report.moved += 1
            # Jeden bit przy 126 BPM to ~476 ms. Ruch większy niż połowa bitu
            # znaczy, że nasza faza i faza Pioneera to dwie różne odpowiedzi,
            # a nie zaokrąglenie — DJ ma o tym wiedzieć.
            if abs(delta) > 240:
                report.big_moves.append((track.track_title or track.content_id, delta))

    return plan, report
