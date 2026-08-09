"""Pasek odtwarzacza — JEDEN komponent, trzy zakładki (decyzja Janka 09.08:
„player powinien być w każdym etapie aplikacji").

Wcześniej pasek był wbudowany na sztywno w Bibliotekę, więc po przejściu do
Setu czy Eksportu utwór grał, ale nie było czym sterować ani czego czytać.
Teraz to widget wstawiany trzy razy; identyfikuje się KLASAMI, nie `id`
(id musi być unikalne w całym drzewie, a instancje są trzy), a aplikacja
odświeża wszystkie naraz — stan odtwarzacza jest jeden i wspólny.

Układ jak w Apple Music (zatwierdzony 06.08): sterowanie po lewej, okładka,
metadane; pod metadanymi OŚ CZASU — energia utworu z głowicą odtwarzania,
bo wszystkie cegiełki (klatki RMS, pozycja, długość) już mamy.
"""

from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static


class PasekOdtwarzacza(Horizontal):
    """Sterowanie + okładka + tytuł + oś czasu. Bez własnej logiki —
    wszystko rysuje i obsługuje aplikacja, żeby stan był jeden."""

    DEFAULT_CLASSES = "pb-box"

    def compose(self):
        with Horizontal(classes="pb-row1"):
            yield Button("Poprz.", classes="pb-prev")
            yield Button("-8", classes="pb-back")
            yield Button("Graj", variant="primary", classes="pb-play")
            yield Button("+8", classes="pb-fwd")
            yield Button("Nast.", classes="pb-next")
        yield Static("", classes="pb-art")
        with Vertical(classes="pb-meta"):
            yield Static("nic nie gra", classes="pb-info")
            yield Static("", classes="pb-sub")
            yield Static("", classes="pb-os")


def czas(sekundy: float) -> str:
    m, s = divmod(int(max(sekundy, 0)), 60)
    return f"{m}:{s:02d}"


def os_z_glowica(analiza, pozycja_sec: float, szer: int):
    """Oś czasu: energia utworu + głowica odtwarzania + zegar „teraz/całość".

    Zwraca rich.Text albo None, gdy nie ma z czego rysować (brak analizy
    albo długości) — wtedy pasek pokazuje sam zegar, nigdy zmyślony kształt.
    """
    from rich.text import Text

    from dancelab.tui.cue_podglad import czas_utworu, os_energii

    if analiza is None:
        return None
    dlugosc = czas_utworu(analiza)
    if dlugosc <= 0 or szer < 8:
        return None
    energia = os_energii(analiza, szer)
    glowica = min(int(pozycja_sec / dlugosc * szer), szer - 1)
    t = Text()
    t.append(energia[:glowica], style="dim")
    t.append("▮", style="bold #7f77dd")
    t.append(energia[glowica + 1:], style="dim")
    t.append(f"  {czas(pozycja_sec)} / {czas(dlugosc)}", style="dim")
    return t
