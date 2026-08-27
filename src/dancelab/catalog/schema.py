"""DDL for the identity catalog, plus a tiny forward-only migration runner.

Design notes that are easy to lose otherwise:

* The spreadsheet carries two layers. Canonical tables (``artysta``,
  ``utwor``, ``szew``) own the ``A/U/S`` identifiers. Source tables
  (``artysta_profil``, ``miks``, ``wystep``…) are keyed by the stage name as
  typed in the source and never invent an identifier they do not have.
* Dates arrive in mixed and sometimes partial formats. Each date is stored
  twice: ``*_tekst`` keeps the source string verbatim, ``*`` holds the parsed
  DATE when parsing succeeded. Nothing is discarded to make a column tidy.
* Measurement columns on ``utwor`` and ``szew`` exist and start empty. The
  spreadsheet already reserved them; this is where our analyses will land.
"""

from __future__ import annotations

from typing import Any

SCHEMA_VERSION = 3

# --- migration 1 -----------------------------------------------------------
# Kept as one statement block so a fresh database is built in a single
# transaction: either the whole catalog exists or none of it does.
_MIGRATION_1 = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE schema_version (
    version     integer     PRIMARY KEY,
    applied_at  timestamptz NOT NULL DEFAULT now(),
    note        text
);

-- ---------------------------------------------------------------- canonical

CREATE TABLE artysta (
    artysta_id        text PRIMARY KEY,          -- A00001
    nazwa             text NOT NULL,
    ra_id             text,
    soundcloud        text,
    bandcamp          text,
    kraj              text,
    kraj_zamieszkania text,
    wytwornie         text,
    obserwujacych_ra  integer
);
CREATE INDEX artysta_nazwa_idx ON artysta (lower(nazwa));

CREATE TABLE utwor (
    utwor_id          text PRIMARY KEY,          -- U000001
    wykonawca         text,
    tytul             text,
    wydawca           text,
    wystapien         integer,
    granych_przez     integer,
    lata              text,
    zrodla            text,
    -- Measurement columns: reserved by the spreadsheet, filled by our engine.
    bpm               double precision,
    bpm_pewnosc       double precision,
    tonacja           text,
    tonacja_klasyczna text,
    tonacja_pewnosc   double precision,
    energia           double precision,
    gestosc_groove    double precision,
    obecnosc_basu     double precision,
    dlugosc_s         double precision,
    analiza_wersja    text,
    analiza_data      text
);
CREATE INDEX utwor_wykonawca_idx ON utwor (lower(coalesce(wykonawca, '')));
CREATE INDEX utwor_tytul_idx     ON utwor (lower(coalesce(tytul, '')));

CREATE TABLE szew (
    szew_id            text PRIMARY KEY,         -- S000001
    artysta_id         text REFERENCES artysta (artysta_id),
    ksywa              text,
    wydarzenie         text,
    data_tekst         text,
    data               date,
    poz_z              integer,
    poz_do             integer,
    utwor_wychodzacy   text,
    utwor_wchodzacy    text,
    utwor_z_id         text REFERENCES utwor (utwor_id),
    utwor_do_id        text REFERENCES utwor (utwor_id),
    czas_wejscia       text,
    czas_ms            bigint,
    zrodlo_czasu       text,
    zrodlo_pozycji     text,
    status_w_lejku     text,
    link_setu          text,
    -- Measurement columns, empty on import.
    bpm_z                       double precision,
    bpm_do                      double precision,
    delta_bpm                   double precision,
    delta_bpm_proc              double precision,
    tonacja_z                   text,
    tonacja_do                  text,
    zgodnosc_harmoniczna        text,
    dlugosc_przejscia_s         double precision,
    typ_przejscia               text,
    bas_wstrzymany              boolean,
    energia_z                   double precision,
    energia_do                  double precision,
    delta_energii               double precision,
    analiza_wersja              text,
    analiza_data                text,
    zweryfikowany_przez_czlowieka boolean,
    uzywalny_do_uczenia           boolean
);
CREATE INDEX szew_artysta_idx ON szew (artysta_id);
CREATE INDEX szew_para_idx    ON szew (utwor_z_id, utwor_do_id);
CREATE INDEX szew_lejek_idx   ON szew (status_w_lejku);

-- ------------------------------------------------------------------- source

CREATE TABLE artysta_profil (
    ksywa               text PRIMARY KEY,
    artysta_id          text REFERENCES artysta (artysta_id),
    soundcloud          text,
    apple_music         text,
    gatunek_apple       text,
    bandcamp            text,
    skad_bandcamp       text,
    gatunek_bandcamp    text,
    wytwornie_ra        text,
    kraj_ra             text,
    obserwujacych_ra    integer,
    wystepow_w_ra       integer,
    festiwal_2026       text,
    miksow_w_bazie      integer,
    lata_w_garbiczu     text,
    uwagi               text,
    kandydaci           text
);

