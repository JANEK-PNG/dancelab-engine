"""Eksport zmierzonych szwów do płótna warstwy graficznej.

Czyta `experiments_priv/seams/<set>/seam_*.json` (rozkład nagranych setów:
mix minus utwory) i składa jeden `dane/szwy.json` dla strony. Zasady:

* liczby zaokrąglamy (t do 2, wartości do 3 miejsc) — obraz i tak nie
  rozróżni więcej, a plik jest kilkukrotnie mniejszy;
* ścieżki plików audio NIE wchodzą do eksportu (strona ich nie potrzebuje,
  a docs/ nie jest miejscem na układ dysku);
* niczego nie wygładzamy ani nie uzupełniamy — braki zostają brakami.
"""

from __future__ import annotations

import json
import pathlib

TU = pathlib.Path(__file__).parent
KORZEN = TU.parents[2]
ZRODLO = KORZEN / "experiments_priv" / "seams"
CEL = TU / "dane" / "szwy.json"

PIETRA = ("bas", "środek", "góra")


def przytnij(v: float | None, miejsca: int) -> float | None:
    """None przechodzi jako None — niezmierzone zostaje niezmierzone."""
    return None if v is None else round(float(v), miejsca)


def zbierz() -> list[dict]:
    szwy: list[dict] = []
    for katalog in sorted(ZRODLO.iterdir()):
        if not katalog.is_dir():
            continue
        nazwa_setu = katalog.name
        for plik in sorted(katalog.glob("seam_*.json")):
            d = json.loads(plik.read_text())
            bands = {}
            for p in PIETRA:
                b = d["bands"][p]
                bands[p] = {
                    "t": [przytnij(x, 2) for x in b["t"]],
                    "a": [przytnij(x, 3) for x in b["a"]],
                    "b": [przytnij(x, 3) for x in b["b"]],
                    "residual": [przytnij(x, 3) for x in b["residual"]],
                }
            szwy.append(
                {
                    "set": nazwa_setu,
                    "i": d["i"],
                    "from": d["from"],
                    "to": d["to"],
                    "window": [przytnij(x, 2) for x in d["window"]],
                    "floors": {k: przytnij(v, 4) for k, v in d["floors"].items()},
                    "b_in_sec": przytnij(d.get("b_in_sec"), 2),
                    "a_out_sec": przytnij(d.get("a_out_sec"), 2),
                    "blend_sec": przytnij(d.get("blend_sec"), 2),
                    "b_bass_held_sec": przytnij(d.get("b_bass_held_sec"), 2),
                    "a_thinned_sec": przytnij(d.get("a_thinned_sec"), 2),
                    "rate_a": przytnij(d["deck_a"]["rate"], 4),
                    "rate_b": przytnij(d["deck_b"]["rate"], 4),
                    "bands": bands,
                }
            )
    return szwy


def main() -> None:
    szwy = zbierz()
    CEL.parent.mkdir(parents=True, exist_ok=True)
    CEL.write_text(json.dumps({"szwy": szwy}, ensure_ascii=False))
    rozmiar = CEL.stat().st_size / 1_048_576
    print(f"{len(szwy)} szwów → {CEL.relative_to(KORZEN)} ({rozmiar:.1f} MB)")


if __name__ == "__main__":
    main()
