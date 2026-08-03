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


# Powyżej ilu procent różnicy przestajemy twierdzić, że znamy tempo. 1,5% to
# przy 130 BPM dwa uderzenia — tyle wystarczy, żeby po 32 taktach utwory się
# rozjechały, więc to nie jest spór o zaokrąglenie.
TEMPO_DISPUTE_PCT = 1.5


def tempo_disputes(
    analyses: dict,
    mapping: dict,
    db,
    *,
    threshold_pct: float = TEMPO_DISPUTE_PCT,
) -> list[str]:
    """Gdzie nasze tempo kłóci się z tempem Pioneera — zdania dla DJ-a.

    Lipcowy wpis w rejestrze mówił, że trzeba dorobić cross-check tempogramem,
    bo „Red Light Fever: silnik 120,01, realnie 117,45". Sprawdzone 2026-08-03
    wprost na tym pliku: dopasowanie przy 120,00 wynosi 3,00, a przy 117,45
    tylko 1,02 — i jest to wąski pik, nie plateau. Utwór stoi na 120. Rekordbox
    mówi 120,02. Przesłanka tamtej poprawki była fałszywa i tamtej poprawki
    nie ma po co pisać.

    Ale klasa błędu istnieje, tylko inna. Na 191 płytach nasze tempo rozjeżdża
    się z Rekordboxem powyżej 1,5% w czterech przypadkach, z czego TRZY silnik
    oznaczył jako pewne — i wszystkie trzy to wybór oktawy albo relacji (70
    zamiast 140, 69 zamiast 138, 101 zamiast 135), nie dryf. Tego tempogram by
    nie złapał, a Pioneer łapie od razu.

    Nie kopiujemy tu wartości Rekordboxa — on zostaje sędzią, nie składnikiem
    odpowiedzi. Jedyne, co robimy, to przestajemy twierdzić, że wiemy, kiedy
    dwa wiarygodne źródła mówią co innego (ADR-005).
    """
    out: list[str] = []
    for track_id, content_id in mapping.items():
        analysis = analyses.get(track_id)
        if analysis is None or not analysis.beatgrid:
            continue
        ours = float(analysis.beatgrid.bpm or 0)
        content = db.get_content(ID=content_id)
        theirs = float(getattr(content, "BPM", 0) or 0) / 100.0
        if ours <= 0 or theirs <= 0:
            continue
        # Oktawa nie jest sporem sama w sobie — ale jeśli po sprowadzeniu do
        # wspólnej oktawy nadal się nie zgadzają, to jest.
        variants = [ours * r for r in (0.25, 1 / 3, 0.5, 2 / 3, 0.75, 1.0, 4 / 3, 1.5, 2.0, 3.0, 4.0)]
        closest = min(variants, key=lambda v: abs(v - theirs))
        if abs(closest - theirs) / theirs * 100.0 <= threshold_pct:
            continue
        title = (analysis.track.title or track_id)[:44]
        pewne = " (a silnik uznał siatkę za pewną)" if analysis.beatgrid.reliable else ""
        out.append(
            f"⚠ {title}: nasze tempo {ours:.2f}, Rekordbox {theirs:.2f} — "
            f"nie zgadzamy się{pewne}. Sprawdź uchem przed graniem."
        )
    return out


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
