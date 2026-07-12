#!/bin/bash
# DanceLab Pro launcher — heals the macOS ENV-1 dylib-hiding bug BEFORE Qt
# loads (shell-level, synchronous — the in-Python heal can be too late for
# QtMultimedia backend discovery: "No QtMultimedia backends found").
# Usage: ./run_app.sh            (Simple Mode, default)
#        ./run_app.sh --graph    (Advanced Signal Graph editor)
set -e
cd "$(dirname "$0")"

PYSIDE=".venv/lib/python3.12/site-packages/PySide6"
if [ -d "$PYSIDE" ]; then
  chflags -R nohidden "$PYSIDE" 2>/dev/null || true
  xattr -rd com.apple.provenance "$PYSIDE" 2>/dev/null || true
fi

PYTHONPATH=src exec .venv/bin/python -c "
import sys
from dancelab.host.desktop_app import main
sys.exit(main())
" "$@"
