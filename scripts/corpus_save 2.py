#!/usr/bin/env python3
"""Create, list, and verify DanceLab corpus save slots."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dancelab.validation.djmix.checkpoint import create_checkpoint, verify_checkpoint  # noqa: E402


DEFAULT_CORPUS_ROOT = Path("/Volumes/MY_PC/DanceLabCorpus")
DEFAULT_CHECKPOINT_ROOT = PROJECT_ROOT / "data" / "checkpoints" / "corpus"


def _save(args: argparse.Namespace) -> int:
    slot = create_checkpoint(
        project_root=PROJECT_ROOT,
        corpus_root=args.root,
        checkpoint_root=args.checkpoint_root,
        label=args.label,
        engine_mode=args.engine_mode,
        pipeline_command=args.pipeline_command,
    )
    result = verify_checkpoint(slot)
    print(f"SAVE SLOT: {slot}")
    print(f"integrity: {'OK' if result['valid'] else 'FAILED'}")
    print(f"completed reports: {result.get('completed_report_count', 0)}")
    return 0 if result["valid"] else 1


def _verify(args: argparse.Namespace) -> int:
    result = verify_checkpoint(args.slot)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


def _list(args: argparse.Namespace) -> int:
    if not args.checkpoint_root.is_dir():
        print("no save slots")
        return 0
    for slot in sorted(path for path in args.checkpoint_root.iterdir() if path.is_dir()):
        result = verify_checkpoint(slot)
        state = "OK" if result["valid"] else "BROKEN"
        print(f"{slot.name}  {state}  reports={result.get('completed_report_count', '?')}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    save = subparsers.add_parser("save", help="create an incremental save slot")
    save.add_argument("--root", type=Path, default=DEFAULT_CORPUS_ROOT)
    save.add_argument("--checkpoint-root", type=Path, default=DEFAULT_CHECKPOINT_ROOT)
    save.add_argument("--label", default="manual-save")
    save.add_argument("--engine-mode", choices=("legacy", "cache-experiment"), default="legacy")
    save.add_argument("--pipeline-command", default="")
    save.set_defaults(handler=_save)

    verify = subparsers.add_parser("verify", help="verify every artifact in a save slot")
    verify.add_argument("slot", type=Path)
    verify.set_defaults(handler=_verify)

    listing = subparsers.add_parser("list", help="list local save slots")
    listing.add_argument("--checkpoint-root", type=Path, default=DEFAULT_CHECKPOINT_ROOT)
    listing.set_defaults(handler=_list)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
