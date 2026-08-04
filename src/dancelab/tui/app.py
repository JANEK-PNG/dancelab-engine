"""DanceLab TUI — Ekran 1: budowa setu. Formularz → postęp → tabela → W.

Warstwa nad istniejącym silnikiem, zero nowej logiki decyzyjnej: formularz
zbiera dokładnie te parametry, które ma `zagraj`, budowa woła `build_set`
z dokarmianiem, a `W` publikuje przez `ingestion.playlist_publish` (backup,
odmowa przy niejednoznaczności, weryfikacja odczytem).

Dwa tryby puli — bo cache analiz kluczuje po ścieżce (sha1 źródła):
  * BIBLIOTEKA: analizy wprost z katalogu processed (natychmiast, 243 utwory);
  * FOLDER: `analyze_files` z prawdziwym postępem etapów (`stage_progress`)
    i anulowaniem między utworami (`should_stop`) — hooki zostały po Qt
    i od 24.07 nie miały konsumenta.

Zasada ADR-005 jako zasada UI: każde „nie wiem" silnika ma swój piksel —
`SetPlan.warnings` są stale widoczne pod tabelą, nigdy zwinięte; tonacja
o pewności <0,5 jest przygaszona; pasek statusu mówi wprost, czy Rekordbox
jest otwarty (wtedy `W` odmawia, zanim spróbuje).

Edycja gotowego setu (audyt 04.08: brakowało DOKŁADNIE ruchów, którymi Janek
werdyktował piątkowy set ręcznie w Rekordboksie): X wycina, Shift+↑/↓ przesuwa,
A dopisza przez ten sam panel sugestii co Z, S/O zapisuje i wczytuje plan,
V zrzuca werdykt „plan silnika vs stan po Twoich zmianach". Każda edycja
ląduje w dzienniku werdyktów — to rosnąca prawda o guście DJ-a.
"""

from __future__ import annotations

import pathlib
import threading

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Select,
    Static,
    Switch,
)

PROCESSED_DEFAULT = "experiments_priv/2026-07-30_rebuild/processed"

# Higiena puli — oba znaleziska z realnych przebiegów: stemy Demucsa
# („vocals" wylądowało w secie Janka DWA RAZY, pozycje 18 i 19, 05.08),
# a „Janek.mp3" (43-minutowy cudzy set) wskoczył kiedyś na 1. miejsce.
STEM_NAMES = {"drums", "bass", "other", "vocals", "no_vocals", "accompaniment"}
MAX_TRACK_SEC = 15 * 60

# Dziennik werdyktów DJ-a: każda ręczna edycja setu (podmiana, cięcie,
# przesunięcie, dopisanie) to darmowa prawda o guście — dopisujemy, nie gubimy.
WERDYKTY_DIR = pathlib.Path("experiments_priv/2026-08-04_werdykty")


def _parse_bpm(text: str) -> tuple[float | None, float | None, str | None]:
    """'128-140' → (128.0, 140.0). Pusty = brak okna. Błąd = komunikat."""
    t = text.replace(" ", "")
    if not t:
        return None, None, None
    if "-" not in t:
        return None, None, f"okno tempa to 'lo-hi', dostałem {text!r}"
    lo_s, hi_s = t.split("-", 1)
    try:
        lo, hi = float(lo_s), float(hi_s)
    except ValueError:
        return None, None, f"okno tempa to liczby, dostałem {text!r}"
    if lo >= hi:
        return None, None, f"puste okno: {lo:g} >= {hi:g}"
    return lo, hi, None


