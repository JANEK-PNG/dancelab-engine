"""What the DJ said about a seam, and how it comes back to the engine.

The status report's finding: engine and DJ are coupled asymmetrically. The
engine proposes and explains, but the DJ's correction reaches it through an
engineer rather than through the product. This module is the return path — the
place a verdict lands so the next proposal already knows it.

Honesty rules, deliberately narrow (ADR-005):
- a verdict is remembered for the PAIR it was given on, and nothing more. With
  a handful of judgements, generalising to "he dislikes minor keys" would be
  invention, not learning;
- the engine's own score is never overwritten. A verdict is a separate,
  inspectable adjustment, so the two voices stay distinguishable;
- length feedback ("longer"/"shorter") adjusts that pair's suggested blend and
  is expressed in the renderer's own phrase options, not free numbers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["yes", "no", "longer", "shorter"]

# How strongly an accepted or rejected pair moves in the ranking. Named, tunable
# and small: a verdict is a nudge from one listen, not a law.
ACCEPT_BONUS = 0.15
REJECT_PENALTY = 0.40

PHRASE_OPTIONS = (32, 64, 96, 128, 160, 192, 224, 256)


class SeamVerdict(BaseModel):
    from_track_id: str
    to_track_id: str
    verdict: Verdict
    beats: int | None = None          # the length that was auditioned
    at: str = ""                      # ISO timestamp, for provenance only


class VerdictStore(BaseModel):
    """Every judgement the DJ has given, newest last."""

    verdicts: list[SeamVerdict] = Field(default_factory=list)

    # ---------------------------------------------------------------- storage
    @classmethod
    def load(cls, path: Path) -> "VerdictStore":
        path = Path(path)
        if not path.exists():
            return cls()
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            # A corrupt store must not block the session; it also must not be
            # silently replaced, so the caller sees an empty store and the file
            # stays on disk for inspection.
            return cls()

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    # ---------------------------------------------------------------- writing
    def record(self, from_id: str, to_id: str, verdict: Verdict,
               beats: int | None = None) -> SeamVerdict:
        entry = SeamVerdict(
            from_track_id=str(from_id), to_track_id=str(to_id),
            verdict=verdict, beats=beats,
            at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        self.verdicts.append(entry)
        return entry

    # ---------------------------------------------------------------- reading
    def latest_for(self, from_id: str, to_id: str) -> SeamVerdict | None:
        """The DJ's most recent word on this exact pair, if any."""
        for entry in reversed(self.verdicts):
            if entry.from_track_id == str(from_id) and entry.to_track_id == str(to_id):
                return entry
        return None

    def score_adjustment(self, from_id: str, to_id: str) -> float:
        """Additive nudge for this pair — 0.0 when the DJ never judged it."""
        entry = self.latest_for(from_id, to_id)
        if entry is None:
            return 0.0
        if entry.verdict == "yes":
            return ACCEPT_BONUS
        if entry.verdict == "no":
            return -REJECT_PENALTY
        return 0.0        # length feedback says nothing about whether to play it

    def preferred_beats(self, from_id: str, to_id: str, suggested: int | None) -> int | None:
        """The blend length this pair should be auditioned at next time.

        'longer' and 'shorter' step through the renderer's own phrase options,
        starting from whatever was last auditioned, so the value stays something
        the preview can actually produce.
        """
        entry = self.latest_for(from_id, to_id)
        if entry is None or entry.verdict not in ("longer", "shorter"):
            return suggested
        anchor = entry.beats if entry.beats in PHRASE_OPTIONS else suggested
        if anchor not in PHRASE_OPTIONS:
            return suggested
        index = PHRASE_OPTIONS.index(anchor)
        step = 1 if entry.verdict == "longer" else -1
        return PHRASE_OPTIONS[max(0, min(len(PHRASE_OPTIONS) - 1, index + step))]

    # ---------------------------------------------------------------- summary
    def counts(self) -> dict[str, int]:
        out = {"yes": 0, "no": 0, "longer": 0, "shorter": 0}
        for entry in self.verdicts:
            out[entry.verdict] = out.get(entry.verdict, 0) + 1
        return out
