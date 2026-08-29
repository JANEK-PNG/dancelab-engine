"""Co kupić, żeby oceny z papieru dało się w ogóle wykorzystać.

Problem: 158 ocenionych przejść, ale 107 ze 155 utworów to strumienie Apple
Music bez pliku. Przejście nadaje się do uczenia silnika dopiero wtedy, gdy
OBA jego utwory mają audio — inaczej nie ma z czego liczyć barwy.

Ten skrypt nie kupuje niczego. Liczy, ile przejść odblokowuje każdy kolejny
zakup, i układa listę tak, żeby najpierw szły utwory odblokowujące najwięcej.
Wynik: krzywa „ile utworów kupionych → ile ocen użytecznych" i lista zakupowa
z nazwami.
"""

from __future__ import annotations

import csv
import json
import pathlib
import unicodedata

TU = pathlib.Path(__file__).parent
ROOT = TU.parents[1]
OCENY = ROOT / "experiments_priv/2026-08-17_ocena_papierowa"
PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
MUZ = pathlib.Path.home() / "Music"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", str(s))


def main() -> int:
    from dancelab.storage.repositories import FileAnalysisRepository
    from dancelab.tui.duplikaty import scal

    dane = json.loads((OCENY / "playlisty_dane.json").read_text(encoding="utf-8"))
    potrzebne = {t["track_id"] for lista in dane.values() for t in lista}
    repo = FileAnalysisRepository(PROCESSED)
    widok, _ = scal([repo.get(t) for t in repo.list_track_ids()])
    by_id = {a.track.track_id: a for a in widok if a.track.track_id in potrzebne}

    ma_plik = {}
    for tid, a in by_id.items():
        raw = str(a.track.source_path or "")
        p = pathlib.Path(nfc(raw))
        ma_plik[tid] = (not raw.startswith("apple-music:")
                        and p.is_absolute() and p.exists())

    przejscia = []
    for p in sorted(OCENY.glob("SESJA_*_transition_ratings.csv")):
        for r in csv.DictReader(p.open(encoding="utf-8")):
            a, b = r["track_id_a"], r["track_id_b"]
            if a in by_id and b in by_id:
                przejscia.append((a, b, int(r["dj_mixability_rating"])))

    def pokryte(kupione: set[str]) -> int:
        return sum(1 for a, b, _ in przejscia
                   if (ma_plik[a] or a in kupione) and (ma_plik[b] or b in kupione))

    print(f"utworów: {len(by_id)} · z plikiem: {sum(ma_plik.values())} · "
          f"do kupienia: {sum(1 for v in ma_plik.values() if not v)}")
    print(f"ocenionych przejść: {len(przejscia)}")
    print(f"użytecznych DZIŚ (oba utwory z plikiem): {pokryte(set())}\n")

    brak = [t for t, v in ma_plik.items() if not v]
    kupione: set[str] = set()
    kroki = []
    while brak:
        najlepszy, zysk = None, -1
        for t in brak:
            z = pokryte(kupione | {t}) - pokryte(kupione)
            if z > zysk:
                najlepszy, zysk = t, z
        kupione.add(najlepszy)
        brak.remove(najlepszy)
        kroki.append((najlepszy, zysk, pokryte(kupione)))

    print("ILE KUPIONYCH → ILE OCEN UŻYTECZNYCH")
    for prog in (10, 20, 30, 40, 50, 60, 80, 100, len(kroki)):
        if prog <= len(kroki):
            _, _, ile = kroki[prog - 1]
            print(f"  {prog:3d} utworów → {ile:3d} ze 158 przejść "
                  f"({100 * ile / len(przejscia):.0f}%)")

    lista = []
    for i, (tid, zysk, suma) in enumerate(kroki, 1):
        t = by_id[tid].track
        lista.append({"nr": i, "track_id": tid,
                      "wykonawca": t.artist, "tytul": t.title,
                      "bpm": t.bpm_estimate, "tonacja": t.key_estimate,
                      "odblokowuje": zysk, "razem_przejsc": suma})
    (TU / "lista_zakupow.json").write_text(
        json.dumps(lista, ensure_ascii=False, indent=1), encoding="utf-8")

    with (TU / "lista_zakupow.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(lista[0]))
        w.writeheader()
        w.writerows(lista)
    print(f"\nlista → {TU / 'lista_zakupow.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
