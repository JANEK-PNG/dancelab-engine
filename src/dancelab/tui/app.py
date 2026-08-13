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
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from dancelab.tui import zrodlo as Z
from dancelab.tui.pasek import PasekOdtwarzacza
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
RAPORT_ART = pathlib.Path("data/exports/artwork_raport.json")


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
_TAB_ORDER = ("tab-lib", "tab-dj", "tab-set", "tab-export")


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


def _opcje_kotwic(wpisy: list[tuple], kolekcja: list[str]) -> list[tuple[str, str]]:
    """Kolejność pola „Brzmi jak…": KOLEKCJA DJ-ów użytkownika przed resztą,
    z ✓ obok nazwiska (decyzja Janka 12.08, przeniesiona ze ściany kart:
    kolekcjonujesz w panelu, owoce zbierasz przy budowie). Kolejność wewnątrz
    kolekcji = kolejność zbierania; reszta zostaje w porządku księgi."""
    w_kol = set(kolekcja)
    kol = [w for w in wpisy if w[0] in w_kol]
    kol.sort(key=lambda w: kolekcja.index(w[0]))
    reszta = [w for w in wpisy if w[0] not in w_kol]
    return ([(f"✓ {n}  ({ile} wekt., skok {med})", n) for n, ile, med in kol]
            + [(f"{n}  ({ile} wekt., skok {med})", n) for n, ile, med in reszta])


def _filary_for_build(state: dict, by_id: dict, bpm_min: float | None,
                      bpm_max: float | None, count: int | None
                      ) -> tuple[list[str], list[str], dict[str, str]]:
    """Filary AKTYWNEJ PLAYLISTY → `pinned_track_ids` silnika + ROLE, z jawnym losem
    każdego konfliktu: filar spoza puli i filar poza oknem tempa są POMIJANE
    z imienną notką (okno ustawił użytkownik — konflikt ma być widoczny, nie
    rozstrzygany po cichu); więcej filarów niż miejsc = odmowa z liczbami."""
    from dancelab.tui.user_store import (MIN_FILARY, filary_wpisy,
                                         resolve_tracks)
    wpisy = filary_wpisy(state)
    ids, missing = resolve_tracks(wpisy, by_id)
    by_path = {a.track.source_path: tid for tid, a in by_id.items()}
    role: dict[str, str] = {}
    for e in wpisy:
        tid = e.get("track_id")
        if tid not in by_id:
            tid = by_path.get(e.get("path", ""))
        if tid and e.get("rola"):
            role[tid] = e["rola"]
    notes = [f"FILAR nieobecny w puli (pominięty): {m}" for m in missing]
    wyciete = [f"{m} (spoza puli)" for m in missing]
    kept: list[str] = []
    for tid in ids:
        bpm = by_id[tid].track.bpm_estimate or 0.0
        if (bpm_min is not None and bpm < bpm_min) or \
                (bpm_max is not None and bpm > bpm_max):
            name = pathlib.Path(by_id[tid].track.source_path).stem[:40]
            notes.append(f"FILAR poza oknem tempa (pominięty): {name} ({bpm:.1f})")
            wyciete.append(f"{name} ({bpm:.0f} — poza oknem)")
            continue
        kept.append(tid)
    if kept and len(kept) < MIN_FILARY:
        # ODMOWA MUSI NIEŚĆ WINOWAJCÓW (skarga Janka 09.08: „mimo że dodałem
        # 4 filary" — liczby bez nazwisk nie mówią, czy poszerzyć okno,
        # czy wymienić filary)
        kogo = "; ".join(wyciete[:3])
        if len(wyciete) > 3:
            kogo += f" i {len(wyciete) - 3} dalszych"
        okno = (f"{bpm_min:g}–{bpm_max:g}" if bpm_min is not None
                and bpm_max is not None else "ustawione")
        raise ValueError(
            f"filary to minimum {MIN_FILARY}, a po sitach zostało {len(kept)} "
            f"— wypadły: {kogo}. Poszerz okno tempa ({okno}) "
            f"albo wymień filary (F w Bibliotece)")
    if count is not None and len(kept) > count:
        raise ValueError(f"filarów ({len(kept)}) więcej niż miejsc w secie "
                         f"({count}) — wydłuż set albo zdejmij filary")
    if kept:
        notes.append(f"filary w budowie: {len(kept)} (każdy MUSI zagrać)")
    role = {tid: r for tid, r in role.items() if tid in set(kept)}
    if role:
        notes.append("role filarów: " + ", ".join(
            f"{r}" for r in sorted(set(role.values()))))
    return kept, notes, role


def _zastosuj_role_krancowe(rozstaw: dict[int, str], role: dict[str, str],
                            count: int) -> tuple[dict[int, str], list[str]]:
    """Role OTWARCIE i ZAMKNIĘCIE wymuszają krańce setu (Janek 11.08).

    Nadpisują rozstawienie z trybu filarów: deklaracja DJ-a jest mocniejsza
    niż sortowanie po tempie. Oddech i buildup na razie NIE celują miejscem —
    silnik gwarantuje obecność i most do filara; celowanie rolą w środku setu
    to następny krok i mówimy to wprost zamiast udawać (ADR-005)."""
    nowe = dict(rozstaw)
    notes: list[str] = []
    cele = {"otwarcie": 1, "zamkniecie": count}
    for rola, pozycja in cele.items():
        tid = next((t for t, r in role.items() if r == rola), None)
        if tid is None:
            continue
        nowe = {p: t for p, t in nowe.items() if t != tid and p != pozycja}
        nowe[pozycja] = tid
        notes.append(f"rola {rola}: pozycja #{pozycja} (deklaracja DJ-a "
                     f"nadpisuje rozstawienie trybu)")
    if any(r in ("oddech", "buildup") for r in role.values()):
        notes.append("role oddech/buildup: zapisane — silnik gwarantuje "
                     "obecność i most; celowanie miejscem wg roli to "
                     "następny krok")
    return nowe, notes


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


def _lib_sort_missing(col: int, a, energy: dict, lufs: dict) -> bool:
    """Czy utwór nie ma wartości w sortowanej kolumnie — braki idą NA KONIEC
    niezależnie od kierunku sortowania (brak to brak, nie zero)."""
    t = a.track
    if col == 3:
        return t.bpm_estimate is None
    if col == 4:
        return t.key_estimate is None
    if col == 5:
        return t.key_confidence is None
    if col == 6:
        return energy.get(t.track_id) is None
    if col == 7:
        return lufs.get(t.source_path) is None
    if col == 8:
        return not t.style_label
    return False


def _lib_sort_key(col: int, favs: set, filary: set, energy: dict,
                  lufs: dict):
    """Klucz sortowania Biblioteki po klikniętej kolumnie (standard branży)."""
    def name(a):
        return pathlib.Path(a.track.source_path).stem.lower()

    def key(a):
        t = a.track
        if col == 1:
            return (t.track_id not in favs, name(a))
        if col == 2:
            return (t.track_id not in filary, name(a))
        if col == 3:
            return t.bpm_estimate or 0.0
        if col == 4:
            k = str(t.key_estimate or "")
            num = int(k[:-1]) if len(k) > 1 and k[:-1].isdigit() else 99
            return (num, k[-1:])
        if col == 5:
            return t.key_confidence or 0.0
        if col == 6:
            return energy.get(t.track_id) or 0
        if col == 7:
            return lufs.get(t.source_path) or 0.0
        if col == 8:
            return (t.style_label or "").lower()
        if col == 9:
            return t.duration_sec or 0.0
        if col == 10:
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


class NazwaPlaylistyScreen(NazwaPlanuScreen):
    """＋ nowa playlista: NAJPIERW nazwa (zaproponowana z metadanych puli —
    wzór z praktyki Janka: „Piątek · 130–135 · jak Ben UFO"), a po Enterze
    OD RAZU Biblioteka, gdzie DJ zaznacza filary (decyzja Janka 12.08 —
    kotwica przestała być wymuszonym krokiem)."""

    def compose(self) -> ComposeResult:
        with Vertical(id="nazwa-box"):
            yield Label("Nazwa playlisty (z metadanych — popraw, jeśli chcesz):")
            yield Input(value=self._domyslna, id="plan-name")
            with Horizontal(id="nazwa-przyciski"):
                yield Button("Dalej: filary", id="nazwa-ok", variant="primary")
                yield Button("Anuluj", id="nazwa-cancel")


class KartaDJ(Static):
    """Karta DJ-a na ścianie zakładki DJ-e — fokusowalna jak kafelek
    w GUI: strzałki chodzą po siatce, K zbiera do kolekcji, Enter
    ustawia kotwicę „Brzmi jak…"."""

    can_focus = True

    def __init__(self, dj: str, tresc: str, w_kolekcji: bool) -> None:
        super().__init__(tresc)
        self.dj = dj
        self.add_class("karta-dj")
        if not w_kolekcji:
            self.add_class("szara")

    def on_key(self, event) -> None:
        if event.key == "k":
            event.stop()
            event.prevent_default()
            self.app._kolekcja_z_karty_sciennej(self.dj)
        elif event.key == "enter":
            event.stop()
            event.prevent_default()
            self.app._kotwica_z_karty_sciennej(self.dj)
        elif event.key in ("left", "right", "up", "down"):
            event.stop()
            event.prevent_default()
            self.app._ruch_po_scianie(self, event.key)


