"""The hard export invariant, checked without a Rekordbox library.

Rule: cue export writes cues and nothing else. It must never touch a track's
tempo or beat grid — Rekordbox's own analysis stays authoritative, and a DJ who
accepts our cues must not silently inherit our BPM.

The behavioural version of this test (test_never_writes_bpm_or_beatgrid) needs a
real master.db and therefore skips on CI, on a fresh clone, and whenever
Rekordbox is open — exactly the runs where a regression would slip through. This
structural guard runs everywhere: it reads the writer's own source and fails if
it ever starts assigning tempo or grid fields.
"""

import ast
from pathlib import Path

from dancelab.decision.cue_export_models import CuePlan, TrackCuePlan, PlannedCue
from dancelab.decision.cue_write_ops import resolve_write_operations

WRITER = Path("src/dancelab/ingestion/rekordbox_cue_writer.py")

# Rekordbox columns that carry tempo or grid meaning. Writing any of these from
# the cue path would break the invariant.
FORBIDDEN_FIELDS = {
    "BPM", "AverageBpm", "Tempo", "TEMPO", "BeatGrid", "DjmdBeatGrid",
    "Inizio", "Battito", "Metro",
}


def _assigned_keyword_names(source: str) -> set[str]:
    """Every keyword argument name and attribute assigned anywhere in the file."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg:
            names.add(node.arg)
        elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            names.add(node.attr)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
    return names


def test_writer_never_names_a_tempo_or_grid_field():
    source = WRITER.read_text(encoding="utf-8")
    used = _assigned_keyword_names(source)
    offenders = sorted(used & FORBIDDEN_FIELDS)
    assert not offenders, (
        f"{WRITER} references tempo/beatgrid field(s) {offenders}; "
        "cue export must write cues only"
    )


def test_planned_write_operations_describe_cues_only():
    """Whatever the planner asks for, the write is expressed purely as cues."""
    plan = CuePlan(tracks=[TrackCuePlan(content_id="t1", cues=[
        PlannedCue(content_id="t1", position_ms=1000, kind=1, pad_label="A"),
        PlannedCue(content_id="t1", position_ms=2000, kind=2, pad_label="B"),
    ])])
    ops = resolve_write_operations(
        plan, known_content_ids={"t1"}, existing_pad_cues=[]
    )
    assert all(isinstance(item, PlannedCue) for item in ops.inserts)
    for item in ops.inserts:
        assert not (set(item.model_dump()) & FORBIDDEN_FIELDS)
