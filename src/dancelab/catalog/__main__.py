"""Command line for the catalog: ``python -m dancelab.catalog <polecenie>``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dancelab.catalog import (
    dopasuj,
    eksport_ekselu,
    import_analiz,
    import_mapa,
    import_pomiarow,
    import_wektorow,
    schema,
    zapytania,
)
from dancelab.catalog.db import CatalogUnavailable, connect, database_url, table_counts


def _wypisz(title: str, data: dict[str, int]) -> None:
    print(f"\n{title}")
    for key, value in data.items():
        print(f"  {key:34s} {value:>8d}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dancelab.catalog")
    sub = parser.add_subparsers(dest="polecenie", required=True)

    budowa = sub.add_parser("buduj", help="schemat + wszystkie importy")
    budowa.add_argument("--od-zera", action="store_true",
                        help="skasuj i odtwórz schemat")
    budowa.add_argument("--bez-wektorow", action="store_true")

    sub.add_parser("dopasuj", help="przelicz tabelę mapowanie")
    sub.add_parser("stan", help="liczba wierszy w każdej tabeli")

    eksport = sub.add_parser("eksportuj", help="baza -> arkusz")
    eksport.add_argument("--do", default="experiments_priv/2026-08-28_baza/eksport_z_bazy.xlsx")

    pytaj = sub.add_parser("pytaj", help="zapytania przekrojowe")
    pytaj.add_argument("nazwa", nargs="?", default="wszystko")

    args = parser.parse_args(argv)

    try:
        with connect() as conn:
            if args.polecenie == "buduj":
                if args.od_zera:
                    schema.drop_all(conn)
                print("migracje:", schema.apply(conn) or "brak (aktualny)")
                _wypisz("mapa DJ-ów:", import_mapa.run(conn))
                _wypisz("analizy:", import_analiz.run(conn))
                _wypisz("pomiary:", import_pomiarow.run(conn))
                if not args.bez_wektorow:
                    _wypisz("wektory:", import_wektorow.run(conn))
                _wypisz("dopasowanie:", dopasuj.run(conn))

            elif args.polecenie == "dopasuj":
                _wypisz("dopasowanie:", dopasuj.run(conn))

            elif args.polecenie == "stan":
                print(f"baza: {database_url().rsplit('@', 1)[-1]}")
                print(f"wersja schematu: {schema.current_version(conn)}")
                _wypisz("wiersze:", table_counts(conn))

            elif args.polecenie == "eksportuj":
                _wypisz("zapisano:", eksport_ekselu.run(conn, Path(args.do)))
                print(f"\nplik: {args.do}")

            elif args.polecenie == "pytaj":
                print(f"szwy z analizami obu utworów: "
                      f"{len(zapytania.szwy_z_obiema_analizami(conn))}")
                print(f"utwory granych przez >=3 DJ-ów: "
                      f"{len(zapytania.utwory_wielu_djow(conn, limit=100000))}")
                print(f"moje sesje: {len(zapytania.sesje_kompletne(conn))}")
                print(f"DJ-e z korpusem i mapą: "
                      f"{len(zapytania.dje_z_korpusem_i_mapa(conn, limit=100000))}")
                print(f"oceny wpisane: {len(zapytania.oceny_kontra_silnik(conn))} z 158")
    except CatalogUnavailable as exc:
        print(f"BŁĄD: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