CREATE TABLE dyskografia (
    id        bigserial PRIMARY KEY,
    ksywa     text,
    tytul     text,
    album     text,
    rok       integer,
    link      text,
    zrodlo    text
);
CREATE INDEX dyskografia_ksywa_idx ON dyskografia (lower(ksywa));

CREATE TABLE miks (
    miks_id        bigserial PRIMARY KEY,
    ksywa          text,
    tytul          text,
    wydarzenie     text,
    typ            text,
    scena          text,
    format         text,
    rola           text,
    czas           text,
    data_tekst     text,
    data           date,
    zrodlo         text,
    pewnosc        text,
    dlugosc_min    double precision,
    konto          text,
    kto_gral_obok  text,
    link           text,
    opis           text,
    -- Extracted from the link when it is a YouTube URL: this is the join key
    -- to the corpus embeddings, whose track keys are video IDs.
    youtube_id     text
);
CREATE INDEX miks_ksywa_idx   ON miks (lower(ksywa));
CREATE INDEX miks_youtube_idx ON miks (youtube_id);

CREATE TABLE wystep (
    id          bigserial PRIMARY KEY,
    ksywa       text,
    kiedy       text,
    data_tekst  text,
    data        date,
    wydarzenie  text,
    miejsce     text,
    miasto      text,
    kraj        text,
    link        text
);
CREATE INDEX wystep_ksywa_idx ON wystep (lower(ksywa));
CREATE INDEX wystep_data_idx  ON wystep (data);

CREATE TABLE pozycja_tracklisty (
    id                bigserial PRIMARY KEY,
    ksywa             text,
    setname           text,
    wydarzenie        text,
    data_tekst        text,
    data              date,
    pewnosc_polaczenia text,
    pozycja           integer,
    czas              text,
    rozpoznany        text,
    wykonawca_utworu  text,
    tytul_utworu      text,
    wydawca           text,
    zrodlo_pozycji    text,
    link_setu         text,
    -- Filled by dopasuj.py, never by the importer.
    utwor_id          text REFERENCES utwor (utwor_id)
);
CREATE INDEX poztr_ksywa_idx ON pozycja_tracklisty (lower(ksywa));
CREATE INDEX poztr_utwor_idx ON pozycja_tracklisty (utwor_id);
CREATE INDEX poztr_set_idx   ON pozycja_tracklisty (link_setu, pozycja);

CREATE TABLE program (
    id               bigserial PRIMARY KEY,
    festiwal         text,
    ksywa            text,
    dzien            text,
    data_tekst       text,
    data             date,
    scena            text,
    charakter_sceny  text,
    start            text,
    koniec           text,
    rola             text,
    format           text
);

CREATE TABLE kanon_ra (
    id                  bigserial PRIMARY KEY,
    kategoria           text,
    miejsce             text,
    kolejnosc           integer,
    ksywa               text,
    tytul               text,
    rok                 integer,
    profil_ra           text,
    soundcloud_id       text,
    autor_tekstu        text,
    uzasadnienie        text,
    artykul_ra          text
);

CREATE TABLE de_school (
    id             bigserial PRIMARY KEY,
    data_tekst     text,
    data           date,
    dzien          text,
    cykl           text,
    ksywa          text,
    scena          text,
    typ            text,
    format         text,
    zrodlo         text,
    pewnosc        text,
    strona_archiwum text,
    link           text
);

-- --------------------------------------------------------------- our own

CREATE TABLE analiza (
    track_id        text PRIMARY KEY,            -- rb{ContentID} or a hash
    sciezka_json    text NOT NULL,
    suma_kontrolna  text,
    rozmiar_b       bigint,
    wykonawca       text,
    tytul           text,
    sciezka_audio   text,
    bpm             double precision,
    tonacja         text,
    zrodlo_tonacji  text,
    pewnosc_tonacji double precision,
    dlugosc_s       double precision,
    wersja          text,
    data_analizy    text,
    -- Local library vs corpus. The 11.08 rule limits measurements to the DJ
    -- map, so every query that produces an argument must filter on this.
    zrodlo          text NOT NULL DEFAULT 'nieznane'
);
CREATE INDEX analiza_wyk_idx    ON analiza (lower(coalesce(wykonawca, '')));
CREATE INDEX analiza_tytul_idx  ON analiza (lower(coalesce(tytul, '')));
CREATE INDEX analiza_zrodlo_idx ON analiza (zrodlo);

CREATE TABLE wektor (
    id           bigserial PRIMARY KEY,
    klucz        text NOT NULL,                  -- file path or YouTube ID
    przestrzen   text NOT NULL,                  -- which embedding file
    model        text,
    embedding    vector(512) NOT NULL,
    zrodlo       text NOT NULL DEFAULT 'nieznane',
    UNIQUE (przestrzen, klucz)
);
CREATE INDEX wektor_klucz_idx ON wektor (klucz);

CREATE TABLE sesja (
    sesja_id            bigserial PRIMARY KEY,
    nazwa               text,
    data                date,
    sprzet              text,
    pozycje_startowe    boolean NOT NULL DEFAULT false,
    uwagi               text
);

