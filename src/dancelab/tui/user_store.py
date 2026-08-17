"""Ulubione i filary — trwały stan użytkownika Biblioteki (TUI 2.0, krok b).

Dwa piny, jak chciał Janek (wzór Apple Music): na utwory i na playlisty,
osobno FILARY — utwory OBOWIĄZKOWE dla generatora setu. Filarów jest 3–10
(Janek, 05.08 — minimum wróciło po dniu przerwy): górna granica to bezpiecznik
z jego uzasadnienia (set złożony z samych filarów nie zostawia silnikowi nic
do zaprojektowania — silnik projektuje drogę MIĘDZY filarami), dolna pilnuje,
żeby budowa „z filarów" miała z czego wyznaczyć trasę. Minimum egzekwuje
BUDOWA, nie przełącznik — pierwszy i drugi filar musi się dać zaznaczyć.

Wpisy trzymają track_id ORAZ ścieżkę: id to sha1 ścieżki, więc po przenosinach
pliku wpis ratuje dopasowanie po ścieżce (ten sam wzór co magazyn planów).
Utwór nieobecny w puli jest raportowany, nigdy zgadywany.

Pin na playlisty jest w strukturze od dziś, ale UI dostanie dopiero, gdy
powstanie widok playlist. Plik: `data/exports/` — osobiste, poza gitem.
"""

from __future__ import annotations

import json
import pathlib

STATE_PATH = pathlib.Path("data/exports/tui_stan.json")   # stan sprzed podziału


def sciezka_stanu(pula: str | None = None) -> pathlib.Path:
    """Stan JEST WŁASNOŚCIĄ BIBLIOTEKI, nie programu.

    Złapane 09.08 testem person: filary Janka pojawiały się w KAŻDEJ innej
    bibliotece („FILAR nieobecny w puli" ×9 u każdej persony), bo stan leżał
    w jednym pliku niezależnym od puli. Ulubiony utwór i filar odnoszą się do
    konkretnego zbioru — po zmianie zbioru nie znaczą nic.

    Stary plik zostaje jako stan puli DOMYŚLNEJ, żeby nikt nie stracił
    swoich filarów przy tej zmianie.
    """
    if not pula:
        return STATE_PATH
    import hashlib

    # SHA-1 służy tu wyłącznie za KLUCZ NAZWY PLIKU dla stanu przypisanego do
    # puli — nie chroni niczego i nie jest podpisem. `usedforsecurity=False`
    # mówi to wprost, także audytowi bezpieczeństwa (bandit B324).
    klucz = hashlib.sha1(str(pathlib.Path(pula).expanduser().resolve(
        strict=False)).encode(), usedforsecurity=False).hexdigest()[:12]
    return STATE_PATH.with_name(f"tui_stan__{klucz}.json")
MIN_FILARY = 3
MAX_FILARY = 10

# Role filarów (Janek, 11.08): filar przestaje być tylko „musi zagrać" —
# niesie deklarację MIEJSCA w secie. To jest odpowiedź na obalony łuk:
# zamiast narzuconej krzywej DJ deklaruje punkty stałe, a silnik napina
# set między nimi. Nazwa „filar" została świadomie (Janek: „nie rozstawiasz
# 5 kotwic, a filary już tak") — „kotwica" pozostaje przy „Brzmi jak…".
ROLE_FILARA = {
    "otwarcie": "pierwszy utwór",
    "buildup": "rozpędza w górę",
    "oddech": "zejście w środku",
    "zamkniecie": "ostatni utwór",
    "": "bez roli — po prostu musi zagrać",
}

_EMPTY = {"ulubione_utwory": [], "ulubione_playlisty": [], "filary": [],
          "tryb_filarow": "rozstaw", "okladki_w_liscie": False,
          "playlisty": [], "aktywna_playlista": None,
          "kolekcja_djow": []}


def _kopia(v):
    return list(v) if isinstance(v, list) else v


def load_state(pula: str | None = None) -> dict:
    sciezka = sciezka_stanu(pula)
    if not sciezka.exists():
        # PIERWSZE uruchomienie na tej puli: jeśli to pula domyślna, a stan
        # sprzed podziału istnieje, przejmujemy go — inaczej pusty.
        if pula and STATE_PATH.exists() and _domyslna(pula):
            sciezka = STATE_PATH
        else:
            return {k: _kopia(v) for k, v in _EMPTY.items()}
    state = json.loads(sciezka.read_text())
    for key, default in _EMPTY.items():
        state.setdefault(key, _kopia(default))
    _migruj_filary_do_playlisty(state)
    return state


