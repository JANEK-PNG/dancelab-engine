"""Cross-cutting queries — the reason the catalog exists.

Each one spans identifier systems that could not be joined before. They are
kept here rather than inlined in scripts so the definition of, say, "a seam we
can actually learn from" lives in exactly one place.

Queries that produce an argument default to corpus-only material, honouring
the 11.08 rule at the level where it is easy to get right.
"""

from __future__ import annotations

from typing import Any

# Seams where both sides of the transition resolve to a track we analysed.
# This is the population any seam model can be trained or tested on.
SZWY_Z_OBIEMA_ANALIZAMI = """
SELECT s.szew_id, s.ksywa, s.wydarzenie,
       s.utwor_wychodzacy, s.utwor_wchodzacy,
       ma.id_docelowy AS analiza_z, mb.id_docelowy AS analiza_do
FROM szew s
JOIN mapowanie ma ON ma.system_zrodlowy = 'utwor'
                 AND ma.id_zrodlowy = s.utwor_z_id
                 AND ma.system_docelowy = 'analiza'
JOIN mapowanie mb ON mb.system_zrodlowy = 'utwor'
                 AND mb.id_zrodlowy = s.utwor_do_id
                 AND mb.system_docelowy = 'analiza'
ORDER BY s.szew_id
"""

# Tracks several DJs reach for. Popularity here is measured across people,
# not plays, so one DJ looping a record cannot inflate it.
UTWORY_WIELU_DJOW = """
SELECT u.utwor_id, u.wykonawca, u.tytul, u.granych_przez,
       count(DISTINCT p.ksywa) AS potwierdzonych_djow
FROM utwor u
JOIN pozycja_tracklisty p ON p.utwor_id = u.utwor_id
WHERE p.ksywa IS NOT NULL
GROUP BY u.utwor_id, u.wykonawca, u.tytul, u.granych_przez
HAVING count(DISTINCT p.ksywa) >= %(min_djow)s
ORDER BY potwierdzonych_djow DESC, u.tytul
LIMIT %(limit)s
"""

# Sessions with everything needed to replay them honestly: a registry, its
# starting knob positions, and the audio Rekordbox recorded at the same time.
SESJE_KOMPLETNE = """
SELECT s.sesja_id, s.nazwa, s.data, s.pozycje_startowe,
       r.zdarzen, round(r.dlugosc_s::numeric / 60, 1) AS minut,
       n.sciezka_wav IS NOT NULL AS ma_audio
FROM sesja s
JOIN rejestr r ON r.sesja_id = s.sesja_id
LEFT JOIN nagranie n ON n.sesja_id = s.sesja_id
ORDER BY r.zdarzen DESC
"""

# DJs we hold both a festival appearance and recorded corpus material for —
# the only people we can compare "what they were booked for" against "what
# they actually played".
DJE_Z_KORPUSEM_I_MAPA = """
SELECT a.artysta_id, a.nazwa, a.kraj, ap.obserwujacych_ra,
       count(DISTINCT m.id_zrodlowy) AS miksow_w_korpusie,
       count(DISTINCT w.ksywa)       AS wystapien_festiwalowych
FROM artysta a
JOIN mapowanie m ON m.system_docelowy = 'artysta'
                AND m.id_docelowy = a.artysta_id
                AND m.system_zrodlowy = 'korpus_mix'
LEFT JOIN artysta_profil ap ON ap.artysta_id = a.artysta_id
LEFT JOIN wystep w ON lower(w.ksywa) = lower(a.nazwa)
GROUP BY a.artysta_id, a.nazwa, a.kraj, ap.obserwujacych_ra
ORDER BY miksow_w_korpusie DESC, a.nazwa
LIMIT %(limit)s
"""

# Rated transitions next to the engine's own score. Empty until the paper
# forms are entered; the row count is the honest progress indicator.
OCENY_KONTRA_SILNIK = """
SELECT o.pair_id, o.sesja_papier, o.ocena, o.engine_score,
       aa.tytul AS utwor_a, ab.tytul AS utwor_b
FROM ocena o
LEFT JOIN analiza aa ON aa.track_id = o.track_id_a
LEFT JOIN analiza ab ON ab.track_id = o.track_id_b
WHERE o.ocena IS NOT NULL
ORDER BY o.pair_id
"""

# Sound neighbours, restricted to corpus material by default.
PODOBNE_BRZMIENIOWO = """
SELECT w.klucz,
       1 - (w.embedding <=> (SELECT embedding FROM wektor
                             WHERE przestrzen = %(przestrzen)s
                               AND klucz = %(klucz)s)) AS podobienstwo,
       map.id_docelowy AS artysta_id
FROM wektor w
LEFT JOIN mapowanie map ON map.system_docelowy = 'wektor_korpus'
                       AND map.id_docelowy = w.klucz
WHERE w.przestrzen = %(przestrzen)s
  AND w.klucz <> %(klucz)s
  AND w.zrodlo = 'korpus'
ORDER BY w.embedding <=> (SELECT embedding FROM wektor
                          WHERE przestrzen = %(przestrzen)s
                            AND klucz = %(klucz)s)
LIMIT %(limit)s
"""


def _run(conn: Any, sql: str, params: dict[str, Any] | None = None) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params or {})
        return cur.fetchall()


def szwy_z_obiema_analizami(conn: Any) -> list[tuple]:
    return _run(conn, SZWY_Z_OBIEMA_ANALIZAMI)


def utwory_wielu_djow(conn: Any, *, min_djow: int = 3, limit: int = 50) -> list[tuple]:
    return _run(conn, UTWORY_WIELU_DJOW, {"min_djow": min_djow, "limit": limit})


def sesje_kompletne(conn: Any) -> list[tuple]:
    return _run(conn, SESJE_KOMPLETNE)


def dje_z_korpusem_i_mapa(conn: Any, *, limit: int = 50) -> list[tuple]:
    return _run(conn, DJE_Z_KORPUSEM_I_MAPA, {"limit": limit})


def oceny_kontra_silnik(conn: Any) -> list[tuple]:
    return _run(conn, OCENY_KONTRA_SILNIK)


def podobne_brzmieniowo(
    conn: Any, klucz: str, *, przestrzen: str = "korpus_pelny", limit: int = 10
) -> list[tuple]:
    return _run(
        conn,
        PODOBNE_BRZMIENIOWO,
        {"klucz": klucz, "przestrzen": przestrzen, "limit": limit},
    )