CREATE TABLE rejestr (
    rejestr_id     bigserial PRIMARY KEY,
    sesja_id       bigint REFERENCES sesja (sesja_id) ON DELETE CASCADE,
    sciezka        text NOT NULL UNIQUE,
    suma_kontrolna text,
    zdarzen        integer,
    dlugosc_s      double precision,
    zaczeto        timestamptz
);

CREATE TABLE nagranie (
    nagranie_id  bigserial PRIMARY KEY,
    sesja_id     bigint REFERENCES sesja (sesja_id) ON DELETE CASCADE,
    sciezka_wav  text NOT NULL,
    sciezka_cue  text,
    dlugosc_s    double precision,
    czestotliwosc integer
);

CREATE TABLE playlista (
    playlista_id bigserial PRIMARY KEY,
    nazwa        text NOT NULL UNIQUE,
    rodzaj       text,
    utworzona    date,
    uwagi        text
);

CREATE TABLE pozycja_playlisty (
    id           bigserial PRIMARY KEY,
    playlista_id bigint NOT NULL REFERENCES playlista (playlista_id) ON DELETE CASCADE,
    pozycja      integer NOT NULL,
    wykonawca    text,
    tytul        text,
    track_id     text REFERENCES analiza (track_id),
    UNIQUE (playlista_id, pozycja)
);

CREATE TABLE ocena (
    ocena_id       bigserial PRIMARY KEY,
    playlista_id   bigint REFERENCES playlista (playlista_id),
    pozycja_z      integer,
    pozycja_do     integer,
    ocena          integer CHECK (ocena BETWEEN 1 AND 5),
    kategorie      text[],
    komentarz      text,
    oceniajacy     text,
    data           date
);

-- ------------------------------------------------------------------ glue

CREATE TABLE mapowanie (
    id               bigserial PRIMARY KEY,
    system_zrodlowy  text NOT NULL,
    id_zrodlowy      text NOT NULL,
    system_docelowy  text NOT NULL,
    id_docelowy      text NOT NULL,
    metoda           text NOT NULL,
    pewnosc          double precision NOT NULL CHECK (pewnosc >= 0 AND pewnosc <= 1),
    kto_potwierdzil  text,
    data             timestamptz NOT NULL DEFAULT now(),
    UNIQUE (system_zrodlowy, id_zrodlowy, system_docelowy, id_docelowy, metoda)
);
CREATE INDEX mapowanie_z_idx  ON mapowanie (system_zrodlowy, id_zrodlowy);
CREATE INDEX mapowanie_do_idx ON mapowanie (system_docelowy, id_docelowy);
"""

# --- migration 2 -----------------------------------------------------------
# The rating tables were designed before the paper forms existed. The forms key
# a judgement by pair_id and by the two track ids, not by playlist positions,
# and they carry the engine's own score so agreement can be measured later.
_MIGRATION_2 = """
ALTER TABLE ocena
    ADD COLUMN pair_id      text,
    ADD COLUMN track_id_a   text,
    ADD COLUMN track_id_b   text,
    ADD COLUMN engine_score double precision,
    ADD COLUMN slepa        boolean,
    ADD COLUMN sesja_papier text;

ALTER TABLE ocena ADD CONSTRAINT ocena_pair_unique UNIQUE (pair_id);
CREATE INDEX ocena_pusta_idx ON ocena ((ocena IS NULL));
"""

# --- migration 3 -----------------------------------------------------------
# Not every embedding file is a bare key -> vector map. The Apple preview file
# stores a record per track carrying the Rekordbox content_id, which is a
# direct bridge between two of our identifier systems. Rather than discard it,
# whatever the file supplied alongside the vector is kept as JSONB.
_MIGRATION_3 = """
ALTER TABLE wektor ADD COLUMN meta jsonb;
CREATE INDEX wektor_meta_content_idx
    ON wektor ((meta ->> 'content_id'))
    WHERE meta ? 'content_id';
"""

MIGRATIONS: dict[int, str] = {
    1: _MIGRATION_1,
    2: _MIGRATION_2,
    3: _MIGRATION_3,
}


def current_version(conn: Any) -> int:
    """Return the applied schema version, or 0 on an empty database."""
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.schema_version')")
        if cur.fetchone()[0] is None:
            return 0
        cur.execute("SELECT coalesce(max(version), 0) FROM schema_version")
        return int(cur.fetchone()[0])


def apply(conn: Any, *, target: int = SCHEMA_VERSION) -> list[int]:
    """Apply pending migrations up to ``target``; return the ones applied."""
    applied: list[int] = []
    version = current_version(conn)
    for number in sorted(MIGRATIONS):
        if version < number <= target:
            with conn.cursor() as cur:
                cur.execute(MIGRATIONS[number])
                cur.execute(
                    "INSERT INTO schema_version (version, note) VALUES (%s, %s)",
                    (number, f"catalog migration {number}"),
                )
            conn.commit()
            applied.append(number)
    return applied


def drop_all(conn: Any) -> None:
    """Remove every catalog object. Used by tests and by a deliberate rebuild."""
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    conn.commit()