def _migruj_filary_do_playlisty(state: dict) -> None:
    """Filary żyją W PLAYLISTACH (decyzja Janka 11.08), nie globalnie.

    Stare globalne filary nie znikają: przy pierwszym wczytaniu stają się
    playlistą „Moje filary" (bez ról — role to nowość, nie zgadujemy ich),
    która od razu jest aktywna. Stary klucz zostaje nietknięty jako zapis
    historyczny — źródłem prawdy są od teraz playlisty."""
    if state["playlisty"] or not state["filary"]:
        return
    state["playlisty"].append({
        "nazwa": "Moje filary",
        "kotwica": None,
        "filary": [{**e, "rola": ""} for e in state["filary"]],
        "utwory": [],
    })
    state["aktywna_playlista"] = 0


def aktywna_playlista(state: dict) -> dict | None:
    idx = state.get("aktywna_playlista")
    pl = state.get("playlisty", [])
    if idx is None or not (0 <= idx < len(pl)):
        return None
    return pl[idx]


def nowa_playlista(state: dict, nazwa: str) -> int:
    """Nowa playlista staje się aktywna; zaraz po nazwie wracamy do Biblioteki,
    gdzie DJ zaznacza filary (kolejność z decyzji Janka 12.08 — kotwica nie jest
    wymuszonym krokiem, ustawia się ją polem „Brzmi jak…" w dowolnej chwili)."""
    state["playlisty"].append({"nazwa": nazwa, "kotwica": None, "filary": [],
                               "utwory": []})
    state["aktywna_playlista"] = len(state["playlisty"]) - 1
    return state["aktywna_playlista"]


def ustaw_kotwice_playlisty(state: dict, kotwica: str | None) -> bool:
    pl = aktywna_playlista(state)
    if pl is None:
        return False
    pl["kotwica"] = kotwica
    return True


def zapisz_utwory_playlisty(state: dict, wpisy: list[dict]) -> bool:
    """Zbudowany set trafia DO aktywnej playlisty (Janek 12.08: „powinno
    automatycznie zapisywać utwory po tym jak klikam buduj").

    Ostatnia budowa wygrywa — playlista trzyma jeden, aktualny set. Wpisy
    niosą track_id ORAZ ścieżkę (ten sam wzór ratunkowy co filary)."""
    pl = aktywna_playlista(state)
    if pl is None:
        return False
    pl["utwory"] = list(wpisy)
    return True


def utwory_playlisty(state: dict) -> list[dict]:
    pl = aktywna_playlista(state)
    return pl.get("utwory", []) if pl is not None else []


def filary_wpisy(state: dict) -> list[dict]:
    """Wpisy filarów AKTYWNEJ playlisty — jedyne źródło prawdy dla budowy."""
    pl = aktywna_playlista(state)
    return pl["filary"] if pl is not None else []


def rola_filara(state: dict, track_id: str, path: str) -> str | None:
    """Rola filara albo None, gdy utwór nie jest filarem aktywnej playlisty."""
    i = _entry_index(filary_wpisy(state), track_id, path)
    return filary_wpisy(state)[i].get("rola", "") if i is not None else None


def ustaw_filar(state: dict, track_id: str, path: str,
                rola: str) -> tuple[bool, str | None]:
    """Wpisz/zmień filar Z ROLĄ w aktywnej playliście.

    Zwraca (czy_wpisany, powód_odmowy). Role wyłączności (otwarcie,
    zamknięcie) wypierają poprzedniego posiadacza — dwóch otwierających
    to sprzeczność, a cichy konflikt byłby gorszy niż jawna wymiana."""
    if rola not in ROLE_FILARA:
        return False, f"nieznana rola: {rola}"
    pl = aktywna_playlista(state)
    if pl is None:
        return False, ("filary żyją w playlistach — najpierw wybierz albo "
                       "utwórz playlistę")
    wpisy = pl["filary"]
    i = _entry_index(wpisy, track_id, path)
    if i is None and len(wpisy) >= MAX_FILARY:
        return False, (f"limit {MAX_FILARY} filarów — więcej filarów niż "
                       f"przestrzeni do projektowania to już playlista ręczna")
    if rola in ("otwarcie", "zamkniecie"):
        for e in wpisy:
            if e.get("rola") == rola and e.get("track_id") != track_id:
                e["rola"] = ""
    if i is None:
        wpisy.append({"track_id": track_id, "path": path, "rola": rola})
    else:
        wpisy[i]["rola"] = rola
    return True, None


