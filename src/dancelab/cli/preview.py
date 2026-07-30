"""`dancelab preview` — hear a transition before you play it.

The renderer has existed for a long time but had no way in: only two
verification scripts ever called it, so the one thing a DJ can judge instantly —
what the seam actually sounds like — was unreachable from the terminal.

Given two tracks, this analyzes them, takes the engine's own mix-out and mix-in
windows, snaps the cues to the beat with the same rule the cue exporter uses,
and renders a single phrase-locked WAV of the handoff.
"""

from __future__ import annotations

from pathlib import Path

import typer

from dancelab.core.errors import DanceLabError


DEFAULT_PROFILE = "contour_blend"


def _best_window(windows, want):
    from dancelab.core.models import WindowType

    kind = WindowType.mix_out if want == "out" else WindowType.mix_in
    matching = [w for w in windows if w.window_type == kind] or list(windows)
    return max(matching, key=lambda w: w.score) if matching else None


def render(
    track_a: Path = typer.Argument(..., help="Outgoing track (audio file)"),
    track_b: Path = typer.Argument(..., help="Incoming track (audio file)"),
    output: Path = typer.Option(Path("transition_preview.wav"), "--output", "-o"),
    profile: str = typer.Option(DEFAULT_PROFILE, "--profile",
                                help="Blend shape: linear, plain_blend, bass_swap, "
                                     "tops_swap, contour_blend"),
    beats: int = typer.Option(None, "--beats",
                              help="Transition length in beats (32/64/96/128/160/"
                                   "192/224/256). Omit to let the stability of "
                                   "both tracks at the seam decide."),
    tempo_mode: str = typer.Option(
        "varispeed", "--tempo-mode",
        help="varispeed = pitch moves with tempo, like a pitch fader with Master "
             "Tempo off (clean). stretch = hold pitch via phase vocoder (smears "
             "transients, can sound dull).",
    ),
    config: str = typer.Option("configs/default.yaml", "--config", "-c"),
) -> dict:
    """Render an audible preview of the A→B transition to a WAV file.

    Returns where the seam actually landed. Typer ignores the value, but a
    caller driving this from a review screen needs the cue points to let the DJ
    hear where A leaves and B enters, not only the blend.
    """
    from dancelab.core.config import load_config, load_weights
    from dancelab.core.models import TransitionWindowInput
    from dancelab.core.pipeline import analyze_track
    from dancelab.decision.cue_grid import snap_cue_start
    from dancelab.decision.tempo_adjustment import nearest_octave_candidate
    from dancelab.decision.transition_windows import detect_transition_windows
    from dancelab.preview.transition_simulation import (
        plan_transition_duration,
        profile_description,
        render_transition_preview,
    )

    for path in (track_a, track_b):
        if not path.exists():
            typer.secho(f"INPUT ERROR: no such audio file: {path}", fg="red", err=True)
            raise typer.Exit(2)

    try:
        profile_description(profile)
    except Exception:
        typer.secho(
            f"INPUT ERROR: unknown profile '{profile}'. Available: linear, "
            "plain_blend, bass_swap, tops_swap, contour_blend",
            fg="red", err=True,
        )
        raise typer.Exit(2)

    cfg = load_config(config)
    weights = load_weights(cfg.weights_file)

    try:
        typer.echo(f"analyzing {track_a.name} …")
        analysis_a = analyze_track(track_a, cfg)
        typer.echo(f"analyzing {track_b.name} …")
        analysis_b = analyze_track(track_b, cfg)
    except DanceLabError as exc:
        typer.secho(f"ERROR: {exc}", fg="red", err=True)
        raise typer.Exit(1)

    bpm_a = analysis_a.track.bpm_estimate
    bpm_b = analysis_b.track.bpm_estimate
    if not bpm_a or not bpm_b:
        typer.secho(
            "ERROR: a preview is phrase-locked, so both tracks need a tempo; "
            "the analysis did not produce one.",
            fg="red", err=True,
        )
        raise typer.Exit(1)

    def _windows(analysis):
        return detect_transition_windows(
            TransitionWindowInput(
                track_id=analysis.track.track_id,
                segments=analysis.segments,
                feature_frames=analysis.features,
                beatgrid=analysis.beatgrid,
            ),
            weights.transition_window,
        ).windows

    out_window = _best_window(_windows(analysis_a), "out")
    in_window = _best_window(_windows(analysis_b), "in")
    if out_window is None or in_window is None:
        typer.secho(
            "ERROR: the engine found no usable mix-out/mix-in window for this pair.",
            fg="red", err=True,
        )
        raise typer.Exit(1)

    # Same snapping rule the cue exporter uses: an unreliable grid snaps nothing.
    cue_a = snap_cue_start(analysis_a.beatgrid, out_window.start_sec)
    cue_b = snap_cue_start(analysis_b.beatgrid, in_window.start_sec)

    if beats is None:
        from dancelab.decision.transition_length import suggest_transition_beats

        suggestion = suggest_transition_beats(analysis_a, out_window.start_sec,
                                              analysis_b, in_window.start_sec)
        if suggestion.beats is not None:
            beats = suggestion.beats
            typer.echo("length from seam stability (craft rule, not a measurement):")
            for line in suggestion.reasoning:
                typer.echo(f"  {line}")
        else:
            beats = 64
            typer.echo("⚠ seam stability could not be read — falling back to 64 beats:")
            for line in suggestion.reasoning:
                typer.echo(f"  {line}")

    rate_b = bpm_a / nearest_octave_candidate(bpm_a, bpm_b).bpm
    duration_a = analysis_a.track.duration_sec or 0.0
    duration_b = analysis_b.track.duration_sec or 0.0
    plan = plan_transition_duration(
        beats,
        available_a_beats=max(duration_a - cue_a, 0.0) * bpm_a / 60.0,
        available_b_beats=max(duration_b - cue_b, 0.0) / rate_b * bpm_a / 60.0,
    )
    if plan.selected_beats is None:
        typer.secho(
            f"ERROR: neither track has {beats} beats of runway left from its cue "
            "— try a shorter --beats.",
            fg="red", err=True,
        )
        raise typer.Exit(1)
    if plan.selected_beats != beats:
        typer.echo(f"⚠ {beats} beats did not fit; using {plan.selected_beats}")

    output.parent.mkdir(parents=True, exist_ok=True)
    render_transition_preview(
        source_a=track_a,
        source_b=track_b,
        cue_a_sec=cue_a,
        cue_b_sec=cue_b,
        bpm_master=bpm_a,
        playback_rate_b=rate_b,
        profile_id=profile,
        output_path=output,
        duration_beats=plan.selected_beats,
        tempo_mode=tempo_mode,
    )

    mins_a, secs_a = divmod(int(cue_a), 60)
    mins_b, secs_b = divmod(int(cue_b), 60)
    typer.echo(
        f"✓ {output}\n"
        f"  out of A at {mins_a}:{secs_a:02d} · into B at {mins_b}:{secs_b:02d} · "
        f"{plan.selected_beats} beats at {bpm_a:.1f} BPM · {profile} · {tempo_mode}"
    )
    return {"cue_a_sec": cue_a, "cue_b_sec": cue_b,
            "beats": plan.selected_beats, "bpm": bpm_a, "output": output}
