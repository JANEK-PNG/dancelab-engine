#!/bin/zsh
# DanceLab — start TUI podwójnym kliknięciem.
# Plik celowo leży w korzeniu repo: `dirname $0` prowadzi do silnika
# niezależnie od tego, skąd Janek go kliknie (alias na biurku też działa).
cd "$(dirname "$0")" || exit 1
exec .venv/bin/dancelab tui
