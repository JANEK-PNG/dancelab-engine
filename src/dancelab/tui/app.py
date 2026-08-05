"""DanceLab TUI — Ekran 1: budowa setu. Formularz → postęp → tabela → W.

Warstwa nad istniejącym silnikiem, zero nowej logiki decyzyjnej: formularz
zbiera dokładnie te parametry, które ma `zagraj`, budowa woła `build_set`
z dokarmianiem, a `W` publikuje przez `ingestion.playlist_publish` (backup,
odmowa przy niejednoznaczności, weryfikacja odczytem).

Dwa tryby puli — bo cache analiz kluczuje po ścieżce (sha1 źródła):
  * BIBLIOTEKA: analizy wprost z katalogu processed (natychmiast, 243 utwory);
  * FOLDER: `analyze_files` z prawdziwym postępem etapów (`stage_progress`)
    i anulowaniem między utworami (`should_stop`) — hooki zostały po Qt
    i od 24.07 nie miały konsumenta.

Zasada ADR-005 jako zasada UI: każde „nie wiem" silnika ma swój piksel —
`SetPlan.warnings` są stale widoczne pod tabelą, nigdy zwinięte; tonacja
o pewności <0,5 jest przygaszona; pasek statusu mówi wprost, czy Rekordbox
jest otwarty (wtedy `W` odmawia, zanim spróbuje).

Edycja gotowego setu (audyt 04.08: brakowało DOKŁADNIE ruchów, którymi Janek
werdyktował piątkowy set ręcznie w Rekordboksie): X wycina, Shift+↑/↓ przesuwa,
A dopisza przez ten sam panel sugestii co Z, S/O zapisuje i wczytuje plan,
V zrzuca werdykt „plan silnika vs stan po Twoich zmianach". Każda edycja
ląduje w dzienniku werdyktów — to rosnąca prawda o guście DJ-a.
"""

from __future__ import annotations

import pathlib
import threading

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    Log,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

PROCESSED_DEFAULT = "experiments_priv/2026-07-30_rebuild/processed"

# Higiena puli — oba znaleziska z realnych przebiegów: stemy Demucsa
# („vocals" wylądowało w secie Janka DWA RAZY, pozycje 18 i 19, 05.08),
# a „Janek.mp3" (43-minutowy cudzy set) wskoczył kiedyś na 1. miejsce.
STEM_NAMES = {"drums", "bass", "other", "vocals", "no_vocals", "accompaniment"}
MAX_TRACK_SEC = 15 * 60

# Dziennik werdyktów DJ-a: każda ręczna edycja setu (podmiana, cięcie,
# przesunięcie, dopisanie) to darmowa prawda o guście — dopisujemy, nie gubimy.
WERDYKTY_DIR = pathlib.Path("experiments_priv/2026-08-04_werdykty")

# Historia zbudowanych setów (odciski) — karmi tryby świeżości silnika:
# „fresh" umie omijać utwory i przejścia grane w poprzednich budowach.
HISTORIA_SETOW = pathlib.Path("data/cache/tui_historia_setow.jsonl")


def _parse_bpm(text: str) -> tuple[float | None, float | None, str | None]:
    """'128-140' → (128.0, 140.0). Pusty = brak okna. Błąd = komunikat."""
    t = text.replace(" ", "")
    if not t:
        return None, None, None
    if "-" not in t:
        return None, None, f"okno tempa to 'lo-hi', dostałem {text!r}"
    lo_s, hi_s = t.split("-", 1)
    try:
        lo, hi = float(lo_s), float(hi_s)
    except ValueError:
        return None, None, f"okno tempa to liczby, dostałem {text!r}"
    if lo >= hi:
        return None, None, f"puste okno: {lo:g} >= {hi:g}"
    return lo, hi, None


# Zakładki wg TUI_WIZJA_2 (inspiracja rmpc, układ zatwierdzony 05.08):
# Biblioteka → Set → Export/Cue; Ctrl+Tab krąży (część terminali połyka
# Ctrl+Tab — stąd też skróty w nawiasach na etykietach zakładek).
_TAB_ORDER = ("tab-lib", "tab-set", "tab-export")


def _energy_raw(a) -> float | None:
    """Średni RMS z ramek — do WYŚWIETLANIA: brak ramek = None, nie 0,5."""
    vals = [f.rms for f in (getattr(a, "features", None) or [])
            if getattr(f, "rms", None) is not None]
    return float(sum(vals) / len(vals)) if vals else None


def _energia_do_oceny(by_id: dict) -> tuple[dict[str, float], float]:
    """Mapa energii pod transition_score (0,5 gdy brak ramek — do OCENY,
    nie do wyświetlania) + rozpiętość. Wspólne dla sugestii i trybu Podpory."""
    energy = {tid: (_energy_raw(a) if _energy_raw(a) is not None else 0.5)
              for tid, a in by_id.items()}
    e_rng = (max(energy.values()) - min(energy.values())) or 1.0
    return energy, e_rng


def filter_library(analyses, *, search: str = "", key: str = "",
                   bpm_lo: float | None = None,
                   bpm_hi: float | None = None) -> list:
    """Filtr Biblioteki: podciąg w nazwie pliku LUB gatunku (bez wielkości
    liter), dokładna tonacja Camelota, domknięte okno BPM. Utwór bez tempa
    przy aktywnym oknie BPM odpada — okno ma znaczyć to, co mówi."""
    s = search.strip().lower()
    k = key.strip().upper()
    out = []
    for a in analyses:
        t = a.track
        if s:
            art, tit = _wykonawca_tytul(t)
            haystack = " ".join((pathlib.Path(t.source_path).stem,
                                 art, tit, t.style_label or "")).lower()
            if s not in haystack:
                continue
        if k and str(t.key_estimate or "").upper() != k:
            continue
        bpm = t.bpm_estimate or 0.0
        if bpm_lo is not None and bpm < bpm_lo:
            continue
        if bpm_hi is not None and bpm > bpm_hi:
            continue
        out.append(a)
    return out


def _rozstaw_filary(filary: list[str], by_id: dict, count: int,
                    tryb: str = "rozstaw") -> dict[int, str]:
    """Filary → pozycje w secie, metafora Janka (05.08): filar ma PODPIERAĆ
    konstrukcję, nie leżeć na końcu (zmierzone: z samym „musi zagrać" 6
    filarów lądowało na pozycjach 13-18 z 18). Pozycje wyznaczamy Z GÓRY,
    a silnik projektuje przęsła między nimi.

    Tryby pozycyjne: `rozstaw` — równomiernie po całym secie; `rama` —
    pierwszy filar ZAWSZE otwiera set, ostatni ZAWSZE zamyka, środek
    równomiernie. (Tryb `podpory` nie jest pozycyjny — patrz _wstaw_podpory.)

    Kolejność filarów wzdłuż setu: rosnąco po tempie — zgodnie ze schodkami
    tempa (`staircase`) i łukiem `build`, którymi Janek gra. Ograniczenie v1,
    nazwane wprost: przy łuku `peak` przydział powinien kiedyś patrzeć
    w krzywą tempa, nie tylko rosnąć."""
    posortowane = sorted(filary,
                         key=lambda t: by_id[t].track.bpm_estimate or 0.0)
    k = len(posortowane)
    pozycje: dict[int, str] = {}
    if tryb == "rama" and k >= 2 and count >= k:
        pozycje[1] = posortowane[0]
        pozycje[count] = posortowane[-1]
        srodek = posortowane[1:-1]
        m = len(srodek)
        prev = 1
        for i, tid in enumerate(srodek):
            pos = int((i + 0.5) * (count - 2) / m + 0.5) + 1
            pos = min(max(pos, prev + 1), count - 1 - (m - 1 - i))
            pozycje[pos] = tid
            prev = pos
        return pozycje
    prev = 0
    for i, tid in enumerate(posortowane):
        pos = int((i + 0.5) * count / k + 0.5)
        pos = min(max(pos, prev + 1), count - (k - 1 - i))
        pozycje[pos] = tid
        prev = pos
    return pozycje


def _filary_for_build(state: dict, by_id: dict, bpm_min: float | None,
                      bpm_max: float | None, count: int | None
                      ) -> tuple[list[str], list[str]]:
    """Filary z Biblioteki → `pinned_track_ids` silnika, z jawnym losem
    każdego konfliktu: filar spoza puli i filar poza oknem tempa są POMIJANE
    z imienną notką (okno ustawił użytkownik — konflikt ma być widoczny, nie
    rozstrzygany po cichu); więcej filarów niż miejsc = odmowa z liczbami."""
    from dancelab.tui.user_store import MIN_FILARY, resolve_tracks
    ids, missing = resolve_tracks(state.get("filary", []), by_id)
    notes = [f"FILAR nieobecny w puli (pominięty): {m}" for m in missing]
    kept: list[str] = []
    for tid in ids:
        bpm = by_id[tid].track.bpm_estimate or 0.0
        if (bpm_min is not None and bpm < bpm_min) or \
                (bpm_max is not None and bpm > bpm_max):
            name = pathlib.Path(by_id[tid].track.source_path).stem[:40]
            notes.append(f"FILAR poza oknem tempa (pominięty): {name} ({bpm:.1f})")
            continue
        kept.append(tid)
    if kept and len(kept) < MIN_FILARY:
        raise ValueError(
            f"filary to minimum {MIN_FILARY}, a po sitach zostało {len(kept)} "
            f"— dodaj filary w Bibliotece (F) albo zdejmij wszystkie")
    if count is not None and len(kept) > count:
        raise ValueError(f"filarów ({len(kept)}) więcej niż miejsc w secie "
                         f"({count}) — wydłuż set albo zdejmij filary")
    if kept:
        notes.append(f"filary w budowie: {len(kept)} (każdy MUSI zagrać)")
    return kept, notes


# Poświata „influence" ŻYŁA JEDEN DZIEŃ: pomysł Janka 04.08, jego własne weto
# 05.08 po użyciu („makes no sense and it's distracting") — usunięta w całości.
# Ta notka zostaje, żeby pomysł nie wrócił bez pamięci o werdykcie.

# Filary w tabeli setu: złota flaga ⚑ + złoty tekst.
PILLAR_COLOR = "#d9a441"

# Wyróżnienie BPM i tonacji: BOLD, nie tło (Janek 05.08 rano: podkładka;
# 06.08: weto po zobaczeniu jasnego motywu — ciemne tło wygląda tam jak
# dziury). Ramki wokół komórki tabela terminalowa nie ma; bold działa
# w obu motywach.


def _bpm_cell(t):
    from rich.text import Text
    return Text(f"{t.bpm_estimate or 0:.1f}", style="bold")


# Waveformy w panelu porównania ŻYŁY DWA DNI: zbudowane 06.08 (RGB, warstwy
# basu, siatka, frazy), skasowane 06.08 wieczorem wetem Janka: „they are not
# even functional, just for the look purposes". Wróciliśmy do wzorca z CURVE
# (poprzedni projekt): między parą utworów tylko JEDEN przycisk odsłuchu.
# Ta notka zostaje, żeby waveformy nie wróciły bez pamięci o werdykcie.

def _wykonawca_tytul(t) -> tuple[str, str]:
    """Wykonawca i tytuł do kolumn Biblioteki: tag z analizy → uzupełnienie
    z RB (enrichment) → parsowanie nazwy pliku „Artysta - Tytuł" → sam stem."""
    art = (getattr(t, "artist", None) or "").strip()
    tit = (getattr(t, "title", None) or "").strip()
    if art and tit:
        return art, tit
    stem = pathlib.Path(t.source_path).stem
    if " - " in stem:
        a, b = stem.split(" - ", 1)
        return (art or a.strip()), (tit or b.strip())
    return art, (tit or stem)


