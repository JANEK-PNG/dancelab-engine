"""Podgląd bazy DanceLab — serwer: PostgreSQL → przeglądarka.

Tylko ODCZYT. Serwer nie ma ani jednego zapytania, które coś zmienia, więc
można go zostawić włączonego obok pracy na bazie bez ryzyka.

Uruchomienie:
    cd ~/Developer/dancelab-engine
    uv run python docs/baza-podglad/serwer.py [port]
Domyślny port 8656. Strona: http://localhost:8656/

Panel pokazuje też LUKI (ile zostało bez pary, ile ocen nie wpisano) —
to nie jest ozdoba, tylko warunek: liczba bez swojej luki kłamie.
"""

from __future__ import annotations

import json
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src"))

from dancelab.catalog.db import CatalogUnavailable, connect  # noqa: E402

KATALOG = pathlib.Path(__file__).parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8656


def _pytaj(sql: str, params: dict | None = None) -> list[dict]:
    """Wykonaj zapytanie i zwróć listę słowników (nazwa kolumny → wartość)."""
    with connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params or {})
        kolumny = [d.name for d in cur.description]
        return [dict(zip(kolumny, row, strict=False)) for row in cur.fetchall()]


# --------------------------------------------------------------- pojedyncze widoki


def stan() -> dict:
    tabele = _pytaj(
        "SELECT relname AS tabela, n_live_tup AS wierszy"
        " FROM pg_stat_user_tables ORDER BY n_live_tup DESC"
    )
    # n_live_tup to szacunek planisty; dla małych tabel bywa nieaktualny zaraz
    # po imporcie, więc liczymy dokładnie tam, gdzie to widać.
    dokladne = _pytaj(
        "SELECT (SELECT count(*) FROM artysta)            AS artysci,"
        "       (SELECT count(*) FROM utwor)              AS utwory,"
        "       (SELECT count(*) FROM szew)               AS szwy,"
        "       (SELECT count(*) FROM analiza)            AS analizy,"
        "       (SELECT count(*) FROM wektor)             AS wektory,"
        "       (SELECT count(*) FROM mapowanie)          AS mapowania,"
        "       (SELECT count(*) FROM pozycja_tracklisty) AS pozycje,"
        "       (SELECT count(*) FROM miks)               AS miksy"
    )[0]
    wersja = _pytaj("SELECT max(version) AS w FROM schema_version")[0]["w"]
    return {"tabele": tabele, "kafle": dokladne, "wersja_schematu": wersja}


def pokrycie() -> dict:
    """Ile rzeczy udało się połączyć, a ile zostało samotnych."""
    metody = _pytaj(
        "SELECT system_zrodlowy, system_docelowy, metoda, pewnosc,"
        "       count(*) AS ile"
        " FROM mapowanie"
        " GROUP BY 1, 2, 3, 4 ORDER BY ile DESC"
    )
    luki = _pytaj(
        "SELECT 'pozycje tracklist bez utworu' AS co,"
        "       count(*) FILTER (WHERE utwor_id IS NULL) AS ile,"
        "       count(*) AS z_ilu FROM pozycja_tracklisty"
        " UNION ALL"
        " SELECT 'szwy bez pary utworów', count(*) FILTER"
        "        (WHERE utwor_z_id IS NULL OR utwor_do_id IS NULL), count(*)"
        " FROM szew"
        " UNION ALL"
        " SELECT 'oceny niewpisane', count(*) FILTER (WHERE ocena IS NULL),"
        "        count(*) FROM ocena"
        " UNION ALL"
        " SELECT 'analizy bez wykonawcy', count(*) FILTER"
        "        (WHERE wykonawca IS NULL), count(*) FROM analiza"
        " UNION ALL"
        " SELECT 'nagrania bez sesji', count(*) FILTER"
        "        (WHERE sesja_id IS NULL), count(*) FROM nagranie"
        " UNION ALL"
        " SELECT 'profile bez wpisanego kraju', count(*) FILTER"
        "        (WHERE kraj_ra IS NULL), count(*) FROM artysta_profil"
    )
    zrodla = _pytaj(
        "SELECT 'analizy' AS gdzie, zrodlo, count(*) AS ile FROM analiza"
        " GROUP BY 1, 2"
        " UNION ALL"
        " SELECT 'wektory', zrodlo, count(*) FROM wektor GROUP BY 1, 2"
        " ORDER BY 1, 3 DESC"
    )
    return {"metody": metody, "luki": luki, "zrodla": zrodla}


