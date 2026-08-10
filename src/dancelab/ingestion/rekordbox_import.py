"""Analiza Rekordboxa → AnalysisResult dla utworów BEZ pliku na dysku.

Zmierzone 09.08 na kolekcji Janka: z 1880 pozycji **1571 to strumienie Apple
Music**, bez pliku, więc DanceLab widział 229 utworów zamiast ~1800. To nie
jest brak muzyki — to brak dostępu do niej. A Rekordbox te utwory JUŻ
przeanalizował: tempo, tonacja, gatunek i siatka w 100%, do tego w plikach
`.EXT` leży fala energii (PWV3, 150 punktów na sekundę) i podział na frazy
(PSSI). Wszystko, czego silnik potrzebuje, żeby wstawić utwór do setu, poza
wektorem brzmienia.

UCZCIWOŚĆ — to są liczby PIONEERA, nie nasze:
* `engine_version="rekordbox-anlz"` na każdej takiej analizie, żeby nikt
  nigdy nie pomylił jej z naszym pomiarem;
* `source_path` zostaje takie, jakie jest (`apple-music:tracks:123`) — to NIE
  jest ścieżka do pliku i nikt nie ma prawa myśleć, że jest;
* czego tu nie ma i nie będzie: odsłuchu, renderu szwu i zapisu cue liczonego
  z audio. Nie ma pliku, więc nie ma dźwięku — warstwy, które go wymagają,
  muszą odmówić z powodem, a nie udawać.

Etykiety sekcji: GRANICE fraz są Pioneera (pole `beat` w PSSI, pewne), ale
jego nazewnictwa faz NIE zgadujemy. Typ nadaje nasza reguła na ZMIERZONEJ
energii: pierwsza fraza to intro, ostatnia outro, reszta groove albo
breakdown wg energii względem mediany utworu, a przy braku rozstrzygnięcia
`unknown`. Lepiej „nie wiem" niż wymyślona nazwa.
"""

from __future__ import annotations

import pathlib
import unicodedata

from dancelab.core.models import (
    AnalysisResult,
    BeatGrid,
    FeatureFrame,
    Segment,
    SegmentType,
    Track,
)

KATALOG_ANALIZ = pathlib.Path.home() / "Library/Pioneer/rekordbox/share"
WERSJA = "rekordbox-anlz"
KLATKA_SEC = 1.0          # tak samo jak w naszych analizach
FALA_NA_SEK = 150         # zmierzone: 31 828 punktów PWV3 na 212 s utworu


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", str(s))


def _sciezki_anlz(anlz: str) -> tuple[pathlib.Path, pathlib.Path]:
    dat = KATALOG_ANALIZ / str(anlz).lstrip("/")
    return dat, dat.with_suffix(".EXT")


def siatka_z_anlz(dat: pathlib.Path, bpm: float) -> BeatGrid | None:
    """Siatka bitów Pioneera: czasy bitów + PEWNA faza taktu (pole `beat`)."""
    from pyrekordbox.anlz import AnlzFile

    if not dat.exists():
        return None
    plik = AnlzFile.parse_file(str(dat))
    tagi = plik.getall_tags("PQTZ")
    if not tagi:
        return None
    bity, downbeaty = [], []
    for wpis in getattr(tagi[0].content, "entries", None) or []:
        czas = float(wpis.time) / 1000.0
        bity.append(czas)
        if int(getattr(wpis, "beat", 0)) == 1:
            downbeaty.append(czas)
    if not bity:
        return None
    return BeatGrid(
        bpm=bpm, beat_times_sec=bity, downbeats_sec=downbeaty,
        # Pioneer NUMERUJE bity w takcie, więc faza taktu jest znana — to
        # jest ta sama informacja, którą rysuje czerwoną linią.
        downbeat_phase_verified=bool(downbeaty), reliable=True,
        diagnostic_flags=["siatka z analizy Rekordboxa"])


