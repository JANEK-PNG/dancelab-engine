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


# The reason has to be arguable by a DJ, not only readable by an engineer.
_HARMONIC_PL = {
    "exact": "ta sama tonacja",
    "relative_major_minor": "tonacja równoległa",
    "adjacent_same_mode": "sąsiednia tonacja",
    "cautious": "tonacja o dwa kroki",
    "risky": "tonacje się gryzą",
    "unknown": "tonacja nieznana",
}


def _tempo_pl(delta_pct: float) -> str:
    if abs(delta_pct) < 0.5:
        return "to samo tempo"
    direction = "szybciej" if delta_pct > 0 else "wolniej"
    return f"{abs(delta_pct):.1f}% {direction}"


def _corpus_pl(lift: float) -> str:
    """What the measured corpus says about this kind of move."""
    if lift >= 1.30:
        return f"DJ-e robią tak często (×{lift:.2f})"
    if lift >= 1.05:
        return f"DJ-e to lubią (×{lift:.2f})"
    if lift <= 0.75:
        return f"DJ-e tego unikają (×{lift:.2f})"
    return f"neutralne (×{lift:.2f})"


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
    reason = (f"{_HARMONIC_PL.get(harm.harmonic_relation, harm.harmonic_relation)} "
              f"({a.camelot}→{b.camelot}) · {_tempo_pl(delta)} · {_corpus_pl(lift)}")
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
    from dancelab.cli.audition import Audition, player_available
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
    console.print(Panel(
        "Oceniasz [bold]przejścia[/bold], nie utwory.\n\n"
        "1. wybierasz utwór, od którego zaczynasz\n"
        "2. silnik proponuje, co może po nim pójść — i tłumaczy dlaczego\n"
        "3. wybierasz jedną propozycję, [bold]słuchasz szwu[/bold] i oceniasz\n"
        "4. Twoja ocena zostaje zapamiętana i zmienia kolejne propozycje",
        title="DanceLab · pokój przejść",
        subtitle=f"{len(library)} utworów w bibliotece · "
                 f"ocen zapisanych: {sum(store.counts().values())}",
    ))

    player = Audition()
    if not player_available():
        console.print("[yellow]brak afplay — szwy będą renderowane, ale nie "
                      "odtworzę ich stąd[/yellow]")

    current = _pick_start(library, start)
    if current is None:
        raise typer.Exit(0)

    while True:
        console.print()
        console.print(_header(current, store))
        rows = _rank(current, library, store, weights)
        console.print(f"\n[bold]Co może pójść po tym utworze?[/bold] "
                      f"[dim](propozycje silnika, najlepsze u góry)[/dim]")
        console.print(_candidate_table(rows))
        console.print(f"[dim]wpisz numer 1-{len(rows)}, zeby posluchac tego "
                      "przejscia   ·   s = inny utwor startowy   ·   "
                      "q = wyjscie[/dim]")

        choice = console.input("numer › ").strip().lower()
        if choice in ("q", "quit"):
            break
        if choice == "s":
            picked = _pick_start(library, None)
            if picked:
                current = picked
            continue
        if choice == "":
            console.print("[yellow]Wpisz numer propozycji, ktorej chcesz "
                          "posluchac.[/yellow]")
            continue
        if not choice.isdigit() or not 1 <= int(choice) <= len(rows):
            console.print(f"[yellow]To nie jest numer z listy: {choice}[/yellow]")
            continue

        _score, candidate, _reason, _v = rows[int(choice) - 1]
        moved = _review_seam(current, candidate, store, verdicts_path, config, player)
        if moved:
            current = candidate