def przekroje() -> dict:
    """Zapytania, których wczoraj nie dało się zadać."""
    szwy = _pytaj(
        "SELECT count(*) AS ile FROM szew s"
        " JOIN mapowanie ma ON ma.system_zrodlowy = 'utwor'"
        "   AND ma.id_zrodlowy = s.utwor_z_id AND ma.system_docelowy = 'analiza'"
        " JOIN mapowanie mb ON mb.system_zrodlowy = 'utwor'"
        "   AND mb.id_zrodlowy = s.utwor_do_id AND mb.system_docelowy = 'analiza'"
    )[0]["ile"]
    djow = _pytaj(
        "SELECT count(DISTINCT id_docelowy) AS ile FROM mapowanie"
        " WHERE system_zrodlowy = 'korpus_mix' AND system_docelowy = 'artysta'"
    )[0]["ile"]
    sesje = _pytaj(
        "SELECT s.nazwa, s.data, s.pozycje_startowe, r.zdarzen,"
        "       round((r.dlugosc_s / 60)::numeric, 1) AS minut"
        " FROM sesja s JOIN rejestr r ON r.sesja_id = s.sesja_id"
        " ORDER BY r.zdarzen DESC"
    )
    wielu = _pytaj(
        "SELECT u.wykonawca, u.tytul, count(DISTINCT p.ksywa) AS djow"
        " FROM utwor u JOIN pozycja_tracklisty p ON p.utwor_id = u.utwor_id"
        " WHERE p.ksywa IS NOT NULL"
        " GROUP BY u.utwor_id, u.wykonawca, u.tytul"
        " HAVING count(DISTINCT p.ksywa) >= 3"
        " ORDER BY djow DESC, u.tytul LIMIT 25"
    )
    top = _pytaj(
        "SELECT a.nazwa, ap.kraj_ra AS kraj, ap.obserwujacych_ra AS obserwujacych,"
        "       count(DISTINCT m.id_zrodlowy) AS miksow"
        " FROM artysta a"
        " JOIN mapowanie m ON m.system_docelowy = 'artysta'"
        "   AND m.id_docelowy = a.artysta_id AND m.system_zrodlowy = 'korpus_mix'"
        " LEFT JOIN artysta_profil ap ON ap.artysta_id = a.artysta_id"
        " GROUP BY a.nazwa, ap.kraj_ra, ap.obserwujacych_ra"
        " ORDER BY miksow DESC, a.nazwa LIMIT 25"
    )
    return {
        "szwy_z_obiema_analizami": szwy,
        "djow_w_korpusie_i_mapie": djow,
        "sesje": sesje,
        "utwory_wielu_djow": wielu,
        "dje_korpus_mapa": top,
    }


