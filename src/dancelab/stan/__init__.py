"""Warstwa stanu — jeden rdzeń pod dwie skóry: terminal i okno.

Decyzja Janka z 11.08 (`docs/TERRAIN_X_TUI_SYNTEZA_2026-08-11.md`): „rdzeń TUI,
wygląd GUI". Sześć modułów w `dancelab.tui` nie importuje Textual w ogóle —
są czystą logiką, która przez przypadek mieszka w pakiecie o nazwie „tui".

Ten pakiet **nie przenosi kodu**. Re-eksportuje go pod nazwami niezwiązanymi z
żadną skórą, żeby GUI nie musiało importować z `tui`, a terminal nie stracił
niczego. Jedyne nowe jest `przebieg` — dane do rysowania zamiast znaków.

Przeniesienie plików byłoby ryzykiem bez zysku: TUI ma zielone testy, a import
z nowej ścieżki nie zmienia zachowania ani jednej funkcji.
"""

from dancelab.stan import przebieg
from dancelab.tui import cue_edycje as edycje
from dancelab.tui import cue_podglad as cue
from dancelab.tui import cue_zapis as zapis
from dancelab.tui import plan_store as plany
from dancelab.tui import seam_preview as szew
from dancelab.tui import user_store as uzytkownik

__all__ = ["cue", "edycje", "plany", "przebieg", "szew", "uzytkownik", "zapis"]
