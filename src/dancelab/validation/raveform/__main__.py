"""CLI for training a separate Raveform transition-duration prior artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from dancelab.validation.raveform.dataset import load_raveform_observations
from dancelab.validation.raveform.training import train_raveform_prior


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dancelab.validation.raveform",
        description="Train and evaluate an offline duration prior from a local Raveform archive.",
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", "-o", type=Path, required=True)
    parser.add_argument("--split-seed", default="dancelab-raveform-v1")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    observations, dataset_audit = load_raveform_observations(args.archive)
    _, training_report = train_raveform_prior(observations, split_seed=args.split_seed)
    report = {
        "dataset": dataset_audit,
        "training": training_report,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
