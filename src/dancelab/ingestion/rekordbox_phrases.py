"""Struktura utworu z analizy Rekordboxa — intro, wejścia, chorus, outro.

To był największy brak silnika: segmenty istniały, ale **wszystkie 1881 były bez
etykiety** (zmierzone 2026-08-03 na 243 utworach). Silnik wiedział, że w tym
miejscu coś się zmienia; nie wiedział, czy to intro, breakdown czy outro.
Bez tego nie da się powiedzieć „wyjdź w outro" ani rzetelnie snapować do fraz.

Okazało się, że liczyć tego nie trzeba. Rekordbox robi własną analizę fraz
(Phrase Analysis, od wersji 5.2) i **zapisuje ją na dysku Janka dla 1871 utworów**.
Leży w `~/Library/Pioneer/rekordbox/share/PIONEER/USBANLZ/**/ANLZ*.EXT`, tag
`PSSI`; przeliczenie bitów na sekundy bierzemy z siatki Rekordboxa (`PQTZ`
w `.DAT`), bo numery fraz indeksują właśnie ją, nie naszą.

SŁOWNIKI odczytane ze zrzutów ekranu Janka, nie zgadnięte — dla każdego utworu
porównana sekwencja typów z etykietami, które on widzi w programie:

  mood 1 (klubowy)   Coil: [1,1,2,2,2,5,3,…,6] ↔ INTRO · INTRO2 · UP1 · UP1 ·
                     UP3 · CHORUS · DOWN · … · OUTRO
  mood 2 (piosenkowy) Mockingbirds: [1,2,3,4,5,6,9,9,9,10] ↔ INTRO · VERSE1 …
                     VERSE5 · CHORUS ×3 · OUTRO; potwierdzone drugi raz na
                     Neurology Department (z BRIDGE = 8)

  mood 3 — NIEPOTWIERDZONE. Sister i Nature Boy używają słownika piosenkowego,
  ale numeracja się nie zgadza z mood 2 (tam 3 wygląda na VERSE1, nie VERSE2).
  Dlatego dla mood 3 **nie podajemy etykiety** — wraca surowy numer i ostrzeżenie.
  Zgadnięcie tutaj byłoby dokładnie tym rodzajem liczby, która wygląda na
  zmierzoną (ADR-005).

CZYJ TO OSĄD. Pioneera, nie nasz — i tak ma być opisany w danych (`source`).
Ale to jest ten sam osąd, który Janek widzi na ekranie i według którego gra,
więc jako wejście do decyzji jest lepszy niż nasza cisza.

Działa wyłącznie dla plików lokalnych. Strumienie Apple Music nie mają analizy.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass, field

SHARE = pathlib.Path.home() / "Library/Pioneer/rekordbox/share"

# Odczytane ze zrzutów Janka (03.08). Numery bez wpisu zostają bez etykiety.
CLUB = {1: "INTRO", 2: "UP", 3: "DOWN", 5: "CHORUS", 6: "OUTRO"}
SONG = {1: "INTRO", 2: "VERSE1", 3: "VERSE2", 4: "VERSE3", 5: "VERSE4",
        6: "VERSE5", 7: "VERSE6", 8: "BRIDGE", 9: "CHORUS", 10: "OUTRO"}
BANKS = {1: CLUB, 2: SONG}          # mood 3 świadomie nieobsłużony

# Etykiety, na których stoją reguły produktu. Trzymane osobno, żeby zmiana
# słownika Pioneera nie rozjechała się cicho z regułami.
ENTRY_LIKE = {"INTRO", "DOWN", "BRIDGE"}      # gdzie da się wejść
EXIT_LIKE = {"OUTRO", "DOWN", "BRIDGE"}       # gdzie da się wyjść
PEAK_LIKE = {"CHORUS", "UP"}


@dataclass(frozen=True)
class Phrase:
    index: int
    kind: int
    label: str | None            # None = słownik niepotwierdzony dla tego mood
    start_beat: int
    start_sec: float | None
    end_beat: int | None
    end_sec: float | None
    has_fill: bool
    fill_start_beat: int | None


@dataclass(frozen=True)
class PhraseAnalysis:
    mood: int
    bank: int
    end_beat: int
    phrases: list[Phrase] = field(default_factory=list)
    source: str = "rekordbox_phrase"
    warnings: list[str] = field(default_factory=list)

    def at(self, sec: float) -> Phrase | None:
        for p in self.phrases:
            if p.start_sec is None:
                continue
            if p.start_sec <= sec and (p.end_sec is None or sec < p.end_sec):
                return p
        return None

    def of_label(self, *labels: str) -> list[Phrase]:
        want = set(labels)
        return [p for p in self.phrases if p.label in want]

    @property
    def outro(self) -> Phrase | None:
        got = self.of_label("OUTRO")
        return got[-1] if got else None

    @property
    def intro(self) -> Phrase | None:
        got = self.of_label("INTRO")
        return got[0] if got else None


def _beat_times(dat: pathlib.Path) -> dict[int, float]:
    """Numer bitu → sekunda, z siatki Rekordboxa. Frazy indeksują JĄ."""
    from pyrekordbox.anlz import AnlzFile
    try:
        a = AnlzFile.parse_file(str(dat))
        c = a.get_tag("PQTZ").content
    except Exception:
        return {}
    return {int(e.beat_index if hasattr(e, "beat_index") else i + 1):
            float(e.time) / 1000.0 for i, e in enumerate(c.entries)}


def read_phrases(ext: str | pathlib.Path,
                 dat: str | pathlib.Path | None = None
                 ) -> tuple[PhraseAnalysis | None, str]:
    """(analiza, powód). None zawsze z powodem — nigdy pusta struktura udająca wynik."""
    from pyrekordbox.anlz import AnlzFile

    ext = pathlib.Path(ext)
    if not ext.exists():
        return None, "brak pliku .EXT"
    try:
        tag = AnlzFile.parse_file(str(ext)).get_tag("PSSI")
    except Exception as exc:                       # noqa: BLE001
        return None, f"nie da się odczytać PSSI: {type(exc).__name__}"
    c = tag.content

    dat = pathlib.Path(dat) if dat else ext.with_suffix(".DAT")
    times = _beat_times(dat) if dat.exists() else {}
    warn: list[str] = []
    if not times:
        warn.append("brak siatki Rekordboxa (.DAT) — frazy tylko w bitach")

    book = BANKS.get(int(c.mood))
    if book is None:
        warn.append(f"słownik dla mood={c.mood} niepotwierdzony — bez etykiet")

    ents = list(c.entries)
    out: list[Phrase] = []
    for i, e in enumerate(ents):
        nxt = ents[i + 1].beat if i + 1 < len(ents) else int(c.end_beat)
        out.append(Phrase(
            index=int(e.index), kind=int(e.kind),
            label=(book or {}).get(int(e.kind)) if book else None,
            start_beat=int(e.beat), start_sec=times.get(int(e.beat)),
            end_beat=int(nxt), end_sec=times.get(int(nxt)),
            has_fill=bool(getattr(e, "fill", 0)),
            fill_start_beat=int(e.beat_fill) if getattr(e, "fill", 0) else None,
        ))

    if book and not any(p.label for p in out):
        warn.append("żaden typ nie trafił w słownik — Pioneer mógł go zmienić")

    return PhraseAnalysis(mood=int(c.mood), bank=int(c.bank),
                          end_beat=int(c.end_beat), phrases=out,
                          warnings=warn), "ok"


def phrases_for_path(audio_path: str | pathlib.Path, *, db=None
                     ) -> tuple[PhraseAnalysis | None, str]:
    """Struktura dla pliku audio, przez bazę Rekordboxa (tylko odczyt)."""
    import unicodedata as U

    from pyrekordbox.db6 import tables

    close = False
    if db is None:
        from pyrekordbox import Rekordbox6Database
        db, close = Rekordbox6Database(), True
    try:
        want = U.normalize("NFC", str(pathlib.Path(audio_path)))
        row = None
        for r in db.session.query(tables.DjmdContent).all():
            if U.normalize("NFC", r.FolderPath or "") == want:
                row = r
                break
        if row is None:
            return None, "utworu nie ma w kolekcji Rekordboxa"
        if not row.AnalysisDataPath:
            return None, "Rekordbox nie przeanalizował tego utworu"
        base = SHARE / row.AnalysisDataPath.lstrip("/")
        return read_phrases(base.with_suffix(".EXT"), base.with_suffix(".DAT"))
    finally:
        if close:
            db.close()
