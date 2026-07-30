"""`dancelab room` — the seam review loop.

The status report of 2026-07-28 measured the DJ-to-engine relation as
asymmetric: the engine proposes and explains, but the DJ's correction reaches it
through an engineer rather than through the product. This screen is the missing
return path, and it is built around the seam rather than around a track list,
because the seam is what DanceLab makes.

One pair at a time: the engine's candidates for what follows the current track,
with the reasoning that produced them. Audition the seam with a keystroke, then
accept it, reject it, or ask for a longer or shorter blend. Every verdict is
written down and the next proposal already knows it.

Library and metadata come from Rekordbox — 1874 tracks already carry tempo and
Camelot key, so the first screen appears immediately instead of after an
analysis run. Deeper features are computed only for the pair being auditioned.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

DEFAULT_VERDICTS = Path.home() / ".dancelab" / "verdicts.json"
CANDIDATES_SHOWN = 6
console = Console()


@dataclass(frozen=True)
class LibTrack:
    content_id: str
    title: str
    artist: str
    bpm: float
    camelot: str
    path: str


def _load_library() -> dict[str, LibTrack]:
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()
    keys = {k.ID: k.ScaleName for k in db.session.query(tables.DjmdKey).all()}
    out: dict[str, LibTrack] = {}
    for row in db.session.query(tables.DjmdContent).all():
        bpm = float(row.BPM or 0)
        if bpm > 300:                      # Rekordbox stores BPM x100
            bpm /= 100.0
        camelot = keys.get(row.KeyID)
        if bpm <= 0 or not camelot or not row.FolderPath:
            continue
        out[str(row.ID)] = LibTrack(
            content_id=str(row.ID),
            title=(row.Title or "?").strip(),
            artist=(row.Artist.Name if row.Artist else "") or "",
            bpm=bpm, camelot=camelot, path=row.FolderPath,
        )
    db.close()
    return out


def _pair_score(a: LibTrack, b: LibTrack, weights) -> tuple[float, str]:
    """Engine score for A -> B plus a one-line reason a DJ can argue with."""
    from dancelab.decision.corpus_priors import transition_prior_lift
    from dancelab.decision.harmonic import harmonic_compatibility
    from dancelab.decision.set_builder import bpm_score

    harm = harmonic_compatibility(a.camelot, b.camelot)
    tempo = bpm_score(a.bpm, b.bpm)
    score = 0.5 * harm.harmonic_compatibility_score + 0.5 * tempo
    lift, _notes = transition_prior_lift(harm.harmonic_relation, a.bpm, b.bpm)
    prior_weight = float(getattr(weights, "corpus_priors_weight", 0.0) or 0.0)
    if prior_weight:
        score *= lift ** prior_weight
    delta = (b.bpm - a.bpm) / a.bpm * 100.0
    reason = (f"{harm.harmonic_relation} {a.camelot}→{b.camelot} · "
              f"{a.bpm:.0f}→{b.bpm:.0f} BPM ({delta:+.1f}%) · korpus ×{lift:.2f}")
    return score, reason


def _find(library: dict[str, LibTrack], text: str) -> list[LibTrack]:
    needle = text.strip().casefold()
    if not needle:
        return []
    return [t for t in library.values()
            if needle in t.title.casefold() or needle in t.artist.casefold()]


def _header(track: LibTrack, store) -> Panel:
    counts = store.counts()
    judged = sum(counts.values())
    return Panel(
        f"[bold]{track.title}[/bold]  —  {track.artist or '—'}\n"
        f"{track.bpm:.1f} BPM · {track.camelot}",
        title="gra teraz",
        subtitle=(f"werdykty: {judged}  "
                  f"(tak {counts['yes']} · nie {counts['no']} · "
                  f"dłużej {counts['longer']} · krócej {counts['shorter']})"),
    )


def _candidate_table(rows) -> Table:
    table = Table(show_lines=False, header_style="bold")
    table.add_column("#", width=3, justify="right")
    table.add_column("utwór", overflow="ellipsis", max_width=38)
    table.add_column("wykonawca", overflow="ellipsis", max_width=20)
    table.add_column("ocena", width=6, justify="right")
    table.add_column("dlaczego", overflow="fold")
    for i, (score, track, reason, verdict) in enumerate(rows, start=1):
        mark = {"yes": " ✓", "no": " ✗"}.get(verdict, "")
        table.add_row(str(i), track.title + mark, track.artist,
                      f"{score:.2f}", reason)
    return table


def room(
    start: str = typer.Option(None, "--start",
                              help="Track to start from (part of a title or artist)"),
    verdicts_path: Path = typer.Option(DEFAULT_VERDICTS, "--verdicts"),
    config: str = typer.Option("configs/default.yaml", "--config", "-c"),
) -> None:
    """Review seams one pair at a time: listen, judge, and teach the engine."""
    from dancelab.core.config import load_config, load_weights
    from dancelab.decision.verdicts import VerdictStore

    cfg = load_config(config)
    weights = load_weights(cfg.weights_file)

    console.print("[dim]czytam bibliotekę Rekordbox…[/dim]")
    try:
        library = _load_library()
    except Exception as exc:
        console.print(f"[red]nie mogę otworzyć biblioteki Rekordbox: {exc}[/red]")
        raise typer.Exit(1)
    if len(library) < 2:
        console.print("[red]biblioteka ma mniej niż 2 utwory z BPM i tonacją[/red]")
        raise typer.Exit(1)

    store = VerdictStore.load(verdicts_path)
    console.print(f"[dim]{len(library)} utworów · werdyktów zapisanych: "
                  f"{sum(store.counts().values())}[/dim]\n")

    current = _pick_start(library, start)
    if current is None:
        raise typer.Exit(0)

    while True:
        console.print(_header(current, store))
        rows = _rank(current, library, store, weights)
        console.print(_candidate_table(rows))
        console.print("[dim][1-6] wybierz szew · [s] szukaj innego startu · "
                      "[q] wyjście[/dim]")

        choice = console.input("› ").strip().lower()
        if choice in ("q", "quit", ""):
            break
        if choice == "s":
            picked = _pick_start(library, None)
            if picked:
                current = picked
            continue
        if not choice.isdigit() or not 1 <= int(choice) <= len(rows):
            continue

        _score, candidate, _reason, _v = rows[int(choice) - 1]
        moved = _review_seam(current, candidate, store, verdicts_path, config)
        if moved:
            current = candidate


def _pick_start(library: dict[str, LibTrack], text: str | None) -> LibTrack | None:
    while True:
        query = text or console.input("szukaj utworu startowego (Enter = wyjście) › ")
        text = None
        matches = _find(library, query)
        if not matches:
            if not query.strip():
                return None
            console.print("[yellow]nic nie znalazłem[/yellow]")
            continue
        if len(matches) == 1:
            return matches[0]
        table = Table(show_header=False)
        for i, t in enumerate(matches[:10], start=1):
            table.add_row(str(i), t.title, t.artist, f"{t.bpm:.0f}", t.camelot)
        console.print(table)
        pick = console.input("› ").strip()
        if pick.isdigit() and 1 <= int(pick) <= min(10, len(matches)):
            return matches[int(pick) - 1]


def _rank(current: LibTrack, library, store, weights):
    scored = []
    for track in library.values():
        if track.content_id == current.content_id:
            continue
        score, reason = _pair_score(current, track, weights)
        verdict_entry = store.latest_for(current.content_id, track.content_id)
        score += store.score_adjustment(current.content_id, track.content_id)
        scored.append((score, track, reason,
                       verdict_entry.verdict if verdict_entry else None))
    scored.sort(key=lambda row: (-row[0], row[1].title))
    return scored[:CANDIDATES_SHOWN]


def _review_seam(a: LibTrack, b: LibTrack, store, verdicts_path, config: str) -> bool:
    """Audition one seam and record the verdict. Returns True to move on to B."""
    from dancelab.cli.preview import render as render_preview

    suggested = store.preferred_beats(a.content_id, b.content_id, None)
    out = Path.home() / ".dancelab" / "seam.wav"
    console.print(f"\n[bold]{a.title}[/bold] → [bold]{b.title}[/bold]")
    console.print("[dim]renderuję szew (analiza obu utworów przy pierwszym razie)…[/dim]")

    try:
        render_preview(
            track_a=Path(a.path), track_b=Path(b.path), output=out,
            profile="contour_blend", beats=suggested,
            tempo_mode="varispeed", config=config,
        )
    except SystemExit:
        console.print("[yellow]nie udało się zrenderować tego szwu[/yellow]")
        return False
    except Exception as exc:
        console.print(f"[yellow]render nieudany: {exc}[/yellow]")
        return False

    while True:
        console.print("[dim][Enter] posłuchaj · [t]ak · [n]ie · [d]łużej · "
                      "[k]rócej · [p]omiń[/dim]")
        key = console.input("› ").strip().lower()
        if key == "":
            subprocess.run(["afplay", str(out)], check=False)
            continue
        mapping = {"t": "yes", "n": "no", "d": "longer", "k": "shorter"}
        if key in mapping:
            store.record(a.content_id, b.content_id, mapping[key], beats=suggested)
            store.save(verdicts_path)
            console.print(f"[green]zapisane: {mapping[key]}[/green]\n")
            return key == "t"
        if key == "p":
            return False
