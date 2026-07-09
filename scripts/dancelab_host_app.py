from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_repo_src() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_dir = repo_root / "src"
    if src_dir.exists():
        src_str = str(src_dir)
        if src_str not in sys.path:
            sys.path.insert(0, src_str)


_bootstrap_repo_src()

from dancelab.host.desktop_app import main


if __name__ == "__main__":
    raise SystemExit(main())
