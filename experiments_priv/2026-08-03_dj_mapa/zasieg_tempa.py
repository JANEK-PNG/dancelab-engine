"""Siatka OSIĄGALNOŚCI TEMPA wyjęta z prawdziwego silnika.

Janek 13.08: „przejście to chwila, w której całe pole możliwości się
przelicza" — pole ma gasnąć do tego, co osiągalne z grającego utworu.
Żeby to nie było moim widzimisię, osiągalność liczy TA SAMA funkcja,
która wybiera następny utwór w secie: `set_builder.bpm_score`. Jest
świadoma oktawy — 140 i 70 to dla niej jedna rodzina, tylko przygaszona
o SAME_OCTAVE_PREFERENCE, bo korpus pokazuje, że DJ-e trzymają się
jednej rodziny temp.

Czego w tej siatce NIE MA i dlaczego:
  · harmonia — mapa nie ma uczciwych tonacji do czasu odczytu Rekordboxa;
    dopiero wtedy pole będzie mogło gasnąć także tonalnie;
  · energia — przy domyślnym łuku „off" (pomiar 10.08) człon energii
    w silniku jest NEUTRALNY, więc pole nie ma prawa gasnąć po energii.
    To nie jest brak — to wynik pomiaru i tak zostaje narysowane.

Wyjście: docs/scena-v2/zasieg_tempa.json
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "src"))

from dancelab.decision.set_builder import bpm_score  # noqa: E402

CEL = pathlib.Path(
    "/Users/jantrybus/Developer/dancelab-engine/docs/scena-v2/zasieg_tempa.json")
OD, DO = 60, 200                      # ten sam zakres, co pole możliwości


def main() -> None:
    tempa = list(range(OD, DO + 1))
    siatka = [[round(bpm_score(a, b), 4) for b in tempa] for a in tempa]
    CEL.write_text(json.dumps({"od": OD, "do": DO, "n": len(tempa),
                               "siatka": siatka}, ensure_ascii=False))
    # kontrola na oko: z 140 osiągalne są 140 (identyczność) i okolice 70
    z140 = siatka[140 - OD]
    najlepsze = sorted(range(len(tempa)), key=lambda i: -z140[i])[:6]
    print("zapisane:", CEL)
    print("z 140 najlepiej osiągalne:",
          ", ".join(f"{tempa[i]}={z140[i]}" for i in najlepsze))
    print("kontrola oktawy: 140→70 =", z140[70 - OD],
          "· 140→105 =", z140[105 - OD],
          "· 140→128 =", z140[128 - OD])


if __name__ == "__main__":
    main()