def klatki_z_anlz(ext: pathlib.Path, track_id: str,
                  dlugosc_sec: float) -> list[FeatureFrame]:
    """Energia w czasie z fali szczegółowej Pioneera (PWV3).

    Jeden bajt na punkt: dolne 5 bitów to WYSOKOŚĆ słupka (0–31), górne trzy
    to barwa. Bierzemy wysokość, uśredniamy do jednej klatki na sekundę —
    tak samo gęsto jak nasze własne analizy.
    """
    from pyrekordbox.anlz import AnlzFile

    if not ext.exists():
        return []
    plik = AnlzFile.parse_file(str(ext))
    tagi = plik.getall_tags("PWV3")
    if not tagi:
        return []
    punkty = [int(v) & 0x1F for v in (tagi[0].content.entries or [])]
    if not punkty:
        return []
    na_klatke = max(int(FALA_NA_SEK * KLATKA_SEC), 1)
    klatki: list[FeatureFrame] = []
    for i in range(0, len(punkty), na_klatke):
        kawalek = punkty[i:i + na_klatke]
        if not kawalek:
            continue
        klatki.append(FeatureFrame(
            track_id=track_id,
            timestamp_sec=round(i / FALA_NA_SEK, 3),
            rms=round(sum(kawalek) / len(kawalek) / 31.0, 5)))
    return klatki


def _typ_frazy(srednia: float, mediana: float, pierwsza: bool,
               ostatnia: bool) -> SegmentType:
    """Nasza reguła na ZMIERZONEJ energii — nie zgadywanie nazw Pioneera."""
    if pierwsza:
        return SegmentType.intro
    if ostatnia:
        return SegmentType.outro
    if mediana <= 0:
        return SegmentType.unknown
    stosunek = srednia / mediana
    if stosunek >= 1.05:
        return SegmentType.groove
    if stosunek <= 0.75:
        return SegmentType.breakdown
    return SegmentType.unknown