class DanceLabTUI(App):
    TITLE = "DanceLab — budowa setu"
    CSS = """
    #form { width: 44; padding: 0 1; border-right: solid $primary; }
    #form Input, #form Select { margin-bottom: 1; }
    #results { padding: 0 1; }
    #warnings { height: 9; border-top: solid $warning; }
    #status { height: 1; background: $panel; color: $text-muted; padding: 0 1; }
    #suggest { width: 42; border-left: solid $accent; padding: 0 1; display: none; }
    #suggest.open { display: block; }
    #suggest-title { color: $accent; text-style: bold; }
    .field-label { color: $text-muted; }
    """
    BINDINGS = [
        Binding("b", "build", "Buduj"),
        Binding("w", "write", "→ Rekordbox"),
        Binding("z", "replace", "Zamień"),
        Binding("x", "cut", "Wytnij"),
        Binding("a", "add", "Dopisz"),
        Binding("shift+up", "move_up", "przesuń ▲", show=False),
        Binding("shift+down", "move_down", "przesuń ▼", show=False),
        Binding("s", "save_plan", "Zapisz plan"),
        Binding("o", "load_plan", "Wczytaj"),
        Binding("v", "verdict", "Werdykt"),
        Binding("escape", "cancel", "Anuluj"),
        Binding("q", "quit", "Wyjdź"),
    ]

    def __init__(self, processed_dir: str = PROCESSED_DEFAULT):
        super().__init__()
        self.processed_dir = processed_dir
        self._stop = threading.Event()
        self._plan_paths: list[str] = []
        self._plan_name = ""
        self._order: list[str] = []
        self._engine_order: list[str] = []
        self._edits: list[dict] = []
        self._mean_score = None
        self._ctx: dict = {}
        self._suggest_slot: int | None = None
        self._panel_mode: str | None = None   # "suggest" | "insert" | "plans"

    # ------------------------------------------------------------- układ

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with VerticalScroll(id="form"):
                yield Label("Pula", classes="field-label")
                yield Select([("Biblioteka (cache analiz)", "library"),
                              ("Folder…", "folder")],
                             value="library", id="pool", allow_blank=False)
                yield Input(placeholder="ścieżka folderu (tryb Folder)", id="folder")
                yield Label("Długość [min]", classes="field-label")
                yield Input(value="90", id="minutes", type="number")
                yield Label("Okno tempa (np. 128-140)", classes="field-label")
                yield Input(placeholder="puste = bez okna", id="bpm")
                yield Label("Gatunki (Twoje tagi RB, po przecinku)", classes="field-label")
                yield Input(placeholder="garage, breaks, bass", id="styles")
                yield Label("Graj jak… (kotwica)", classes="field-label")
                yield Select([], id="dj", prompt="— bez kotwicy —")
                with Horizontal():
                    yield Switch(value=False, id="contour")
                    yield Label(" kontur skoków tego DJ-a")
                yield Label("Łuk / plan tempa / tryb", classes="field-label")
                yield Select([("build", "build"), ("peak", "peak"), ("flat", "flat")],
                             value="build", id="arc", allow_blank=False)
                yield Select([("staircase", "staircase"), ("linear", "linear"),
                              ("off", "off")], value="staircase", id="tempo",
                             allow_blank=False)
                yield Select([("smart", "smart"), ("harmonic", "harmonic"),
                              ("bpm", "bpm")], value="smart", id="planner",
                             allow_blank=False)
                yield Button("Buduj set  [B]", id="go", variant="primary")
            with Vertical(id="results"):
                yield Static("Ustaw parametry i naciśnij B.", id="progress")
                yield DataTable(id="set")
                yield Log(id="warnings", highlight=False)
            with Vertical(id="suggest"):
                yield Label("", id="suggest-title")
                yield OptionList(id="suggest-list")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#set", DataTable)
        table.add_columns("#", "BPM", "ton", "pew.", "gatunek", "Σ min", "utwór")
        table.cursor_type = "row"
        self._load_anchors()
        self._refresh_status()
        self.set_interval(5.0, self._refresh_status)

    def _load_anchors(self) -> None:
        try:
            from dancelab.decision.anchors import list_anchors
            options = [(f"{name}  ({n} wekt., skok {med})", name)
                       for name, n, med in list_anchors(limit=500)]
            self.query_one("#dj", Select).set_options(options)
        except Exception as exc:  # noqa: BLE001 — brak pliku kotwic to stan, nie awaria
            self._note(f"kotwice niedostępne: {exc}")

    def _refresh_status(self) -> None:
        from dancelab.ingestion.playlist_publish import BACKUP_DIR, rekordbox_running
        rb = "⛔ Rekordbox OTWARTY — zapis W zablokowany" if rekordbox_running() \
            else "✅ Rekordbox zamknięty — W dostępne"
        n_bak = len(list(BACKUP_DIR.glob("*.db"))) if BACKUP_DIR.exists() else 0
        self.query_one("#status", Static).update(
            f"{rb}   ·   backupy: {n_bak}   ·   pula: {self.processed_dir}")

    def _note(self, line: str) -> None:
        self.query_one("#warnings", Log).write_line(f"· {line}")

    # ------------------------------------------------------------- budowa

    def action_build(self) -> None:
        self.query_one("#warnings", Log).clear()
        self.query_one("#set", DataTable).clear()
        self._stop.clear()
        self._build_worker()

    @work(thread=True, exclusive=True)
    def _build_worker(self) -> None:
        ui = self.call_from_thread
        try:
            plan, by_id, warnings = self._build_plan()
        except Exception as exc:  # noqa: BLE001 — pokazujemy powód, nie traceback
            ui(self._note, f"ODMOWA: {exc}")
            ui(self.query_one("#progress", Static).update, "Nie zbudowano — powód niżej.")
            return
        ui(self._show_plan, plan, by_id, warnings)

    def _params(self) -> dict:
        get = lambda i, t: self.query_one(i, t)  # noqa: E731
        lo, hi, err = _parse_bpm(get("#bpm", Input).value)
        if err:
            raise ValueError(err)
        minutes = float(get("#minutes", Input).value or 90)
        dj = get("#dj", Select).value
        return dict(
            pool=get("#pool", Select).value,
            folder=get("#folder", Input).value.strip(),
            minutes=minutes, bpm_min=lo, bpm_max=hi,
            styles=[s.strip() for s in get("#styles", Input).value.split(",") if s.strip()],
            dj=None if dj is Select.BLANK else dj,
            contour=get("#contour", Switch).value,
            arc=get("#arc", Select).value,
            tempo=get("#tempo", Select).value,
            planner=get("#planner", Select).value,
        )

    def _library_analyses(self):
        """Pula z cache analiz + higiena (stemy, >15 min, brakujące pliki)."""
        from dancelab.storage.repositories import FileAnalysisRepository
        repo = FileAnalysisRepository(self.processed_dir)
        analyses = [repo.get(t) for t in repo.list_track_ids()]
        before = len(analyses)
        analyses = [a for a in analyses
                    if pathlib.Path(a.track.source_path).exists()
                    and pathlib.Path(a.track.source_path).stem.strip().lower()
                    not in STEM_NAMES
                    and (a.track.duration_sec or 0) <= MAX_TRACK_SEC]
        notes = []
        if before - len(analyses):
            notes.append(f"higiena puli: odrzucone {before - len(analyses)} "
                         f"(stemy / pliki >15 min / brak pliku)")
        return analyses, notes

    def _build_plan(self):
        from dancelab.core.config import load_config, load_weights
        from dancelab.decision.set_builder import build_set
        from dancelab.ingestion.analysis_enrichment import (
            attach_rekordbox_genres, attach_sound_embeddings)
        from dancelab.workflows.smart_playlist import (
            analyze_files, discover_audio_files, estimate_track_count_for_duration)

        p = self.call_from_thread(self._params)
        ui = self.call_from_thread
        progress = self.query_one("#progress", Static)
        cfg = load_config("configs/default.yaml")

        if p["pool"] == "folder":
            if not p["folder"]:
                raise ValueError("tryb Folder wymaga ścieżki")
            files = discover_audio_files(p["folder"])
            ui(progress.update, f"Analiza {len(files)} plików…")
            analyses, failures = analyze_files(
                files, cfg, processed_dir=self.processed_dir,
                stage_progress=lambda path, stage: ui(
                    progress.update,
                    f"{stage}: {pathlib.Path(path).name[:40]}"),
                should_stop=self._stop.is_set,
            )
            for f in failures[:5]:
                ui(self._note, f"nie przeanalizowano {pathlib.Path(f.source_path).name}: {f.error}")
        else:
            ui(progress.update, "Wczytuję analizy z biblioteki…")
            analyses, hygiene = self._library_analyses()
            for note in hygiene:
                ui(self._note, note)
        if self._stop.is_set():
            raise ValueError("anulowane")
        if not analyses:
            raise ValueError("pusta pula — nie ma z czego budować")

        ui(progress.update, "Dokarmianie (wektory, gatunki)…")
        emb = attach_sound_embeddings(analyses)
        gen = attach_rekordbox_genres(analyses)

        anchor = None
        if p["dj"]:
            from dancelab.decision.anchors import resolve_anchor
            anchor = resolve_anchor(p["dj"])

        count = estimate_track_count_for_duration(analyses, p["minutes"])
        ui(progress.update, f"Budowa: {count} utworów z {len(analyses)}…")
        plan = build_set(
            analyses, load_weights(cfg.weights_file),
            arc=p["arc"], target_track_count=count, planner_mode=p["planner"],
            tempo_shape=p["tempo"],
            preferred_styles=p["styles"] or None,
            bpm_min=p["bpm_min"], bpm_max=p["bpm_max"],
            sound_anchor=anchor.centroid if anchor else None,
            anchor_name=anchor.name if anchor else None,
            jump_contour=(anchor.contour if (anchor and p["contour"]) else None),
        )
        by_id = {a.track.track_id: a for a in analyses}
        self._ctx = dict(
            by_id=by_id, weights=load_weights(cfg.weights_file),
            arc=p["arc"], planner=p["planner"],
            bpm_min=p["bpm_min"], bpm_max=p["bpm_max"],
            anchor=(anchor.centroid if anchor else None),
            params=p,
        )
        notes = [*emb.notes, *gen.notes,
                 f"dokarmione: wektory {emb.attached}, gatunki {gen.attached}"]
        self._plan_name = (f"TUI {p['dj'] or 'set'} "
                           f"{p['bpm_min']:g}-{p['bpm_max']:g}" if p["bpm_min"]
                           else f"TUI {p['dj'] or 'set'}")
        return plan, by_id, notes

    def _show_plan(self, plan, by_id, extra_notes) -> None:
        self._order = list(plan.track_order)
        self._engine_order = list(plan.track_order)   # pierwotny plan — do werdyktu V
        self._edits = []
        self._mean_score = plan.mean_transition_score
        self._render_order(by_id)
        for note in [*plan.warnings, *extra_notes]:
            self._note(note)

    def _render_order(self, by_id) -> None:
        table = self.query_one("#set", DataTable)
        table.clear()
        total = 0.0
        self._plan_paths = []
        for i, tid in enumerate(self._order, 1):
            t = by_id[tid].track
            total += t.duration_sec or 0
            conf = t.key_confidence
            key = str(t.key_estimate or "?")
            key_cell = key if (conf or 0) >= 0.5 else f"[dim]{key}?[/]"
            table.add_row(
                str(i), f"{t.bpm_estimate or 0:.1f}", key_cell,
                f"{conf:.2f}" if conf is not None else "—",
                (t.style_label or "")[:22], f"{total/60:5.1f}",
                pathlib.Path(t.source_path).stem[:46],
            )
            self._plan_paths.append(t.source_path)
        n = len(self._order)
        score = self._mean_score if self._mean_score is not None else "—"
        self.query_one("#progress", Static).update(
            f"SET: {n} utworów · {total/60:.0f} min pełnych "
            f"(~{max(0,(total-75*(n-1)))/60:.0f} min przy blendach 75 s) "
            f"· zgodność {score}")

    # ------------------------------------------------------------- zapis

    def action_write(self) -> None:
        if not self._plan_paths:
            self._note("najpierw zbuduj set (B)")
            return
        self._write_worker()

    # Panel po prawej gra w trzech trybach tym samym wzorcem dwóch naciśnięć
    # (klik/strzałki = wybierz, ten sam klawisz = potwierdź, Esc = zostaw):
    # Z podmienia, A dopisza, O wczytuje plan.

    def _panel_choice(self, mode: str) -> str | None:
        """Podświetlony wybór, jeśli panel otwarty w danym trybie."""
        panel = self.query_one("#suggest")
        lst = self.query_one("#suggest-list", OptionList)
        if panel.has_class("open") and self._panel_mode == mode \
                and lst.highlighted is not None:
            return lst.get_option_at_index(lst.highlighted).id
        return None

    def _close_panel(self) -> None:
        self.query_one("#suggest").remove_class("open")
        self._suggest_slot = None
        self._panel_mode = None

    def _cursor_row(self, po_co: str) -> int | None:
        idx = self.query_one("#set", DataTable).cursor_row
        if not self._order or not self._ctx:
            self._note("najpierw zbuduj set (B) albo wczytaj plan (O)")
            return None
        if idx is None or not (0 <= idx < len(self._order)):
            self._note(f"ustaw kursor na utworze — {po_co}")
            return None
        return idx

    def action_replace(self) -> None:
        choice = self._panel_choice("suggest")
        if choice is not None and self._suggest_slot is not None:
            self._apply_swap(self._suggest_slot, choice)
            return
        self._close_panel()
        idx = self._cursor_row("podmiana")
        if idx is not None:
            self._suggest_worker(idx, "suggest")

    def action_add(self) -> None:
        choice = self._panel_choice("insert")
        if choice is not None and self._suggest_slot is not None:
            self._apply_insert(self._suggest_slot, choice)
            return
        self._close_panel()
        idx = self._cursor_row("dopisuję ZA zaznaczonym")
        if idx is not None:
            self._suggest_worker(idx, "insert")

    def action_cut(self) -> None:
        self._close_panel()
        idx = self._cursor_row("cięcie")
        if idx is None:
            return
        by_id = self._ctx["by_id"]
        tid = self._order.pop(idx)
        path = by_id[tid].track.source_path
        self._log_verdict("ciecie", pozycja=idx + 1, out=path)
        self._render_order(by_id)
        self._note(f"CIĘCIE #{idx+1}: {pathlib.Path(path).stem[:40]} "
                   f"(werdykt zapisany)")
        table = self.query_one("#set", DataTable)
        if self._order:
            table.move_cursor(row=min(idx, len(self._order) - 1))
        table.focus()

    def action_move_up(self) -> None:
        self._move(-1)

    def action_move_down(self) -> None:
        self._move(+1)

    def _move(self, delta: int) -> None:
        self._close_panel()
        idx = self._cursor_row("przesuwanie")
        if idx is None:
            return
        j = idx + delta
        if not (0 <= j < len(self._order)):
            return                                   # brzeg setu — nie ma dokąd
        self._order[idx], self._order[j] = self._order[j], self._order[idx]
        by_id = self._ctx["by_id"]
        self._log_verdict("przesuniecie", z=idx + 1, na=j + 1,
                          utwor=by_id[self._order[j]].track.source_path)
        self._render_order(by_id)
        table = self.query_one("#set", DataTable)
        table.move_cursor(row=j)
        table.focus()

    def action_cancel(self) -> None:
        if self.query_one("#suggest").has_class("open"):
            self._close_panel()
            self.query_one("#set", DataTable).focus()
            return
        self._stop.set()
        self._note("anulowanie — dokończę bieżący utwór i stanę (cache zostaje)")

    @work(thread=True, exclusive=True)
    def _suggest_worker(self, idx: int, mode: str) -> None:
        from dancelab.decision.slot_suggest import (
            suggest_for_insertion, suggest_for_slot)
        ui = self.call_from_thread
        ctx = self._ctx
        by_id = ctx["by_id"]

        def energy_of(a):
            vals = [f.rms for f in (getattr(a, "features", None) or [])
                    if getattr(f, "rms", None) is not None]
            return float(sum(vals) / len(vals)) if vals else 0.5
        energy = {tid: energy_of(a) for tid, a in by_id.items()}
        e_rng = (max(energy.values()) - min(energy.values())) or 1.0
        fn = suggest_for_slot if mode == "suggest" else suggest_for_insertion
        try:
            sugg = fn(by_id, self._order, idx, k=10,
                      weights=ctx["weights"], arc=ctx["arc"],
                      planner_mode=ctx["planner"], energy=energy,
                      energy_range=e_rng,
                      bpm_min=ctx["bpm_min"], bpm_max=ctx["bpm_max"],
                      anchor=ctx["anchor"])
        except Exception as exc:  # noqa: BLE001
            ui(self._note, f"sugestie nie wyszły: {exc}")
            return
        if not sugg:
            ui(self._note, "brak kandydatów do tej szczeliny (okno tempa? pula?)")
            return
        here = pathlib.Path(by_id[self._order[idx]].track.source_path).stem[:40]
        options = []
        for sg in sugg:
            t = by_id[sg.track_id].track
            options.append((
                f"{sg.score:.2f} {t.bpm_estimate or 0:5.1f} "
                f"{str(t.key_estimate or '?'):>3} "
                f"{pathlib.Path(t.source_path).stem[:30]}",
                sg.track_id))
        if mode == "suggest":
            title = (f"#{idx+1} {here}\n"
                     f"klik/strzałki = wybierz · Z = zamień · Esc = zostaw")
        else:
            title = (f"DOPISZ za #{idx+1} {here}\n"
                     f"klik/strzałki = wybierz · A = dopisz · Esc = zostaw")
        ui(self._open_suggest_panel, idx, title, options, mode)

    def _open_suggest_panel(self, idx: int | None, title: str,
                            options: list[tuple[str, str]], mode: str) -> None:
        self._suggest_slot = idx
        self._panel_mode = mode
        self.query_one("#suggest-title", Label).update(title)
        lst = self.query_one("#suggest-list", OptionList)
        lst.clear_options()
        for label, oid in options:
            lst.add_option(Option(label, id=oid))
        self.query_one("#suggest").add_class("open")
        lst.highlighted = 0
        lst.focus()

    def _apply_swap(self, idx: int, choice: str) -> None:
        by_id = self._ctx["by_id"]
        old_id = self._order[idx]
        self._order[idx] = choice
        self._render_order(by_id)
        old_n = pathlib.Path(by_id[old_id].track.source_path).stem[:40]
        new_n = pathlib.Path(by_id[choice].track.source_path).stem[:40]
        self._note(f"PODMIANA #{idx+1}: {old_n} → {new_n} (werdykt zapisany)")
        self._log_verdict("podmiana", pozycja=idx + 1,
                          **{"out": by_id[old_id].track.source_path,
                             "in": by_id[choice].track.source_path})
        self._close_panel()
        table = self.query_one("#set", DataTable)
        table.move_cursor(row=idx)
        table.focus()

    def _apply_insert(self, after_idx: int, choice: str) -> None:
        by_id = self._ctx["by_id"]
        self._order.insert(after_idx + 1, choice)
        self._render_order(by_id)
        path = by_id[choice].track.source_path
        self._note(f"DOPISANE #{after_idx+2}: {pathlib.Path(path).stem[:40]} "
                   f"(werdykt zapisany)")
        self._log_verdict("dopisanie", pozycja=after_idx + 2, **{"in": path})
        self._close_panel()
        table = self.query_one("#set", DataTable)
        table.move_cursor(row=after_idx + 1)
        table.focus()

    def _log_verdict(self, typ: str, **fields) -> None:
        """Każda ręczna edycja to werdykt DJ-a — dopisujemy, nie gubimy."""
        import json
        import time
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "typ": typ, **fields}
        self._edits.append(rec)
        WERDYKTY_DIR.mkdir(parents=True, exist_ok=True)
        with (WERDYKTY_DIR / "tui_edycje.jsonl").open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # ------------------------------------------------- plan: zapis / wczytanie

    def action_save_plan(self) -> None:
        if not self._order or not self._ctx:
            self._note("najpierw zbuduj set (B) albo wczytaj plan (O)")
            return
        from dancelab.tui.plan_store import save_plan
        path = save_plan(self._order, self._ctx["by_id"],
                         name=self._plan_name or "TUI plan",
                         params=self._ctx.get("params", {}),
                         engine_order=self._engine_order, edits=self._edits)
        self._note(f"plan zapisany: {path}")

    def action_load_plan(self) -> None:
        choice = self._panel_choice("plans")
        if choice is not None:
            self._close_panel()
            self._load_plan_worker(choice)
            return
        self._close_panel()
        from dancelab.tui.plan_store import list_plans
        plans = list_plans()
        if not plans:
            self._note("brak zapisanych planów (S zapisuje bieżący)")
            return
        options = [(f"{p['zapisano'][5:16]} · {p['n']:2d} utw · {p['nazwa'][:22]}",
                    p["path"]) for p in plans[:30]]
        self._open_suggest_panel(
            None, "WCZYTAJ PLAN\nklik/strzałki = wybierz · O = wczytaj · Esc = zostaw",
            options, "plans")

    @work(thread=True, exclusive=True)
    def _load_plan_worker(self, path: str) -> None:
        from dancelab.tui.plan_store import match_order, read_plan
        ui = self.call_from_thread
        try:
            rec = read_plan(path)
            if not self._ctx:
                self._ctx = self._pool_ctx_for(rec.get("parametry", {}))
            order, notes = match_order(rec, self._ctx["by_id"])
        except Exception as exc:  # noqa: BLE001 — powód, nie traceback
            ui(self._note, f"wczytanie nie wyszło: {exc}")
            return
        if not order:
            ui(self._note, "w planie nie został żaden utwór obecny w puli — nie wczytuję")
            return
        ui(self._after_plan_load, rec, order, notes)

    def _pool_ctx_for(self, params: dict) -> dict:
        """Kontekst oceniania dla wczytanego planu, gdy nic nie zbudowano:
        pula z biblioteki + dokarmienie + parametry zapisane w planie —
        dzięki temu Z/A po samym O oceniają tak, jak oceniała budowa."""
        from dancelab.core.config import load_config, load_weights
        from dancelab.ingestion.analysis_enrichment import (
            attach_rekordbox_genres, attach_sound_embeddings)
        ui = self.call_from_thread
        ui(self.query_one("#progress", Static).update,
           "Wczytuję pulę z biblioteki pod plan…")
        analyses, hygiene = self._library_analyses()
        for note in hygiene:
            ui(self._note, note)
        if not analyses:
            raise ValueError("pusta pula — nie mam do czego dopasować planu")
        attach_sound_embeddings(analyses)
        attach_rekordbox_genres(analyses)
        anchor = None
        if params.get("dj"):
            from dancelab.decision.anchors import resolve_anchor
            anchor = resolve_anchor(params["dj"])
        cfg = load_config("configs/default.yaml")
        return dict(
            by_id={a.track.track_id: a for a in analyses},
            weights=load_weights(cfg.weights_file),
            arc=params.get("arc", "build"), planner=params.get("planner", "smart"),
            bpm_min=params.get("bpm_min"), bpm_max=params.get("bpm_max"),
            anchor=(anchor.centroid if anchor else None),
            params=params,
        )

    def _after_plan_load(self, rec: dict, order: list[str],
                         notes: list[str]) -> None:
        self._order = order
        self._engine_order = list(rec.get("plan_silnika", []))
        self._edits = list(rec.get("edycje", []))
        self._plan_name = rec.get("nazwa") or "TUI plan"
        self._mean_score = None      # po edycjach nie udajemy zgodności z budowy
        self._set_form(rec.get("parametry", {}))
        self._render_order(self._ctx["by_id"])
        for note in notes:
            self._note(note)
        self._note(f"plan wczytany: {self._plan_name} ({len(order)} utworów, "
                   f"zapisany {rec.get('zapisano', '?')})")
        self.query_one("#set", DataTable).focus()

    def _set_form(self, p: dict) -> None:
        """Przywróć formularz z planu — żeby ponowna budowa była odtwarzalna.
        Pojedyncze pole może nie wejść (np. kotwica zniknęła z pliku) —
        wtedy notka, nie wywrotka."""
        try:
            if p.get("minutes"):
                self.query_one("#minutes", Input).value = f"{p['minutes']:g}"
            if p.get("bpm_min") is not None and p.get("bpm_max") is not None:
                self.query_one("#bpm", Input).value = \
                    f"{p['bpm_min']:g}-{p['bpm_max']:g}"
            self.query_one("#styles", Input).value = ", ".join(p.get("styles", []))
            for wid, key in (("#arc", "arc"), ("#tempo", "tempo"),
                             ("#planner", "planner")):
                if p.get(key):
                    self.query_one(wid, Select).value = p[key]
            if p.get("dj"):
                self.query_one("#dj", Select).value = p["dj"]
            self.query_one("#contour", Switch).value = bool(p.get("contour"))
        except Exception as exc:  # noqa: BLE001
            self._note(f"formularza nie dało się w pełni przywrócić: {exc}")

    # ------------------------------------------------------------- werdykt V

    def action_verdict(self) -> None:
        """Świadomy zrzut: plan silnika vs stan po Twoich edycjach."""
        if not self._order or not self._ctx:
            self._note("najpierw zbuduj set (B) albo wczytaj plan (O)")
            return
        import json
        import time
        by_id = self._ctx["by_id"]

        def rows(ids):
            return [{"track_id": t, "path": by_id[t].track.source_path}
                    for t in ids if t in by_id]
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "nazwa": self._plan_name,
               "parametry": self._ctx.get("params", {}),
               "plan_silnika": rows(self._engine_order),
               "stan_dja": rows(self._order),
               "edycje": self._edits}
        WERDYKTY_DIR.mkdir(parents=True, exist_ok=True)
        path = WERDYKTY_DIR / f"tui_werdykt_{time.strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        self._note(f"WERDYKT: plan {len(self._engine_order)} utworów vs "
                   f"Twoje {len(self._order)}, edycji {len(self._edits)} "
                   f"→ {path.name}")

    @work(thread=True, exclusive=True)
    def _write_worker(self) -> None:
        from dancelab.ingestion.playlist_publish import publish_playlist
        ui = self.call_from_thread
        report = publish_playlist(self._plan_paths, name=self._plan_name)
        for note in report.notes:
            ui(self._note, note)
        if report.ok and report.written:
            ui(self._note,
               f"✅ zapisane: {report.playlist_name} ({report.written} utworów) "
               f"· backup {report.backup_path}")
        elif not report.ok:
            ui(self._note, "❌ zapis nieudany — szczegóły wyżej")
        ui(self._refresh_status)


def main() -> None:
    DanceLabTUI().run()


if __name__ == "__main__":
    main()