def szukaj(fraza: str) -> dict:
    """Jedna nazwa, wszystko co baza o niej wie — z każdego z pięciu światów."""
    like = f"%{fraza.lower()}%"
    artysci = _pytaj(
        "SELECT a.artysta_id, a.nazwa, ap.kraj_ra AS kraj,"
        "       ap.obserwujacych_ra AS obserwujacych, ap.festiwal_2026,"
        "       (SELECT count(*) FROM wystep w"
        "        WHERE lower(w.ksywa) = lower(a.nazwa))  AS wystepow,"
        "       (SELECT count(*) FROM miks m"
        "        WHERE lower(m.ksywa) = lower(a.nazwa))  AS miksow,"
        "       (SELECT count(*) FROM mapowanie mp"
        "        WHERE mp.system_zrodlowy = 'korpus_mix'"
        "          AND mp.system_docelowy = 'artysta'"
        "          AND mp.id_docelowy = a.artysta_id)    AS miksow_w_korpusie"
        " FROM artysta a"
        " LEFT JOIN artysta_profil ap ON ap.artysta_id = a.artysta_id"
        " WHERE lower(a.nazwa) LIKE %(q)s ORDER BY a.nazwa LIMIT 20",
        {"q": like},
    )
    utwory = _pytaj(
        "SELECT u.utwor_id, u.wykonawca, u.tytul, u.granych_przez,"
        "       m.id_docelowy AS analiza"
        " FROM utwor u"
        " LEFT JOIN mapowanie m ON m.system_zrodlowy = 'utwor'"
        "   AND m.id_zrodlowy = u.utwor_id AND m.system_docelowy = 'analiza'"
        " WHERE lower(coalesce(u.wykonawca, '') || ' ' || coalesce(u.tytul, ''))"
        "       LIKE %(q)s"
        " ORDER BY u.granych_przez DESC NULLS LAST LIMIT 20",
        {"q": like},
    )
    szwy = _pytaj(
        "SELECT szew_id, ksywa, wydarzenie, utwor_wychodzacy, utwor_wchodzacy,"
        "       status_w_lejku"
        " FROM szew"
        " WHERE lower(coalesce(utwor_wychodzacy, '') || ' '"
        "             || coalesce(utwor_wchodzacy, '') || ' '"
        "             || coalesce(ksywa, '')) LIKE %(q)s"
        " LIMIT 20",
        {"q": like},
    )
    return {"artysci": artysci, "utwory": utwory, "szwy": szwy}


def podobne(klucz: str, limit: int = 12) -> dict:
    """Najbliżsi sąsiedzi brzmieniowi — liczone przez pgvector w bazie."""
    istnieje = _pytaj(
        "SELECT count(*) AS ile FROM wektor"
        " WHERE przestrzen = 'korpus_pelny' AND klucz = %(k)s",
        {"k": klucz},
    )[0]["ile"]
    if not istnieje:
        return {"blad": f"nie mam wektora dla klucza {klucz!r}", "wyniki": []}
    wyniki = _pytaj(
        "SELECT w.klucz,"
        "       round((1 - (w.embedding <=> (SELECT embedding FROM wektor"
        "         WHERE przestrzen = 'korpus_pelny' AND klucz = %(k)s)))::numeric, 4)"
        "         AS podobienstwo,"
        # Whose mix this recording came from, when the chain of mappings
        # reaches an artist. A bare video id is unreadable on its own.
        "       (SELECT string_agg(DISTINCT a.nazwa, ', ')"
        "        FROM mapowanie mw"
        "        JOIN mapowanie ma ON ma.system_zrodlowy = 'korpus_mix'"
        "          AND ma.id_zrodlowy = mw.id_zrodlowy"
        "          AND ma.system_docelowy = 'artysta'"
        "        JOIN artysta a ON a.artysta_id = ma.id_docelowy"
        "        WHERE mw.system_zrodlowy = 'korpus_mix'"
        "          AND mw.system_docelowy = 'wektor_korpus'"
        "          AND mw.id_docelowy = w.klucz) AS z_miksu_dj"
        " FROM wektor w"
        " WHERE w.przestrzen = 'korpus_pelny' AND w.klucz <> %(k)s"
        "   AND w.zrodlo = 'korpus'"
        " ORDER BY w.embedding <=> (SELECT embedding FROM wektor"
        "   WHERE przestrzen = 'korpus_pelny' AND klucz = %(k)s)"
        " LIMIT %(n)s",
        {"k": klucz, "n": limit},
    )
    # Attribution coverage, sent with every answer. The DJ column is empty far
    # more often than not, and a reader must be told that this is the state of
    # the data rather than a fault in the panel.
    pokrycie_dj = _pytaj(
        "SELECT (SELECT count(DISTINCT w.klucz) FROM wektor w"
        "        JOIN mapowanie mw ON mw.system_docelowy = 'wektor_korpus'"
        "          AND mw.id_docelowy = w.klucz"
        "        JOIN mapowanie ma ON ma.system_zrodlowy = 'korpus_mix'"
        "          AND ma.id_zrodlowy = mw.id_zrodlowy"
        "          AND ma.system_docelowy = 'artysta'"
        "        WHERE w.przestrzen = 'korpus_pelny')            AS ze_znanym_dj,"
        "       (SELECT count(*) FROM wektor"
        "        WHERE przestrzen = 'korpus_pelny')              AS wszystkich"
    )[0]
    return {"wyniki": wyniki, "pokrycie_dj": pokrycie_dj}