def segmenty_z_anlz(ext: pathlib.Path, siatka: BeatGrid, track_id: str,
                    dlugosc_sec: float,
                    klatki: list[FeatureFrame]) -> list[Segment]:
    """Sekcje z granic fraz Pioneera (PSSI), typ z naszej reguły energii."""
    from pyrekordbox.anlz import AnlzFile

    if not ext.exists() or not siatka.beat_times_sec:
        return []
    plik = AnlzFile.parse_file(str(ext))
    tagi = plik.getall_tags("PSSI")
    if not tagi:
        return []
    bity = siatka.beat_times_sec
    granice: list[float] = []
    for wpis in getattr(tagi[0].content, "entries", None) or []:
        nr = int(getattr(wpis, "beat", 0)) - 1
        if 0 <= nr < len(bity):
            granice.append(bity[nr])
    granice = sorted(set(granice))
    if len(granice) < 2:
        return []

    def energia(od: float, do: float) -> float:
        w = [k.rms for k in klatki
             if k.rms is not None and od <= k.timestamp_sec < do]
        return sum(w) / len(w) if w else 0.0

    konce = granice[1:] + [max(dlugosc_sec, granice[-1] + 1.0)]
    srednie = [energia(a, b) for a, b in zip(granice, konce)]
    znane = sorted(x for x in srednie if x > 0)
    mediana = znane[len(znane) // 2] if znane else 0.0

    segmenty: list[Segment] = []
    for i, (start, koniec) in enumerate(zip(granice, konce)):
        if koniec <= start:
            continue
        segmenty.append(Segment(
            segment_id=f"{track_id}_rb{i}", track_id=track_id,
            start_sec=round(start, 3), end_sec=round(koniec, 3),
            segment_type=_typ_frazy(srednie[i], mediana, i == 0,
                                    i == len(granice) - 1)))
    return segmenty


def analiza_z_wiersza(wiersz, kamelot: dict[str, str],
                      gatunki: dict[int, str],
                      tonacje: dict[str, str] | None = None
                      ) -> AnalysisResult | None:
    """AnalysisResult dla jednego wiersza kolekcji albo None, gdy brak danych."""
    anlz = getattr(wiersz, "AnalysisDataPath", None)
    if not anlz:
        return None
    dat, ext = _sciezki_anlz(str(anlz))
    bpm = (float(wiersz.BPM) / 100.0) if wiersz.BPM else 0.0
    if bpm <= 0:
        return None
    siatka = siatka_z_anlz(dat, bpm)
    if siatka is None:
        return None

    sciezka = str(wiersz.FolderPath or "")
    tid = f"rb{wiersz.ID}"
    dlugosc = float(wiersz.Length or 0) or (
        siatka.beat_times_sec[-1] if siatka.beat_times_sec else 0.0)
    klatki = klatki_z_anlz(ext, tid, dlugosc)
    segmenty = segmenty_z_anlz(ext, siatka, tid, dlugosc, klatki)

    utwor = Track(
        track_id=tid, title=wiersz.Title or None,
        artist=(wiersz.Artist.Name if getattr(wiersz, "Artist", None) else None),
        source_path=sciezka, duration_sec=dlugosc or None,
        bpm_estimate=bpm,
        style_label=gatunki.get(wiersz.GenreID) if wiersz.GenreID else None)
    # Tonacja wprost z tabeli kluczy Rekordboxa — mapa po ścieżkach obejmuje
    # tylko pliki lokalne, a strumienie mają tonację w 1566 z 1571 wierszy.
    cam = (tonacje or {}).get(str(wiersz.KeyID)) if wiersz.KeyID else None
    cam = cam or kamelot.get(_nfc(sciezka))
    if cam:
        from dancelab.decision.harmonic import parse_camelot
        rozbite = parse_camelot(cam)
        utwor.key_estimate = cam
        utwor.key_detection_source = "rekordbox"
        utwor.key_confidence = 1.0
        if rozbite:
            utwor.camelot_number, utwor.camelot_mode = rozbite
    return AnalysisResult(engine_version=WERSJA, track=utwor, beatgrid=siatka,
                          segments=segmenty, features=klatki)


def importuj(limit: int | None = None,
             tylko_bez_pliku: bool = True) -> tuple[list[AnalysisResult],
                                                    list[str]]:
    """(analizy, notatki). Domyślnie tylko utwory BEZ pliku na dysku —
    te z plikiem mierzymy sami i tego nie oddajemy."""
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    from dancelab.ingestion.analysis_enrichment import load_rekordbox_key_map

    kamelot, notka = load_rekordbox_key_map()
    notatki = [notka] if notka else []

    db = Rekordbox6Database()
    try:
        gatunki = {g.ID: g.Name
                   for g in db.session.query(tables.DjmdGenre).all()}
        tonacje = {str(k.ID): k.ScaleName
                   for k in db.session.query(tables.DjmdKey).all()
                   if k.ScaleName}
        wiersze = db.session.query(tables.DjmdContent).all()
        wybrane = []
        for r in wiersze:
            sciezka = str(r.FolderPath or "")
            if not sciezka or not r.AnalysisDataPath:
                continue
            if tylko_bez_pliku and pathlib.Path(sciezka).exists():
                continue
            wybrane.append(r)
        if limit:
            wybrane = wybrane[:limit]
        analizy, odpadly = [], 0
        for r in wybrane:
            try:
                a = analiza_z_wiersza(r, kamelot, gatunki, tonacje)
            except Exception:  # noqa: BLE001 — jeden chory plik ≠ brak importu
                a = None
            if a is None:
                odpadly += 1
            else:
                analizy.append(a)
    finally:
        db.close()

    notatki.append(f"import z Rekordboxa: {len(analizy)} analiz "
                   f"({odpadly} pominiętych — brak siatki albo tempa)")
    return analizy, notatki
