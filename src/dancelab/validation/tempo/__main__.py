"""CLI for the read-only Rekordbox tempo benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from dancelab.validation.tempo.benchmark import run_tempo_benchmark, write_tempo_benchmark


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m dancelab.validation.tempo",
        description="Compare DanceLab BPM/beat grids with an explicit Rekordbox XML export.",
    )
    parser.add_argument("--analyses", type=Path, required=True)
    parser.add_argument("--rekordbox-xml", type=Path, action="append", required=True)
    parser.add_argument("--output", "-o", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = run_tempo_benchmark(args.analyses, args.rekordbox_xml)
    write_tempo_benchmark(report, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