def zdejmij_filar(state: dict, track_id: str, path: str) -> bool:
    wpisy = filary_wpisy(state)
    i = _entry_index(wpisy, track_id, path)
    if i is None:
        return False
    wpisy.pop(i)
    return True


def kolekcja_djow(state: dict) -> list[str]:
    """Kolekcja DJ-ów (decyzja Janka 12.08, przeniesiona ze ściany kart):
    ręcznie zbierani DJ-e, którzy dostają PIERWSZEŃSTWO w polu „Brzmi jak…"
    i ✓ obok nazwiska. Kolejność = kolejność zbierania."""
    return state.get("kolekcja_djow", [])


def w_kolekcji(state: dict, dj: str) -> bool:
    return dj in state.get("kolekcja_djow", [])


def przelacz_kolekcje_dj(state: dict, dj: str) -> bool:
    """Dodaj/zdejmij DJ-a z kolekcji. Zwraca True, gdy jest TERAZ w kolekcji."""
    kol = state.setdefault("kolekcja_djow", [])
    if dj in kol:
        kol.remove(dj)
        return False
    kol.append(dj)
    return True


def nazwa_z_metadanych(by_id: dict) -> str:
    """Propozycja nazwy playlisty z metadanych puli (wzór z praktyki Janka:
    „Piątek · 130–135 · jak Ben UFO"): dzień tygodnia + rozpiętość tempa +
    dominujący gatunek. Propozycja, nie wyrok — pole zostaje edytowalne."""
    import datetime

    dni = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek",
           "Sobota", "Niedziela"]
    czesci = [dni[datetime.date.today().weekday()]]
    bpmy = [a.track.bpm_estimate for a in by_id.values()
            if a.track.bpm_estimate]
    if bpmy:
        czesci.append(f"{round(min(bpmy))}–{round(max(bpmy))}")
    gatunki: dict[str, int] = {}
    for a in by_id.values():
        g = (a.track.style_label or "").strip()
        if g:
            gatunki[g] = gatunki.get(g, 0) + 1
    if gatunki:
        czesci.append(max(gatunki, key=gatunki.get))
    return " · ".join(czesci)


def _domyslna(pula: str) -> bool:
    from dancelab.tui.app import PROCESSED_DEFAULT

    return (pathlib.Path(pula).expanduser().resolve(strict=False)
            == pathlib.Path(PROCESSED_DEFAULT).expanduser().resolve(strict=False))


def save_state(state: dict, pula: str | None = None) -> None:
    sciezka = sciezka_stanu(pula)
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    sciezka.write_text(json.dumps(state, ensure_ascii=False, indent=1))


def _entry_index(entries: list[dict], track_id: str, path: str) -> int | None:
    for i, e in enumerate(entries):
        if e.get("track_id") == track_id or e.get("path") == path:
            return i
    return None


def toggle_track(state: dict, kind: str, track_id: str,
                 path: str) -> tuple[bool, str | None]:
    """Przełącz wpis utworu. kind: 'ulubione_utwory' | 'filary'.

    Zwraca (czy_teraz_wpisany, powód_odmowy). Odmowa tylko przy limicie
    filarów — i mówi dlaczego, zgodnie z uzasadnieniem Janka."""
    entries = state[kind]
    i = _entry_index(entries, track_id, path)
    if i is not None:
        entries.pop(i)
        return False, None
    if kind == "filary" and len(entries) >= MAX_FILARY:
        return False, (f"limit {MAX_FILARY} filarów — więcej filarów niż "
                       f"przestrzeni do projektowania to już playlista ręczna")
    entries.append({"track_id": track_id, "path": path})
    return True, None


def resolve_tracks(entries: list[dict], by_id: dict) -> tuple[list[str], list[str]]:
    """Wpisy → track_id obecne w puli. Braki wracają po imieniu, nie znikają."""
    by_path = {a.track.source_path: tid for tid, a in by_id.items()}
    ids: list[str] = []
    missing: list[str] = []
    for e in entries:
        tid = e.get("track_id")
        if tid in by_id:
            ids.append(tid)
            continue
        alt = by_path.get(e.get("path", ""))
        if alt is not None:
            ids.append(alt)
        else:
            missing.append(pathlib.Path(e.get("path", "?")).stem[:40])
    return ids, missing
