"""Build the ``mapowanie`` table linking the separate identifier systems.

Every link records how it was made and how much it is worth:

``identycznosc`` (1.0)
    The same value appears on both sides — a Rekordbox content_id embedded in
    an Apple record, a YouTube id in a mix link. This is identity.

``nazwa_nfc`` (0.8)
    Artist and title agree after normalisation. This is a strong hint and
    nothing more: two different pressings, edits or remasters can normalise to
    the same string. It is never promoted to identity.

Ambiguous name matches — one normalised name pointing at several candidates —
are deliberately **not** written. They are counted and reported instead,
because a link nobody can trust is worse than a gap somebody can see.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

DJ_MAP = Path("data/reports/corpus_ordering/dj_map.json")
DATASET = Path("data/reports/corpus_ordering/dataset.json")

PEWNOSC_IDENTYCZNOSC = 1.0
PEWNOSC_NAZWA = 0.8


def norm(text: str | None) -> str:
    """Normalise a name for comparison.

    Taken verbatim from ``wgraj_playlisty.py``, where it was measured on 7086
    playlist entries. Reusing the proven function matters more than tidying it:
    a different normaliser would silently produce different coverage numbers.
    """
    s = unicodedata.normalize("NFC", text or "").casefold()
    s = re.sub(r"[\(\[].*?[\)\]]", " ", s)  # (Original Mix), [Remaster]…
    s = re.sub(r"feat\.?.*$", " ", s)
    s = re.sub(r"[^0-9a-zà-ɏ]+", " ", s)
    return " ".join(s.split())


def _klucz(wykonawca: str | None, tytul: str | None) -> str:
    """Join key: normalised artist and title. Empty when either side is blank."""
    a, t = norm(wykonawca), norm(tytul)
    return f"{a}|{t}" if a and t else ""


def _wpisz(conn: Any, rows: list[tuple[Any, ...]]) -> int:
    if not rows:
        return 0
    with conn.cursor() as cur, cur.copy(
        "COPY mapowanie (system_zrodlowy, id_zrodlowy, system_docelowy,"
        " id_docelowy, metoda, pewnosc) FROM STDIN"
    ) as copy:
        for row in rows:
            copy.write_row(row)
    return len(rows)


def _index(pairs: list[tuple[str, str | None, str | None]]) -> dict[str, list[str]]:
    """Group ids by their normalised artist|title key."""
    out: dict[str, list[str]] = {}
    for ident, wykonawca, tytul in pairs:
        key = _klucz(wykonawca, tytul)
        if key:
            out.setdefault(key, []).append(ident)
    return out


def run(conn: Any) -> dict[str, int]:
    """Rebuild ``mapowanie`` from scratch. Returns a coverage report."""
    report: dict[str, int] = {}
    with conn.cursor() as cur:
        cur.execute("TRUNCATE mapowanie RESTART IDENTITY")

        # ---- 1. stage name -> canonical artist (exact, case-insensitive) ---
        cur.execute("SELECT artysta_id, nazwa FROM artysta")
        artysci = {norm(n): a for a, n in cur.fetchall() if norm(n)}

        rows: list[tuple[Any, ...]] = []
        for tabela, system in (
            ("artysta_profil", "profil"),
            ("miks", "miks_ksywa"),
            ("wystep", "wystep_ksywa"),
        ):
            cur.execute(
                f"SELECT DISTINCT ksywa FROM {tabela} WHERE ksywa IS NOT NULL"  # noqa: S608
            )
            nazwy = [r[0] for r in cur.fetchall()]
            trafione = 0
            for ksywa in nazwy:
                target = artysci.get(norm(ksywa))
                if target:
                    rows.append(
                        (system, ksywa, "artysta", target, "nazwa_nfc", PEWNOSC_NAZWA)
                    )
                    trafione += 1
            report[f"{system}->artysta"] = trafione
            report[f"_{system}_bez_pary"] = len(nazwy) - trafione

        # ---- 2. tracklist position -> canonical track ---------------------
        cur.execute("SELECT utwor_id, wykonawca, tytul FROM utwor")
        utwory = _index(cur.fetchall())

        cur.execute(
            "SELECT id, wykonawca_utworu, tytul_utworu FROM pozycja_tracklisty"
        )
        pozycje = cur.fetchall()
        trafione = niejednoznaczne = 0
        aktualizacje: list[tuple[str, int]] = []
        for poz_id, wykonawca, tytul in pozycje:
            key = _klucz(wykonawca, tytul)
            kandydaci = utwory.get(key, []) if key else []
            if len(kandydaci) == 1:
                aktualizacje.append((kandydaci[0], poz_id))
                trafione += 1
            elif len(kandydaci) > 1:
                niejednoznaczne += 1
        report["tracklista->utwor"] = trafione
        report["_tracklista_niejednoznaczne"] = niejednoznaczne
        report["_tracklista_bez_pary"] = len(pozycje) - trafione - niejednoznaczne

        # The FK on pozycja_tracklisty is the working link; mapowanie would
        # duplicate 40k rows for no gain, so only the column is filled.
        cur.executemany(
            "UPDATE pozycja_tracklisty SET utwor_id = %s WHERE id = %s",
            aktualizacje,
        )

        # ---- 3. canonical track -> our analysis ---------------------------
        cur.execute("SELECT track_id, wykonawca, tytul FROM analiza")
        analizy = _index(cur.fetchall())

        trafione = niejednoznaczne = 0
        for key, utwor_ids in utwory.items():
            kandydaci = analizy.get(key, [])
            if len(kandydaci) == 1 and len(utwor_ids) == 1:
                rows.append(
                    (
                        "utwor", utwor_ids[0], "analiza", kandydaci[0],
                        "nazwa_nfc", PEWNOSC_NAZWA,
                    )
                )
                trafione += 1
            elif kandydaci:
                niejednoznaczne += 1
        report["utwor->analiza"] = trafione
        report["_utwor_analiza_niejednoznaczne"] = niejednoznaczne

        # ---- 4. Apple preview vector -> our analysis (true identity) -------
        cur.execute(
            "SELECT klucz, meta ->> 'content_id' FROM wektor"
            " WHERE przestrzen = 'apple_preview' AND meta ? 'content_id'"
        )
        apple = cur.fetchall()
        cur.execute("SELECT track_id FROM analiza")
        znane = {r[0] for r in cur.fetchall()}
        trafione = 0
        for klucz, content_id in apple:
            track_id = f"rb{content_id}"
            if track_id in znane:
                rows.append(
                    (
                        "apple_wektor", klucz, "analiza", track_id,
                        "identycznosc", PEWNOSC_IDENTYCZNOSC,
                    )
                )
                trafione += 1
        report["apple_wektor->analiza"] = trafione
        report["_apple_bez_analizy"] = len(apple) - trafione

        # ---- 5. mix -> corpus embedding, by YouTube id (true identity) ----
        cur.execute(
            "SELECT miks_id, youtube_id FROM miks WHERE youtube_id IS NOT NULL"
        )
        miksy = cur.fetchall()
        cur.execute("SELECT DISTINCT klucz FROM wektor WHERE zrodlo = 'korpus'")
        korpus = {r[0] for r in cur.fetchall()}
        trafione = 0
        for miks_id, youtube_id in miksy:
            if youtube_id in korpus:
                rows.append(
                    (
                        "miks", str(miks_id), "wektor_korpus", youtube_id,
                        "identycznosc", PEWNOSC_IDENTYCZNOSC,
                    )
                )
                trafione += 1
        report["miks->wektor_korpus"] = trafione
        report["_miks_yt_bez_wektora"] = len(miksy) - trafione

        # ---- 6. corpus mix -> canonical artist ---------------------------
        # The corpus and the festival map turned out to share no mixes at all
        # (the map links to SoundCloud, the corpus to YouTube). They do share
        # people, and that is the bridge worth having: it says which DJs we
        # hold both a festival record and recorded material for.
        dj_by_mix: dict[str, str] = {}
        if DJ_MAP.exists():
            dj_by_mix = json.loads(DJ_MAP.read_text(encoding="utf-8")).get(
                "dj_by_mix", {}
            )
        trafione = 0
        nieznani: set[str] = set()
        for mix_id, slug in dj_by_mix.items():
            # Slugs are hyphenated names; norm() flattens both sides equally.
            target = artysci.get(norm(slug))
            if target:
                rows.append(
                    (
                        "korpus_mix", mix_id, "artysta", target,
                        "nazwa_nfc", PEWNOSC_NAZWA,
                    )
                )
                trafione += 1
            else:
                nieznani.add(slug)
        report["korpus_mix->artysta"] = trafione
        report["_korpus_djow_spoza_mapy"] = len(nieznani)

        # ---- 7. corpus mix -> the track vectors it actually used ---------
        if DATASET.exists() and dj_by_mix:
            observations = json.loads(DATASET.read_text(encoding="utf-8")).get(
                "observations", []
            )
            pary: set[tuple[str, str]] = set()
            for obs in observations:
                mix_id = obs.get("mix_id")
                if not mix_id:
                    continue
                # Only the selected track is a decision the DJ actually made;
                # candidates were merely offered and must not be recorded as
                # something they played.
                selected = obs.get("selected_track_id")
                if selected:
                    pary.add((mix_id, selected))
                for played in obs.get("history_track_ids") or []:
                    pary.add((mix_id, played))
            trafione = 0
            for mix_id, klucz in sorted(pary):
                if klucz in korpus:
                    rows.append(
                        (
                            "korpus_mix", mix_id, "wektor_korpus", klucz,
                            "identycznosc", PEWNOSC_IDENTYCZNOSC,
                        )
                    )
                    trafione += 1
            report["korpus_mix->wektor_korpus"] = trafione
            report["_korpus_par_bez_wektora"] = len(pary) - trafione

    report["mapowanie_wierszy"] = _wpisz(conn, rows)
    conn.commit()
    return report