class DanceLabTUI(App):
    TITLE = "DanceLab — budowa setu"
    CSS = """
    #form { width: 44; padding: 0 1; border-right: solid $primary; }
    #go { dock: bottom; width: 100%; margin: 1 0; }
    #form Input, #form Select { margin-bottom: 1; }
    #results { padding: 0 1; }
    #set { height: 1fr; }
    #tab-set .pb-box { dock: bottom; }
    #warnings { height: 9; border-top: solid $warning; display: none; }
    #warnings.open { display: block; }
    #status { height: 1; background: $panel;
              color: $text-muted; padding: 0 1; }
    #suggest { width: 42; border-left: solid $accent; padding: 0 1; display: none; }
    #suggest.open { display: block; }
    #suggest-title { color: $accent; text-style: bold; }
    #suggest-mode { margin: 1 0; }
    #suggest-mode.hide { display: none; }
    #suggest-list.hide { display: none; }
    #suggest-info { display: none; margin: 1 0; }
    #suggest-info.show { display: block; }
    .field-label { color: $text-muted; }
    #tabs { height: 1fr; }
    #lib-side-list { height: auto; }
    .pb-box { height: 6; }
    .pb-row1 { height: 3; width: auto; margin-top: 1; }
    .pb-row1 Button { margin-right: 1; min-width: 8; }
    .pb-art { width: 12; height: 6; margin: 0 2; }
    .pb-meta { height: 6; padding-top: 1; width: 1fr; }
    .pb-info { height: 1; text-style: bold; }
    .pb-sub { height: 1; color: $text-muted; }
    .pb-os { height: 1; }
    #lib-side { width: 26; border-right: solid $primary; padding: 0 1; }
    #dj-licznik { height: 2; padding: 0 1; color: $text-muted; }
    #dj-filtry { height: 3; }
    #dj-filtry Button { margin-right: 1; min-width: 12; }
    #dj-brzmi { height: 2; padding: 0 1; }
    #dj-przewijak { height: 1fr; }
    #dj-sciana { layout: grid; grid-size: 3; grid-gutter: 1 2; height: auto; padding: 0 1; }
    .karta-dj { border: solid $panel; padding: 0 1; height: auto; }
    .karta-dj:focus { border: solid $primary; }
    .karta-dj.szara { opacity: 55%; }
    #lib-filters { height: 3; }
    #lib-filters Input { width: 1fr; margin-right: 1; }
    #lib-tools { height: 1; }
    #lib-artwork { border: none; height: 1; padding: 0 1; }
    #lib-artwork-label { color: $text-muted; padding: 0 1; }
    #lib-count { height: 2; color: $text-muted; padding: 0 1 1 1; }
    #lib-table .datatable--header { text-style: bold; background: $boost; }
    #compare { height: 7; border-bottom: solid $accent; padding: 0 1;
               display: none; }
    #compare.open { display: block; }
    #cmp-title { color: $accent; text-style: bold; }
    #lib-table { height: 1fr; }
    #lib-onboard { height: 3; }
    #lib-onboard Input { width: 1fr; margin-right: 1; }
    #cue-table { height: 1fr; }
    #cue-head { height: 2; padding: 0 1; }
    #cue-gora { dock: top; height: auto; }
    #cue-karta { height: auto; border-bottom: solid $accent; }
    #cue-os { width: 1fr; height: auto; padding: 0 1; }
    #cue-pady { width: 46; height: auto; padding: 0 1;
                border-left: solid $accent; }
    #cue-info { height: auto; padding: 0 1; color: $text-muted; }
    #cue-dol { dock: bottom; height: auto; }
    #cue-tools { height: 3; padding: 0 1; }
    #cue-tools Button { margin-left: 2; }
    /* STAŁA szerokość na najdłuższą etykietę stanu: przycisk zmienia napis
       w trakcie pracy, a szerokość „auto" policzona przy budowie ekranu
       już się nie przelicza — napis „POTWIERDŹ…" wychodził UCIĘTY
       (złapane na zrzucie do instrukcji 09.08) */
    #cue-write { width: 36; }
    #cue-luz { width: 1fr; }
    """
    BINDINGS = [
        Binding("b", "build", "Buduj"),
        Binding("w", "write", "Wyślij do RB"),
        Binding("z", "replace", "Zamień"),
        Binding("x", "cut", "Wytnij"),
        Binding("a", "add", "Dopisz"),
        Binding("shift+up", "move_up", "przesuń ▲", show=False),
        Binding("shift+down", "move_down", "przesuń ▼", show=False),
        Binding("s", "save_plan", "Zapisz plan"),
        Binding("o", "load_plan", "Wczytaj plan"),
        Binding("space", "preview_seam", "Graj/Pauza", priority=True),
        Binding("p", "preview_seam", "Posłuchaj", show=False),
        Binding("right", "skok_przod", "skok +8", show=False, priority=True),
        Binding("left", "skok_tyl", "skok -8", show=False, priority=True),
        Binding("shift+right", "skok_przod_32", "skok +32", show=False,
                priority=True),
        Binding("shift+left", "skok_tyl_32", "skok -32", show=False,
                priority=True),
        Binding("cmd+shift+right", "skok_przod_128", "skok +128", show=False,
                priority=True),
        Binding("cmd+shift+left", "skok_tyl_128", "skok -128", show=False,
                priority=True),
        Binding("pagedown", "skok_przod_128", "skok +128", show=False,
                priority=True),
        Binding("pageup", "skok_tyl_128", "skok -128", show=False,
                priority=True),
        Binding("ctrl+g", "gatunki", "Gatunki", show=False),
        Binding("ctrl+d", "grupy_dj", "Brzmi jak…", show=False),
        Binding("c", "compare_pair", "Porównaj"),
        Binding("i", "track_info", "Info"),
        Binding("l", "toggle_notes", "Notki"),
        Binding("u", "toggle_fav", "♥ Ulubiony"),
        Binding("f", "toggle_filar", "Filar"),
        Binding("g", "build_from_filary", "Z filarów", show=False),
        Binding("k", "toggle_okladki", "Okładki", show=False),
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
        # notatki zgłoszone, zanim ekran się zmontował — patrz `_note`
        self._notatki_przed_startem: list[str] = []
        # Ściana kart DJ-ów. MUSI istnieć od początku: `_render_dj_tab`
        # wychodzi wcześniej, gdy nie ma księgi kotwic (czyli na każdej
        # świeżej instalce), a filtr sięgał po tę listę i wywracał aplikację
        # — Janek trafił na to przy pierwszym uruchomieniu z czystego klonu.
        self._dj_karty: list = []
        self._artwork_przerwij = threading.Event()
        self._artwork_programowo = False   # lustrzane ustawianie przełącznika
        self._plan_paths: list[str] = []
        self._plan_name = ""
        self._order: list[str] = []
        self._engine_order: list[str] = []
        self._edits: list[dict] = []
        self._mean_score = None
        self._ctx: dict = {}
        self._cue_plan = None            # CuePlan z podglądu (etap 1)
        from dancelab.tui import cue_edycje
        self._cue_edycje = cue_edycje.nowe()   # warstwa edycji DJ-a (etap 2)
        self._cue_widok: list[str] = []        # kolejność wierszy listy cue
        self._cue_track: str | None = None     # utwór w karcie
        self._cue_wybor: str | None = None     # wybrany pad (litera)
        self._cue_zapis_gotowy = None          # policzony plan zapisu (2 naciśnięcia W)
        self._cue_czas_bufor: str | None = None   # edycja w kratce
        self._cue_prop: list = []              # gotowe czasy fraz
        self._cue_prop_i = 0
        self._suggest_slot: int | None = None
        self._panel_mode: str | None = None   # "suggest" | "insert" | "plans"
        self._row_cells: list[tuple[str, str]] = []   # (nr, utwór) do poświaty
        self._n_notes = 0
        self._lib: list = []                  # pula Biblioteki (analizy)
        self._lib_view: list = []             # pula po filtrach (widoczna)
        self._lib_energy: dict[str, float | None] = {}   # tid → energia 0-100
        self._lib_lufs: dict[str, float] = {}            # ścieżka → LUFS (tło)
        self._user_state: dict = {"ulubione_utwory": [],
                                  "ulubione_playlisty": [], "filary": []}
        # None = porządek domyślny (BPM rosnąco); cykl klikania w nagłówek:
        # liczby ↓ → ↑ → kasacja, teksty A-Z → Z-A → kasacja (Janek 06.08)
        self._lib_sort: tuple[int, bool] | None = None
        from dancelab.tui.odtwarzacz import Odtwarzacz
        self._odtwarzacz = Odtwarzacz()       # P: utwór / szew, pauza, skoki
        self._auto_timer = None               # debounce podążania za kursorem
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
                        with Horizontal(id="lib-tools"):
                            # dodatek, nie killer feature (Janek): mały
                            # przełącznik zamiast przycisku — ON pokazuje
                            # okładki w liście I dociąga brakujące (iTunes →
                            # tagi); OFF tylko chowa, niczego nie kasuje
                            yield Switch(value=False, id="lib-artwork")
                            yield Label("okładki", id="lib-artwork-label")
                        yield Static("", id="lib-count")
                        # priorytet fg "renderable": obrazki TGP kodują SIEBIE
                        # w kolorze pisma (kolor = id obrazka u terminala) —
                        # kursor nadpisujący kolor wiersza kasował okładkę
                        yield DataTable(id="lib-table",
                                        cursor_foreground_priority="renderable")
                        yield PasekOdtwarzacza()
                        with Horizontal(id="lib-onboard"):
                            yield Input(placeholder="folder z muzyką do "
                                                    "przeskanowania (pierwszy raz "
                                                    "albo dogranie)",
                                        id="lib-folder")
                            yield Button("Analizuj", id="lib-analyze",
                                         variant="primary")
                            yield Button("→ Zbuduj z filarów  [G]",
                                         id="lib-build", variant="success")
            with TabPane("DJ-e", id="tab-dj"):
                # ŚCIANA KART jak w GUI (Janek 13.08: „czemu w TUI dostaję
                # listę?" — bo poszedłem na skróty; hierarchia makiety:
                # licznik → filtry → pasek „Brzmi jak…" → siatka kart).
                # Poza zasięgiem terminala zostają tylko: jedwabny portret
                # (jest wersja z klocków), odsłuch SoundCloud i crossfade.
                with Vertical():
                    yield Static("", id="dj-licznik")
                    with Horizontal(id="dj-filtry"):
                        yield Button("wszyscy", id="dj-f-all",
                                     variant="primary")
                        yield Button("w kolekcji", id="dj-f-kol")
                    yield Static("", id="dj-brzmi")
                    with VerticalScroll(id="dj-przewijak"):
                        yield Grid(id="dj-sciana")
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
                            yield Label("Gatunki (Ctrl+G = lista z biblioteki)",
                                        classes="field-label")
                            yield Input(placeholder="Tech House, UK Garage / Bassline",
                                        id="styles")
                            yield Label("Brzmi jak… (Ctrl+D = rodziny brzmienia)", classes="field-label")
                            yield Select([], id="dj", prompt="— bez kotwicy —")
                            with Horizontal():
                                yield Switch(value=False, id="contour")
                                yield Label(" kontur skoków tego DJ-a")
                            yield Label("Łuk / plan tempa / tryb", classes="field-label")
                            yield Select([("bez łuku (zmierzone)", "off"),
                                          ("build", "build"), ("peak", "peak"),
                                          ("flat", "flat")],
                                         value="off", id="arc", allow_blank=False)
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
                            # BUDUJ dokowany do dołu kolumny: przewijają
                            # się pola briefu, nie przycisk (skarga Janka
                            # 09.08 — trzeba było skrolować, żeby go znaleźć)
                            yield Button("Buduj set  [B]", id="go",
                                         variant="primary")
                        with Vertical(id="results"):
                            yield Static("Ustaw parametry i naciśnij B.", id="progress")
                            with Vertical(id="compare"):
                                yield Static("", id="cmp-title")
                                yield Static("", id="cmp-info")
                            yield DataTable(id="set")
                            yield PasekOdtwarzacza()
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
                with Vertical():
                    with Vertical(id="cue-gora"):
                        yield Static("", id="cue-head")
                        with Horizontal(id="cue-karta"):
                            yield Static("", id="cue-os")
                            yield Static("", id="cue-pady")
                        yield Static("", id="cue-info")
                    yield DataTable(id="cue-table",
                                    cursor_foreground_priority="renderable")
                    # DÓŁ: odtwarzacz, a pod nim CTA w prawym rogu —
                    # dokładnie jak w Bibliotece (życzenie Janka 09.08).
                    # Jeden blok, bo dwa osobne dokowania do tej samej
                    # krawędzi nakładały się na siebie (pasek przykrywał
                    # guziki — złapane na zrzucie).
                    with Vertical(id="cue-dol"):
                        yield PasekOdtwarzacza()
                        with Horizontal(id="cue-tools"):
                            yield Static("", id="cue-luz")
                            yield Button("Wyślij cue do RB  [W]",
                                         id="cue-write")
                            yield Button("Wyślij playlistę do RB",
                                         id="cue-playlist")
        yield Static("", id="status")
        yield Footer()

    def on_mount(self) -> None:
        # Paleta TERRAIN z makiet GUI (decyzja Janka 12.08 — „powoli zbliżamy
        # się do oryginału"; nadpisuje monokai z 06.08): ciepły grafit tła,
        # volt na wybór/akcję, ciepły bursztyn i chłodny błękit jak talie A/B.
        from textual.theme import Theme
        self.register_theme(Theme(
            name="dancelab-terrain",
            primary="#d6f549",       # volt — wybór i jeden czasownik
            secondary="#6db3c9",     # chłodny błękit (talia B)
            accent="#e0a458",        # ciepły bursztyn (talia A)
            warning="#e0a458",
            error="#e07458",         # ciepła czerwień usuwania (jak ✕ karty)
            success="#a8c952",       # oliwkowa zieleń (miernik groove)
            foreground="#e8e4da",
            background="#171614",
            surface="#211f1c",
            panel="#26241f",
            dark=True,
        ))
        self.theme = "dancelab-terrain"
        table = self.query_one("#set", DataTable)
        for lbl, w in (("#", None), ("BPM", 10), ("ton", 8), ("pew.", None),
                       ("gatunek", None), ("Σ min", None), ("utwór", None)):
            table.add_column(lbl, width=w)
        table.cursor_type = "row"
        lib = self.query_one("#lib-table", DataTable)
        self._lib_col_keys = [
            lib.add_column(lbl, width=w)
            # „źr." NA KOŃCU celowo: numery kolumn są twardo zapisane
            # w sortowaniu (_lib_sort_missing, _lib_sort_key), więc wstawienie
            # czegokolwiek w środek przesuwa je wszystkie.
            for lbl, w in ((" ", 8), ("♥", None), ("F", None), ("BPM", 10),
                           ("ton", 8), ("pew.", None), ("energia", None),
                           ("LUFS", 7), ("gatunek", None), ("min", None),
                           ("wykonawca", None), ("tytuł", None), ("źr.", 5))]
        lib.cursor_type = "row"
        cue = self.query_one("#cue-table", DataTable)
        for lbl, w in (("#", 3), ("utwór", 30), ("oś utworu", 38),
                       ("pady", 6), ("pewność", None)):
            cue.add_column(lbl, width=w)
        cue.cursor_type = "row"
        self._lib_section = "all"
        try:
            from dancelab.tui.user_store import load_state
            self._user_state = load_state(self.processed_dir)
        except Exception as exc:  # noqa: BLE001 — zepsuty plik stanu ≠ martwa apka
            self._note(f"stan ulubionych/filarów nieodczytany: {exc}")
            self._user_state = {"ulubione_utwory": [], "ulubione_playlisty": [],
                                "filary": [], "playlisty": [],
                                "aktywna_playlista": None}
        self._render_side_list()
        # lustro zapisanego stanu okładek na przełączniku — bez uruchamiania
        # synchronizacji (ta rusza wyłącznie z ręki użytkownika)
        if bool(self._user_state.get("okladki_w_liscie")):
            self._artwork_programowo = True
            self.query_one("#lib-artwork", Switch).value = True
        self._load_anchors()
        self._render_dj_tab()
        self._refresh_status()
        self.set_interval(5.0, self._refresh_status)
        self.set_interval(1.0, self._tick_player)
        self._lib_loader()

    # ------------------------------------------------------------ zakładki

    # Pasek skrótów jest KONTEKSTOWY (prośba Janka: „lista skrótów rośnie") —
    # w Bibliotece widać klawisze Biblioteki, w Secie klawisze Setu.
    _LIB_ONLY = {"toggle_fav", "build_from_filary", "toggle_okladki"}
    _SET_ONLY = {"build", "replace", "cut", "add", "move_up",
                 "move_down", "save_plan", "load_plan", "gatunki",
                 "grupy_dj",
                 "track_info", "compare_pair"}

    def check_action(self, action: str, parameters) -> bool:
        try:
            active = self.query_one("#tabs", TabbedContent).active
        except Exception:  # noqa: BLE001 — przed zmontowaniem zakładek
            return True
        if action.startswith("skok_"):
            # strzałki poziome przejmuje odtwarzacz TYLKO podczas grania
            # (decyzja Janka) i tylko z fokusem na tabeli — w polu tekstowym
            # dalej ruszają kursorem tekstu; a przy WYBRANYM padzie w cue
            # strzałki należą do edycji pada, nie do odtwarzacza
            if active == "tab-export" and self._cue_wybor:
                return False
            return (self._odtwarzacz.gra()
                    and isinstance(self.focused, DataTable))
        if action == "preview_seam":
            # spacja ma priorytet, więc bramka musi puszczać ją do pól
            # tekstowych i przycisków, gdy to one mają fokus
            return (active in ("tab-lib", "tab-set")
                    and isinstance(self.focused, DataTable))
        if action in self._LIB_ONLY:
            return active == "tab-lib"
        if action in self._SET_ONLY:
            return active == "tab-set"
        return True

    def on_key(self, event) -> None:
        """Klawisze edytora cue (etap 2): litera = pad (jak na CDJ),
        strzałki przesuwają wybrany pad po siatce bitów, X zdejmuje,
        Z cofa. Tylko zakładka Eksport/Cue z fokusem na liście.
        Wyjątek: K w otwartym panelu „Brzmi jak…" zbiera DJ-a do kolekcji."""
        try:
            panel_dj = getattr(self, "_panel_mode", None) == "dj" \
                and self.query_one("#suggest").has_class("open")
        except Exception:  # noqa: BLE001 — panel może nie istnieć w testach
            panel_dj = False
        if event.key == "k" and panel_dj:
            event.stop()
            event.prevent_default()
            self._przelacz_kolekcje_dj_z_panelu()
            return
        try:
            active = self.query_one("#tabs", TabbedContent).active
        except Exception:  # noqa: BLE001
            return
        if active != "tab-export" or self._cue_plan is None:
            return
        if getattr(self.focused, "id", None) != "cue-table":
            return
        if self._cue_czas_bufor is not None:
            # EDYCJA W KRATCE PADA (weto Janka 09.08 na osobne pole):
            # cyfry piszą, ↑↓ wybierają gotowy czas frazy, Enter zatwierdza.
            event.stop()
            event.prevent_default()
            k = event.key
            if k == "escape":
                self._cue_czas_bufor = None
                self._render_cue_karta()
            elif k == "enter":
                self._cue_ustaw_czas(self._cue_czas_bufor)
            elif k == "backspace":
                self._cue_czas_bufor = self._cue_czas_bufor[:-1]
                self._render_cue_karta()
            elif k in ("up", "down") and self._cue_prop:
                krok = -1 if k == "up" else 1
                self._cue_prop_i = ((self._cue_prop_i + krok)
                                    % len(self._cue_prop))
                from dancelab.tui.cue_podglad import _mmss
                self._cue_czas_bufor = _mmss(
                    int(self._cue_prop[self._cue_prop_i][1] * 1000))
                self._render_cue_karta()
            elif len(getattr(event, "character", "") or "") == 1 \
                    and event.character in "0123456789:.,":
                self._cue_czas_bufor += event.character
                self._render_cue_karta()
            return
        klawisz = event.key
        if klawisz in tuple("abcdefgh"):
            event.stop()
            event.prevent_default()
            self._cue_litera(klawisz.upper())
        elif self._cue_wybor and klawisz in ("left", "right", "shift+left",
                                             "shift+right", "pageup",
                                             "pagedown"):
            event.stop()
            event.prevent_default()
            kroki = {"left": -1, "right": +1, "shift+left": -8,
                     "shift+right": +8, "pageup": -32, "pagedown": +32}
            self._cue_przesun(kroki[klawisz])
        elif klawisz == "s":
            # S jak SZEW. Nie C — C to pad C na siatce CDJ, litery A–H
            # należą do padów i nie wolno im nic odbierać.
            event.stop()
            event.prevent_default()
            self._cue_graj_szew()
        elif klawisz == "t" and self._cue_wybor:
            event.stop()
            event.prevent_default()
            self._cue_wpisz_czas()
        elif klawisz in ("p", "space"):
            event.stop()
            event.prevent_default()
            self._cue_posluchaj()
        elif self._cue_wybor and klawisz == "x":
            event.stop()
            event.prevent_default()
            self._cue_zdejmij()
        elif klawisz == "z":
            event.stop()
            event.prevent_default()
            self._cue_cofnij()
        elif self._cue_wybor and klawisz == "escape":
            event.stop()
            event.prevent_default()
            self._cue_wybor = None
            self._render_cue_karta()

    def _bez_pliku(self, track) -> str | None:
        """Powód odmowy, gdy czynność wymaga PLIKU, a utwór go nie ma.

        Utwory zaimportowane z analiz Rekordboxa (strumienie Apple Music) mają
        tempo, siatkę, energię i sekcje, ale nie mają audio na dysku — więc
        odsłuch i render szwu są niemożliwe. Mówimy to wprost, zamiast
        pokazywać błąd odtwarzacza."""
        # Kryterium: ścieżka NIE JEST ścieżką w systemie plików (strumień
        # zapisany jako `apple-music:tracks:123`). Plik, który zniknął, to
        # inny przypadek — tam odtwarzacz ma prawo powiedzieć swoje.
        sciezka = str(getattr(track, "source_path", "") or "")
        if sciezka and not sciezka.startswith("/"):
            return (f"{(track.title or sciezka)[:38]}: nie ma pliku na dysku "
                    f"(utwór ze strumienia) — zagrasz go w Rekordboksie, "
                    f"tutaj policzymy tylko dobór")
        return None

    def _cue_takty(self, tid: str | None = None) -> list[float]:
        """Takty utworu wg Rekordboxa — te same czerwone linie, które widzisz
        w jego oknie. Pusta lista = tego utworu nie ma w kolekcji albo nie ma
        pliku analizy; wtedy schodzimy na naszą siatkę i mówimy o tym."""
        from dancelab.ingestion.rekordbox_siatka import downbeaty_dla_sciezki
        analiza = self._ctx.get("by_id", {}).get(tid or self._cue_track)
        if analiza is None:
            return []
        return downbeaty_dla_sciezki(analiza.track.source_path)

    def _cue_pady_teraz(self) -> dict:
        from dancelab.tui import cue_edycje
        return cue_edycje.efektywne_pady(
            self._cue_plan, self._cue_edycje, self._cue_track)

    def _cue_litera(self, pad: str) -> None:
        """Litera A–H: istniejący pad → wybór; brak pada → nowy pad ręczny
        (pozycja odtwarzacza, gdy gra ten utwór; inaczej środek utworu)."""
        from dancelab.tui import cue_edycje
        from dancelab.tui.cue_podglad import czas_utworu
        if not self._cue_track:
            return
        pady = self._cue_pady_teraz()
        if pad in pady:
            if self._cue_wybor != pad:
                self._cue_wybor = pad          # pierwsze naciśnięcie: wybór
                self._render_cue_karta()
                return
            # DRUGIE naciśnięcie tej samej litery: PRZENIEŚ PAD TUTAJ, czyli
            # do głowicy odtwarzacza (skarga Janka 09.08: strzałki po jednym
            # uderzeniu są nieintuicyjne przy dużych przeskokach). Wzorzec
            # dwóch naciśnięć jak w całej aplikacji; Z cofa.
            analiza = self._ctx["by_id"][self._cue_track]
            if self._odtwarzacz.sciezka != analiza.track.source_path:
                self._note(f"pad {pad}: najpierw P — odtwarzacz musi stać "
                           f"na TYM utworze, żeby przenieść pad w to miejsce")
                return
            p = pady[pad]
            bpm = (analiza.beatgrid.bpm if analiza.beatgrid else 0) or 120.0
            beat = 60000.0 / bpm
            # pad ląduje na POCZĄTKU TAKTU, nie na dowolnym bicie
            cel_sec, powod = cue_edycje.czas_po_kwantyzacji(
                analiza.beatgrid, self._odtwarzacz.pozycja(),
                self._cue_takty())
            cel = int(round(cel_sec * 1000))
            uderzenia = int(round((cel - p["position_ms"]) / beat))
            from dancelab.tui import cue_edycje
            nowa = cue_edycje.przesun(
                self._cue_edycje, self._cue_track, pad, uderzenia, bpm,
                p.get("silnik_ms"), p["position_ms"])
            self._log_verdict("cue_przeniesienie", track_id=self._cue_track,
                              pad=pad, position_ms=nowa,
                              silnik_ms=p.get("silnik_ms"))
            m, sek = divmod(int(nowa / 1000), 60)
            self._note(f"pad {pad} przeniesiony na {m}:{sek:02d} "
                       f"({powod}) · Z cofa")
            self._render_cue_lista()
            return
        analiza = self._ctx["by_id"][self._cue_track]
        sciezka = analiza.track.source_path
        if (self._odtwarzacz.gra()
                and self._odtwarzacz.sciezka == sciezka):
            pozycja_ms = int(self._odtwarzacz.pozycja() * 1000)
        else:
            pozycja_ms = int(czas_utworu(analiza) * 500)  # środek utworu
        # nowy pad także siada na POCZĄTKU TAKTU (jedna reguła w całym
        # edytorze — hot cue nigdy nie stoi w połowie taktu)
        cel_sec, _powod = cue_edycje.czas_po_kwantyzacji(
            analiza.beatgrid, pozycja_ms / 1000.0, self._cue_takty())
        pozycja_ms = int(round(cel_sec * 1000))
        cue_edycje.postaw(self._cue_edycje, self._cue_track, pad, pozycja_ms)
        self._cue_wybor = pad
        self._log_verdict("cue_postaw", track_id=self._cue_track, pad=pad,
                          position_ms=pozycja_ms)
        self._render_cue_lista()

    def _cue_przesun(self, takty: int) -> None:
        """Strzałki przesuwają pad o TAKTY, nie o pojedyncze bity — hot cue
        ma stać na „jedynce" (Janek 09.08), więc ruch o jeden bit tylko by
        z niej zsuwał i zaraz wracał kwantyzacją."""
        from dancelab.ingestion.rekordbox_siatka import sasiedni_takt
        from dancelab.tui import cue_edycje
        pady = self._cue_pady_teraz()
        p = pady.get(self._cue_wybor)
        if p is None:
            return
        analiza = self._ctx["by_id"][self._cue_track]
        bpm = (analiza.beatgrid.bpm if analiza.beatgrid else 0) or 120.0
        downbeaty = self._cue_takty()
        skok = sasiedni_takt(downbeaty, p["position_ms"] / 1000.0, takty)
        if skok is not None:
            cel_ms, numer = int(round(skok[0] * 1000)), skok[1]
            uderzenia = int(round((cel_ms - p["position_ms"])
                                  / (60000.0 / bpm)))
            dopisek = f" · takt {numer}"
        else:                       # bez siatki Rekordboxa: takt = 4 bity
            uderzenia = takty * 4
            dopisek = ""
        nowa = cue_edycje.przesun(
            self._cue_edycje, self._cue_track, self._cue_wybor,
            uderzenia, bpm, p.get("silnik_ms"), p["position_ms"])
        self._log_verdict("cue_przesuniecie", track_id=self._cue_track,
                          pad=self._cue_wybor, takty=takty,
                          position_ms=nowa, silnik_ms=p.get("silnik_ms"))
        if dopisek:
            m, sek = divmod(int(nowa / 1000), 60)
            self._note(f"pad {self._cue_wybor}: {m}:{sek:02d}{dopisek}")
        self._render_cue_lista()

    def _cue_graj_szew(self) -> None:
        """S w Eksport/Cue: posłuchaj szwu Z TWOICH PADÓW — wyjścia z tego
        utworu w wejście do następnego (decyzja Janka 09.08: porównanie
        pary przeniesione tutaj, bo tu słychać to, co naprawdę pojedzie
        na CDJ-e, a nie propozycję silnika).

        Który pad jest wyjściem: ten ZAZNACZONY, a bez zaznaczenia ostatnie
        „wyjście" na osi, a gdy go nie ma — ostatni pad utworu. Wejście
        analogicznie od początku następnego utworu. Wybór jest zawsze
        wypisany imiennie, żebyś wiedział, czego słuchasz."""
        if not self._cue_track or not self._cue_widok:
            return
        i = self._cue_widok.index(self._cue_track)
        if i + 1 >= len(self._cue_widok):
            self._note("ostatni utwór nie ma następnika — S gra szew "
                       "do następnego utworu setu")
            return
        nastepny = self._cue_widok[i + 1]
        for tid in (self._cue_track, nastepny):
            powod = self._bez_pliku(self._ctx["by_id"][tid].track)
            if powod:
                self._note(f"szew: {powod}")
                return
        from dancelab.tui import cue_edycje
        pady_a = self._cue_pady_teraz()
        pady_b = cue_edycje.efektywne_pady(
            self._cue_plan, self._cue_edycje, nastepny)
        if not pady_a or not pady_b:
            czego = ("tego utworu" if not pady_a else "następnego utworu")
            self._note(f"S: {czego} nie ma ani jednego pada — postaw pad "
                       f"(litera A–H), wtedy zszyję parę z Twoich padów")
            return

        def wybierz(pady: dict, typ: str, ostatni: bool) -> tuple[str, dict]:
            kand = [(k, v) for k, v in pady.items() if v["typ"] == typ] \
                or list(pady.items())
            kand.sort(key=lambda kv: kv[1]["position_ms"])
            return kand[-1] if ostatni else kand[0]

        if self._cue_wybor and self._cue_wybor in pady_a:
            pad_a, p_a = self._cue_wybor, pady_a[self._cue_wybor]
        else:
            pad_a, p_a = wybierz(pady_a, "mix_out", ostatni=True)
        pad_b, p_b = wybierz(pady_b, "mix_in", ostatni=False)
        self._note(f"szew z padów: wyjście {pad_a} → wejście {pad_b} "
                   f"({self._cue_nazwa(nastepny)[:30]})")
        self._szew_z_padow_worker(self._cue_track, nastepny,
                                  p_a["position_ms"] / 1000.0,
                                  p_b["position_ms"] / 1000.0)

    @work(thread=True, exclusive=True, group="seam")
    def _szew_z_padow_worker(self, tid_a: str, tid_b: str,
                             cue_a: float, cue_b: float) -> None:
        """Render szwu jest CICHY (plik w cache); dźwięk rusza dopiero
        w `_zagraj_szew_z_padow` na wątku UI, po Twoim S."""
        from dancelab.tui.seam_preview import zbuduj_szew_z_padow
        ui = self.call_from_thread
        by_id = self._ctx["by_id"]
        ui(self._note, "szew z Twoich padów: renderuję…")
        try:
            info = zbuduj_szew_z_padow(by_id[tid_a], by_id[tid_b],
                                       cue_a_sec=cue_a, cue_b_sec=cue_b)
        except Exception as exc:  # noqa: BLE001 — powód, nie traceback
            ui(self._note, f"szew nie wyszedł: {exc}")
            ui(self.notify, f"szew nie wyszedł: {exc}",
               severity="warning", timeout=6)
            return
        ui(self._zagraj_szew_z_padow, info, tid_a, tid_b)

    def _zagraj_szew_z_padow(self, info: dict, tid_a: str,
                             tid_b: str) -> None:
        blad = self._odtwarzacz.graj_od_zera(str(info["output"]), info["bpm"])
        if blad:
            self.notify(f"odsłuch szwu nie wyszedł: {blad}",
                        severity="warning", timeout=6)
            self._note(f"odsłuch szwu nie wyszedł: {blad}")
            return
        self._gra_meta = ("szew z Twoich padów",
                          f"{self._cue_nazwa(tid_a)[:22]} → "
                          f"{self._cue_nazwa(tid_b)[:22]}")
        from rich.text import Text
        for art_w in self.query(".pb-art"):
            art_w.update(Text(""))
        ma, sa = divmod(int(info["cue_a_sec"]), 60)
        mb, sb = divmod(int(info["cue_b_sec"]), 60)
        self._note(f"szew Z TWOICH PADÓW: wyjście {ma}:{sa:02d} → wejście "
                   f"{mb}:{sb:02d} · {info['beats']} uderzeń "
                   f"@ {info['bpm']:.1f} BPM · P zatrzymuje")
        self._tick_player()

    def _cue_wpisz_czas(self) -> None:
        """T: edycja czasu W KRATCE pada + lista gotowych czasów fraz
        (życzenie Janka 09.08: „edytujmy timing zaraz obok hot cue,
        z dropdownem gotowych timingów fraz")."""
        from dancelab.tui.cue_podglad import _mmss, propozycje_czasu
        pady = self._cue_pady_teraz()
        p = pady.get(self._cue_wybor)
        if p is None:
            return
        analiza = self._ctx["by_id"][self._cue_track]
        self._cue_czas_bufor = _mmss(p["position_ms"])
        # frazy też startują na początku taktu (Janek 09.08)
        self._cue_prop = propozycje_czasu(analiza, p.get("silnik_ms"),
                                          downbeaty=self._cue_takty())
        self._cue_prop_i = 0
        self._render_cue_karta()

    def _cue_ustaw_czas(self, tekst: str) -> None:
        """Enter w polu czasu: parsowanie, kwantyzacja, przesunięcie pada."""
        from dancelab.tui.cue_edycje import (czas_po_kwantyzacji, parsuj_czas,
                                             przesun)
        from dancelab.tui.cue_podglad import _mmss
        pady = self._cue_pady_teraz()
        p = pady.get(self._cue_wybor)
        if p is None:
            self._cue_czas_bufor = None
            return
        analiza = self._ctx["by_id"][self._cue_track]
        sekundy = parsuj_czas(tekst)
        if sekundy is None:
            self._note(f'nie rozumiem czasu „{tekst}” — wpisz np. 2:31 '
                       f'albo 151')
            return
        dlugosc = analiza.track.duration_sec or 0
        if dlugosc and sekundy > dlugosc:
            self._note(f"{tekst} jest za końcem utworu "
                       f"({_mmss(int(dlugosc * 1000))}) — pad zostaje")
            return
        cel, powod = czas_po_kwantyzacji(analiza.beatgrid, sekundy,
                                         self._cue_takty())
        bpm = (analiza.beatgrid.bpm if analiza.beatgrid else 0) or 120.0
        beat = 60000.0 / bpm
        uderzenia = int(round((cel * 1000 - p["position_ms"]) / beat))
        nowa = przesun(self._cue_edycje, self._cue_track, self._cue_wybor,
                       uderzenia, bpm, p.get("silnik_ms"), p["position_ms"])
        self._log_verdict("cue_czas_wpisany", track_id=self._cue_track,
                          pad=self._cue_wybor, wpisane_sec=sekundy,
                          position_ms=nowa)
        self._note(f"pad {self._cue_wybor} → {_mmss(nowa)} · {powod}")
        self._cue_czas_bufor = None
        self._render_cue_lista()

    def _cue_posluchaj(self) -> None:
        """P/Spacja w edytorze cue (etap 3): gra TEN utwór od wybranego pada
        (bez pada — od zera); drugi raz zatrzymuje. Dźwięk wyłącznie z tego
        jawnego klawisza — twarda zasada projektu."""
        if not self._cue_track:
            return
        analiza = self._ctx["by_id"].get(self._cue_track)
        if analiza is None:
            return
        powod = self._bez_pliku(analiza.track)
        if powod:
            self._note(powod)
            return
        sciezka = analiza.track.source_path
        if self._odtwarzacz.gra() and self._odtwarzacz.sciezka == sciezka:
            self._odtwarzacz.stop()
            self._note("odsłuch zatrzymany")
            return
        bpm = analiza.beatgrid.bpm if analiza.beatgrid else None
        if self._cue_wybor:
            pady = self._cue_pady_teraz()
            p = pady.get(self._cue_wybor)
            sekunda = (p["position_ms"] / 1000.0) if p else 0.0
            blad = self._odtwarzacz.graj_od(sciezka, bpm, sekunda)
            gdzie = f"od pada {self._cue_wybor}"
        else:
            blad = self._odtwarzacz.graj_od_zera(sciezka, bpm)
            gdzie = "od zera"
        if blad:
            # błąd odsłuchu MUSI być widoczny od razu (dymek), nie tylko
            # w schowanych notkach — lekcja z niemego P w Ghostty (09.08)
            self.notify(f"odsłuch nie wyszedł: {blad}", severity="warning")
            self._note(f"odsłuch nie wyszedł: {blad}")
        else:
            self._note(f"gra {gdzie}")

    def _wyslij_cue(self) -> None:
        """W w zakładce Eksport/Cue: pady z ekranu → hot cue w Rekordboksie.

        DWA NACIŚNIĘCIA (wzorzec całej aplikacji dla rzeczy nieodwracalnych):
        pierwsze liczy i pokazuje, co dokładnie się stanie; drugie zapisuje.
        Polityka kolizji: NIGDY nie nadpisujemy padów, które ustawiłeś sam —
        nasz pad ustępuje Twojemu i mówimy o tym wprost."""
        if self._cue_plan is None or not self._order or not self._ctx:
            self._note("najpierw zbuduj set (B) — wtedy będzie co wysyłać")
            return
        from dancelab.ingestion.playlist_publish import rekordbox_running
        if rekordbox_running():
            self._note("Rekordbox OTWARTY — zamknij go przed zapisem cue")
            self.notify("Rekordbox otwarty — zapis cue zablokowany",
                        severity="warning")
            return
        if getattr(self, "_cue_zapis_gotowy", None) is None:
            self._cue_przygotuj_zapis()
        else:
            self._cue_zapisz_worker()

    @work(thread=True, exclusive=True, group="cue-zapis")
    def _cue_przygotuj_zapis(self) -> None:
        """Krok 1: policz plan i kolizje NA ŻYWEJ bazie, ale niczego nie
        zapisuj — DJ ma najpierw zobaczyć liczby."""
        from dancelab.tui import cue_zapis as CZ
        ui = self.call_from_thread
        ui(self._note, "cue: liczę plan i sprawdzam kolizje z Twoimi padami…")
        try:
            content_ids = CZ.mapa_content_id()
            plan, ids_setu, pominiete = CZ.zbuduj_plan_do_zapisu(
                self._cue_plan, self._cue_edycje, self._ctx["by_id"],
                list(self._order), content_ids)
            from dancelab.ingestion.rekordbox_cue_writer import (
                _open, read_existing_cues)
            from dancelab.ingestion.playlist_publish import PIONEER
            db, tables = _open(PIONEER / "master.db")
            try:
                istniejace = read_existing_cues(db, tables)
            finally:
                db.close()
            from dancelab.ingestion import cue_ledger
            wynik = CZ.policz_kolizje(plan, istniejace, cue_ledger.wczytaj())
        except Exception as exc:  # noqa: BLE001 — powód, nie traceback
            ui(self._note, f"cue: przygotowanie nie wyszło: {exc}")
            return
        self._cue_zapis_gotowy = (wynik["plan"], ids_setu)
        ui(self._refresh_status)   # przycisk ma od razu pokazać POTWIERDŹ
        for nazwa in pominiete[:5]:
            ui(self._note, f"cue: utwór spoza kolekcji RB (pominięty): {nazwa}")
        ui(self._note,
           f"cue GOTOWE DO ZAPISU: {wynik['do_zapisu']} padów na "
           f"{len(wynik['plan'].tracks)} utworach"
           + (f" (w tym {wynik['odswiezone']} odświeżamy po sobie)"
              if wynik.get("odswiezone") else "")
           + f" · Twoich padów nie ruszam "
           f"({wynik['pominiete_kolizje']} naszych ustąpiło)"
           + (f" · {len(pominiete)} utworów spoza kolekcji" if pominiete else "")
           + " — naciśnij W jeszcze raz, żeby zapisać (backup automatyczny)")
        ui(self.notify, f"W jeszcze raz = zapis {wynik['do_zapisu']} padów")

    @work(thread=True, exclusive=True, group="cue-zapis")
    def _cue_zapisz_worker(self) -> None:
        """Krok 2: zapis przez sprawdzoną warstwę bezpieczeństwa (odmowa przy
        otwartym RB, backup, weryfikacja odczytem, auto-przywrócenie)."""
        import time
        from dancelab.ingestion.playlist_publish import BACKUP_DIR, PIONEER
        from dancelab.ingestion.rekordbox_cue_writer import write_plan
        ui = self.call_from_thread
        plan, _ids = self._cue_zapis_gotowy
        ui(self._note, "cue: zapisuję (backup przed zmianą)…")
        try:
            wynik = write_plan(
                plan,
                db_path=PIONEER / "master.db",
                backup_dir=BACKUP_DIR,
                timestamp=time.strftime("%Y%m%d_%H%M%S"),
                meta={"zrodlo": "TUI edytor cue", "plan": self._plan_name},
                safe_swap=True)
        except Exception as exc:  # noqa: BLE001
            self._cue_zapis_gotowy = None
            ui(self._refresh_status)
            ui(self._note, f"cue: ZAPIS NIEUDANY — {exc}")
            ui(self.notify, "zapis cue nieudany — szczegóły w notkach (L)",
               severity="error")
            return
        self._cue_zapis_gotowy = None
        from dancelab.ingestion import cue_ledger
        cue_ledger.zapamietaj(wynik.inserted,
                              znacznik=time.strftime("%Y-%m-%d %H:%M"))
        ui(self._note,
           f"✅ cue zapisane: {wynik.written} padów"
           + (f", usunięte {wynik.deleted}" if wynik.deleted else "")
           + f" · backup {wynik.backup_path}")
        ui(self._note, "cue: OTWÓRZ Rekordboksa — pady widać dopiero po jego "
                       "starcie (czyta bazę przy uruchomieniu)")
        ui(self.notify, f"✅ {wynik.written} padów w Rekordboksie")
        ui(self._refresh_status)

    def _cue_zdejmij(self) -> None:
        from dancelab.tui import cue_edycje
        cue_edycje.zdejmij(self._cue_edycje, self._cue_track, self._cue_wybor)
        self._log_verdict("cue_zdjecie", track_id=self._cue_track,
                          pad=self._cue_wybor)
        self._cue_wybor = None
        self._render_cue_lista()

    def _cue_cofnij(self) -> None:
        from dancelab.tui import cue_edycje
        if cue_edycje.cofnij(self._cue_edycje):
            self._note("cofnięte")
            self._render_cue_lista()
        else:
            self._note("nie ma czego cofać")

    def action_gatunki(self) -> None:
        """Ctrl+G: OTWIERA i ZAMYKA listę gatunków z Twojej biblioteki
        w taksonomii Beatportu. Wyboru dokonuje ENTER — strzałkami stajesz
        na gatunku, Enter go dodaje albo zdejmuje, a lista zostaje otwarta,
        bo gatunków wybiera się kilka (życzenie Janka 09.08: „Ctrl+G dopiero
        zamyka, Enter dodaje")."""
        from dancelab.tui import gatunki as G
        if self.query_one("#suggest").has_class("open") \
                and self._panel_mode == "gatunki":
            self._close_panel()
            self.query_one("#set", DataTable).focus()
            return
        if not self._lib:
            self._note("Biblioteka jeszcze się ładuje — gatunki za chwilę")
            return
        if not G.policz(self._lib):
            self._note("żaden utwór w puli nie ma gatunku — otaguj "
                       "w Rekordboksie albo wpisz ręcznie")
            return
        mam, wszystkich, bez = G.pokrycie(self._lib)
        self._open_suggest_panel(
            None,
            f"GATUNKI — masz {mam} z {wszystkich} gatunków Beatportu"
            + (f" · {bez} bez tagu" if bez else "")
            + "\nEnter dodaje/zdejmuje · Ctrl+G albo Esc zamyka",
            self._opcje_gatunkow(), "gatunki")

    def _opcje_gatunkow(self) -> list[tuple[str, str]]:
        """Lista do panelu; wybrane gatunki niosą ✓, żeby było widać stan
        BEZ patrzenia w pole briefu."""
        from dancelab.tui import gatunki as G
        wpisane = self.query_one("#styles", Input).value
        opcje: list[tuple[str, str]] = []
        for sekcja, pozycje in G.policz(self._lib):
            opcje.append((f"— {sekcja} —", f"__{sekcja}"))
            for nazwa, ile in pozycje:
                znak = "✓" if G.jest_wybrany(wpisane, nazwa) else " "
                opcje.append((f" {znak} {nazwa}  ({ile})", nazwa))
        return opcje

    def _gatunek_enterem(self, wybor: str) -> None:
        """Enter na gatunku: dopisz albo zdejmij, lista zostaje otwarta."""
        from dancelab.tui import gatunki as G
        pole = self.query_one("#styles", Input)
        pole.value = G.przelacz(pole.value, wybor)
        lst = self.query_one("#suggest-list", OptionList)
        gdzie = lst.highlighted
        lst.clear_options()
        for label, oid in self._opcje_gatunkow():
            lst.add_option(Option(label, id=oid))
        if gdzie is not None:
            lst.highlighted = min(gdzie, lst.option_count - 1)
        self._note(f"gatunki: {pole.value or '(puste — bez filtra)'}")

    def action_grupy_dj(self) -> None:
        """Ctrl+D: OTWIERA i ZAMYKA listę kotwic pogrupowanych po BRZMIENIU
        (zmierzone klastry centroidów, nie gatunek). Wyboru dokonuje ENTER —
        kotwica jest jedna, więc Enter ją ustawia i zamyka listę."""
        if self.query_one("#suggest").has_class("open") \
                and self._panel_mode == "dj":
            self._close_panel()
            self.query_one("#set", DataTable).focus()
            return
        try:
            naglowek, opcje = self._dj_panel_opcje()
        except Exception as exc:  # noqa: BLE001 — brak pliku to stan, nie awaria
            self._note(f"kotwice niedostępne: {exc}")
            return
        self._open_suggest_panel(None, naglowek, opcje, "dj")

    def _dj_panel_opcje(self) -> tuple[str, list[tuple[str, str]]]:
        """Panel „Brzmi jak…": twoje brzmienie → TWOJA KOLEKCJA (✓, decyzja
        Janka 12.08 ze ściany kart) → grupy brzmieniowe. K w panelu zbiera."""
        from dancelab.decision.anchors import MOJE_ULUBIONE, load_anchor_book
        from dancelab.tui import grupy_dj as G
        from dancelab.tui.user_store import kolekcja_djow
        book = load_anchor_book()
        grupy = G.grupuj(book["djs"])
        kol = kolekcja_djow(self._user_state)
        opis_dj = {dj: (n, skok) for _e, czl in grupy for dj, n, skok in czl}
        # karta w zakładce DJ-e czyta stąd: (wektory, skok, etykieta grupy)
        self._dj_info = {dj: (n, skok, etykieta)
                         for etykieta, czl in grupy for dj, n, skok in czl}
        opcje: list[tuple[str, str]] = []
        ilu = len(self._user_state.get("ulubione_utwory", []))
        opcje.append(("— twoje brzmienie —", "__twoje"))
        opcje.append((f"  {MOJE_ULUBIONE} ({ilu} utworów) — kotwica policzona "
                      f"z Twoich ♥, gdy Twojego DJ-a tu nie ma", MOJE_ULUBIONE))
        if kol:
            opcje.append((f"— twoja kolekcja ({len(kol)}) — pierwszeństwo "
                          f"w polu Brzmi jak… —", "__kolekcja"))
            for dj in kol:
                if dj in opis_dj:
                    n, skok = opis_dj[dj]
                    opcje.append((f"  ✓ {G.opis(dj, n, skok)}", dj))
                else:
                    opcje.append((f"  ✓ {dj}", dj))
        kol_set = set(kol)
        for etykieta, czlonkowie in grupy:
            # zebrani są już wyżej, w sekcji kolekcji — lista opcji nie
            # przyjmuje dwóch pozycji o tym samym id (złapane testem 12.08)
            zostali = [w for w in czlonkowie if w[0] not in kol_set]
            if not zostali:
                continue
            opcje.append((f"— {etykieta} ({len(zostali)}) —",
                          f"__{etykieta[:20]}"))
            opcje.extend((f"  {G.opis(dj, n, skok)}", dj)
                         for dj, n, skok in zostali)
        naglowek = (
            f"BRZMI JAK… — {len(book['djs'])} DJ-ów ZMIERZONYCH z ich setów; "
            f"kogo tu nie ma, tego nie mierzyliśmy\n"
            f"Enter wybiera kotwicę · K dodaje/zdejmuje z kolekcji "
            f"(✓ = pierwszeństwo w polu) · Ctrl+D albo Esc zamyka")
        return naglowek, opcje

    def _kolekcja_przelacz(self, dj: str) -> bool:
        """Wspólny rdzeń K (panel i zakładka DJ-e): przełącz kolekcję,
        zapisz stan, przestaw pole „Brzmi jak…" i powiedz co się stało."""
        from dancelab.tui.user_store import (kolekcja_djow,
                                             przelacz_kolekcje_dj, save_state)
        teraz = przelacz_kolekcje_dj(self._user_state, dj)
        save_state(self._user_state, self.processed_dir)
        self._load_anchors()
        n = len(kolekcja_djow(self._user_state))
        self._note(f"{dj} {'w kolekcji' if teraz else 'poza kolekcją'} · "
                   f"kolekcja: {n} — kolejność pola Brzmi jak… przestawiona")
        return teraz

    def _dj_pod_kursorem(self, lst: OptionList) -> str | None:
        from dancelab.decision.anchors import MOJE_ULUBIONE
        i = lst.highlighted
        if i is None:
            return None
        dj = lst.get_option_at_index(i).id or ""
        if dj.startswith("__") or dj == MOJE_ULUBIONE:
            self._note("kolekcja przyjmuje DJ-ów — najedź na nazwisko")
            return None
        return dj

    def _przelacz_kolekcje_dj_z_panelu(self) -> None:
        """K w panelu „Brzmi jak…": zbierz/wypuść DJ-a pod kursorem.
        Lista zostaje otwarta (wzór dwóch naciśnięć jak przy gatunkach),
        a pole „Brzmi jak…" od razu przestawia kolejność."""
        lst = self.query_one("#suggest-list", OptionList)
        dj = self._dj_pod_kursorem(lst)
        if dj is None:
            return
        self._kolekcja_przelacz(dj)
        _n, opcje = self._dj_panel_opcje()
        gdzie = lst.highlighted
        lst.clear_options()
        for label, oid in opcje:
            lst.add_option(Option(label, id=oid))
        if gdzie is not None:
            lst.highlighted = min(gdzie, lst.option_count - 1)
        self._render_dj_tab()

    MAX_KART = 48

    def _render_dj_tab(self, fokus_dj: str | None = None) -> None:
        """Ściana kart jak w GUI: kolekcja najpierw (pełny kolor), potem
        pełne profile z mapy, potem reszta przygaszona — z filtrami
        i paskiem podglądu pola „Brzmi jak…". Limit MAX_KART z jawną notą
        (terminal montuje widżety, nie diva — bez limitu klęka)."""
        try:
            self._dj_panel_opcje()          # wypełnia _dj_info (grupy)
        except Exception as exc:  # noqa: BLE001 — brak księgi to stan, nie awaria
            self.query_one("#dj-licznik", Static).update(
                f"księga kotwic niedostępna: {exc}")
            return
        from dancelab.tui import dj_profile as P
        from dancelab.tui.user_store import kolekcja_djow, w_kolekcji
        if not hasattr(self, "_dj_profile"):
            self._dj_profile = P.wczytaj()
        info = self._dj_info
        kol = [d for d in kolekcja_djow(self._user_state) if d in info]
        prof = {d: P.znajdz(self._dj_profile, d) for d in info}
        filtr = getattr(self, "_dj_filtr", "all")

        self._dj_edycje_filtry = self._policz_edycje(prof)
        self._domontuj_filtry_edycji()

        w_kol = set(kol)
        pelni = sorted((d for d in info if d not in w_kol
                        and prof[d] and "bpm_med" in prof[d]),
                       key=lambda d: -prof[d].get("szwy_pelne", 0))
        reszta = sorted(d for d in info
                        if d not in w_kol and d not in set(pelni))
        wybor = [*kol, *pelni, *reszta]
        if filtr == "kolekcja":
            wybor = [d for d in wybor if d in w_kol]
        elif filtr.startswith("edycja:"):
            ed = filtr.split(":", 1)[1]
            wybor = [d for d in wybor
                     if prof[d] and ed in prof[d].get("edycje", [])]
        uciete = max(0, len(wybor) - self.MAX_KART)
        wybor = wybor[:self.MAX_KART]

        sciana = self.query_one("#dj-sciana", Grid)
        sciana.remove_children()
        self._dj_karty = []
        for d in wybor:
            jest = w_kolekcji(self._user_state, d)
            tresc = P.karta(d, prof[d], jest,
                            info[d][2] if d in info else None)
            karta = KartaDJ(d, tresc, jest)
            self._dj_karty.append(karta)
            sciana.mount(karta)

        pelne = sum(1 for v in prof.values() if v and "bpm_med" in v)
        nota = (f" · pokazuję {len(wybor)}, resztę ({uciete}) zawęź filtrem"
                if uciete else "")
        self.query_one("#dj-licznik", Static).update(
            f"[b]DJ-e[/b] · w kolekcji: [b]{len(kol)}[/b] z {len(info)} "
            f"zmierzonych · pełnych profili z mapy: {pelne}{nota}   —   "
            f"żadnych ocen, tylko jak kto gra · K zbiera · Enter = kotwica")
        self._render_dj_brzmi(kol, wybor)
        if fokus_dj and fokus_dj in wybor:
            self._dj_karty[wybor.index(fokus_dj)].focus()

    def _policz_edycje(self, prof: dict) -> list[str]:
        from collections import Counter
        c = Counter(ed for v in prof.values() if v
                    for ed in v.get("edycje", []))
        return [ed for ed, _n in c.most_common(3)]

    def _domontuj_filtry_edycji(self) -> None:
        """Guziki edycji (np. „Garbicz 2026") montują się raz, z danych."""
        pasek = self.query_one("#dj-filtry", Horizontal)
        if len(pasek.children) > 2:
            return
        for i, ed in enumerate(self._dj_edycje_filtry):
            pasek.mount(Button(ed, id=f"dj-f-e{i}"))

    def _render_dj_brzmi(self, kol: list[str], widoczni: list[str]) -> None:
        czesci = [f"[#d6f549]✓ {d}[/]" for d in kol]
        czesci += [f"[dim]{d}[/]" for d in widoczni
                   if d not in set(kol)][:max(0, 6 - len(kol))]
        ogon = len(self._dj_info) - len(kol)
        self.query_one("#dj-brzmi", Static).update(
            "[dim]tak ułoży się pole „Brzmi jak…”:[/]  "
            + " · ".join(czesci) + f"  [dim]… i {ogon} kolejnych[/]")

    def _ustaw_dj_filtr(self, filtr: str, guzik_id: str) -> None:
        self._dj_filtr = filtr
        for b in self.query_one("#dj-filtry", Horizontal).children:
            if isinstance(b, Button):
                b.variant = "primary" if b.id == guzik_id else "default"
        self._render_dj_tab()
        karty = getattr(self, "_dj_karty", [])
        if karty:
            karty[0].focus()

    def _kolekcja_z_karty_sciennej(self, dj: str) -> None:
        self._kolekcja_przelacz(dj)
        self._render_dj_tab(fokus_dj=dj)

    def _kotwica_z_karty_sciennej(self, dj: str) -> None:
        self._ustaw_kotwice(dj)
        self._note(f"kotwica: {dj} — pole „Brzmi jak…” ustawione, "
                   f"brief czeka w zakładce Set")

    def _ruch_po_scianie(self, karta, klawisz: str) -> None:
        """Strzałki chodzą PO KARTACH jak po kafelkach: lewo/prawo ±1,
        góra/dół ±szerokość siatki."""
        karty = getattr(self, "_dj_karty", [])
        if karta not in karty:
            return
        i = karty.index(karta)
        krok = {"left": -1, "right": 1, "up": -3, "down": 3}[klawisz]
        j = max(0, min(len(karty) - 1, i + krok))
        karty[j].focus()
        karty[j].scroll_visible()

    def action_next_tab(self) -> None:
        self._switch_tab(+1)

    def action_prev_tab(self) -> None:
        self._switch_tab(-1)

    def _switch_tab(self, delta: int) -> None:
        # sfokusowana karta DJ-a przyciąga TabbedContent z powrotem do
        # swojej zakładki (Textual aktywuje panel z fokusem) — zdejmujemy
        # fokus PRZED przełączeniem, inaczej Ctrl+Tab cichnie
        if isinstance(self.focused, KartaDJ):
            self.set_focus(None)
        tc = self.query_one("#tabs", TabbedContent)
        i = _TAB_ORDER.index(tc.active) if tc.active in _TAB_ORDER else 0
        tc.active = _TAB_ORDER[(i + delta) % len(_TAB_ORDER)]
        self.refresh_bindings()

    def on_tabbed_content_tab_activated(self, event) -> None:
        self.refresh_bindings()              # klik w zakładkę też odświeża pasek
        pane = getattr(event, "pane", None)
        if pane is not None and pane.id != "tab-dj" \
                and isinstance(self.focused, KartaDJ):
            self.set_focus(None)         # klik w nagłówek zakładki też
        if pane is not None and pane.id == "tab-export":
            # podgląd liczy się przy każdym wejściu — po edycjach setu też;
            # fokus na listę, żeby litery/strzałki edytora działały od razu
            self._cue_podglad_worker()
            self.query_one("#cue-table", DataTable).focus()
        if pane is not None and pane.id == "tab-dj":
            # wejście w DJ-e = od razu pełna karta pod fokusem
            karty = getattr(self, "_dj_karty", [])
            if karty and self.focused not in karty:
                karty[0].focus()

    # --------------------------------------------------------- Eksport / Cue

    @work(thread=True, exclusive=True, group="cue")
    def _cue_podglad_worker(self) -> None:
        """Etap 1 edytora cue: propozycje padów dla BIEŻĄCEGO setu (po
        edycjach). Tylko podgląd — zapis do Rekordboksa to etap 4."""
        from dancelab.tui.cue_podglad import zbuduj_plan_cue
        ui = self.call_from_thread
        head = self.query_one("#cue-head", Static)
        info = self.query_one("#cue-info", Static)
        tabela = self.query_one("#cue-table", DataTable)
        if not self._order or not self._ctx:
            ui(head.update, "Brak setu — zbuduj go w zakładce Set (B); "
                            "wtedy zobaczysz tu propozycje padów.")
            ui(tabela.clear)
            ui(self.query_one("#cue-os", Static).update, "")
            ui(self.query_one("#cue-pady", Static).update, "")
            ui(info.update, "")
            return
        ui(head.update, "Liczę okna przejść dla bieżącego setu…")
        order = list(self._order)
        by_id = self._ctx["by_id"]
        try:
            from dancelab.ingestion.rekordbox_siatka import (
                downbeaty_dla_sciezki)
            plan = zbuduj_plan_cue(order, by_id, self._ctx["weights"],
                                   downbeaty_dla=downbeaty_dla_sciezki)
        except Exception as exc:  # noqa: BLE001
            ui(head.update, f"Podgląd cue nie wyszedł: {exc}")
            return
        self._cue_plan = plan
        ui(self._render_cue_lista)

    _CUE_OS_SZER = 36        # oś w liście (komórki)
    _CUE_KARTA_SZER = 64     # oś w karcie

    def _cue_nazwa(self, tid: str) -> str:
        a = self._ctx["by_id"].get(tid)
        if a is None:
            return tid
        art, tit = _wykonawca_tytul(a.track)
        # tag tytułu często niesie już artystę („O'Flynn - Sekete") — nie
        # dublować („O'Flynn – O'Flynn – Sekete"; skarga Janka 09.08)
        if art and tit.lower().startswith(art.lower()):
            reszta = tit[len(art):].lstrip(" -–—")
            if reszta:
                tit = reszta
        return f"{art} – {tit}" if art else tit

    def _render_cue_lista(self) -> None:
        """Lista: jeden wiersz = jeden utwór, z osią energii i literami padów
        (sparkline Tufte'a — decyzja Janka 08.08 po wecie na wiersz-na-cue).

        Każda zmiana padów unieważnia policzony plan zapisu — inaczej drugie
        W zapisałoby stan sprzed edycji."""
        self._cue_zapis_gotowy = None
        from rich.text import Text
        from dancelab.tui import cue_edycje
        from dancelab.tui.cue_podglad import (czas_utworu, komorka_pada,
                                              os_energii)
        tabela = self.query_one("#cue-table", DataTable)
        head = self.query_one("#cue-head", Static)
        info = self.query_one("#cue-info", Static)
        plan = self._cue_plan
        by_id = self._ctx["by_id"]
        tabela.clear()
        self._cue_widok = [t for t in self._order if t in by_id]
        razem, pewne = 0, 0
        for poz, tid in enumerate(self._cue_widok, start=1):
            pady = cue_edycje.efektywne_pady(plan, self._cue_edycje, tid)
            razem += len(pady)
            ok = sum(1 for p in pady.values() if p["confident"])
            pewne += ok
            dur = czas_utworu(by_id[tid])
            os = list(os_energii(by_id[tid], self._CUE_OS_SZER))
            tekst = Text()
            zajete = {}
            for litera, p in pady.items():
                zajete[komorka_pada(p["position_ms"], dur,
                                    self._CUE_OS_SZER)] = litera
            for i, znak in enumerate(os):
                if i in zajete:
                    tekst.append(zajete[i], style=f"bold {PILLAR_COLOR}")
                else:
                    tekst.append(znak, style="dim")
            watpliwe = len(pady) - ok
            tabela.add_row(str(poz), self._cue_nazwa(tid)[:30], tekst,
                           str(len(pady)),
                           f"{ok}✓ {watpliwe}?" if pady else "—")
        head.update(
            f"Pady bieżącego setu: {razem} cue na {len(self._cue_widok)} "
            f"utworów · ✓ pewne: {pewne} — TYLKO PODGLĄD, nic nie zapisuję")
        linie = [f"⚠ {w}" for w in plan.warnings[:3]]
        if len(plan.warnings) > 3:
            linie.append(f"…i {len(plan.warnings) - 3} dalszych ostrzeżeń")
        linie.append("litera A–H = wybierz pad (pusty slot = postaw) · "
                     "TA SAMA litera drugi raz = przenieś pod głowicę · "
                     "T = wpisz czas z klawiatury (dociągnę do taktu) · "
                     "←/→ ±1 TAKT (Shift ±8, PgUp/PgDn ±32) · "
                     "P posłuchaj utwór · S posłuchaj SZEW do następnego "
                     "(z Twoich padów) · X zdejmij · Z cofnij · W wysyła cue")
        info.update("\n".join(linie))
        if self._cue_widok:
            if self._cue_track not in self._cue_widok:
                self._cue_track = self._cue_widok[0]
            tabela.move_cursor(row=self._cue_widok.index(self._cue_track))
        self._render_cue_karta()

    def _render_cue_karta(self) -> None:
        """Karta utworu pod listą — terminalowy deck: energia, sekcje, pady
        na osi, podziałka i lista padów. Propozycja silnika zostaje widoczna
        (kropka) po każdym ręcznym przesunięciu."""
        from rich.text import Text
        from dancelab.tui import cue_edycje
        from dancelab.tui.cue_podglad import (TYPY_PO_POLSKU, _mmss,
                                              czas_utworu, komorka_pada,
                                              linijka_czasu, os_energii,
                                              pas_sekcji)
        os_w = self.query_one("#cue-os", Static)
        pady_w = self.query_one("#cue-pady", Static)
        tid = self._cue_track
        if not tid or self._cue_plan is None or tid not in self._ctx["by_id"]:
            os_w.update("")
            pady_w.update("")
            return
        analiza = self._ctx["by_id"][tid]
        dur = czas_utworu(analiza)
        # szerokość osi z REALNEGO widgetu (kolumna zwęziła się o tabelkę
        # padów po prawej — stała szerokość zawijała wiersze)
        szer = max(os_w.content_size.width - 10, 20) or self._CUE_KARTA_SZER
        pady = cue_edycje.efektywne_pady(
            self._cue_plan, self._cue_edycje, tid)
        bg = analiza.beatgrid
        naglowek = Text()
        naglowek.append(f"{self._cue_nazwa(tid)[:44]} ", style="bold")
        if bg and bg.bpm:
            naglowek.append(f"· {bg.bpm:g} BPM ", style="dim")
        if analiza.track.key_estimate:
            naglowek.append(f"· {analiza.track.key_estimate} ", style="dim")
        if self._cue_wybor:
            naglowek.append(
                f"· pad {self._cue_wybor}: {self._cue_wybor} jeszcze raz = "
                f"przenieś pod głowicę · T = wpisz czas · ←/→ ±1 TAKT "
                f"(Shift ±8) · P posłuchaj · X zdejmij · Esc",
                style=f"bold {PILLAR_COLOR}")
        else:
            naglowek.append("· litera A–H = wybierz/postaw pad · "
                            "P = posłuchaj", style="dim")
        linia_padow = [" "] * szer
        kropki = {}
        for litera, p in pady.items():
            linia_padow[komorka_pada(p["position_ms"], dur, szer)] = litera
            if p["zrodlo"] == "reka" and p.get("silnik_ms") is not None:
                kropki[komorka_pada(p["silnik_ms"], dur, szer)] = True
        pady_t = Text("pady     ")
        for i, znak in enumerate(linia_padow):
            if znak != " ":
                styl = (f"bold reverse {PILLAR_COLOR}"
                        if znak == self._cue_wybor else f"bold {PILLAR_COLOR}")
                pady_t.append(znak, style=styl)
            elif i in kropki:
                pady_t.append("·", style="dim")
            else:
                pady_t.append(" ")
        # LEWA KOLUMNA: oś utworu (energia, sekcje, pady na osi, czas)
        tekst = Text()
        tekst.append_text(naglowek)
        tekst.append("\n")
        tekst.append("energia  ", style="dim")
        tekst.append(os_energii(analiza, szer))
        tekst.append("\n")
        sekcje = pas_sekcji(analiza, szer)
        if sekcje:
            tekst.append("sekcje   ", style="dim")
            tekst.append(sekcje, style="dim")
            tekst.append("\n")
        tekst.append_text(pady_t)
        tekst.append("\n")
        tekst.append("czas     ", style="dim")
        tekst.append(linijka_czasu(dur, szer), style="dim")
        os_w.update(tekst)

        # PRAWA KOLUMNA: pady w SIATCE 2×4, jak pady na CDJ-u
        # (życzenie Janka 09.08). Puste sloty widoczne — to one mówią
        # „tu możesz postawić kolejny"; szczegóły wybranego pod siatką,
        # żeby kratka została czytelna.
        from dancelab.tui.cue_edycje import PADY
        tab = Text()
        tab.append("HOT CUE\n", style="bold")
        for rzad in (PADY[:4], PADY[4:]):
            for litera in rzad:
                p = pady.get(litera)
                wybrany = litera == self._cue_wybor
                if p is None:
                    tab.append("▶" if wybrany else " ",
                               style=f"bold {PILLAR_COLOR}")
                    tab.append(f"{litera} ", style="dim")
                    tab.append("—     ", style="dim")
                    continue
                styl = (f"bold reverse {PILLAR_COLOR}" if wybrany
                        else f"bold {PILLAR_COLOR}")
                tab.append("▶" if wybrany else " ",
                           style=f"bold {PILLAR_COLOR}")
                tab.append(f"{litera} ", style=styl)
                if wybrany and self._cue_czas_bufor is not None:
                    # EDYCJA W KRATCE: wartość pisze się tam, gdzie stoi
                    tab.append(f"{self._cue_czas_bufor}▏",
                               style="bold reverse")
                    tab.append(" ")
                    continue
                m, sek = divmod(int(p["position_ms"] / 1000), 60)
                tab.append(f"{m}:{sek:02d} ", style="bold" if wybrany else "")
                if p["zrodlo"] == "reka":
                    tab.append("✋", style="yellow")
                else:
                    tab.append("✓" if p["confident"] else "?",
                               style="green" if p["confident"] else "yellow")
            tab.append("\n")
        if self._cue_czas_bufor is not None:
            from dancelab.tui.cue_podglad import _mmss as _mm
            ile = len(self._cue_prop)
            okno = 6                       # widok przewija się po całej liście
            start = max(0, min(self._cue_prop_i - okno // 2, ile - okno))
            licznik = (f" {self._cue_prop_i + 1}/{ile}" if ile else "")
            tab.append(f"\nwpisz czas albo wybierz frazę (↑↓){licznik}:\n",
                       style="dim")
            if start > 0:
                tab.append(f"  ↑ {start} wyżej\n", style="dim")
            for i in range(start, min(start + okno, ile)):
                etykieta, sek = self._cue_prop[i]
                wskazany = i == self._cue_prop_i
                tab.append("▸ " if wskazany else "  ",
                           style=f"bold {PILLAR_COLOR}" if wskazany else "")
                tab.append(f"{etykieta:<8} {_mm(int(sek * 1000)):>7}\n",
                           style="" if wskazany else "dim")
            if start + okno < ile:
                tab.append(f"  ↓ {ile - start - okno} niżej\n", style="dim")
            if not self._cue_prop:
                tab.append("  (ten utwór nie ma segmentacji — wpisz ręcznie)\n",
                           style="dim")
            tab.append("Enter zatwierdź · Esc anuluj", style="dim")
            pady_w.update(tab)
            return
        wyb = pady.get(self._cue_wybor or "")
        if wyb is not None:
            from dancelab.ingestion.rekordbox_siatka import numer_taktu
            takt = numer_taktu(self._cue_takty(),
                               wyb["position_ms"] / 1000.0)
            tab.append(f"\n{self._cue_wybor} · ", style=f"bold {PILLAR_COLOR}")
            tab.append(f"{TYPY_PO_POLSKU.get(wyb['typ'], wyb['typ'])} · "
                       f"{_mmss(wyb['position_ms'])}", style="dim")
            if takt is not None:
                tab.append(f" · takt {takt}.1", style="dim")
            if wyb["zrodlo"] == "reka" and wyb.get("silnik_ms") is not None:
                tab.append(f"\nręka (silnik: {_mmss(wyb['silnik_ms'])})",
                           style="dim")
            tab.append("\nX zdejmij · P posłuchaj od pada", style="dim")
        pady_w.update(tab)

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
        if not analyses and self._lib:
            return   # pusty załadunek nie kasuje niepustej biblioteki
        ui(self._set_library, analyses)

    def _set_library(self, analyses: list) -> None:
        self._lib = analyses
        from dancelab.ingestion.loudness import wczytaj_cache
        try:
            self._lib_lufs = wczytaj_cache()
        except Exception:  # noqa: BLE001
            self._lib_lufs = {}
        if analyses:
            self._lufs_worker()
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
        """ENTER (albo klik) na liście.

        W Bibliotece przełącza sekcję po lewej. W panelu gatunków i kotwic
        ZATWIERDZA wybór — konwencja z każdego programu, a skrót, którym
        panel otwarto, tylko go zamyka (życzenie Janka 09.08: „Enter dodaje
        gatunek, Ctrl+G dopiero zamyka"). Panele propozycji (Z/A/O) zostają
        przy wzorcu dwóch naciśnięć — tam Enter tylko zaznacza."""
        if getattr(event.option_list, "id", None) == "lib-side-list":
            self._set_lib_section(event.option.id)
            return
        if not self.query_one("#suggest").has_class("open"):
            return
        wybor = event.option.id
        if not wybor or wybor.startswith("__"):   # nagłówek sekcji
            return
        if self._panel_mode == "gatunki":
            event.stop()
            self._gatunek_enterem(wybor)
        elif self._panel_mode == "rola_filaru":
            event.stop()
            self._apply_rola_filaru(wybor)
        elif self._panel_mode == "dj":
            event.stop()
            self._ustaw_kotwice(wybor)
            self._close_panel()
            self.query_one("#set", DataTable).focus()
            self._note(f"kotwica: {wybor}")

    def _ustaw_kotwice(self, wybor: str) -> None:
        """Ustaw kotwicę w polu „Brzmi jak…" (i w aktywnej playliście).

        Lista w panelu i lista w polu mogą się rozjechać (np. gdy pole
        dostało opcje z innego źródła). Textual rzuca wtedy wyjątkiem
        i ubija budowę — dokładamy brakującą pozycję zamiast wywalać
        aplikację (złapane 09.08 przy dodawaniu kotwicy z ulubionych).
        Kotwica należy do playlisty: gdy jakaś jest aktywna, wybór DJ-a
        ustawia JEJ kotwicę — jawnie, z notką (Janek 12.08)."""
        pole = self.query_one("#dj", Select)
        dostepne = {w for _e, w in (pole._options or [])}
        if wybor not in dostepne:
            pole.set_options([(wybor, wybor),
                              *((e, w) for e, w in (pole._options or []))])
        pole.value = wybor
        from dancelab.tui.user_store import (aktywna_playlista, save_state,
                                             ustaw_kotwice_playlisty)
        if aktywna_playlista(self._user_state) is not None:
            ustaw_kotwice_playlisty(self._user_state, wybor)
            save_state(self._user_state, self.processed_dir)
            pl = aktywna_playlista(self._user_state)
            self._note(f"kotwica playlisty „{pl['nazwa']}” to teraz: {wybor}")
            self.notify(f"„{pl['nazwa']}” · kotwica: {wybor}", timeout=5)
            self._render_side_list()

    def _render_side_list(self) -> None:
        """Sekcje + PLAYLISTY (decyzja Janka 11.08: playlista = projekt —
        własna nazwa z metadanych, własna kotwica, własne filary z rolami)."""
        from dancelab.tui.user_store import aktywna_playlista
        side = self.query_one("#lib-side-list", OptionList)
        side.clear_options()
        side.add_option(Option("Cała biblioteka", id="all"))
        side.add_option(Option("♥ Ulubione utwory", id="fav"))
        side.add_option(Option("⚑ Filary (playlisty)", id="filary"))
        # skąd bierze się utwór (Janek 13.08). Kategorie są TRZY, nie dwie:
        # „niedostępne" to pliki lokalne na odpiętym dysku, a nie streaming —
        # i to jest rzecz, którą DJ chce zobaczyć PRZED setem.
        for sek, etyk in (("zr:dysk", f"{Z.IKONA[Z.DYSK]} Na dysku"),
                          ("zr:apple", f"{Z.IKONA[Z.APPLE]} Apple Music"),
                          ("zr:brak", f"{Z.IKONA[Z.BRAK]} Niedostępne")):
            side.add_option(Option(etyk, id=sek))
        # ile wierszy zajmują SEKCJE — playlisty zaczynają się za nimi.
        # Liczone, nie wpisane na sztywno: dołożenie sekcji przesuwało
        # podświetlenie aktywnej playlisty na przypadkowy wiersz.
        pierwsza_playlista = side.option_count
        aktywny_wiersz = None
        for i, pl in enumerate(self._user_state.get("playlisty", [])):
            if aktywna_playlista(self._user_state) is pl:
                znak, aktywny_wiersz = "▸ ", pierwsza_playlista + i
            else:
                znak = "  "
            n_utw = len(pl.get("utwory", []))
            ogon = f" · {n_utw}" if n_utw else ""
            side.add_option(Option(f"{znak}{pl['nazwa'][:24]}{ogon}",
                                   id=f"pl:{i}"))
        side.add_option(Option("＋ nowa playlista", id="pl-new"))
        # podświetlenie stoi na aktywnej playliście, nie skacze na początek
        side.highlighted = aktywny_wiersz if aktywny_wiersz is not None else 0

    def _set_lib_section(self, section: str) -> None:
        from dancelab.tui.user_store import (aktywna_playlista,
                                             nazwa_z_metadanych,
                                             nowa_playlista, save_state)
        if section == "pl-new":
            by_id = {a.track.track_id: a for a in self._lib}
            propozycja = nazwa_z_metadanych(by_id) if by_id else "Nowa playlista"

            def po_nazwie(nazwa: str | None) -> None:
                if not nazwa:
                    return
                nowa_playlista(self._user_state, nazwa)
                save_state(self._user_state, self.processed_dir)
                self._render_side_list()
                # Janek 12.08: po nazwie OD RAZU Biblioteka — DJ zaznacza
                # filary (F) do tej playlisty; kotwica nie jest wymuszonym
                # krokiem, ustawia się ją panelem „Brzmi jak…" (Ctrl+G).
                self._lib_section = "all"
                self._render_library()
                self.query_one("#lib-table", DataTable).focus()
                self._note(f"playlista „{nazwa}” utworzona i aktywna — "
                           f"F przypina filary do niej, B buduje i zapisuje "
                           f"set w playliście; kotwica: panel Brzmi jak…")
                self.notify(f"„{nazwa}” aktywna — zaznacz filary klawiszem F",
                            timeout=6)

            self.push_screen(NazwaPlaylistyScreen(propozycja), po_nazwie)
            return
        if section.startswith("pl:"):
            idx = int(section.split(":", 1)[1])
            self._user_state["aktywna_playlista"] = idx
            from dancelab.tui.user_store import save_state as _zapisz
            _zapisz(self._user_state, self.processed_dir)
            pl = aktywna_playlista(self._user_state)
            if pl and pl.get("kotwica"):
                pole = self.query_one("#dj", Select)
                dostepne = {w for _e, w in (pole._options or [])}
                if pl["kotwica"] not in dostepne:
                    pole.set_options([(pl["kotwica"], pl["kotwica"]),
                                      *((e, w)
                                        for e, w in (pole._options or []))])
                pole.value = pl["kotwica"]
            self._render_side_list()
            # Aktywacja playlisty pokazuje PEŁNĄ bibliotekę (Janek 12.08:
            # świeża playlista ma zero filarów — widok „filary" był pustą
            # ścianą i nie dało się nic wybrać). Filary tej playlisty są
            # w tabeli oznaczone F, a sekcja „Filary (playlisty)" nadal
            # pokazuje sam wybór.
            self._lib_section = "all"
            self._render_library()
            self._note(f"playlista aktywna: {pl['nazwa']} · kotwica: "
                       f"{pl.get('kotwica') or '—'} · filary: "
                       f"{len(pl['filary'])} · utwory z budowy: "
                       f"{len(pl.get('utwory', []))} — F przypina filar, "
                       f"B buduje i zapisuje set")
            self.query_one("#lib-table", DataTable).focus()
            return
        self._lib_section = section
        self._render_library()
        self.query_one("#lib-table", DataTable).focus()

    def _render_library(self, keep_cursor: bool = False) -> None:
        from dancelab.tui.user_store import resolve_tracks
        table = self.query_one("#lib-table", DataTable)
        cursor = table.cursor_row if keep_cursor else None
        self._render_w_toku = True
        if self._auto_timer is not None:
            self._auto_timer.stop()
            self._auto_timer = None
        table.clear()
        search, key, lo, hi, err = self._lib_filters()
        rows = filter_library(self._lib, search=search, key=key,
                              bpm_lo=lo, bpm_hi=hi)
        # Ten sam utwór leży w kilku folderach naraz i ma bliźniaka z Apple
        # Music: 1914 analiz to 1690 utworów. Scalamy WIDOK — pliki, analizy,
        # ulubione i filary zostają nietknięte, a licznik mówi ile scalono.
        from dancelab.tui import duplikaty as D
        kopie = D.ile_kopii(rows)
        rows, scalonych = D.scal(rows)
        from dancelab.tui.user_store import filary_wpisy
        by_id = {a.track.track_id: a for a in self._lib}
        favs, _ = resolve_tracks(self._user_state["ulubione_utwory"], by_id)
        by_path = {a.track.source_path: a.track.track_id for a in self._lib}
        role_f: dict[str, str] = {}
        for e in filary_wpisy(self._user_state):
            tid = e.get("track_id")
            if tid not in by_id:
                tid = by_path.get(e.get("path", ""))
            if tid:
                role_f[tid] = e.get("rola", "")
        favs, filary = set(favs), set(role_f)
        col, rev = self._lib_sort if self._lib_sort is not None else (3, False)
        znane = [a for a in rows if not _lib_sort_missing(
            col, a, self._lib_energy, self._lib_lufs)]
        braki = [a for a in rows if _lib_sort_missing(
            col, a, self._lib_energy, self._lib_lufs)]
        znane.sort(key=_lib_sort_key(col, favs, filary, self._lib_energy,
                                     self._lib_lufs),
                   reverse=rev)
        rows = znane + braki                 # braki zawsze na końcu
        section = getattr(self, "_lib_section", "all")
        if section == "fav":
            rows = [a for a in rows if a.track.track_id in favs]
        elif section == "filary":
            rows = [a for a in rows if a.track.track_id in filary]
        elif section.startswith("zr:"):
            chce = section.split(":", 1)[1]
            rows = [a for a in rows if Z.zrodlo(a.track.source_path) == chce]
        galeria = bool(self._user_state.get("okladki_w_liscie"))
        if galeria:
            from dancelab.tui.okladki import mozaika
        for a in rows:
            t = a.track
            conf = t.key_confidence
            en = self._lib_energy.get(t.track_id)
            dur = t.duration_sec or 0
            art_cell = (mozaika(str(t.source_path), 7, 3) or ""
                        ) if galeria else ""
            table.add_row(
                art_cell,
                "♥" if t.track_id in favs else "",
                ({"otwarcie": "F·O", "buildup": "F·B", "oddech": "F·~",
                  "zamkniecie": "F·Z"}.get(role_f.get(t.track_id, ""), "F")
                 if t.track_id in filary else ""),
                _bpm_cell(t), _key_cell(t),
                _conf_cell(t),
                f"{en:3d}" if en is not None else "—",
                (f"{self._lib_lufs[t.source_path]:5.1f}"
                 if t.source_path in self._lib_lufs else "…"),
                (t.style_label or "")[:20],
                f"{dur/60:4.1f}",
                _wykonawca_tytul(t)[0][:24],
                _wykonawca_tytul(t)[1][:36],
                # ikona źródła, a przy scalonych kopiach ich liczba
                Z.ikona(t.source_path)
                + (f"×{kopie[t.track_id]}" if kopie.get(t.track_id, 1) > 1
                   else ""),
                height=3 if galeria else 1,
            )
        self._lib_view = rows
        from dancelab.tui.user_store import aktywna_playlista
        sekcja = {"fav": "♥ Ulubione", "filary": "⚑ Filary"}.get(
            section, "Cała biblioteka")
        pl_akt = aktywna_playlista(self._user_state)
        filary_info = (f"playlista: {pl_akt['nazwa'][:22]} · filary: "
                       f"{len(pl_akt['filary'])} (min 3, max 10)"
                       if pl_akt else "filary: brak playlisty (＋ po lewej)")
        info = (f"{sekcja}: {len(rows)} z {len(self._lib)} utworów"
                + (f" (scalono {scalonych} kopii — pliki zostają)"
                   if scalonych else "")
                + f"   ·   {filary_info}"
                f"   ·   ♥ {len(self._user_state['ulubione_utwory'])}"
                f"   ·   U=♥  F=filar  G=filary do Set  K=okładki  ·  "
                + (f"sort: {self._SORT_NAMES[self._lib_sort[0]]}"
                   f"{'↑' if self._lib_sort[1] else '↓'} (3. klik kasuje)"
                   if self._lib_sort is not None else "sort: klik w nagłówek"))
        if err:
            info += f"   ·   filtr BPM: {err}"
        self.query_one("#lib-count", Static).update(info)
        self._update_lib_headers(table)
        # kursor odnajduje GRANY utwór na nowej liście (żeby zdjęcie filtra
        # nie gubiło kontekstu odsłuchu); w drugiej kolejności keep_cursor
        grany = self._odtwarzacz.sciezka
        wiersz_granego = next((i for i, a in enumerate(rows)
                               if a.track.source_path == grany), None)             if grany else None
        # ...ale TYLKO gdy lista naprawdę się zmieniła. Przy zwykłym
        # odświeżeniu (keep_cursor) skok na grany utwór wyrywał kursor spod
        # palca w trakcie przewijania — Janek 13.08: „czemu jak scroluję to
        # skacze". Odświeżenia lecą w tle (LUFS, okładki), więc widok wracał
        # co chwilę na grany wiersz.
        if wiersz_granego is not None and not keep_cursor:
            table.move_cursor(row=wiersz_granego)
        elif cursor is not None and rows:
            table.move_cursor(row=min(cursor, len(rows) - 1))
        # zdarzenia podświetlenia przychodzą PO tym kodzie — flaga schodzi
        # dopiero po przetworzeniu odświeżenia
        self.call_after_refresh(setattr, self, "_render_w_toku", False)

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

    def action_toggle_okladki(self) -> None:
        """K: to samo co przełącznik „artwork" — jedna dźwignia, dwa wejścia
        (decyzja Janka 08.08: toggle scala pokazywanie okładek z dociąganiem
        braków; OFF tylko chowa, niczego nie kasuje)."""
        przelacznik = self.query_one("#lib-artwork", Switch)
        przelacznik.value = not przelacznik.value   # resztę robi on_switch_changed

    def _przelacz_okladki_w_liscie(self) -> None:
        from dancelab.tui.user_store import save_state
        self._user_state["okladki_w_liscie"] = \
            not self._user_state.get("okladki_w_liscie")
        save_state(self._user_state, self.processed_dir)
        stan = "włączone" if self._user_state["okladki_w_liscie"] else "wyłączone"
        self._note(f"okładki w liście: {stan}")
        self._render_library(keep_cursor=True)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id != "lib-artwork":
            return
        if self._artwork_programowo:      # lustro stanu, nie decyzja użytkownika
            self._artwork_programowo = False
            return
        wlaczone = bool(event.value)
        if wlaczone != bool(self._user_state.get("okladki_w_liscie")):
            self._przelacz_okladki_w_liscie()
        if wlaczone:
            self._artwork_przerwij.clear()
            self._artwork_worker()
        else:
            # zatrzymaj dociąganie po bieżącym pliku; osadzone okładki ZOSTAJĄ
            self._artwork_przerwij.set()

    def action_toggle_fav(self) -> None:
        self._lib_toggle("ulubione_utwory", "♥")

    def action_toggle_filar(self) -> None:
        """F: w Bibliotece otwiera wybór ROLI filara (otwarcie / buildup /
        oddech / zamknięcie / bez roli — decyzja Janka 11.08: filar niesie
        deklarację miejsca w secie); w zakładce Set otwiera TRYB FILARÓW.
        Wzorzec dwóch naciśnięć w obu przypadkach."""
        if self.query_one("#tabs", TabbedContent).active == "tab-set":
            choice = self._panel_choice("pillar_mode")
            if choice is not None:
                self._apply_pillar_mode(choice)
                return
            self._close_panel()
            self._open_pillar_mode_panel()
            return
        choice = self._panel_choice("rola_filaru")
        if choice is not None:
            self._apply_rola_filaru(choice)
            return
        self._close_panel()
        self._open_rola_filaru_panel()

    def _wybrany_utwor_biblioteki(self):
        table = self.query_one("#lib-table", DataTable)
        row = table.cursor_row
        widok = getattr(self, "_lib_view", [])
        if row is None or not (0 <= row < len(widok)):
            return None
        return widok[row]

    def _open_rola_filaru_panel(self) -> None:
        from dancelab.tui.user_store import (ROLE_FILARA, aktywna_playlista,
                                             rola_filara)
        if self.query_one("#tabs", TabbedContent).active != "tab-lib":
            self._note("filar: zaznacz utwór w zakładce Biblioteka")
            return
        pl = aktywna_playlista(self._user_state)
        if pl is None:
            self._note("filary żyją W PLAYLISTACH — wybierz playlistę na "
                       "liście po lewej albo utwórz nową (＋)")
            self.notify("Najpierw playlista: filary żyją w playlistach (＋)",
                        severity="warning", timeout=6)
            return
        a = self._wybrany_utwor_biblioteki()
        if a is None:
            return
        self._filar_kandydat = (a.track.track_id, str(a.track.source_path))
        obecna = rola_filara(self._user_state, *self._filar_kandydat)
        znaki = {"otwarcie": "O", "buildup": "B", "oddech": "~",
                 "zamkniecie": "Z", "": "⚑"}
        options = [(f"{znaki[r]} · {r or 'bez roli'} — {opis}"
                    + ("   ✓" if obecna == r else ""), r or "__bez")
                   for r, opis in ROLE_FILARA.items()]
        if obecna is not None:
            options.append(("✕ · zdejmij filar", "__zdejmij"))
        nazwa = _wykonawca_tytul(a.track)[1][:34]
        self._open_suggest_panel(
            None, f"FILAR Z ROLĄ — {nazwa}\nplaylista: {pl['nazwa'][:30]}\n"
                  f"Enter/klik+F przypisuje · Esc anuluje",
            options, "rola_filaru")

    def _apply_rola_filaru(self, wybor: str) -> None:
        from dancelab.tui.user_store import (ROLE_FILARA, save_state,
                                             ustaw_filar, zdejmij_filar)
        kandydat = getattr(self, "_filar_kandydat", None)
        self._close_panel()
        if kandydat is None:
            return
        tid, sciezka = kandydat
        if wybor == "__zdejmij":
            if zdejmij_filar(self._user_state, tid, sciezka):
                self._note("filar zdjęty z playlisty")
        else:
            rola = "" if wybor == "__bez" else wybor
            ok, powod = ustaw_filar(self._user_state, tid, sciezka, rola)
            if not ok:
                self._note(f"filar: {powod}")
                self.notify(powod, severity="warning", timeout=6)
                return
            self._note(f"⚑ filar ({ROLE_FILARA[rola]})")
        save_state(self._user_state, self.processed_dir)
        self._render_library(keep_cursor=True)
        self.query_one("#lib-table", DataTable).focus()

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
        save_state(self._user_state, self.processed_dir)
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
        save_state(self._user_state, self.processed_dir)
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
    _SORT_NAMES = (" ", "♥", "F", "BPM", "ton", "pew.", "energia", "LUFS",
                   "gatunek", "min", "wykonawca", "tytuł", "źr.")

    def _cycle_sort(self, col: int) -> None:
        if col == 0:
            return                      # kolumna okładek nie sortuje
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
        if (event.button.id or "").startswith("dj-f-"):
            gid = event.button.id
            if gid == "dj-f-all":
                self._ustaw_dj_filtr("all", gid)
            elif gid == "dj-f-kol":
                self._ustaw_dj_filtr("kolekcja", gid)
            else:                        # dj-f-e0..e2 — edycje z danych
                i = int(gid.rsplit("e", 1)[1])
                self._ustaw_dj_filtr(
                    f"edycja:{self._dj_edycje_filtry[i]}", gid)
            return
        if event.button.id == "go":
            self.action_build()          # przycisk robi to samo co B —
        elif event.button.id == "lib-analyze":   # wcześniej był atrapą
            self._lib_analyze_worker()
        elif event.button.id == "lib-build":
            self.action_build_from_filary()
        elif event.button.id == "cue-write":
            self.action_write()
        elif event.button.id == "cue-playlist":
            # ta sama publikacja playlisty co W w Secie — zakładka nazywa się
            # „Eksport", więc oba eksporty mają tu być (skarga Janka 09.08)
            if not self._plan_paths:
                self._note("najpierw zbuduj set (B) — wtedy będzie co wysyłać")
            else:
                self._write_worker()
        elif event.button.has_class("pb-play"):
            self.action_preview_seam()
            self._tick_player()
        elif event.button.has_class("pb-next"):
            self._nastepny(+1)
        elif event.button.has_class("pb-prev"):
            self._nastepny(-1)
        elif event.button.has_class("pb-fwd"):
            self._skok(+8)
        elif event.button.has_class("pb-back"):
            self._skok(-8)

    def action_build_from_filary(self) -> None:
        """G / przycisk w Bibliotece: filary → zakładka Set jako SZKIC.

        CELOWO BEZ automatycznej budowy (Janek 05.08: „przez to omijamy całą
        sekcję briefu") — filary lądują w tabelce podświetlone na złoto,
        użytkownik uzupełnia formularz i dopiero B buduje wokół nich."""
        from dancelab.core.config import load_config, load_weights
        from dancelab.tui.user_store import (MIN_FILARY, filary_wpisy,
                                             resolve_tracks)
        n = len(filary_wpisy(self._user_state))
        if n < MIN_FILARY:
            self.notify(f"do budowy z filarów trzeba minimum {MIN_FILARY} "
                        f"(masz {n}) — klawisz F w Bibliotece zaznacza",
                        severity="warning", timeout=6)
            return
        if not self._lib:
            self.notify("Biblioteka jeszcze się ładuje — chwila", timeout=4)
            return
        by_id = {a.track.track_id: a for a in self._lib}
        ids, missing = resolve_tracks(filary_wpisy(self._user_state), by_id)
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

    @work(thread=True, exclusive=True, group="artwork")
    def _artwork_worker(self) -> None:
        """Synchronizacja okładek: iTunes → tagi plików (z weryfikacją) →
        po Twoim „Reload Tags" w Rekordboksie → ekrany CDJ. W tle, z
        postępem; raport w notkach i w data/exports/artwork_raport.json."""
        from textual.worker import get_current_worker

        from dancelab.ingestion.artwork_sync import synchronizuj
        ui = self.call_from_thread
        if not self._lib:
            ui(self._note, "Artwork: Biblioteka jeszcze się ładuje")
            return
        count = self.query_one("#lib-count", Static)
        worker = get_current_worker()

        def przerwac() -> bool:
            return (self._stop.is_set() or self._artwork_przerwij.is_set()
                    or worker.is_cancelled)

        def postep(i, n, path):
            ui(count.update, f"Artwork: {i}/{n} · "
                             f"{pathlib.Path(path).stem[:40]}")
        ui(self._note, "Artwork: szukam braków i pytam iTunes…")
        try:
            raport = synchronizuj(self._lib, progress=postep,
                                  should_stop=przerwac)
        except Exception as exc:  # noqa: BLE001
            ui(self._note, f"Artwork: synchronizacja nie wyszła: {exc}")
            return
        from dancelab.tui.okladki import mozaika
        mozaika.cache_clear()
        ui(self._note,
           f"Artwork: osadzone {len(raport['osadzone'])} · "
           f"niejednoznaczne {len(raport['niejednoznaczne'])} · "
           f"nieznalezione {len(raport['nieznalezione'])} · "
           f"błędy {len(raport['bledy'])} · "
           f"miały już: {raport['z_okladka_juz']} — raport: {RAPORT_ART}")
        ui(self._note, "Artwork: w Rekordboksie zaznacz utwory i daj "
                       "Reload Tags — wtedy okładki wejdą na CDJ-e")
        self.call_from_thread(
            self.notify,
            f"Artwork: osadzone {len(raport['osadzone'])}, "
            f"do przejrzenia {len(raport['niejednoznaczne'])}")
        ui(self._render_library, True)

    @work(thread=True, exclusive=True, group="lufs")
    def _lufs_worker(self) -> None:
        """Domierz LUFS w tle (ffmpeg, jeden utwór na raz, trwały cache);
        kolumna dopełnia się w trakcie."""
        from dancelab.ingestion.loudness import zmierz_brakujace
        ui = self.call_from_thread
        sciezki = [a.track.source_path for a in self._lib]
        brak = [p for p in sciezki if p not in self._lib_lufs]
        if not brak:
            return

        licznik = {"n": 0}

        def postep(i, n, path):
            licznik["n"] = i
            if i % 5 == 0 or i == n:
                ui(self._po_lufs, i, n)

        try:
            mapa = zmierz_brakujace(sciezki, progress=postep,
                                    should_stop=self._stop.is_set)
        except Exception as exc:  # noqa: BLE001
            ui(self._note, f"pomiar LUFS nie wyszedł: {exc}")
            return
        self._lib_lufs = mapa
        ui(self._po_lufs, licznik["n"], licznik["n"])

    def _po_lufs(self, i: int, n: int) -> None:
        from dancelab.ingestion.loudness import wczytaj_cache
        try:
            self._lib_lufs = wczytaj_cache()
        except Exception:  # noqa: BLE001
            pass
        self._render_library(keep_cursor=True)
        if i < n:
            self.query_one("#lib-count", Static).update(
                str(self.query_one("#lib-count", Static).render())
                .split("   ·   mierzę")[0]
                + f"   ·   mierzę LUFS w tle: {i}/{n}")

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
            from dancelab.ingestion.bramkarz import przesiej
            files, odrzucone = przesiej(files)
            for sciezka, powod in odrzucone[:5]:
                ui(self._note, f"BRAMKARZ odrzucił: "
                               f"{pathlib.Path(sciezka).name[:40]} — {powod}")
            if len(odrzucone) > 5:
                ui(self._note, f"…i {len(odrzucone) - 5} kolejnych odrzutów")
            if not files:
                ui(self._note, "bramkarz odrzucił wszystko — nie ma co analizować")
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
            from dancelab.decision.anchors import MOJE_ULUBIONE, list_anchors
            from dancelab.tui.user_store import kolekcja_djow
            # Własne brzmienie NA POCZĄTKU listy: księga ma 285 DJ-ów
            # zmierzonych z ich setów i nie ma jak dopisać kogoś, czyich
            # setów nie mamy (test person 09.08 — Kuba gra jak Amelie Lens,
            # której tam nie ma). Ulubione działają dla każdego.
            options = [(f"{MOJE_ULUBIONE} — z Twoich ♥", MOJE_ULUBIONE)]
            # Księga DJ-ów jest liczona z korpusu i NIE jedzie z repozytorium,
            # więc na świeżej instalce jej po prostu nie ma. Wcześniej jej brak
            # wywracał całą funkcję — wyjątek leciał wyżej i pole „Brzmi jak…"
            # zostawało PUSTE, także bez „moje ulubione", które przecież żadnej
            # księgi nie potrzebuje. Kotwica z ulubionych ma działać od
            # pierwszego uruchomienia.
            try:
                options += _opcje_kotwic(
                    list_anchors(limit=500),
                    kolekcja_djow(getattr(self, "_user_state", {}) or {}))
            except Exception as exc:  # noqa: BLE001 — brak księgi to stan, nie awaria
                self._note(f"księga DJ-ów niedostępna ({exc}); "
                           "zostaje kotwica z Twoich ulubionych")
            pole = self.query_one("#dj", Select)
            try:
                biezacy = pole.value
            except Exception:  # noqa: BLE001
                biezacy = None
            pole.set_options(options)
            # przeładowanie kolejności nie może gubić wybranej kotwicy
            if isinstance(biezacy, str) and biezacy in {v for _e, v in options}:
                pole.value = biezacy
        except Exception as exc:  # noqa: BLE001 — brak pliku kotwic to stan, nie awaria
            self._note(f"kotwice niedostępne: {exc}")

    def _refresh_status(self) -> None:
        from dancelab.ingestion.playlist_publish import BACKUP_DIR, rekordbox_running
        otwarty = rekordbox_running()
        rb = "⛔ Rekordbox OTWARTY — zapis W zablokowany" if otwarty \
            else "✅ Rekordbox zamknięty — W dostępne"
        n_bak = len(list(BACKUP_DIR.glob("*.db"))) if BACKUP_DIR.exists() else 0
        self.query_one("#status", Static).update(
            f"{rb}   ·   backupy: {n_bak}   ·   notki: {self._n_notes} (L)"
            + f"   ·   pula: {self.processed_dir}")
        self._odswiez_guzik_cue(otwarty)

    def _odswiez_guzik_cue(self, rb_otwarty: bool) -> None:
        """Przycisk wysyłki cue MÓWI, w jakim jest stanie (skarga Janka
        09.08: „stawianie cue pointów nie działa, bo nie widzę w Rekordbox").
        Wcześniej wyglądał tak samo zawsze: przy otwartym Rekordboksie zapis
        był niemożliwy, a jedynym sygnałem był znikający dymek; po pierwszym
        naciśnięciu (które tylko LICZY) też nic się na nim nie zmieniało."""
        try:
            guzik = self.query_one("#cue-write", Button)
        except Exception:  # noqa: BLE001 — ekran jeszcze nie zbudowany
            return
        gotowy = getattr(self, "_cue_zapis_gotowy", None)
        if rb_otwarty:
            etykieta, wariant, aktywny = ("Zamknij Rekordbox, by wysłać cue",
                                          "default", False)
        elif gotowy is not None:
            ile = sum(len(t.cues) for t in gotowy[0].tracks)
            etykieta, wariant, aktywny = (f"POTWIERDŹ zapis {ile} padów [W]",
                                          "warning", True)
        else:
            etykieta, wariant, aktywny = ("Wyślij cue do RB  [W]",
                                          "default", True)
        if str(guzik.label) != etykieta:
            guzik.label = etykieta
        guzik.variant = wariant
        guzik.disabled = not aktywny

    def _note(self, line: str) -> None:
        # Notatka NIGDY nie może położyć aplikacji. Wołają ją też wątki robocze
        # startujące zanim ekran się zmontuje — wtedy `#warnings` jeszcze nie
        # istnieje i `query_one` rzuca NoMatches, co ubijało workera i cały
        # start (złapane na czystym klonie: brak księgi DJ-ów → notatka →
        # wywrotka). Wiadomość zostaje w buforze i trafi na ekran, gdy będzie
        # dokąd.
        from dancelab.tui.po_polsku import po_polsku
        tekst = f"· {po_polsku(line)}"
        try:
            log = self.query_one("#warnings", Log)
        except Exception:  # noqa: BLE001 — brak widżetu to etap startu, nie błąd
            self._notatki_przed_startem.append(tekst)
            self._n_notes += 1
            return
        for zalegla in self._notatki_przed_startem:
            log.write_line(zalegla)
        self._notatki_przed_startem.clear()
        log.write_line(tekst)
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
        # puste „Brzmi jak…" to NoSelection, NIE zawsze identyczne z Select.BLANK
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
        # Kryterium jest to samo, co przy odmowie odsłuchu (`_bez_pliku`):
        # ŚCIEŻKA NIE JEST ŚCIEŻKĄ W SYSTEMIE PLIKÓW = utwór ze źródła bez
        # pliku (strumień) i to jest jego stan normalny. Sito „brak pliku"
        # powstało przeciw plikom, które ZNIKNĘŁY.
        # Wcześniej przepustka była przywiązana do jednej wersji silnika
        # (`rekordbox-anlz`) — złapane 09.08 testem person: biblioteka
        # zbudowana z innego źródła znikała w całości, a użytkownik dostawał
        # „pusta pula" i notkę o stemach.
        odrzucone = {"stem": 0, "dlugosc": 0, "brak_pliku": 0}

        def zdrowy(a) -> bool:
            if (a.track.duration_sec or 0) > MAX_TRACK_SEC:
                odrzucone["dlugosc"] += 1
                return False
            sciezka = str(a.track.source_path or "")
            if not sciezka.startswith("/"):
                return True                     # źródło bez pliku — w porządku
            p = pathlib.Path(sciezka)
            if not p.exists():
                odrzucone["brak_pliku"] += 1
                return False
            if p.stem.strip().lower() in STEM_NAMES:
                odrzucone["stem"] += 1
                return False
            return True

        analyses = [a for a in analyses if zdrowy(a)]
        notes = []
        if before - len(analyses):
            powody = ", ".join(f"{n}: {i}" for n, i in (
                ("stemy", odrzucone["stem"]),
                ("dłuższe niż 15 min", odrzucone["dlugosc"]),
                ("brak pliku na dysku", odrzucone["brak_pliku"])) if i)
            notes.append(f"higiena puli: odrzucone {before - len(analyses)} "
                         f"({powody})")
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
            from dancelab.ingestion.bramkarz import przesiej
            files, odrzucone = przesiej(files)
            for sciezka, powod in odrzucone[:5]:
                ui(self._note, f"BRAMKARZ odrzucił: "
                               f"{pathlib.Path(sciezka).name[:40]} — {powod}")
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
        # UWAGA: `notes` powstaje dopiero pod koniec tej metody — komunikaty
        # o kotwicy zbieramy osobno i doklejamy tam. (Dwa razy 09.08 sięgnąłem
        # po zmienną, której w tym miejscu jeszcze nie ma, i ubiłem budowę.)
        uwagi_kotwicy: list[str] = []
        if p["dj"]:
            from dancelab.decision.anchors import (MOJE_ULUBIONE, AnchorError,
                                                   kotwica_z_utworow,
                                                   resolve_anchor)
            if p["dj"] == MOJE_ULUBIONE:
                from dancelab.tui.user_store import resolve_tracks
                ulubione, _brak = resolve_tracks(
                    self._user_state.get("ulubione_utwory", []),
                    {a.track.track_id: a for a in analyses})
                try:
                    anchor = kotwica_z_utworow(
                        [a for a in analyses if a.track.track_id in ulubione])
                    uwagi_kotwicy.append(
                        f"kotwica z Twoich ulubionych: {anchor.n_tracks} "
                        f"utworów (kontur skoków niedostępny — to cecha "
                        f"sposobu grania, nie zbioru)")
                except AnchorError as exc:
                    uwagi_kotwicy.append(
                        f"kotwica z ulubionych niemożliwa: {exc}")
            else:
                anchor = resolve_anchor(p["dj"])

        count = estimate_track_count_for_duration(analyses, p["minutes"])
        filary, filar_notes, role_filarow = _filary_for_build(
            self._user_state, {a.track.track_id: a for a in analyses},
            p["bpm_min"], p["bpm_max"], count)
        # filar może wskazywać duplikat bajt-w-bajt, który dedup wytnie —
        # mapujemy na egzemplarz kanoniczny, żeby budowa nie odmawiała
        # o utwór, który muzycznie w puli JEST (złapane E2E 05.08)
        from dancelab.decision.dedup import canonical_ids
        mapping = canonical_ids(analyses)
        filary = list(dict.fromkeys(mapping.get(t, t) for t in filary))
        role_filarow = {mapping.get(t, t): r for t, r in role_filarow.items()}
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

        # role krańcowe wyjmujemy z podpór: otwarcie/zamknięcie to deklaracje
        # miejsc, a podpory szukają najsłabszych przęseł W ŚRODKU
        otwarcie_id = next((t for t, r in role_filarow.items()
                            if r == "otwarcie"), None)
        zamkniecie_id = next((t for t, r in role_filarow.items()
                              if r == "zamkniecie"), None)

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
            srodkowe = [t for t in filary
                        if t not in (otwarcie_id, zamkniecie_id)]
            final, podpory_notes = _wstaw_podpory(
                list(plan.track_order), srodkowe, score)
            if otwarcie_id:
                final = [otwarcie_id, *final]
                podpory_notes.append("rola otwarcie: pozycja #1 (poza "
                                     "pomiarem przęseł — deklaracja DJ-a)")
            if zamkniecie_id:
                final = [*final, zamkniecie_id]
                podpory_notes.append(f"rola zamknięcie: pozycja "
                                     f"#{len(final)} (deklaracja DJ-a)")
            filar_notes.extend(podpory_notes)
            filar_notes.append(f"zgodność konstrukcji (bez podpór): "
                               f"{plan.mean_transition_score}")
            # zgodność CAŁOŚCI nie jest tą samą liczbą co z budowy — nie udajemy
            plan = plan.model_copy(update={"track_order": final,
                                           "mean_transition_score": None})
        else:
            rozstaw = _rozstaw_filary(filary, by_id_all, count, tryb) \
                if filary else {}
            rozstaw, role_notes = _zastosuj_role_krancowe(
                rozstaw, role_filarow, count)
            filar_notes.extend(role_notes)
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
        notes = [*uwagi_kotwicy, *emb.notes, *gen.notes, *ton.notes,
                 *filar_notes,
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
        # Zbudowany set trafia DO aktywnej playlisty (Janek 12.08: zapis ma
        # być automatyczny po „buduj"). Ostatnia budowa wygrywa.
        from dancelab.tui.user_store import (aktywna_playlista, save_state,
                                             zapisz_utwory_playlisty)
        wpisy = [{"track_id": t, "path": by_id[t].track.source_path}
                 for t in self._order if t in by_id]
        if wpisy and zapisz_utwory_playlisty(self._user_state, wpisy):
            save_state(self._user_state, self.processed_dir)
            pl = aktywna_playlista(self._user_state)
            self._note(f"set zapisany w playliście „{pl['nazwa']}” "
                       f"({len(wpisy)} utworów) — ostatnia budowa wygrywa")
            self._render_side_list()
        # Dwa rodzaje ostrzeżeń nie mogą siedzieć w schowanych notkach:
        # „brief zignorowany" i „set się sypie" zmieniają to, co DJ dostał
        # (oba złapane testem person 09.08).
        for w in plan.warnings:
            if w.startswith(("GATUNEK Z BRIEFU", "SŁABE SZWY")):
                # `_show_plan` biegnie już na wątku UI — bez pośrednika
                self.notify(w[:180], severity="warning", timeout=10)
        for note in [*plan.warnings, *extra_notes]:
            self._note(note)

    def _render_order(self, by_id) -> None:
        from rich.text import Text
        from dancelab.tui.user_store import resolve_tracks
        table = self.query_one("#set", DataTable)
        self._render_w_toku = True
        if self._auto_timer is not None:
            self._auto_timer.stop()
            self._auto_timer = None
        table.clear()
        total = 0.0
        self._plan_paths = []
        self._row_cells = []
        # flagi z kontekstu budowy (id już po mapowaniu duplikatów);
        # bez kontekstu (świeży szkic/wczytany plan) — ze stanu użytkownika
        from dancelab.tui.user_store import filary_wpisy
        filary = set(self._ctx.get("filary") or
                     resolve_tracks(filary_wpisy(self._user_state),
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
        self.call_after_refresh(setattr, self, "_render_w_toku", False)
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
        if self.query_one("#tabs", TabbedContent).active == "tab-export":
            self._wyslij_cue()
            return
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
        from dancelab.tui.user_store import filary_wpisy
        entries = filary_wpisy(self._user_state)
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
        save_state(self._user_state, self.processed_dir)
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
            attach_rekordbox_meta, attach_sound_embeddings)
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

    def _zapisz_werdykt_koncowy(self) -> None:
        """AUTOMATYCZNY werdykt w chwili wysyłki do Rekordboksa (decyzja
        Janka 09.08: ręczne V wyleciało — lista przy W jest OSTATECZNA,
        więc dopiero wtedy wiadomo, jak bardzo DJ zmienił propozycję
        silnika). Zrzut: plan silnika vs stan końcowy + wszystkie edycje
        po drodze + prosta miara rozjazdu."""
        if not self._order or not self._ctx:
            return
        import json
        import time
        by_id = self._ctx["by_id"]

        def rows(ids):
            return [{"track_id": t, "path": by_id[t].track.source_path}
                    for t in ids if t in by_id]
        wspolne = [t for t in self._order if t in self._engine_order]
        te_same_pozycje = sum(
            1 for i, t in enumerate(self._order)
            if i < len(self._engine_order) and self._engine_order[i] == t)
        rec = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"),
               "powod": "wysylka_do_rekordboxa",
               "nazwa": self._plan_name,
               "parametry": self._ctx.get("params", {}),
               "plan_silnika": rows(self._engine_order),
               "stan_dja": rows(self._order),
               "edycje": self._edits,
               "miara": {"utworow_finalnie": len(self._order),
                         "utworow_z_planu": len(wspolne),
                         "na_tej_samej_pozycji": te_same_pozycje,
                         "liczba_edycji": len(self._edits)}}
        WERDYKTY_DIR.mkdir(parents=True, exist_ok=True)
        path = WERDYKTY_DIR / f"tui_werdykt_{time.strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        self._note(f"werdykt końcowy zapisany automatycznie: "
                   f"{te_same_pozycje}/{len(self._order)} pozycji bez zmian, "
                   f"edycji {len(self._edits)} → {path.name}")

    # ---------------------------------------------------- odsłuch szwu (P)

    def _stop_player(self) -> bool:
        if self._odtwarzacz.stop():
            self._note("odsłuch: pauza (spacja na tym samym utworze wznawia)")
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
        """P gra ZAZNACZONY UTWÓR — w każdej zakładce to samo (decyzja
        Janka 09.08: odsłuch szwu przeniesiony do Eksport/Cue, gdzie szew
        powstaje z TWOICH padów, a nie z propozycji silnika).
        P drugi raz = pauza; P na tym samym utworze = wznowienie od miejsca.
        Dźwięk startuje WYŁĄCZNIE z jawnego klawisza."""
        track = self._biezacy_track()
        if track is None:
            if not self._stop_player():
                self._note("ustaw kursor na utworze do odsłuchu")
            return
        powod = self._bez_pliku(track)
        if powod:
            self._note(powod)
            return
        akcja, blad = self._odtwarzacz.przelacz(
            str(track.source_path), track.bpm_estimate)
        if blad:
            self._note(f"odsłuch: {blad}")
            return
        nazwa = pathlib.Path(track.source_path).stem[:40]
        if akcja == "pauza":
            self._note("odsłuch: pauza (spacja wznawia)")
        else:
            self._note(f"odsłuch: {nazwa} ({akcja}) · spacja pauza · "
                       f"↓/↑ następny · →/← ±8 uderzeń")
            self._ustaw_meta_odtwarzacza(track)
        self._pokaz_odtwarzacz()

    # --------------------------------------- pasek odtwarzacza (Apple Music)

    def _ustaw_meta_odtwarzacza(self, track) -> None:
        """Okładka + tytuł/wykonawca w odtwarzaczu (układ Apple Music)."""
        art, tyt = _wykonawca_tytul(track)
        self._gra_meta = (art, tyt)
        from dancelab.tui.okladki import mozaika
        moz = mozaika(str(track.source_path), 12, 6)
        from rich.text import Text
        for art_w in self.query(".pb-art"):
            art_w.update(moz if moz is not None else Text(""))

    def _tick_player(self) -> None:
        # standard odtwarzaczy (pytanie Janka 06.08): koniec utworu = graj
        # następny z listy; bezpieczniki: auto-przejście tylko gdy skończył
        # się utwór SPOD KURSORA (szew/odsłuch spoza listy nie skacze po
        # liście), koniec listy = cisza
        skonczony = self._odtwarzacz.skonczyl_sie()
        if skonczony is not None:
            track = self._biezacy_track()
            if track is not None and str(track.source_path) == skonczony:
                self._nastepny(+1, auto=True)
        gra = self._odtwarzacz.gra()
        for guzik in self.query(".pb-play"):
            guzik.label = "Pauza" if gra else "Graj"
        if self._odtwarzacz.sciezka:
            art, tyt = getattr(self, "_gra_meta", ("", ""))
            m, s = divmod(int(self._odtwarzacz.pozycja()), 60)
            stan = "" if gra else " · pauza"
            tytul = tyt or pathlib.Path(self._odtwarzacz.sciezka).stem[:40]
            podtytul = f"{art + ' · ' if art else ''}{m}:{s:02d}{stan}"
            for w in self.query(".pb-info"):
                w.update(tytul)
            for w in self.query(".pb-sub"):
                w.update(podtytul)
            self._rysuj_os()
        else:
            for w in self.query(".pb-info"):
                w.update("nic nie gra")
            for w in self.query(".pb-sub"):
                w.update("")
            for w in self.query(".pb-os"):
                w.update("")

    def _analiza_grajaca(self):
        """Analiza utworu, który AKTUALNIE gra — szukana po ścieżce w puli
        setu, a jak jej nie ma, w bibliotece. None = gra coś spoza puli
        (np. wyrenderowany szew) i oś czasu zostaje pusta."""
        sciezka = self._odtwarzacz.sciezka
        if not sciezka:
            return None
        zrodla = [(self._ctx or {}).get("by_id", {}).values(), self._lib or []]
        for zrodlo in zrodla:
            for a in zrodlo:
                if str(a.track.source_path) == str(sciezka):
                    return a
        return None

    def _rysuj_os(self) -> None:
        """Żywa oś czasu w KAŻDEJ instancji paska: energia utworu, głowica
        odtwarzania i zegar. Bez analizy — sam zegar, nigdy zmyślony rysunek
        (decyzja Janka 09.08: odtwarzacz w każdej zakładce)."""
        from dancelab.tui.pasek import czas, os_z_glowica
        analiza = self._analiza_grajaca()
        pozycja = self._odtwarzacz.pozycja()
        for w in self.query(".pb-os"):
            szer = max(w.content_size.width - 14, 0)
            os = os_z_glowica(analiza, pozycja, szer)
            w.update(os if os is not None else czas(pozycja))

    def _nastepny(self, delta: int, auto: bool = False) -> None:
        """Nast./Poprz.: przesuń zaznaczenie w aktywnej tabeli i graj od
        zera — jak next/previous w każdym odtwarzaczu. `auto` = wywołane
        końcem utworu; na końcu listy zapada cisza zamiast pętli."""
        aktywna = self.query_one("#tabs", TabbedContent).active
        if aktywna == "tab-lib":
            table = self.query_one("#lib-table", DataTable)
        elif aktywna == "tab-set":
            table = self.query_one("#set", DataTable)
        else:
            return
        if table.row_count == 0 or table.cursor_row is None:
            return
        cel = table.cursor_row + delta
        if not (0 <= cel < table.row_count):
            if auto:
                self._note("koniec listy — odsłuch zakończony")
            return
        table.move_cursor(row=cel)
        track = self._biezacy_track()
        if track is None:
            return
        blad = self._odtwarzacz.graj_od_zera(str(track.source_path),
                                             track.bpm_estimate)
        if blad:
            self._note(f"odsłuch: {blad}")
            return
        self._ustaw_meta_odtwarzacza(track)
        self._pokaz_odtwarzacz()
        self._tick_player()

    def action_skok_przod(self) -> None:
        self._skok(+8)

    def action_skok_tyl(self) -> None:
        self._skok(-8)

    def action_skok_przod_32(self) -> None:
        self._skok(+32)

    def action_skok_tyl_32(self) -> None:
        self._skok(-32)

    def action_skok_przod_128(self) -> None:
        self._skok(+128)

    def action_skok_tyl_128(self) -> None:
        self._skok(-128)

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
                f"▶ {opis} · spacja pauza · →/← 8 · ⇧ 32 · PgUp/Dn 128 · ↓/↑ następny")

    def on_data_table_row_highlighted(self, event) -> None:
        """Wzorzec Finder Quick Look (decyzja Janka 06.08 — koniec
        z wynajdywaniem koła): GDY COŚ GRA, ↓/↑ działa jak next/previous —
        przełącza odtwarzanie na nowo zaznaczony utwór. Przy pauzy/ciszy
        strzałki tylko chodzą po liście. Małe opóźnienie, żeby przytrzymana
        strzałka nie restartowała co wiersz (0,12 s — skrócone
        na skargę Janka o sekundową przerwę).
        PRZEBUDOWA tabeli (np. zdjęcie filtra) NIE jest nawigacją — złapane
        na żywo 06.08: czyszczenie szukajki ubijało grany utwór i grało
        pierwszy z listy."""
        if getattr(event.data_table, "id", None) == "cue-table":
            # karta cue podąża za kursorem listy; zmiana utworu gasi wybór pada
            idx = event.cursor_row
            if 0 <= idx < len(self._cue_widok):
                nowy = self._cue_widok[idx]
                if nowy != self._cue_track:
                    self._cue_track = nowy
                    self._cue_wybor = None
                    self._render_cue_karta()
            return
        if getattr(self, "_render_w_toku", False):
            return
        if not self._odtwarzacz.gra():
            return
        if getattr(event.data_table, "id", None) not in ("set", "lib-table"):
            return
        if self._auto_timer is not None:
            self._auto_timer.stop()
        self._auto_timer = self.set_timer(0.12, self._auto_graj)

    def _auto_graj(self) -> None:
        track = self._biezacy_track()
        if track is None:
            return
        if str(track.source_path) == self._odtwarzacz.sciezka \
                and self._odtwarzacz.gra():
            return   # ten utwór JUŻ gra (np. kursor odnalazł go po renderze)
        blad = self._odtwarzacz.graj_od_zera(str(track.source_path),
                                             track.bpm_estimate)
        if blad:
            self._note(f"odsłuch: {blad}")
            return
        self._ustaw_meta_odtwarzacza(track)
        self._pokaz_odtwarzacz()

    # ------------------------------------------- porównanie pary od dołu (C)

    def action_compare_pair(self) -> None:
        """C: panel porównania pary zaznaczony→następny wysuwa się od dołu —
        fakty o szwie z planu silnika (wzorzec: zakładka Export
        w Rekordboksie). Drugie C / Esc chowa. Tu się PATRZY; słucha się
        w Eksport/Cue (C), bo tam szew powstaje z Twoich padów — czyli
        z tego, co naprawdę pojedzie na CDJ-e."""
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
        faktów o szwie, bez odsłuchu. Odsłuch mieszka w Eksport/Cue, żeby
        DJ słyszał SWOJE pady, nie propozycję silnika."""
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
            f"posłuchaj w Eksport/Cue (C) — z Twoich padów · C/Esc chowa")
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
            ui(self._zapisz_werdykt_koncowy)
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