def losowy_klucz() -> str:
    znane = _pytaj(
        "SELECT w.klucz FROM wektor w"
        " JOIN mapowanie mw ON mw.system_docelowy = 'wektor_korpus'"
        "   AND mw.id_docelowy = w.klucz AND mw.system_zrodlowy = 'korpus_mix'"
        " JOIN mapowanie ma ON ma.system_zrodlowy = 'korpus_mix'"
        "   AND ma.id_zrodlowy = mw.id_zrodlowy AND ma.system_docelowy = 'artysta'"
        " WHERE w.przestrzen = 'korpus_pelny' ORDER BY random() LIMIT 1"
    )
    if znane:
        return znane[0]["klucz"]
    return _pytaj(
        "SELECT klucz FROM wektor WHERE przestrzen = 'korpus_pelny'"
        " AND zrodlo = 'korpus' ORDER BY random() LIMIT 1"
    )[0]["klucz"]


TRASY = {
    "/api/stan": lambda q: stan(),
    "/api/pokrycie": lambda q: pokrycie(),
    "/api/przekroje": lambda q: przekroje(),
    "/api/szukaj": lambda q: szukaj(q.get("q", [""])[0]),
    "/api/podobne": lambda q: podobne(q.get("klucz", [losowy_klucz()])[0]),
    "/api/losowy": lambda q: {"klucz": losowy_klucz()},
}


class Serwer(BaseHTTPRequestHandler):
    def log_message(self, *args):  # cisza w terminalu
        pass

    def _wyslij(self, kod: int, typ: str, tresc: bytes) -> None:
        self.send_response(kod)
        self.send_header("Content-Type", typ)
        self.send_header("Content-Length", str(len(tresc)))
        # Bez cache: panel musi pokazywać stan bazy TERAZ, a nie sprzed importu.
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(tresc)

    def do_GET(self) -> None:
        url = urlparse(self.path)
        zapytanie = parse_qs(url.query)

        if url.path in ("/", "/index.html"):
            plik = KATALOG / "index.html"
            self._wyslij(200, "text/html; charset=utf-8", plik.read_bytes())
            return

        handler = TRASY.get(url.path)
        if handler is None:
            self._wyslij(404, "text/plain; charset=utf-8", b"nie ma takiej strony")
            return

        try:
            dane = handler(zapytanie)
            kod = 200
        except CatalogUnavailable as exc:
            dane = {"blad": str(exc)}
            kod = 503
        except Exception as exc:  # noqa: BLE001 - panel ma pokazać błąd, nie zniknąć
            dane = {"blad": f"{type(exc).__name__}: {exc}"}
            kod = 500

        self._wyslij(
            kod,
            "application/json; charset=utf-8",
            json.dumps(dane, ensure_ascii=False, default=str).encode("utf-8"),
        )


def main() -> None:
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM artysta")
            ile = cur.fetchone()[0]
    except CatalogUnavailable as exc:
        print(f"BŁĄD: {exc}")
        print("Baza nie odpowiada. Uruchom ją:  docker compose up -d db")
        raise SystemExit(1) from exc

    print(f"Baza odpowiada ({ile} artystów).")
    print(f"Podgląd:  http://localhost:{PORT}/")
    print("Zatrzymanie: Ctrl+C")
    ThreadingHTTPServer(("127.0.0.1", PORT), Serwer).serve_forever()


if __name__ == "__main__":
    main()
