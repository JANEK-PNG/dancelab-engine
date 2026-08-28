"""Playlista z katalogu → pliki, które Apple Music (Muzyka) potrafi przyjąć.

Powód: po nieudanym secie Janek sam nazwał przyczynę — „nie znałem żadnego
utworu, nie wiedziałem, gdzie się zaczyna". Wniosek był jego: przygotowany set
ma dać się posłuchać ZANIM się go zagra. Ten skrypt robi z playlisty coś, co
wchodzi do telefonu.

Trzy wyjścia, bo żadne jedno nie pokrywa całości:

* ``.m3u8``   — dla utworów, których pliki nadal leżą na dysku. Muzyka
                zaimportuje je jako playlistę jednym przeciągnięciem.
* ``.txt``    — czytelna lista „wykonawca — tytuł". Do wyszukania ręką albo do
                wysłania komuś.
* ``.applescript`` — szuka każdego utworu w bibliotece Muzyki po nazwie i składa
                z nich playlistę. URUCHAMIA GO JANEK, nie ja: to zmiana w jego
                aplikacji i jego bibliotece.

Pokrycie jest częścią wyniku, nie przypisem. Przy pierwszym uruchomieniu
(28.08.2026) na playlistach OCENA istniało 54 ze 168 plików — reszta to nagrania
skasowane po analizie, zgodnie z zasadą „pobierz, policz, skasuj audio".
Playlista m3u8 obejmie więc tylko część; pozostałe utwory trzeba znaleźć w
katalogu Apple i do tego służą dwa pozostałe pliki.

Użycie:
    uv run python scripts/eksport_playlisty.py "OCENA A" --wyjscie ~/Desktop
    uv run python scripts/eksport_playlisty.py --wszystkie --wyjscie ~/Desktop
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dancelab.catalog.db import CatalogUnavailable, connect  # noqa: E402


def rozdziel(tytul: str | None, wykonawca: str | None) -> tuple[str, str]:
    """Rozdziel 'Wykonawca - Tytuł' — w katalogu wykonawca bywa pusty.

    Bierzemy PIERWSZY separator: tytuły często zawierają kolejne myślniki
    ("Fries With That- (Unmixed) - 13 First Principles"), więc dzielenie od
    końca dałoby wykonawcę złożonego z pół tytułu.
    """
    t = (tytul or "").strip()
    a = (wykonawca or "").strip()
    if not a and " - " in t:
        a, t = (x.strip() for x in t.split(" - ", 1))

    # Sporo tytułów w katalogu to nazwy plików z wyrwanych albumów:
    # "Eats Everything - Fries With That- (Unmixed) - 13 First Principles".
    # Muzyka nie znajdzie takiego łańcucha, więc odcinamy wszystko przed
    # numerem ścieżki — po nim zostaje prawdziwy tytuł.
    numer = re.search(r"(?:^|\s-\s)\s*\d{1,2}\s+(?=\S)", t)
    if numer:
        t = t[numer.end():].strip()
    return a, t


def bezpieczna_nazwa(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"[^\w\s-]+", "", s).strip().replace(" ", "_") or "playlista"


def applescript_tekst(nazwa: str, utwory: list[tuple[str, str]]) -> str:
    """Skrypt tworzący playlistę w Muzyce z tego, co znajdzie w bibliotece."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    wiersze = "\n".join(
        f'  szukaj("{esc(a)}", "{esc(t)}")' for a, t in utwory
    )
    return f'''-- Playlista "{nazwa}" z DanceLab.
-- Szuka każdego utworu w Twojej bibliotece Muzyki i dodaje go do nowej
-- playlisty. Utwory, których nie ma w bibliotece, są wypisane na końcu —
-- skrypt niczego nie kupuje ani nie pobiera.
--
-- Uruchomienie: dwuklik, potem przycisk ▶ w Edytorze skryptów.

property brakujace : {{}}

on szukaj(wykonawca, tytul)
  tell application "Music"
    set znalezione to (every track of library playlist 1 whose name contains tytul)
    if (count of znalezione) is 0 then
      set end of brakujace to (wykonawca & " — " & tytul)
    else
      duplicate (item 1 of znalezione) to playlist "{esc(nazwa)}"
    end if
  end tell
end szukaj

tell application "Music"
  if not (exists playlist "{esc(nazwa)}") then
    make new playlist with properties {{name:"{esc(nazwa)}"}}
  end if
end tell

{wiersze}

if (count of brakujace) > 0 then
  set tekst to "Nie znalazłem w bibliotece:" & return & return
  repeat with b in brakujace
    set tekst to tekst & "• " & b & return
  end repeat
  display dialog tekst
else
  display dialog "Gotowe — wszystkie utwory dodane do playlisty {esc(nazwa)}."
end if
'''


