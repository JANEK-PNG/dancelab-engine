#!/bin/bash
# DanceLab Pro launcher — one command, survives the macOS ENV-1 dylib-hiding bug.
# Usage: ./run_app.sh            (Simple Mode, default)
#        ./run_app.sh --graph    (Advanced Signal Graph editor)
set -e
cd "$(dirname "$0")"
PYTHONPATH=src exec .venv/bin/python -c "
import sys
from dancelab.host.desktop_app import main
sys.exit(main())
" "$@"
