#!/bin/zsh
# DanceLab — start TUI podwójnym kliknięciem.
# Plik celowo leży w korzeniu repo: `dirname $0` prowadzi do silnika
# niezależnie od tego, skąd Janek go kliknie (alias na biurku też działa).
#
# Ostre okładki wymagają Ghostty — Terminal.app nie zna protokołu
# graficznego Kitty i okładki spadają do pikselowej mozaiki. Klik
# w Terminalu przenosi się więc SAM do Ghostty (o ile zainstalowane);
# wewnątrz Ghostty TERM_PROGRAM=ghostty, więc pętli nie ma.
# Awaryjnie: DANCELAB_BEZ_GHOSTTY=1 zostaje w bieżącym terminalu.
if [ "${TERM_PROGRAM:-}" != "ghostty" ] && [ -z "${DANCELAB_BEZ_GHOSTTY:-}" ] \
        && open -Ra Ghostty 2>/dev/null; then
    echo "Przenoszę DanceLab do Ghostty (ostre okładki)…"
    open -na Ghostty --args -e "$0"
    exit 0
fi
cd "$(dirname "$0")" || exit 1
exec .venv/bin/dancelab tui