def _conf_cell(t):
    zrodlo = getattr(t, "key_detection_source", None)
    if zrodlo == "rekordbox":
        return "RB"          # tonacja sędziego, nie liczba z naszego detektora
    if zrodlo == "manual":
        return "ręka"
    conf = t.key_confidence
    return f"{conf:.2f}" if conf is not None else "—"


def _key_cell(t):
    from rich.text import Text
    conf = t.key_confidence
    k = str(t.key_estimate or "?")
    if (conf or 0) >= 0.5:
        return Text(k, style="bold")
    return Text(f"{k}?", style="dim")


# Tryby rozstawiania filarów (Janek, 05.08 — krok konfiguracji po G):
TRYBY_FILAROW = [
    ("podpory", "Podpory — w najsłabsze przęsła"),
    ("rozstaw", "Równy rozstaw — po całym secie"),
    ("rama", "Rama — brzegi + środek równo"),
]
_TRYB_LABEL = dict(TRYBY_FILAROW)


def _wstaw_podpory(core: list[str], filary: list[str],
                   score) -> tuple[list[str], list[str]]:
    """Tryb PODPORY — dosłowna wersja metafory Janka: najpierw konstrukcja
    BEZ filarów, potem pomiar każdego przęsła (ten sam transition_score,
    którym stoi budowa), i filar wchodzi tam, gdzie konstrukcja najsłabsza.
    Przydział filar→przęsło: dla każdego z k najsłabszych przęseł wybieramy
    filar, który je najlepiej mostkuje (średnia wejścia i wyjścia).

    Wymaga przęseł >= filarów; wołający przy braku spada na równy rozstaw
    Z NOTKĄ, nigdy po cichu."""
    if len(core) - 1 < len(filary):
        raise ValueError("za mało przęseł na tryb Podpory")
    seams = sorted((score(core[i], core[i + 1]), i)
                   for i in range(len(core) - 1))
    wolne = list(filary)
    inserts: dict[int, str] = {}
    notes: list[str] = []
    for slabosc, i in seams[:len(filary)]:
        best = max(wolne, key=lambda p: (score(core[i], p)
                                         + score(p, core[i + 1])) / 2)
        wolne.remove(best)
        inserts[i] = best
        notes.append(f"podpora w przęśle #{i+1}→#{i+2} "
                     f"(było {slabosc:.2f})")
    final: list[str] = []
    for i, tid in enumerate(core):
        final.append(tid)
        if i in inserts:
            final.append(inserts[i])
    return final, notes


def _lib_sort_missing(col: int, a, energy: dict) -> bool:
    """Czy utwór nie ma wartości w sortowanej kolumnie — braki idą NA KONIEC
    niezależnie od kierunku sortowania (brak to brak, nie zero)."""
    t = a.track
    if col == 2:
        return t.bpm_estimate is None
    if col == 3:
        return t.key_estimate is None
    if col == 4:
        return t.key_confidence is None
    if col == 5:
        return energy.get(t.track_id) is None
    if col == 6:
        return not t.style_label
    return False


def _lib_sort_key(col: int, favs: set, filary: set, energy: dict):
    """Klucz sortowania Biblioteki po klikniętej kolumnie (standard branży)."""
    def name(a):
        return pathlib.Path(a.track.source_path).stem.lower()

    def key(a):
        t = a.track
        if col == 0:
            return (t.track_id not in favs, name(a))
        if col == 1:
            return (t.track_id not in filary, name(a))
        if col == 2:
            return t.bpm_estimate or 0.0
        if col == 3:
            k = str(t.key_estimate or "")
            num = int(k[:-1]) if len(k) > 1 and k[:-1].isdigit() else 99
            return (num, k[-1:])
        if col == 4:
            return t.key_confidence or 0.0
        if col == 5:
            return energy.get(t.track_id) or 0
        if col == 6:
            return (t.style_label or "").lower()
        if col == 7:
            return t.duration_sec or 0.0
        if col == 8:
            return (_wykonawca_tytul(t)[0].lower() or "~", name(a))
        return (_wykonawca_tytul(t)[1].lower() or "~", name(a))
    return key



def _format_track_info(track, rb: dict | None, rb_note: str | None) -> str:
    """Karta INFO (klawisz I): metadane zaznaczonego utworu z NAZWANYM źródłem
    każdej liczby — silnik osobno, Rekordbox osobno (niezależny sędzia tempa)."""
    conf = track.key_confidence
    dur = track.duration_sec or 0
    lines = [
        "SILNIK:",
        f"  BPM {track.bpm_estimate or '—'} · ton {track.key_estimate or '?'}"
        + (" (źródło: Rekordbox)"
           if getattr(track, "key_detection_source", None) == "rekordbox"
           else (f" (pew. {conf:.2f})" if conf is not None else "")),
        f"  gatunek: {track.style_label or '—'}",
        f"  długość: {int(dur // 60)}:{int(dur % 60):02d}",
        "  wektor brzmienia: "
        + ("jest" if getattr(track, "sound_embedding", None) is not None
           else "brak"),
        "",
        "PLIK:",
        f"  {track.source_path}",
        "",
        "REKORDBOX:",
    ]
    if rb_note:
        lines.append(f"  {rb_note}")
    elif rb is None:
        lines.append("  nie ma w kolekcji")
    else:
        if rb.get("matched_by") == "twin":
            lines.append("  (dopasowany po tytule — inna ścieżka)")
        lines.append(f"  BPM wg Rekordboxa: {rb.get('bpm') or '—'}")
        if rb.get("comment"):
            lines.append(f"  komentarz: {str(rb['comment'])[:60]}")
        pls = rb.get("playlists") or []
        if pls:
            lines.append(f"  playlisty ({len(pls)}):")
            lines += [f"   · {p}" for p in pls[:12]]
            if len(pls) > 12:
                lines.append(f"   … i {len(pls) - 12} więcej")
        else:
            lines.append("  poza wszystkimi playlistami")
    return "\n".join(lines)


def _mode_params(mode: object, ctx: dict) -> tuple[str, object]:
    """Tryb panelu sugestii → (planner_mode silnika, kotwica).

    smart = pełna ocena, którą set powstał, plus kotwica z budowy;
    bpm / harmonic = OFICJALNE tryby plannera silnika (te same wagi, których
    używa budowa w trybie bpm/harmonic: 0,55 na tempo albo na koło Camelota),
    bez kotwicy — tryb nazywa dokładnie to, co ocenia."""
    if mode == "bpm":
        return "bpm", None
    if mode == "harmonic":
        return "harmonic", None
    return ctx.get("planner", "smart"), ctx.get("anchor")


class NazwaPlanuScreen(ModalScreen):
    """S pyta o nazwę planu — bez nazwy lista 100 planów jest bezużyteczna
    (pytanie Janka 06.08: „jak będziemy wiedzieli co wczytać?")."""

    CSS = """
    NazwaPlanuScreen { align: center middle; }
    #nazwa-box { width: 64; height: 9; border: solid $accent;
                 background: $panel; padding: 1 2; }
    #nazwa-przyciski { height: 3; margin-top: 1; }
    #nazwa-przyciski Button { margin-right: 2; }
    """
    BINDINGS = [Binding("escape", "anuluj", "Anuluj")]

    def __init__(self, domyslna: str):
        super().__init__()
        self._domyslna = domyslna

    def compose(self) -> ComposeResult:
        with Vertical(id="nazwa-box"):
            yield Label("Nazwa planu (po niej go potem znajdziesz):")
            yield Input(value=self._domyslna, id="plan-name")
            with Horizontal(id="nazwa-przyciski"):
                yield Button("Zapisz", id="nazwa-ok", variant="primary")
                yield Button("Anuluj", id="nazwa-cancel")

    def on_input_submitted(self, event) -> None:
        self.dismiss(event.value.strip() or None)

    def on_button_pressed(self, event) -> None:
        if event.button.id == "nazwa-ok":
            self.dismiss(self.query_one("#plan-name", Input).value.strip()
                         or None)
        else:
            self.dismiss(None)

    def action_anuluj(self) -> None:
        self.dismiss(None)


