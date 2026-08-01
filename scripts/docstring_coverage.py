"""Measure and enforce docstring coverage across the engine source tree.

Documentation is treated as code here: the coverage of the public surface is
measured, reported and ratcheted in CI, exactly like test coverage. The floors
below are set to the level the tree already meets, so this gate never fails on
work that leaves documentation where it found it — it fails only on regression.
Raise the floors when a pass improves the numbers; never lower them.

The floors deliberately cover modules, classes and public callables, and NOT
parameter-by-parameter prose. 96% of arguments and 95% of return values already
carry type annotations, so restating them in text would add noise rather than
information. Parameter prose is required only where a type cannot express the
contract — units, ranges, ownership, side effects — and that judgement lives in
docs/DOCUMENTATION_STANDARD.md rather than in a percentage.

Usage:
    python scripts/docstring_coverage.py                 # report only
    python scripts/docstring_coverage.py --check         # enforce the floors
    python scripts/docstring_coverage.py --json out.json # machine-readable
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src"

# Floors measured on main at 2026-08-01. Ratchet up, never down.
FLOORS = {
    "modules": 90.0,
    "classes": 45.0,
    "public_callables": 49.0,
}

# Private helpers and generated code are exempt: IBM's own guidance warns that
# overdocumentation hinders readability, and a one-line private helper with full
# type annotations is already as readable as a docstring would make it.
EXCLUDED_PARTS = {"__pycache__", "_vendor"}


@dataclass
class Tally:
    """Counts documented items against total items for one documentation kind."""

    documented: int = 0
    total: int = 0
    undocumented: list[str] = field(default_factory=list)

    def record(self, has_doc: bool, label: str) -> None:
        """Add one item to the tally, remembering it if it lacks a docstring."""
        self.total += 1
        if has_doc:
            self.documented += 1
        else:
            self.undocumented.append(label)

    @property
    def percent(self) -> float:
        """Documented share as a percentage; 100.0 when there is nothing to document."""
        return 100.0 * self.documented / self.total if self.total else 100.0


def _iter_source_files(root: Path) -> list[Path]:
    """Return every Python file under root, skipping caches and vendored trees."""
    return sorted(
        path
        for path in root.rglob("*.py")
        if not EXCLUDED_PARTS.intersection(path.parts)
    )


def measure(root: Path = SOURCE_ROOT) -> dict[str, Tally]:
    """Walk the source tree and tally docstring coverage by documentation kind.

    Returns a mapping with the keys ``modules``, ``classes`` and
    ``public_callables``. A callable counts as public when neither it nor any
    enclosing class starts with an underscore, because that is the surface a
    reader of this repository can actually call.
    """
    tallies = {"modules": Tally(), "classes": Tally(), "public_callables": Tally()}

    for path in _iter_source_files(root):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
            print(f"skipped {path}: {exc}", file=sys.stderr)
            continue

        relative = path.relative_to(ROOT)
        tallies["modules"].record(bool(ast.get_docstring(tree)), str(relative))

        for node, qualname in _walk_named(tree):
            label = f"{relative}::{qualname}"
            if isinstance(node, ast.ClassDef):
                tallies["classes"].record(bool(ast.get_docstring(node)), label)
            elif not any(part.startswith("_") for part in qualname.split(".")):
                tallies["public_callables"].record(bool(ast.get_docstring(node)), label)

    return tallies


def _walk_named(tree: ast.Module) -> list[tuple[ast.AST, str]]:
    """Yield every class and function in the module with its dotted qualified name."""
    found: list[tuple[ast.AST, str]] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qualname = f"{prefix}.{child.name}" if prefix else child.name
                found.append((child, qualname))
                visit(child, qualname)

    visit(tree, "")
    return found


def report(tallies: dict[str, Tally], *, show_missing: int = 0) -> None:
    """Print a human-readable coverage table, optionally listing undocumented items."""
    print("Docstring coverage")
    print("-" * 52)
    for kind, tally in tallies.items():
        floor = FLOORS.get(kind)
        status = "" if floor is None else ("ok" if tally.percent >= floor else "BELOW FLOOR")
        floor_text = "" if floor is None else f"  floor {floor:.0f}%"
        print(
            f"{kind:<18} {tally.documented:>4}/{tally.total:<5} "
            f"{tally.percent:>5.1f}%{floor_text}  {status}"
        )
        if show_missing:
            for label in tally.undocumented[:show_missing]:
                print(f"    missing: {label}")


def check(tallies: dict[str, Tally]) -> int:
    """Return a non-zero exit code if any measured kind fell below its floor."""
    failures = [
        f"{kind}: {tally.percent:.1f}% is below the {FLOORS[kind]:.0f}% floor"
        for kind, tally in tallies.items()
        if kind in FLOORS and tally.percent < FLOORS[kind]
    ]
    for failure in failures:
        print(f"docstring coverage regression — {failure}", file=sys.stderr)
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    """Entry point for the command line: measure, report, and optionally enforce."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if coverage dropped")
    parser.add_argument("--json", type=Path, help="write the tallies to this path")
    parser.add_argument(
        "--show-missing",
        type=int,
        default=0,
        metavar="N",
        help="list up to N undocumented items per kind",
    )
    args = parser.parse_args(argv)

    tallies = measure()
    report(tallies, show_missing=args.show_missing)

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    kind: {
                        "documented": tally.documented,
                        "total": tally.total,
                        "percent": round(tally.percent, 2),
                        "floor": FLOORS.get(kind),
                    }
                    for kind, tally in tallies.items()
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    return check(tallies) if args.check else 0


if __name__ == "__main__":
    raise SystemExit(main())