def _pick_start(library: dict[str, LibTrack], text: str | None) -> LibTrack | None:
    """Choose the track to start from. Every prompt says what it wants."""
    while True:
        if text:
            query, text = text, None
        else:
            console.print("\n[bold]Od którego utworu zaczynamy?[/bold]")
            console.print("[dim]wpisz fragment tytułu lub wykonawcy "
                          "(np. kola, flynn)   ·   q = wyjscie[/dim]")
            query = console.input("szukaj › ").strip()

        if query.lower() in ("q", "quit", "exit"):
            return None
        if not query:
            console.print("[yellow]Nic nie wpisałeś. Wpisz fragment nazwy "
                          "albo q, zeby wyjsc.[/yellow]")
            continue

        matches = _find(library, query)
        if not matches:
            console.print(f"[yellow]Nic nie pasuje do: {query}[/yellow]")
            console.print("[dim]spróbuj krócej — np. samo nazwisko wykonawcy[/dim]")
            continue
        if len(matches) == 1:
            found = matches[0]
            console.print(f"[green]Znalazłem:[/green] {found.title} — {found.artist}")
            return found

        console.print(f"\n[bold]{len(matches)} pasujących — który?[/bold]")
        table = Table(header_style="bold")
        table.add_column("nr", width=3, justify="right")
        table.add_column("utwór", overflow="ellipsis", max_width=40)
        table.add_column("wykonawca", overflow="ellipsis", max_width=24)
        table.add_column("BPM", width=5, justify="right")
        table.add_column("tonacja", width=7)
        shown = matches[:10]
        for i, t in enumerate(shown, start=1):
            table.add_row(str(i), t.title, t.artist or "—", f"{t.bpm:.0f}", t.camelot)
        console.print(table)
        console.print(f"[dim]wpisz numer 1-{len(shown)}   ·   "
                      "s = szukaj jeszcze raz   ·   q = wyjscie[/dim]")
        pick = console.input("numer › ").strip().lower()
        if pick in ("q", "quit"):
            return None
        if pick == "s" or pick == "":
            continue
        if pick.isdigit() and 1 <= int(pick) <= len(shown):
            return shown[int(pick) - 1]
        console.print(f"[yellow]To nie jest numer z listy: {pick}[/yellow]")


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


def _review_seam(a: LibTrack, b: LibTrack, store, verdicts_path, config: str,
                 player) -> bool:
    """Audition one seam and record the verdict. Returns True to move on to B."""
    from dancelab.cli.preview import render as render_preview

    suggested = store.preferred_beats(a.content_id, b.content_id, None)
    # Each pair keeps its own file so [w] can compare against the previous seam
    # instead of one render overwriting the evidence for the last.
    out = Path.home() / ".dancelab" / "seams" / f"{a.content_id}_{b.content_id}.wav"
    console.print(f"\n[bold]{a.title}[/bold]  →  [bold]{b.title}[/bold]")
    console.print("[dim]skladam ten szew w plik audio. Pierwszy raz dla tej pary "
                  "trwa ok. 30 s (analiza obu utworow), potem juz od razu.[/dim]")

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

    player.play(out)
    console.print("[green]gra…[/green]")
    while True:
        console.print(Panel(
            "[bold]Enter[/bold]  zagraj jeszcze raz        "
            "[bold]l[/bold]  w petli x4 (dobre do oceny)\n"
            "[bold]w[/bold]      wroc do poprzedniego (A/B)  "
            "[bold]x[/bold]  cisza\n\n"
            "[bold green]t[/bold green]  dobre przejscie      "
            "[bold red]n[/bold red]  zle przejscie      "
            "[bold]d[/bold]  za krotkie      "
            "[bold]k[/bold]  za dlugie\n"
            "[bold]p[/bold]  pomin, nie oceniam",
            title="jak brzmi ten szew?",
        ))
        key = console.input("› ").strip().lower()
        if key == "":
            player.replay()
            continue
        if key == "l":
            player.replay(repeats=4)
            continue
        if key == "w":
            if not player.back():
                console.print("[dim]nie ma jeszcze z czym porównać[/dim]")
            continue
        if key == "x":
            player.stop()
            continue
        mapping = {"t": "yes", "n": "no", "d": "longer", "k": "shorter"}
        if key in mapping:
            player.stop()
            store.record(a.content_id, b.content_id, mapping[key], beats=suggested)
            store.save(verdicts_path)
            console.print(f"[green]zapisane: {mapping[key]}[/green]\n")
            return key == "t"
        if key == "p":
            player.stop()
            return False