class DanceLabTUI(App):
    TITLE = "DanceLab — budowa setu"
    CSS = """
    #form { width: 44; padding: 0 1; border-right: solid $primary; }
    #form Input, #form Select { margin-bottom: 1; }
    #results { padding: 0 1; }
    #warnings { height: 9; border-top: solid $warning; display: none; }
    #warnings.open { display: block; }
    #status { height: 1; background: $panel; color: $text-muted; padding: 0 1; }
    #suggest { width: 42; border-left: solid $accent; padding: 0 1; display: none; }
    #suggest.open { display: block; }
    #suggest-title { color: $accent; text-style: bold; }
    #suggest-mode { margin: 1 0; }
    #suggest-mode.hide { display: none; }
    #suggest-list.hide { display: none; }
    #suggest-info { display: none; margin: 1 0; }
    #suggest-info.show { display: block; }
    .field-label { color: $text-muted; }
    #lib-side { width: 26; border-right: solid $primary; padding: 0 1; }
    #lib-filters { height: 3; }
    #lib-filters Input { width: 1fr; margin-right: 1; }
    #lib-count { height: 2; color: $text-muted; padding: 0 1 1 1; }
    #lib-table .datatable--header { text-style: bold; background: $boost; }
    #compare { height: 7; border-bottom: solid $accent; padding: 0 1;
               display: none; }
    #cmp-buttons { height: 3; }
    #compare.open { display: block; }
    #cmp-title { color: $accent; text-style: bold; }
    #lib-table { height: 1fr; }
    #lib-onboard { height: 3; }
    #lib-onboard Input { width: 1fr; margin-right: 1; }
    """
    BINDINGS = [
        Binding("b", "build", "Buduj"),
        Binding("w", "write", "→ Rekordbox"),
        Binding("z", "replace", "Zamień"),
        Binding("x", "cut", "Wytnij"),
        Binding("a", "add", "Dopisz"),
        Binding("shift+up", "move_up", "przesuń ▲", show=False),
        Binding("shift+down", "move_down", "przesuń ▼", show=False),
        Binding("s", "save_plan", "Zapisz plan"),
        Binding("o", "load_plan", "Wczytaj"),
        Binding("v", "verdict", "Werdykt"),
        Binding("p", "preview_seam", "Posłuchaj"),
        Binding("P", "toggle_auto", "auto-podgląd", show=False),
        Binding("right", "skok_przod", "skok +8", show=False, priority=True),
        Binding("left", "skok_tyl", "skok -8", show=False, priority=True),
        Binding("c", "compare_pair", "Porównaj"),
        Binding("i", "track_info", "Info"),
        Binding("l", "toggle_notes", "Log"),
        Binding("u", "toggle_fav", "♥ Ulubiony"),
        Binding("f", "toggle_filar", "Filar"),
        Binding("g", "build_from_filary", "Z filarów", show=False),
        Binding("ctrl+tab", "next_tab", "zakładka →", show=False),
        Binding("ctrl+shift+tab", "prev_tab", "← zakładka", show=False),
        Binding("escape", "cancel", "Anuluj"),
        Binding("q", "quit", "Wyjdź"),
    ]

    # Notki (kanał uczciwości ADR-005) są domyślnie SCHOWANE na życzenie Janka
    # (04.08: „usera to nie interesuje") — ale nie giną: licznik zawsze w pasku
    # statusu, L pokazuje pełną listę, a odmowy i wynik zapisu wyskakują dymkiem
    # same. I to karta INFO zaznaczonego utworu (metadane + dysk + playlisty RB).

    def __init__(self, processed_dir: str = PROCESSED_DEFAULT):
        super().__init__()
        self.processed_dir = processed_dir
        self._stop = threading.Event()
        self._plan_paths: list[str] = []
        self._plan_name = ""
        self._order: list[str] = []
        self._engine_order: list[str] = []
        self._edits: list[dict] = []
        self._mean_score = None
        self._ctx: dict = {}
        self._suggest_slot: int | None = None
        self._panel_mode: str | None = None   # "suggest" | "insert" | "plans"
        self._row_cells: list[tuple[str, str]] = []   # (nr, utwór) do poświaty
        self._n_notes = 0
        self._lib: list = []                  # pula Biblioteki (analizy)
        self._lib_view: list = []             # pula po filtrach (widoczna)
        self._lib_energy: dict[str, float | None] = {}   # tid → energia 0-100
        self._user_state: dict = {"ulubione_utwory": [],
                                  "ulubione_playlisty": [], "filary": []}
        # None = porządek domyślny (BPM rosnąco); cykl klikania w nagłówek:
        # liczby ↓ → ↑ → kasacja, teksty A-Z → Z-A → kasacja (Janek 06.08)
        self._lib_sort: tuple[int, bool] | None = None
        from dancelab.tui.odtwarzacz import Odtwarzacz
        self._odtwarzacz = Odtwarzacz()       # P: utwór / szew, pauza, skoki
        self._auto_podglad = False            # Shift+P: strzałki grają same
        self._auto_timer = None
        self._compare_idx: int | None = None  # para w pasku szwu (C)

    # ------------------------------------------------------------- układ

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial="tab-lib", id="tabs"):
            with TabPane("Biblioteka", id="tab-lib"):
                with Horizontal():
                    # sekcje po lewej, zawsze widoczne — wzór Apple Music
                    with Vertical(id="lib-side"):
                        yield Label("SEKCJE", classes="field-label")
                        side = OptionList(id="lib-side-list")
                        yield side
                    with Vertical():
                        with Horizontal(id="lib-filters"):
                            yield Input(placeholder="szukaj (nazwa / gatunek)…",
                                        id="lib-search")
                            yield Input(placeholder="tonacja np. 8A", id="lib-key")
                            yield Input(placeholder="BPM np. 125-140", id="lib-bpm")
                        yield Static("", id="lib-count")
                        yield DataTable(id="lib-table")
                        with Horizontal(id="lib-onboard"):
                            yield Input(placeholder="folder z muzyką do "
                                                    "przeskanowania (pierwszy raz "
                                                    "albo dogranie)",
                                        id="lib-folder")
                            yield Button("Analizuj", id="lib-analyze",
                                         variant="primary")
                            yield Button("→ Zbuduj z filarów  [G]",
                                         id="lib-build", variant="success")
            with TabPane("Set", id="tab-set"):
                with Vertical():
                    with Horizontal(id="set-main"):
                        with VerticalScroll(id="form"):
                            yield Label("Pula", classes="field-label")
                            yield Select([("Biblioteka (cache analiz)", "library"),
                                          ("Folder…", "folder")],
                                         value="library", id="pool", allow_blank=False)
                            yield Input(placeholder="ścieżka folderu (tryb Folder)",
                                        id="folder")
                            yield Label("Długość [min]", classes="field-label")
                            yield Input(value="90", id="minutes", type="number")
                            yield Label("Okno tempa (np. 128-140)", classes="field-label")
                            yield Input(placeholder="puste = bez okna", id="bpm")
                            yield Label("Gatunki (Twoje tagi RB, po przecinku)",
                                        classes="field-label")
                            yield Input(placeholder="garage, breaks, bass", id="styles")
                            yield Label("Graj jak… (kotwica)", classes="field-label")
                            yield Select([], id="dj", prompt="— bez kotwicy —")
                            with Horizontal():
                                yield Switch(value=False, id="contour")
                                yield Label(" kontur skoków tego DJ-a")
                            yield Label("Łuk / plan tempa / tryb", classes="field-label")
                            yield Select([("build", "build"), ("peak", "peak"),
                                          ("flat", "flat")],
                                         value="build", id="arc", allow_blank=False)
                            yield Select([("staircase", "staircase"),
                                          ("linear", "linear"),
                                          ("off", "off")], value="staircase",
                                         id="tempo", allow_blank=False)
                            yield Select([("smart", "smart"), ("harmonic", "harmonic"),
                                          ("bpm", "bpm")], value="smart", id="planner",
                                         allow_blank=False)
                            yield Label("Świeżość", classes="field-label")
                            yield Select(
                                [("deterministyczny — zawsze ten sam", "deterministic"),
                                 ("zachowawczy", "conservative"),
                                 ("zrównoważony", "balanced"),
                                 ("świeży", "fresh"),
                                 ("odkrywczy", "exploratory")],
                                value="deterministic", id="novelty",
                                allow_blank=False)
                            yield Input(placeholder="seed (puste = losowy)",
                                        id="seed")
                            yield Button("Buduj set  [B]", id="go", variant="primary")
                        with Vertical(id="results"):
                            yield Static("Ustaw parametry i naciśnij B.", id="progress")
                            with Vertical(id="compare"):
                                yield Static("", id="cmp-title")
                                yield Static("", id="cmp-info")
                                with Horizontal(id="cmp-buttons"):
                                    yield Button("▶ Graj oba  [P]",
                                                 id="cmp-play",
                                                 variant="primary")
                            yield DataTable(id="set")
                            yield Log(id="warnings", highlight=False)
                        with Vertical(id="suggest"):
                            yield Label("", id="suggest-title")
                            yield Select([("smart — pełna ocena + kotwica", "smart"),
                                          ("BPM najpierw", "bpm"),
                                          ("tonacja najpierw", "harmonic")],
                                         value="smart", id="suggest-mode",
                                         allow_blank=False)
                            yield OptionList(id="suggest-list")
                            yield Static("", id="suggest-info")
            with TabPane("Eksport / Cue", id="tab-export"):
                yield Static(
                    "Edytor hot cue — w budowie (TUI_WIZJA_2: dodaj / usuń / "
                    "przesuń / scal + auto-generacja z planu przejść).\n"
                    "Dziś auto-cue zapisuje komenda `dancelab zagraj`, "
                    "a playlisty klawisz W w zakładce Set.", id="export-stub")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#set", DataTable)
        for lbl, w in (("#", None), ("BPM", 10), ("ton", 8), ("pew.", None),
                       ("gatunek", None), ("Σ min", None), ("utwór", None)):
            table.add_column(lbl, width=w)
        table.cursor_type = "row"
        lib = self.query_one("#lib-table", DataTable)
        self._lib_col_keys = [
            lib.add_column(lbl, width=w)
            for lbl, w in (("♥", None), ("F", None), ("BPM", 10), ("ton", 8),
                           ("pew.", None), ("energia", None), ("gatunek", None),
                           ("min", None), ("wykonawca", None), ("tytuł", None))]
        lib.cursor_type = "row"
        side = self.query_one("#lib-side-list", OptionList)
        side.add_option(Option("Cała biblioteka", id="all"))
        side.add_option(Option("♥ Ulubione utwory", id="fav"))
        side.add_option(Option("⚑ Filary", id="filary"))
        side.add_option(Option("♥ playlisty — wkrótce", id="pl", disabled=True))
        side.highlighted = 0
        self._lib_section = "all"
        try:
            from dancelab.tui.user_store import load_state
            self._user_state = load_state()
        except Exception as exc:  # noqa: BLE001 — zepsuty plik stanu ≠ martwa apka
            self._note(f"stan ulubionych/filarów nieodczytany: {exc}")
            self._user_state = {"ulubione_utwory": [], "ulubione_playlisty": [],
                                "filary": []}
        self._load_anchors()
        self._refresh_status()
        self.set_interval(5.0, self._refresh_status)
        self._lib_loader()

    # ------------------------------------------------------------ zakładki

    # Pasek skrótów jest KONTEKSTOWY (prośba Janka: „lista skrótów rośnie") —
    # w Bibliotece widać klawisze Biblioteki, w Secie klawisze Setu.
    _LIB_ONLY = {"toggle_fav", "build_from_filary"}
    _SET_ONLY = {"build", "write", "replace", "cut", "add", "move_up",
                 "move_down", "save_plan", "load_plan", "verdict",
                 "track_info", "compare_pair"}

    def check_action(self, action: str, parameters) -> bool:
        try:
            active = self.query_one("#tabs", TabbedContent).active
        except Exception:  # noqa: BLE001 — przed zmontowaniem zakładek
            return True
        if action in ("skok_przod", "skok_tyl"):
            # strzałki poziome przejmuje odtwarzacz TYLKO podczas grania
            # (decyzja Janka) i tylko z fokusem na tabeli — w polu tekstowym
            # dalej ruszają kursorem tekstu
            return (self._odtwarzacz.gra()
                    and isinstance(self.focused, DataTable))
        if action in ("preview_seam", "toggle_auto"):
            return active in ("tab-lib", "tab-set")
        if action in self._LIB_ONLY:
            return active == "tab-lib"
        if action in self._SET_ONLY:
            return active == "tab-set"
        return True

    def action_next_tab(self) -> None:
        self._switch_tab(+1)

    def action_prev_tab(self) -> None:
        self._switch_tab(-1)

    def _switch_tab(self, delta: int) -> None:
        tc = self.query_one("#tabs", TabbedContent)
        i = _TAB_ORDER.index(tc.active) if tc.active in _TAB_ORDER else 0
        tc.active = _TAB_ORDER[(i + delta) % len(_TAB_ORDER)]
        self.refresh_bindings()

    def on_tabbed_content_tab_activated(self, event) -> None:
        self.refresh_bindings()              # klik w zakładkę też odświeża pasek

    # ----------------------------------------------------------- Biblioteka

    @work(thread=True, exclusive=True, group="lib")
    def _lib_loader(self) -> None:
        """Pula do zakładki Biblioteka — te same sita higieny co budowa."""
        ui = self.call_from_thread
        try:
            analyses, notes = self._library_analyses()
        except Exception as exc:  # noqa: BLE001
            ui(self._note, f"Biblioteka nie wstała: {exc}")
            return
        if analyses:
            try:
                from dancelab.ingestion.analysis_enrichment import (
                    attach_rekordbox_genres, attach_rekordbox_keys,
                    attach_rekordbox_meta)
                attach_rekordbox_genres(analyses)
                attach_rekordbox_keys(analyses)
                attach_rekordbox_meta(analyses)
            except Exception as exc:  # noqa: BLE001 — brak RB != martwa Biblioteka
                notes.append(f"dokarmianie Biblioteki nie wyszło: {exc}")
        for note in notes:
            ui(self._note, note)
        ui(self._set_library, analyses)

    def _set_library(self, analyses: list) -> None:
        self._lib = analyses
        raw = {a.track.track_id: _energy_raw(a) for a in analyses}
        known = [v for v in raw.values() if v is not None]
        lo, hi = (min(known), max(known)) if known else (0.0, 1.0)
        span = (hi - lo) or 1.0
        # energia RELATYWNA w obrębie biblioteki (0-100); brak ramek = None
        self._lib_energy = {tid: (None if v is None
                                  else round(100 * (v - lo) / span))
                            for tid, v in raw.items()}
        self._render_library()

    def _lib_filters(self) -> tuple[str, str, float | None, float | None, str | None]:
        search = self.query_one("#lib-search", Input).value
        key = self.query_one("#lib-key", Input).value
        lo, hi, err = _parse_bpm(self.query_one("#lib-bpm", Input).value)
        return search, key, lo, hi, err

    def on_option_list_option_selected(self, event) -> None:
        """Klik w sekcję po lewej przełącza widok Biblioteki. Lista sugestii
        w zakładce Set celowo NIE reaguje na Enter — tam obowiązuje wzorzec
        dwóch naciśnięć (Z/A/O potwierdza)."""
        if getattr(event.option_list, "id", None) == "lib-side-list":
            self._set_lib_section(event.option.id)

    def _set_lib_section(self, section: str) -> None:
        self._lib_section = section
        self._render_library()
        self.query_one("#lib-table", DataTable).focus()

    def _render_library(self, keep_cursor: bool = False) -> None:
        from dancelab.tui.user_store import resolve_tracks
        table = self.query_one("#lib-table", DataTable)
        cursor = table.cursor_row if keep_cursor else None
        table.clear()
        search, key, lo, hi, err = self._lib_filters()
        rows = filter_library(self._lib, search=search, key=key,
                              bpm_lo=lo, bpm_hi=hi)
        by_id = {a.track.track_id: a for a in self._lib}
        favs, _ = resolve_tracks(self._user_state["ulubione_utwory"], by_id)
        filary, _ = resolve_tracks(self._user_state["filary"], by_id)
        favs, filary = set(favs), set(filary)
        col, rev = self._lib_sort if self._lib_sort is not None else (2, False)
        znane = [a for a in rows if not _lib_sort_missing(col, a, self._lib_energy)]
        braki = [a for a in rows if _lib_sort_missing(col, a, self._lib_energy)]
        znane.sort(key=_lib_sort_key(col, favs, filary, self._lib_energy),
                   reverse=rev)
        rows = znane + braki                 # braki zawsze na końcu
        section = getattr(self, "_lib_section", "all")
        if section == "fav":
            rows = [a for a in rows if a.track.track_id in favs]
        elif section == "filary":
            rows = [a for a in rows if a.track.track_id in filary]
        for a in rows:
            t = a.track
            conf = t.key_confidence
            en = self._lib_energy.get(t.track_id)
            dur = t.duration_sec or 0
            table.add_row(
                "♥" if t.track_id in favs else "",
                "F" if t.track_id in filary else "",
                _bpm_cell(t), _key_cell(t),
                _conf_cell(t),
                f"{en:3d}" if en is not None else "—",
                (t.style_label or "")[:20],
                f"{dur/60:4.1f}",
                _wykonawca_tytul(t)[0][:24],
                _wykonawca_tytul(t)[1][:36],
            )
        self._lib_view = rows
        sekcja = {"fav": "♥ Ulubione", "filary": "⚑ Filary"}.get(
            section, "Cała biblioteka")
        info = (f"{sekcja}: {len(rows)} z {len(self._lib)} utworów   ·   "
                f"filary: {len(self._user_state['filary'])} (min 3, max 10)"
                f"   ·   ♥ {len(self._user_state['ulubione_utwory'])}"
                f"   ·   U=♥  F=filar  G=filary do Set  ·  "
                + (f"sort: {self._SORT_NAMES[self._lib_sort[0]]}"
                   f"{'↑' if self._lib_sort[1] else '↓'} (3. klik kasuje)"
                   if self._lib_sort is not None else "sort: klik w nagłówek"))
        if err:
            info += f"   ·   filtr BPM: {err}"
        self.query_one("#lib-count", Static).update(info)
        self._update_lib_headers(table)
        if cursor is not None and rows:
            table.move_cursor(row=min(cursor, len(rows) - 1))

    def _update_lib_headers(self, table) -> None:
        """Strzałka sortowania w SAMYM nagłówku: ↓ rosnąco, ↑ malejąco,
        brak = bez sortowania (definicja Janka)."""
        from rich.text import Text
        keys = getattr(self, "_lib_col_keys", None)
        if not keys:
            return
        for i, key in enumerate(keys):
            lbl = self._SORT_NAMES[i]
            if self._lib_sort is not None and self._lib_sort[0] == i:
                lbl += " ↑" if self._lib_sort[1] else " ↓"
            table.columns[key].label = Text(lbl)
        table.refresh()

    def action_toggle_fav(self) -> None:
        self._lib_toggle("ulubione_utwory", "♥")

    def action_toggle_filar(self) -> None:
        """F: w Bibliotece przypina/odpina filar; w zakładce Set otwiera
        TRYB FILARÓW (krok konfiguracji z wizji — wzorzec dwóch naciśnięć)."""
        if self.query_one("#tabs", TabbedContent).active == "tab-set":
            choice = self._panel_choice("pillar_mode")
            if choice is not None:
                self._apply_pillar_mode(choice)
                return
            self._close_panel()
            self._open_pillar_mode_panel()
            return
        self._lib_toggle("filary", "filar")

    def _open_pillar_mode_panel(self) -> None:
        aktualny = self._user_state.get("tryb_filarow", "rozstaw")
        options = [(label + ("   ✓" if mode == aktualny else ""), mode)
                   for mode, label in TRYBY_FILAROW]
        self._open_suggest_panel(
            None, "TRYB FILARÓW\nklik + F = wybierz · Esc = zostaw",
            options, "pillar_mode")

    def _apply_pillar_mode(self, mode: str) -> None:
        from dancelab.tui.user_store import save_state
        self._user_state["tryb_filarow"] = mode
        save_state(self._user_state)
        self._close_panel()
        dopisek = " — zastosuje się przy budowie (B)"
        self._note(f"tryb filarów: {_TRYB_LABEL.get(mode, mode)}{dopisek}")
        self.notify(f"Tryb filarów: {_TRYB_LABEL.get(mode, mode)}", timeout=4)
        self.query_one("#set", DataTable).focus()

    def _lib_toggle(self, kind: str, label: str) -> None:
        from dancelab.tui.user_store import save_state, toggle_track
        if self.query_one("#tabs", TabbedContent).active != "tab-lib":
            self._note(f"{label}: zaznacz utwór w zakładce Biblioteka")
            return
        table = self.query_one("#lib-table", DataTable)
        idx = table.cursor_row
        view = getattr(self, "_lib_view", [])
        if idx is None or not (0 <= idx < len(view)):
            self._note(f"{label}: ustaw kursor na utworze")
            return
        t = view[idx].track
        added, refuse = toggle_track(self._user_state, kind,
                                     t.track_id, t.source_path)
        if refuse:
            self.notify(refuse, severity="warning", timeout=6)
            return
        save_state(self._user_state)
        name = pathlib.Path(t.source_path).stem[:40]
        self._note(f"{label}: {'＋' if added else '－'} {name}")
        self._render_library(keep_cursor=True)
        table.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in ("lib-search", "lib-key", "lib-bpm"):
            self._render_library()

    # Cykl wg definicji Janka (06.08, zastępuje wcześniejsze "liczby od
    # największej"): klik 1 = ↓ od małego do większego, klik 2 = ↑ odwrotnie,
    # klik 3 = reset i strzałka znika.
    _SORT_NAMES = ("♥", "F", "BPM", "ton", "pew.", "energia", "gatunek",
                   "min", "wykonawca", "tytuł")

    def _cycle_sort(self, col: int) -> None:
        cur = self._lib_sort
        if cur is None or cur[0] != col:
            self._lib_sort = (col, False)    # ↓ rosnąco
        elif not cur[1]:
            self._lib_sort = (col, True)     # ↑ malejąco
        else:
            self._lib_sort = None            # trzecie kliknięcie kasuje

    def on_data_table_header_selected(self, event) -> None:
        """Klik w nagłówek Biblioteki: ↓ → ↑ → kasacja (teksty A-Z → Z-A →
        kasacja). Tabela setu celowo NIE sortuje — tam kolejność JEST treścią."""
        if getattr(event.data_table, "id", None) != "lib-table":
            return
        self._cycle_sort(event.column_index)
        self._render_library(keep_cursor=True)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "go":
            self.action_build()          # przycisk robi to samo co B —
        elif event.button.id == "lib-analyze":   # wcześniej był atrapą
            self._lib_analyze_worker()
        elif event.button.id == "lib-build":
            self.action_build_from_filary()
        elif event.button.id == "cmp-play":
            self._graj_z_panelu()

    def _graj_z_panelu(self) -> None:
        if self._stop_player():
            return
        if self._compare_idx is None or self._compare_idx + 1 >= len(self._order):
            self._note("panel nie trzyma pary — otwórz porównanie (C)")
            return
        self._seam_worker(self._compare_idx)

    def action_build_from_filary(self) -> None:
        """G / przycisk w Bibliotece: filary → zakładka Set jako SZKIC.

        CELOWO BEZ automatycznej budowy (Janek 05.08: „przez to omijamy całą
        sekcję briefu") — filary lądują w tabelce podświetlone na złoto,
        użytkownik uzupełnia formularz i dopiero B buduje wokół nich."""
        from dancelab.core.config import load_config, load_weights
        from dancelab.tui.user_store import MIN_FILARY, resolve_tracks
        n = len(self._user_state["filary"])
        if n < MIN_FILARY:
            self.notify(f"do budowy z filarów trzeba minimum {MIN_FILARY} "
                        f"(masz {n}) — klawisz F w Bibliotece zaznacza",
                        severity="warning", timeout=6)
            return
        if not self._lib:
            self.notify("Biblioteka jeszcze się ładuje — chwila", timeout=4)
            return
        by_id = {a.track.track_id: a for a in self._lib}
        ids, missing = resolve_tracks(self._user_state["filary"], by_id)
        for m in missing:
            self._note(f"FILAR nieobecny w puli (pominięty): {m}")
        if len(ids) < MIN_FILARY:
            self.notify(f"po dopasowaniu do puli zostało {len(ids)} filarów "
                        f"(minimum {MIN_FILARY}) — szczegóły pod L",
                        severity="warning", timeout=6)
            return
        try:
            p = self._params()
        except ValueError as exc:
            self.notify(f"popraw formularz: {exc}", severity="warning", timeout=6)
            return
        cfg = load_config("configs/default.yaml")
        self._ctx = dict(by_id=by_id, weights=load_weights(cfg.weights_file),
                         arc=p["arc"], planner=p["planner"],
                         bpm_min=p["bpm_min"], bpm_max=p["bpm_max"],
                         anchor=None, params=p, filary=list(ids))
        self._order = list(ids)
        self._engine_order = []
        self._edits = []
        self._mean_score = None
        self._plan_name = "TUI filary"
        self.query_one("#tabs", TabbedContent).active = "tab-set"
        self._render_order(by_id)
        self.query_one("#progress", Static).update(
            f"SZKIC: {len(ids)} filarów (⚑ złote) — wybierz tryb (F), "
            f"uzupełnij brief po lewej i naciśnij B")
        self._note(f"filary wstawione jako szkic: {len(ids)} — budowa po B")
        # krok konfiguracji z wizji: panel trybów otwiera się sam po G
        self._open_pillar_mode_panel()

    @work(thread=True, exclusive=True, group="lib")
    def _lib_analyze_worker(self) -> None:
        """Onboarding: folder → analiza z postępem → Biblioteka od nowa."""
        from dancelab.core.config import load_config
        from dancelab.workflows.smart_playlist import (
            analyze_files, discover_audio_files)
        ui = self.call_from_thread
        folder = self.query_one("#lib-folder", Input).value.strip()
        count = self.query_one("#lib-count", Static)
        if not folder:
            ui(self._note, "podaj ścieżkę folderu do analizy")
            return
        try:
            files = discover_audio_files(folder)
            if not files:
                ui(self._note, f"brak plików audio w: {folder}")
                return
            ui(count.update, f"Analiza {len(files)} plików…")
            self._stop.clear()
            _, failures = analyze_files(
                files, load_config("configs/default.yaml"),
                processed_dir=self.processed_dir,
                stage_progress=lambda path, stage: ui(
                    count.update,
                    f"{stage}: {pathlib.Path(path).name[:48]}"),
                should_stop=self._stop.is_set,
            )
            for f in failures[:5]:
                ui(self._note, f"nie przeanalizowano "
                               f"{pathlib.Path(f.source_path).name}: {f.error}")
            analyses, notes = self._library_analyses()
            for note in notes:
                ui(self._note, note)
            ui(self._set_library, analyses)
            self.call_from_thread(
                self.notify, f"✅ analiza skończona — w puli {len(analyses)}")
        except Exception as exc:  # noqa: BLE001
            ui(self._note, f"analiza nie wyszła: {exc}")
            self.call_from_thread(self.notify, f"analiza nie wyszła: {exc}",
                                  severity="error", timeout=8)

    def _load_anchors(self) -> None:
        try:
            from dancelab.decision.anchors import list_anchors
            options = [(f"{name}  ({n} wekt., skok {med})", name)
                       for name, n, med in list_anchors(limit=500)]
            self.query_one("#dj", Select).set_options(options)
        except Exception as exc:  # noqa: BLE001 — brak pliku kotwic to stan, nie awaria
            self._note(f"kotwice niedostępne: {exc}")

    def _refresh_status(self) -> None:
        from dancelab.ingestion.playlist_publish import BACKUP_DIR, rekordbox_running
        rb = "⛔ Rekordbox OTWARTY — zapis W zablokowany" if rekordbox_running() \
            else "✅ Rekordbox zamknięty — W dostępne"
        n_bak = len(list(BACKUP_DIR.glob("*.db"))) if BACKUP_DIR.exists() else 0
        self.query_one("#status", Static).update(
            f"{rb}   ·   backupy: {n_bak}   ·   notki: {self._n_notes} (L)"
            + ("   ·   ▶ AUTO-podgląd" if self._auto_podglad else "")
            + f"   ·   pula: {self.processed_dir}")

    def _note(self, line: str) -> None:
        from dancelab.tui.po_polsku import po_polsku
        self.query_one("#warnings", Log).write_line(f"· {po_polsku(line)}")
        self._n_notes += 1
        self._refresh_status()

    def action_toggle_notes(self) -> None:
        self.query_one("#warnings", Log).toggle_class("open")

    # ------------------------------------------------------------- budowa

    def action_build(self) -> None:
        self.query_one("#warnings", Log).clear()
        self._n_notes = 0
        self.query_one("#set", DataTable).clear()
        self._row_cells = []
        self._stop.clear()
        self._build_worker()

    @work(thread=True, exclusive=True)
    def _build_worker(self) -> None:
        ui = self.call_from_thread
        try:
            plan, by_id, warnings = self._build_plan()
        except Exception as exc:  # noqa: BLE001 — pokazujemy powód, nie traceback
            from dancelab.tui.po_polsku import po_polsku
            powod = po_polsku(str(exc))
            ui(self._note, f"ODMOWA: {powod}")
            ui(self.query_one("#progress", Static).update,
               "Nie zbudowano — powód pod L.")
            self.call_from_thread(self.notify, f"ODMOWA: {powod}",
                                  severity="error", timeout=8)
            return
        ui(self._show_plan, plan, by_id, warnings)

    def _params(self) -> dict:
        get = lambda i, t: self.query_one(i, t)  # noqa: E731
        lo, hi, err = _parse_bpm(get("#bpm", Input).value)
        if err:
            raise ValueError(err)
        minutes = float(get("#minutes", Input).value or 90)
        # puste „Graj jak…" to NoSelection, NIE zawsze identyczne z Select.BLANK
        # (złapane 05.08: budowa bez kotwicy padała na ODMOWIE) — bierzemy tylko str
        dj = get("#dj", Select).value
        seed_txt = get("#seed", Input).value.strip()
        if seed_txt and not seed_txt.lstrip("-").isdigit():
            raise ValueError(f"seed to liczba całkowita, dostałem {seed_txt!r}")
        novelty = get("#novelty", Select).value
        if not isinstance(novelty, str) or not novelty:
            novelty = "deterministic"
        seed = int(seed_txt) if seed_txt else None
        if novelty != "deterministic" and seed is None:
            import random
            seed = random.randint(1, 999_999)   # pokazywany w notce — do powtórki
        return dict(
            pool=get("#pool", Select).value,
            folder=get("#folder", Input).value.strip(),
            novelty=novelty, seed=seed,
            minutes=minutes, bpm_min=lo, bpm_max=hi,
            styles=[s.strip() for s in get("#styles", Input).value.split(",") if s.strip()],
            dj=dj if isinstance(dj, str) and dj else None,
            contour=get("#contour", Switch).value,
            arc=get("#arc", Select).value,
            tempo=get("#tempo", Select).value,
            planner=get("#planner", Select).value,
        )

    def _library_analyses(self):
        """Pula z cache analiz + higiena (stemy, >15 min, brakujące pliki)."""
        from dancelab.storage.repositories import FileAnalysisRepository
        repo = FileAnalysisRepository(self.processed_dir)
        analyses = [repo.get(t) for t in repo.list_track_ids()]
        before = len(analyses)
        analyses = [a for a in analyses
                    if pathlib.Path(a.track.source_path).exists()
                    and pathlib.Path(a.track.source_path).stem.strip().lower()
                    not in STEM_NAMES
                    and (a.track.duration_sec or 0) <= MAX_TRACK_SEC]
        notes = []
        if before - len(analyses):
            notes.append(f"higiena puli: odrzucone {before - len(analyses)} "
                         f"(stemy / pliki >15 min / brak pliku)")
        return analyses, notes

    def _build_plan(self):
        from dancelab.core.config import load_config, load_weights
        from dancelab.decision.set_builder import build_set
        from dancelab.ingestion.analysis_enrichment import (
            attach_rekordbox_genres, attach_rekordbox_keys,
            attach_rekordbox_meta, attach_sound_embeddings)
        from dancelab.workflows.smart_playlist import (
            analyze_files, discover_audio_files, estimate_track_count_for_duration)

        p = self.call_from_thread(self._params)
        ui = self.call_from_thread
        progress = self.query_one("#progress", Static)
        cfg = load_config("configs/default.yaml")

        if p["pool"] == "folder":
            if not p["folder"]:
                raise ValueError("tryb Folder wymaga ścieżki")
            files = discover_audio_files(p["folder"])
            ui(progress.update, f"Analiza {len(files)} plików…")
            analyses, failures = analyze_files(
                files, cfg, processed_dir=self.processed_dir,
                stage_progress=lambda path, stage: ui(
                    progress.update,
                    f"{stage}: {pathlib.Path(path).name[:40]}"),
                should_stop=self._stop.is_set,
            )
            for f in failures[:5]:
                ui(self._note, f"nie przeanalizowano {pathlib.Path(f.source_path).name}: {f.error}")
        else:
            ui(progress.update, "Wczytuję analizy z biblioteki…")
            analyses, hygiene = self._library_analyses()
            for note in hygiene:
                ui(self._note, note)
        if self._stop.is_set():
            raise ValueError("anulowane")
        if not analyses:
            raise ValueError("pusta pula — nie ma z czego budować")

        ui(progress.update, "Dokarmianie (wektory, gatunki)…")
        emb = attach_sound_embeddings(analyses)
        gen = attach_rekordbox_genres(analyses)
        ton = attach_rekordbox_keys(analyses)
        attach_rekordbox_meta(analyses)

        anchor = None
        if p["dj"]:
            from dancelab.decision.anchors import resolve_anchor
            anchor = resolve_anchor(p["dj"])

        count = estimate_track_count_for_duration(analyses, p["minutes"])
        filary, filar_notes = _filary_for_build(
            self._user_state, {a.track.track_id: a for a in analyses},
            p["bpm_min"], p["bpm_max"], count)
        # filar może wskazywać duplikat bajt-w-bajt, który dedup wytnie —
        # mapujemy na egzemplarz kanoniczny, żeby budowa nie odmawiała
        # o utwór, który muzycznie w puli JEST (złapane E2E 05.08)
        from dancelab.decision.dedup import canonical_ids
        mapping = canonical_ids(analyses)
        filary = list(dict.fromkeys(mapping.get(t, t) for t in filary))
        by_id_all = {a.track.track_id: a for a in analyses}
        tryb = self._user_state.get("tryb_filarow", "rozstaw")

        from dancelab.decision.history import (HistoryStore, context_hash,
                                               fingerprint_plan)
        historia = HistoryStore(HISTORIA_SETOW).recent(limit=20)
        wspolne = dict(
            novelty_mode=p["novelty"], seed=p["seed"], history=historia,
            arc=p["arc"], planner_mode=p["planner"], tempo_shape=p["tempo"],
            preferred_styles=p["styles"] or None,
            bpm_min=p["bpm_min"], bpm_max=p["bpm_max"],
            sound_anchor=anchor.centroid if anchor else None,
            anchor_name=anchor.name if anchor else None,
            jump_contour=(anchor.contour if (anchor and p["contour"]) else None),
        )
        weights = load_weights(cfg.weights_file)

        if filary and tryb == "podpory" and (count - len(filary)) - 1 < len(filary):
            filar_notes.append("za krótki set na tryb Podpory — spadam na "
                               "równy rozstaw")
            tryb = "rozstaw"

        if filary and tryb == "podpory":
            # metafora dosłownie: konstrukcja bez filarów → pomiar przęseł →
            # filar w najsłabsze; plan tempa/łuk kształtują KONSTRUKCJĘ,
            # podpory wchodzą po pomiarze
            core_pool = [a for a in analyses
                         if a.track.track_id not in set(filary)]
            ui(progress.update, f"Budowa konstrukcji: {count - len(filary)} "
                                f"utworów, potem {len(filary)} podpór…")
            plan = build_set(core_pool, weights,
                             target_track_count=count - len(filary), **wspolne)
            from dancelab.decision.slot_suggest import _default_score_fn
            energy, e_rng = _energia_do_oceny(by_id_all)
            fn = _default_score_fn(weights, p["arc"], p["planner"],
                                   energy, e_rng)
            score = lambda x, y: fn(by_id_all[x], by_id_all[y])  # noqa: E731
            final, podpory_notes = _wstaw_podpory(
                list(plan.track_order), filary, score)
            filar_notes.extend(podpory_notes)
            filar_notes.append(f"zgodność konstrukcji (bez podpór): "
                               f"{plan.mean_transition_score}")
            # zgodność CAŁOŚCI nie jest tą samą liczbą co z budowy — nie udajemy
            plan = plan.model_copy(update={"track_order": final,
                                           "mean_transition_score": None})
        else:
            rozstaw = _rozstaw_filary(filary, by_id_all, count, tryb) \
                if filary else {}
            if rozstaw:
                filar_notes.append(
                    f"filary rozstawione ({_TRYB_LABEL.get(tryb, tryb)}): "
                    + ", ".join(f"#{pos}" for pos in sorted(rozstaw)))
            ui(progress.update,
               f"Budowa: {count} utworów z {len(analyses)}"
               + (f" na {len(filary)} filarach…" if filary else "…"))
            plan = build_set(analyses, weights, target_track_count=count,
                             locked_positions=rozstaw or None, **wspolne)
        # Odcisk czeka w kontekście — do historii trafia dopiero przy S/W.
        # Powód (zmierzony 06.08): dopisywanie przy każdym B zmieniało historię
        # między budowami i TEN SAM seed dawał inny set — obietnica powtórki
        # złamana. Świeżość ma omijać sety UŻYTE, nie każdy eksperymentalny B.
        odcisk = fingerprint_plan(
            list(plan.track_order),
            ctx_hash=context_hash(bpm_min=p["bpm_min"], bpm_max=p["bpm_max"],
                                  styles=tuple(p["styles"]), dj=p["dj"],
                                  arc=p["arc"], tempo=p["tempo"],
                                  planner=p["planner"]),
            seed=p["seed"], novelty_mode=p["novelty"], pinned_ids=filary)
        if p["novelty"] != "deterministic":
            filar_notes.append(
                f"świeżość: {p['novelty']} · seed {p['seed']} — ten sam seed "
                f"powtarza ten set; historię świeżości karmią dopiero "
                f"zapis (S) i wysyłka (W)")
        by_id = {a.track.track_id: a for a in analyses}
        self._ctx = dict(
            by_id=by_id, weights=weights,
            arc=p["arc"], planner=p["planner"],
            bpm_min=p["bpm_min"], bpm_max=p["bpm_max"],
            anchor=(anchor.centroid if anchor else None),
            params=p,
            filary=filary,   # już po mapowaniu na egzemplarze kanoniczne —
            odcisk=odcisk,   # flagi ⚑ muszą trafiać w to, co GRA; odcisk
        )                    # do historii dopiero przy S/W
        notes = [*emb.notes, *gen.notes, *ton.notes, *filar_notes,
                 f"dokarmione: wektory {emb.attached}, gatunki {gen.attached}, "
                 f"tonacje RB {ton.attached}"]
        self._plan_name = (f"TUI {p['dj'] or 'set'} "
                           f"{p['bpm_min']:g}-{p['bpm_max']:g}" if p["bpm_min"]
                           else f"TUI {p['dj'] or 'set'}")
        return plan, by_id, notes

    def _show_plan(self, plan, by_id, extra_notes) -> None:
        self._odcisk_zapisany = False
        self._order = list(plan.track_order)
        self._engine_order = list(plan.track_order)   # pierwotny plan — do werdyktu V
        self._edits = []
        self._mean_score = plan.mean_transition_score
        self._render_order(by_id)
        for note in [*plan.warnings, *extra_notes]:
            self._note(note)

    def _render_order(self, by_id) -> None:
        from rich.text import Text
        from dancelab.tui.user_store import resolve_tracks
        table = self.query_one("#set", DataTable)
        table.clear()
        total = 0.0
        self._plan_paths = []
        self._row_cells = []
        # flagi z kontekstu budowy (id już po mapowaniu duplikatów);
        # bez kontekstu (świeży szkic/wczytany plan) — ze stanu użytkownika
        filary = set(self._ctx.get("filary") or
                     resolve_tracks(self._user_state.get("filary", []),
                                    by_id)[0])
        for i, tid in enumerate(self._order, 1):
            t = by_id[tid].track
            total += t.duration_sec or 0
            conf = t.key_confidence
            name = pathlib.Path(t.source_path).stem[:46]
            is_filar = tid in filary
            nr = f"⚑{i}" if is_filar else str(i)
            base = PILLAR_COLOR if is_filar else None
            table.add_row(
                Text(nr, style=f"bold {base}") if base else nr,
                _bpm_cell(t), _key_cell(t),
                _conf_cell(t),
                (t.style_label or "")[:22], f"{total/60:5.1f}",
                Text(name, style=base) if base else name,
            )
            self._plan_paths.append(t.source_path)
            self._row_cells.append((nr, name, base))
        n = len(self._order)
        score = self._mean_score if self._mean_score is not None else "—"
        par = self._ctx.get("params", {}) if self._ctx else {}
        seed_txt = (f" · {par.get('novelty')} seed {par.get('seed')}"
                    if par.get("novelty") not in (None, "deterministic") else "")
        self.query_one("#progress", Static).update(
            f"SET: {n} utworów · {total/60:.0f} min pełnych "
            f"(~{max(0,(total-75*(n-1)))/60:.0f} min przy blendach 75 s) "
            f"· zgodność {score}{seed_txt}")

    # ------------------------------------------------------------- zapis

    def action_write(self) -> None:
        if not self._plan_paths:
            self._note("najpierw zbuduj set (B)")
            return
        self._write_worker()

    # Panel po prawej gra w trzech trybach tym samym wzorcem dwóch naciśnięć
    # (klik/strzałki = wybierz, ten sam klawisz = potwierdź, Esc = zostaw):
    # Z podmienia, A dopisza, O wczytuje plan.

    def _panel_choice(self, mode: str) -> str | None:
        """Podświetlony wybór, jeśli panel otwarty w danym trybie."""
        panel = self.query_one("#suggest")
        lst = self.query_one("#suggest-list", OptionList)
        if panel.has_class("open") and self._panel_mode == mode \
                and lst.highlighted is not None:
            return lst.get_option_at_index(lst.highlighted).id
        return None

    def _close_panel(self) -> None:
        self.query_one("#suggest").remove_class("open")
        self._suggest_slot = None
        self._panel_mode = None

    def _cursor_row(self, po_co: str) -> int | None:
        idx = self.query_one("#set", DataTable).cursor_row
        if not self._order or not self._ctx:
            self._note("najpierw zbuduj set (B) albo wczytaj plan (O)")
            return None
        if idx is None or not (0 <= idx < len(self._order)):
            self._note(f"ustaw kursor na utworze — {po_co}")
            return None
        return idx

    def action_replace(self) -> None:
        choice = self._panel_choice("suggest")
        if choice is not None and self._suggest_slot is not None:
            self._apply_swap(self._suggest_slot, choice)
            return
        self._close_panel()
        idx = self._cursor_row("podmiana")
        if idx is not None:
            self._suggest_worker(idx, "suggest")

    def action_add(self) -> None:
        choice = self._panel_choice("insert")
        if choice is not None and self._suggest_slot is not None:
            self._apply_insert(self._suggest_slot, choice)
            return
        self._close_panel()
        idx = self._cursor_row("dopisuję ZA zaznaczonym")
        if idx is not None:
            self._suggest_worker(idx, "insert")

    def action_cut(self) -> None:
        if self._panel_mode == "plans":
            self._usun_plan()
            return
        self._close_panel()
        idx = self._cursor_row("cięcie")
        if idx is None:
            return
        by_id = self._ctx["by_id"]
        tid = self._order.pop(idx)
        path = by_id[tid].track.source_path
        odpiety = self._odepnij_filar(tid, path)
        self._log_verdict("ciecie", pozycja=idx + 1, out=path, filar=odpiety)
        self._render_order(by_id)
        nazwa = pathlib.Path(path).stem[:40]
        if odpiety:
            self._note(f"CIĘCIE #{idx+1}: {nazwa} — FILAR ODPIĘTY "
                       f"(F w Bibliotece przypina z powrotem)")
        else:
            self._note(f"CIĘCIE #{idx+1}: {nazwa} (werdykt zapisany)")
        table = self.query_one("#set", DataTable)
        if self._order:
            table.move_cursor(row=min(idx, len(self._order) - 1))
        table.focus()

    def _odepnij_filar(self, tid: str, path: str) -> bool:
        """Wycięcie filaru zdejmuje pin (decyzja Janka 05.08: „wyciąłem,
        a on wraca przy następnej budowie" to najgorsze zaskoczenie).
        Filar-duplikat: wpis w stanie może wskazywać bliźniaka bajt-w-bajt —
        dopasowujemy też przez mapę kanoniczną (cache skrótów ciepły po budowie)."""
        entries = self._user_state.get("filary", [])
        if not entries:
            return False
        by_id = self._ctx["by_id"]
        trafiony = None
        for j, e in enumerate(entries):
            if e.get("track_id") == tid or e.get("path") == path:
                trafiony = j
                break
        if trafiony is None and tid in set(self._ctx.get("filary") or []):
            from dancelab.decision.dedup import canonical_ids
            from dancelab.tui.user_store import resolve_tracks
            mapping = canonical_ids(list(by_id.values()))
            for j, e in enumerate(entries):
                ids, _ = resolve_tracks([e], by_id)
                if ids and mapping.get(ids[0], ids[0]) == tid:
                    trafiony = j
                    break
        if trafiony is None:
            return False
        entries.pop(trafiony)
        from dancelab.tui.user_store import save_state
        save_state(self._user_state)
        if self._lib:
            self._render_library(keep_cursor=True)
        return True

    def action_move_up(self) -> None:
        self._move(-1)

    def action_move_down(self) -> None:
        self._move(+1)

    def _move(self, delta: int) -> None:
        self._close_panel()
        idx = self._cursor_row("przesuwanie")
        if idx is None:
            return
        j = idx + delta
        if not (0 <= j < len(self._order)):
            return                                   # brzeg setu — nie ma dokąd
        self._order[idx], self._order[j] = self._order[j], self._order[idx]
        by_id = self._ctx["by_id"]
        self._log_verdict("przesuniecie", z=idx + 1, na=j + 1,
                          utwor=by_id[self._order[j]].track.source_path)
        self._render_order(by_id)
        table = self.query_one("#set", DataTable)
        table.move_cursor(row=j)
        table.focus()

    def action_cancel(self) -> None:
        if self.query_one("#suggest").has_class("open"):
            self._close_panel()
            self.query_one("#set", DataTable).focus()
            return
        if self.query_one("#compare").has_class("open"):
            self.query_one("#compare").remove_class("open")
            self.query_one("#set", DataTable).focus()
            return
        if self._stop_player():
            return
        self._stop.set()
        self._note("anulowanie — dokończę bieżący utwór i stanę (cache zostaje)")

    @work(thread=True, exclusive=True)
    def _suggest_worker(self, idx: int, mode: str) -> None:
        from dancelab.decision.slot_suggest import (
            suggest_for_insertion, suggest_for_slot)
        ui = self.call_from_thread
        ctx = self._ctx
        by_id = ctx["by_id"]
        energy, e_rng = _energia_do_oceny(by_id)
        fn = suggest_for_slot if mode == "suggest" else suggest_for_insertion
        score_mode = self.query_one("#suggest-mode", Select).value
        planner, anchor = _mode_params(score_mode, ctx)
        try:
            sugg = fn(by_id, self._order, idx, k=10,
                      weights=ctx["weights"], arc=ctx["arc"],
                      planner_mode=planner, energy=energy,
                      energy_range=e_rng,
                      bpm_min=ctx["bpm_min"], bpm_max=ctx["bpm_max"],
                      anchor=anchor)
        except Exception as exc:  # noqa: BLE001
            ui(self._note, f"sugestie nie wyszły: {exc}")
            return
        if not sugg:
            ui(self._note, "brak kandydatów do tej szczeliny (okno tempa? pula?)")
            return
        here = pathlib.Path(by_id[self._order[idx]].track.source_path).stem[:40]
        options = []
        for sg in sugg:
            t = by_id[sg.track_id].track
            options.append((
                f"{sg.score:.2f} {t.bpm_estimate or 0:5.1f} "
                f"{str(t.key_estimate or '?'):>3} "
                f"{pathlib.Path(t.source_path).stem[:30]}",
                sg.track_id))
        mode_label = {"bpm": "BPM najpierw", "harmonic": "tonacja najpierw"} \
            .get(score_mode, "smart")
        if mode == "suggest":
            title = (f"#{idx+1} {here}\n"
                     f"[{mode_label}] klik + Z = zamień · Esc = zostaw")
        else:
            title = (f"DOPISZ za #{idx+1} {here}\n"
                     f"[{mode_label}] klik + A = dopisz · Esc = zostaw")
        ui(self._open_suggest_panel, idx, title, options, mode)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Zmiana trybu oceny przy otwartym panelu → przelicz sugestie na żywo."""
        if getattr(event.select, "id", None) != "suggest-mode":
            return
        if self._panel_mode in ("suggest", "insert") \
                and self._suggest_slot is not None:
            self._suggest_worker(self._suggest_slot, self._panel_mode)

    def _open_suggest_panel(self, idx: int | None, title: str,
                            options: list[tuple[str, str]], mode: str) -> None:
        self._suggest_slot = idx
        self._panel_mode = mode
        self.query_one("#suggest-mode", Select).set_class(
            mode not in ("suggest", "insert"), "hide")
        self.query_one("#suggest-list", OptionList).remove_class("hide")
        self.query_one("#suggest-info", Static).remove_class("show")
        self.query_one("#suggest-title", Label).update(title)
        lst = self.query_one("#suggest-list", OptionList)
        lst.clear_options()
        for label, oid in options:
            lst.add_option(Option(label, id=oid))
        self.query_one("#suggest").add_class("open")
        lst.highlighted = 0
        lst.focus()

    def _apply_swap(self, idx: int, choice: str) -> None:
        by_id = self._ctx["by_id"]
        old_id = self._order[idx]
        self._order[idx] = choice
        self._render_order(by_id)
        old_n = pathlib.Path(by_id[old_id].track.source_path).stem[:40]
        new_n = pathlib.Path(by_id[choice].track.source_path).stem[:40]
        self._note(f"PODMIANA #{idx+1}: {old_n} → {new_n} (werdykt zapisany)")
        self._log_verdict("podmiana", pozycja=idx + 1,
                          **{"out": by_id[old_id].track.source_path,
                             "in": by_id[choice].track.source_path})
        self._close_panel()
        table = self.query_one("#set", DataTable)
        table.move_cursor(row=idx)
        table.focus()

    def _apply_insert(self, after_idx: int, choice: str) -> None:
        by_id = self._ctx["by_id"]
        self._order.insert(after_idx + 1, choice)
        self._render_order(by_id)
        path = by_id[choice].track.source_path
        self._note(f"DOPISANE #{after_idx+2}: {pathlib.Path(path).stem[:40]} "
                   f"(werdykt zapisany)")
        self._log_verdict("dopisanie", pozycja=after_idx + 2, **{"in": path})
        self._close_panel()
        table = self.query_one("#set", DataTable)
        table.move_cursor(row=after_idx + 1)
        table.focus()

    def _log_verdict(self, typ: str, **fields) -> None:
        """Każda ręczna edycja to werdykt DJ-a — dopisujemy, nie gubimy."""
        import json
        import time
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "typ": typ, **fields}
        self._edits.append(rec)
        WERDYKTY_DIR.mkdir(parents=True, exist_ok=True)
        with (WERDYKTY_DIR / "tui_edycje.jsonl").open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _usun_plan(self) -> None:
        """X na liście planów: usunięcie MIĘKKIE (do kosza obok planów),
        lista odświeża się od razu."""
        from dancelab.tui.plan_store import delete_plan
        choice = self._panel_choice("plans")
        if choice is None:
            self._note("zaznacz plan do usunięcia")
            return
        try:
            cel = delete_plan(choice)
        except Exception as exc:  # noqa: BLE001
            self._note(f"nie usunąłem planu: {exc}")
            return
        self._note(f"plan przeniesiony do kosza: {pathlib.Path(cel).name}")
        self._close_panel()
        self.action_load_plan()          # świeża lista

    def _utrwal_odcisk(self, powod: str) -> None:
        """Dopisz odcisk zbudowanego setu do historii świeżości — raz na
        budowę, przy pierwszym użyciu (S albo W)."""
        odcisk = (self._ctx or {}).get("odcisk")
        if odcisk is None or getattr(self, "_odcisk_zapisany", False):
            return
        from dancelab.decision.history import HistoryStore
        try:
            HistoryStore(HISTORIA_SETOW).append(odcisk)
        except Exception as exc:  # noqa: BLE001 — historia to dodatek
            self._note(f"historii setu nie zapisałem: {exc}")
            return
        self._odcisk_zapisany = True
        self._note(f"historia świeżości: odcisk dopisany ({powod})")

    # ------------------------------------------------- plan: zapis / wczytanie

    def action_save_plan(self) -> None:
        if not self._order or not self._ctx:
            self._note("najpierw zbuduj set (B) albo wczytaj plan (O)")
            return

        def _po_nazwie(nazwa) -> None:
            if not nazwa:
                self._note("zapis planu anulowany")
                return
            from dancelab.tui.plan_store import save_plan
            self._plan_name = nazwa
            path = save_plan(self._order, self._ctx["by_id"], name=nazwa,
                             params=self._ctx.get("params", {}),
                             engine_order=self._engine_order,
                             edits=self._edits)
            self._note(f"plan zapisany: {nazwa} → {path}")
            self._utrwal_odcisk("zapisany plan")

        self.push_screen(NazwaPlanuScreen(self._plan_name or "plan"),
                         _po_nazwie)

    def action_load_plan(self) -> None:
        choice = self._panel_choice("plans")
        if choice is not None:
            self._close_panel()
            self._load_plan_worker(choice)
            return
        self._close_panel()
        from dancelab.tui.plan_store import list_plans
        plans = list_plans()
        if not plans:
            self._note("brak zapisanych planów (S zapisuje bieżący)")
            return
        def etykieta(p):
            dod = " · ".join(x for x in (p.get("bpm"), p.get("dj")) if x)
            return (f"{p['nazwa'][:24]}\n  {p['n']:2d} utw"
                    + (f" · {dod}" if dod else "")
                    + f" · {p['zapisano'][5:16]}")
        options = [(etykieta(p), p["path"]) for p in plans[:30]]
        if len(plans) > 30:
            self._note(f"planów jest {len(plans)} — pokazuję 30 najnowszych")
        self._open_suggest_panel(
            None, "WCZYTAJ PLAN\nklik + O = wczytaj · X = usuń · Esc = zostaw",
            options, "plans")

    @work(thread=True, exclusive=True)
    def _load_plan_worker(self, path: str) -> None:
        from dancelab.tui.plan_store import match_order, read_plan
        ui = self.call_from_thread
        try:
            rec = read_plan(path)
            if not self._ctx:
                self._ctx = self._pool_ctx_for(rec.get("parametry", {}))
            order, notes = match_order(rec, self._ctx["by_id"])
        except Exception as exc:  # noqa: BLE001 — powód, nie traceback
            ui(self._note, f"wczytanie nie wyszło: {exc}")
            return
        if not order:
            ui(self._note, "w planie nie został żaden utwór obecny w puli — nie wczytuję")
            return
        ui(self._after_plan_load, rec, order, notes)

    def _pool_ctx_for(self, params: dict) -> dict:
        """Kontekst oceniania dla wczytanego planu, gdy nic nie zbudowano:
        pula z biblioteki + dokarmienie + parametry zapisane w planie —
        dzięki temu Z/A po samym O oceniają tak, jak oceniała budowa."""
        from dancelab.core.config import load_config, load_weights
        from dancelab.ingestion.analysis_enrichment import (
            attach_rekordbox_genres, attach_rekordbox_keys,
            attach_sound_embeddings)
        ui = self.call_from_thread
        ui(self.query_one("#progress", Static).update,
           "Wczytuję pulę z biblioteki pod plan…")
        analyses, hygiene = self._library_analyses()
        for note in hygiene:
            ui(self._note, note)
        if not analyses:
            raise ValueError("pusta pula — nie mam do czego dopasować planu")
        attach_sound_embeddings(analyses)
        attach_rekordbox_genres(analyses)
        attach_rekordbox_keys(analyses)
        attach_rekordbox_meta(analyses)
        anchor = None
        if params.get("dj"):
            from dancelab.decision.anchors import resolve_anchor
            anchor = resolve_anchor(params["dj"])
        cfg = load_config("configs/default.yaml")
        return dict(
            by_id={a.track.track_id: a for a in analyses},
            weights=load_weights(cfg.weights_file),
            arc=params.get("arc", "build"), planner=params.get("planner", "smart"),
            bpm_min=params.get("bpm_min"), bpm_max=params.get("bpm_max"),
            anchor=(anchor.centroid if anchor else None),
            params=params,
        )

    def _after_plan_load(self, rec: dict, order: list[str],
                         notes: list[str]) -> None:
        self._order = order
        self._engine_order = list(rec.get("plan_silnika", []))
        self._edits = list(rec.get("edycje", []))
        self._plan_name = rec.get("nazwa") or "TUI plan"
        self._mean_score = None      # po edycjach nie udajemy zgodności z budowy
        self._set_form(rec.get("parametry", {}))
        self._render_order(self._ctx["by_id"])
        for note in notes:
            self._note(note)
        self._note(f"plan wczytany: {self._plan_name} ({len(order)} utworów, "
                   f"zapisany {rec.get('zapisano', '?')})")
        self.query_one("#set", DataTable).focus()

    def _set_form(self, p: dict) -> None:
        """Przywróć formularz z planu — żeby ponowna budowa była odtwarzalna.
        Pojedyncze pole może nie wejść (np. kotwica zniknęła z pliku) —
        wtedy notka, nie wywrotka."""
        try:
            if p.get("minutes"):
                self.query_one("#minutes", Input).value = f"{p['minutes']:g}"
            if p.get("bpm_min") is not None and p.get("bpm_max") is not None:
                self.query_one("#bpm", Input).value = \
                    f"{p['bpm_min']:g}-{p['bpm_max']:g}"
            self.query_one("#styles", Input).value = ", ".join(p.get("styles", []))
            for wid, key in (("#arc", "arc"), ("#tempo", "tempo"),
                             ("#planner", "planner")):
                if p.get(key):
                    self.query_one(wid, Select).value = p[key]
            if p.get("dj"):
                self.query_one("#dj", Select).value = p["dj"]
            self.query_one("#contour", Switch).value = bool(p.get("contour"))
            if p.get("novelty"):
                self.query_one("#novelty", Select).value = p["novelty"]
            self.query_one("#seed", Input).value = \
                str(p["seed"]) if p.get("seed") is not None else ""
        except Exception as exc:  # noqa: BLE001
            self._note(f"formularza nie dało się w pełni przywrócić: {exc}")

    # ------------------------------------------------------------- werdykt V

    def action_verdict(self) -> None:
        """Świadomy zrzut: plan silnika vs stan po Twoich edycjach."""
        if not self._order or not self._ctx:
            self._note("najpierw zbuduj set (B) albo wczytaj plan (O)")
            return
        import json
        import time
        by_id = self._ctx["by_id"]

        def rows(ids):
            return [{"track_id": t, "path": by_id[t].track.source_path}
                    for t in ids if t in by_id]
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "nazwa": self._plan_name,
               "parametry": self._ctx.get("params", {}),
               "plan_silnika": rows(self._engine_order),
               "stan_dja": rows(self._order),
               "edycje": self._edits}
        WERDYKTY_DIR.mkdir(parents=True, exist_ok=True)
        path = WERDYKTY_DIR / f"tui_werdykt_{time.strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        self._note(f"WERDYKT: plan {len(self._engine_order)} utworów vs "
                   f"Twoje {len(self._order)}, edycji {len(self._edits)} "
                   f"→ {path.name}")

    # ---------------------------------------------------- odsłuch szwu (P)

    def _stop_player(self) -> bool:
        if self._odtwarzacz.stop():
            self._note("odsłuch: pauza (P na tym samym utworze wznawia)")
            return True
        return False

    def on_unmount(self) -> None:
        # dźwięk nie może przeżyć aplikacji
        self._odtwarzacz.stop()

    def _biezacy_track(self):
        """Utwór pod kursorem AKTYWNEJ tabeli (Set albo Biblioteka)."""
        if self.query_one("#tabs", TabbedContent).active == "tab-lib":
            table = self.query_one("#lib-table", DataTable)
            idx = table.cursor_row
            view = getattr(self, "_lib_view", [])
            if idx is None or not (0 <= idx < len(view)):
                return None
            return view[idx].track
        if not self._order or not self._ctx:
            return None
        table = self.query_one("#set", DataTable)
        idx = table.cursor_row
        if idx is None or not (0 <= idx < len(self._order)):
            return None
        return self._ctx["by_id"][self._order[idx]].track

    def action_preview_seam(self) -> None:
        """P jest KONTEKSTOWE: w Secie przy otwartym pasku szwu gra
        PRZEJŚCIE pary; poza tym gra SAM zaznaczony utwór (Set i Biblioteka).
        P drugi raz = pauza; P na tym samym utworze = wznowienie od miejsca.
        Dźwięk startuje WYŁĄCZNIE z jawnego klawisza."""
        aktywna = self.query_one("#tabs", TabbedContent).active
        if aktywna == "tab-set" \
                and self.query_one("#compare").has_class("open") \
                and self._compare_idx is not None:
            if self._stop_player():
                return
            self._seam_worker(self._compare_idx)
            return
        track = self._biezacy_track()
        if track is None:
            if not self._stop_player():
                self._note("ustaw kursor na utworze do odsłuchu")
            return
        akcja, blad = self._odtwarzacz.przelacz(
            str(track.source_path), track.bpm_estimate)
        if blad:
            self._note(f"odsłuch: {blad}")
            return
        nazwa = pathlib.Path(track.source_path).stem[:40]
        if akcja == "pauza":
            self._note("odsłuch: pauza (P wznawia)")
        else:
            self._note(f"GRA: {nazwa} ({akcja}) · P pauza · →/← ±8 uderzeń")
        self._pokaz_odtwarzacz()

    def action_toggle_auto(self) -> None:
        """Shift+P: auto-podgląd — ↓/↑ same grają zaznaczany utwór
        (poprzedni bezwzględnie zatrzymany — zero nakładki)."""
        self._auto_podglad = not self._auto_podglad
        self._note("auto-podgląd: "
                   + ("ON — strzałki grają same" if self._auto_podglad
                      else "OFF"))
        self._refresh_status()

    def action_skok_przod(self) -> None:
        self._skok(+8)

    def action_skok_tyl(self) -> None:
        self._skok(-8)

    def _skok(self, uderzenia: int) -> None:
        _, blad = self._odtwarzacz.skocz(uderzenia)
        if blad:
            self._note(f"skok: {blad}")
            return
        self._pokaz_odtwarzacz()

    def _pokaz_odtwarzacz(self) -> None:
        opis = self._odtwarzacz.opis()
        if opis:
            self.query_one("#progress", Static).update(
                f"▶ {opis} · P pauza · →/← ±8 uderzeń"
                + (" · AUTO" if self._auto_podglad else ""))

    def on_data_table_row_highlighted(self, event) -> None:
        """Auto-podgląd: zmiana zaznaczenia gra nowy utwór (małe opóźnienie,
        żeby przytrzymana strzałka nie restartowała co wiersz)."""
        if not self._auto_podglad:
            return
        if getattr(event.data_table, "id", None) not in ("set", "lib-table"):
            return
        if self._auto_timer is not None:
            self._auto_timer.stop()
        self._auto_timer = self.set_timer(0.25, self._auto_graj)

    def _auto_graj(self) -> None:
        track = self._biezacy_track()
        if track is None:
            return
        blad = self._odtwarzacz.graj_od_zera(str(track.source_path),
                                             track.bpm_estimate)
        if blad:
            self._note(f"auto-podgląd: {blad}")
            return
        self._pokaz_odtwarzacz()

    @work(thread=True, exclusive=True, group="seam")
    def _seam_worker(self, idx: int) -> None:
        from dancelab.tui.seam_preview import zbuduj_szew
        ui = self.call_from_thread
        by_id = self._ctx["by_id"]
        a = by_id[self._order[idx]]
        b = by_id[self._order[idx + 1]]
        ui(self.query_one("#progress", Static).update,
           f"Renderuję szew #{idx+1}→#{idx+2} (fraz-lock, krzywe deckowe)…")
        try:
            info = zbuduj_szew(a, b, self._ctx["weights"])
        except Exception as exc:  # noqa: BLE001 — powód, nie traceback
            ui(self._note, f"szew nie wyszedł: {exc}")
            self.call_from_thread(self.notify, f"szew nie wyszedł: {exc}",
                                  severity="warning", timeout=6)
            return
        ui(self._start_player, info, idx)

    def _start_player(self, info: dict, idx: int) -> None:
        blad = self._odtwarzacz.graj_od_zera(str(info["output"]), info["bpm"])
        if blad:
            self._note(f"odsłuch szwu: {blad}")
            return
        for line in info.get("rozumowanie", [])[:3]:
            self._note(line)
        self._note(f"GRA szew #{idx+1}→#{idx+2}: {info['beats']} uderzeń "
                   f"@ {info['bpm']:.1f} BPM · P pauza · →/← ±8")
        self.query_one("#progress", Static).update(
            f"▶ szew #{idx+1}→#{idx+2} · {info['beats']} uderzeń "
            f"@ {info['bpm']:.1f} BPM · P pauza · →/← ±8 uderzeń")

    # ------------------------------------------- porównanie pary od dołu (C)

    def action_compare_pair(self) -> None:
        """C: panel porównania pary zaznaczony→następny wysuwa się od dołu —
        dwa paski energii ze złotym oknem szwu z planu silnika (wzorzec:
        zakładka Export w Rekordboksie). Drugie C / Esc chowa. Graj oba = P
        (sync i kwantyzacja siedzą w renderze z natury — nic do włączania)."""
        panel = self.query_one("#compare")
        if panel.has_class("open"):
            panel.remove_class("open")
            return
        idx = self._cursor_row("porównanie pary")
        if idx is None:
            return
        if idx + 1 >= len(self._order):
            self._note("ostatni utwór nie ma następnika — C porównuje parę")
            return
        self._compare_worker(idx)

    @work(thread=True, exclusive=True, group="seam")
    def _compare_worker(self, idx: int) -> None:
        from dancelab.tui.seam_preview import zaplanuj_szew
        ui = self.call_from_thread
        by_id = self._ctx["by_id"]
        a = by_id[self._order[idx]]
        b = by_id[self._order[idx + 1]]
        try:
            plan = zaplanuj_szew(a, b, self._ctx["weights"])
        except Exception as exc:  # noqa: BLE001 — powód, nie traceback
            ui(self._note, f"porównanie nie wyszło: {exc}")
            self.call_from_thread(self.notify, f"porównanie nie wyszło: {exc}",
                                  severity="warning", timeout=6)
            return
        ui(self._open_compare, a, b, plan, idx)

    def _open_compare(self, a, b, plan: dict, idx: int) -> None:
        """Pasek szwu w duchu CURVE („+" między dwoma utworami): jedna linia
        faktów o szwie i JEDEN przycisk odsłuchu. Beatsync i kwantyzacja są
        zawsze włączone — siedzą w naturze fraz-lockowanego renderu."""
        art_a, tyt_a = _wykonawca_tytul(a.track)
        art_b, tyt_b = _wykonawca_tytul(b.track)

        def kto(art, tyt):
            return f"{art} — {tyt}" if art else tyt
        ca, cb = plan["cue_a_sec"], plan["cue_b_sec"]
        ma, sa = divmod(int(ca), 60)
        mb, sb = divmod(int(cb), 60)
        self.query_one("#cmp-title", Static).update(
            f"SZEW #{idx+1} ⇄ #{idx+2} · {kto(art_a, tyt_a)[:40]}  →  "
            f"{kto(art_b, tyt_b)[:40]}")
        self.query_one("#cmp-info", Static).update(
            f"{plan['beats']} uderzeń @ {plan['bpm']:.1f} BPM · "
            f"wyjście z A {ma}:{sa:02d} · wejście w B {mb}:{sb:02d} · "
            f"P/▶ gra oba · sync+kwantyzacja zawsze ON · C/Esc chowa")
        self._compare_idx = idx
        self.query_one("#compare").add_class("open")
        self.query_one("#set", DataTable).focus()

    # ------------------------------------------------------------- karta INFO

    def action_track_info(self) -> None:
        """I: metadane zaznaczonego utworu + dysk + playlisty z master.db."""
        if self._panel_mode == "info" \
                and self.query_one("#suggest").has_class("open"):
            self._close_panel()
            self.query_one("#set", DataTable).focus()
            return
        self._close_panel()
        idx = self._cursor_row("info o utworze")
        if idx is not None:
            self._info_worker(idx)

    @work(thread=True, exclusive=True)
    def _info_worker(self, idx: int) -> None:
        ui = self.call_from_thread
        t = self._ctx["by_id"][self._order[idx]].track
        rb, rb_note = None, None
        try:
            from dancelab.ingestion.rekordbox_lookup import track_in_rekordbox
            rb = track_in_rekordbox(t.source_path)
        except Exception as exc:  # noqa: BLE001 — karta mówi, czego nie wie
            rb_note = f"master.db nieodczytany: {exc}"
        text = _format_track_info(t, rb, rb_note)
        title = (f"INFO #{idx+1} {pathlib.Path(t.source_path).stem[:36]}\n"
                 f"I / Esc = zamknij")
        ui(self._open_info_panel, title, text)

    def _open_info_panel(self, title: str, text: str) -> None:
        from rich.text import Text
        self._suggest_slot = None
        self._panel_mode = "info"
        self.query_one("#suggest-mode", Select).add_class("hide")
        self.query_one("#suggest-list", OptionList).add_class("hide")
        info = self.query_one("#suggest-info", Static)
        info.update(Text(text))          # Text, nie markup — ścieżki miewają [ ]
        info.add_class("show")
        self.query_one("#suggest-title", Label).update(title)
        self.query_one("#suggest").add_class("open")
        self.query_one("#set", DataTable).focus()

    @work(thread=True, exclusive=True)
    def _write_worker(self) -> None:
        from dancelab.ingestion.playlist_publish import publish_playlist
        ui = self.call_from_thread
        report = publish_playlist(self._plan_paths, name=self._plan_name)
        for note in report.notes:
            ui(self._note, note)
        if report.ok and report.written:
            ui(self._note,
               f"✅ zapisane: {report.playlist_name} ({report.written} utworów) "
               f"· backup {report.backup_path}")
            ui(self._utrwal_odcisk, "wysłany do Rekordboxa")
            self.call_from_thread(
                self.notify,
                f"✅ {report.playlist_name}: {report.written} utworów w Rekordboksie")
        elif not report.ok:
            ui(self._note, "❌ zapis nieudany — szczegóły pod L")
            self.call_from_thread(self.notify, "❌ zapis nieudany — szczegóły pod L",
                                  severity="error", timeout=8)
        ui(self._refresh_status)


def main() -> None:
    DanceLabTUI().run()


if __name__ == "__main__":
    main()