def eksportuj(conn, nazwa: str, katalog: Path) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT p.pozycja, p.wykonawca, p.tytul, a.sciezka_audio"
            " FROM pozycja_playlisty p"
            " JOIN playlista pl ON pl.playlista_id = p.playlista_id"
            " LEFT JOIN analiza a ON a.track_id = p.track_id"
            " WHERE pl.nazwa = %s ORDER BY p.pozycja",
            (nazwa,),
        )
        wiersze = cur.fetchall()

    if not wiersze:
        return {"nazwa": nazwa, "utworow": 0}

    trzon = bezpieczna_nazwa(nazwa)
    katalog.mkdir(parents=True, exist_ok=True)

    utwory: list[tuple[str, str]] = []
    m3u = ["#EXTM3U"]
    tekst = [f"{nazwa}", "=" * len(nazwa), ""]
    z_plikiem = 0

    for poz, wyk, tyt, sciezka in wiersze:
        a, t = rozdziel(tyt, wyk)
        utwory.append((a, t))
        tekst.append(f"{poz:2d}. {a + ' — ' if a else ''}{t}")
        if sciezka:
            p = Path(sciezka)
            if not p.is_absolute():
                p = ROOT / p
            if p.exists():
                m3u.append(f"#EXTINF:-1,{a} - {t}")
                m3u.append(str(p))
                z_plikiem += 1

    (katalog / f"{trzon}.m3u8").write_text("\n".join(m3u) + "\n", encoding="utf-8")
    tekst += ["", f"({len(wiersze)} utworów, {z_plikiem} z plikiem na dysku)"]
    (katalog / f"{trzon}.txt").write_text("\n".join(tekst) + "\n", encoding="utf-8")
    (katalog / f"{trzon}.applescript").write_text(
        applescript_tekst(nazwa, utwory), encoding="utf-8")

    return {"nazwa": nazwa, "utworow": len(wiersze), "z_plikiem": z_plikiem}


def main(argv: list[str] | None = None) -> int:
    a = argparse.ArgumentParser(description="Playlista z katalogu → Apple Music")
    a.add_argument("playlista", nargs="?", help="nazwa playlisty, np. \"OCENA A\"")
    a.add_argument("--wszystkie", action="store_true")
    a.add_argument("--wyjscie", type=Path, required=True)
    args = a.parse_args(argv)

    if not args.playlista and not args.wszystkie:
        raise SystemExit("podaj nazwę playlisty albo --wszystkie")

    try:
        with connect() as conn:
            if args.wszystkie:
                with conn.cursor() as cur:
                    cur.execute("SELECT nazwa FROM playlista ORDER BY nazwa")
                    nazwy = [r[0] for r in cur.fetchall()]
            else:
                nazwy = [args.playlista]

            print(f"{'playlista':16s} {'utworów':>8s} {'z plikiem':>10s}")
            razem = zplikiem = 0
            for n in nazwy:
                w = eksportuj(conn, n, args.wyjscie)
                if not w["utworow"]:
                    print(f"{n:16s} {'—':>8s}   nie ma takiej playlisty")
                    continue
                print(f"{n:16s} {w['utworow']:>8d} {w['z_plikiem']:>10d}")
                razem += w["utworow"]
                zplikiem += w["z_plikiem"]
    except CatalogUnavailable as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        return 1

    if razem:
        print(f"\nrazem {razem} utworów, {zplikiem} z plikiem na dysku "
              f"({100 * zplikiem // razem}%)")
        print(f"pliki w: {args.wyjscie}")
        print("\n.m3u8         — przeciągnij do Muzyki (tylko utwory z plikiem)")
        print(".txt          — lista do czytania i wyszukania ręką")
        print(".applescript  — dwuklik, potem ▶ w Edytorze skryptów: poskłada")
        print("                playlistę z tego, co masz w bibliotece Muzyki")
    return 0


if __name__ == "__main__":
    sys.exit(main())
