# Wynik pomiaru (a) i (b) — bez werdyktu o wymianie

Utworów: 242, po dedupie 211 (duplikatów: 31).
Kontrola potoku (mój htsat vs lipcowy htsat, n=240): mediana kosinusa 0.999999999997998, min 0.999999999997997.

| | htsat | larger | próg |
|---|---|---|---|
| N_k max (k=10) | 54 | 40 | larger ≤ 64.8 |
| skośność N_k | 1.682 | 0.952 | larger ≤ 2.182 |
| top-5 N_k | [54, 39, 34, 34, 32] | [40, 36, 35, 32, 30] | — |
| czystość gatunkowa top-10 | 0.1139 | 0.0608 | larger ≥ 0.1439 |
| par w mianowniku czystości | 676 | 543 | — |
| Jaccard top-10 między modelami | 0.0691 | | opisowa |

(a) hubness: SPEŁNIONY · (b) czystość: NIESPEŁNIONY
Pary do (c): 17 par na 6 kotwicach — `PARY_DO_ODSLUCHU.md`.

Modele: {"htsat": {"model": "laion/clap-htsat-unfused", "sampling_rate": 48000, "device": "mps", "enable_fusion": false, "sha256": "1cd3c601bc4afe0fa87be3de4c13dd2cfadd249fac1e29acf74a9b296c3219bb", "snapshot": "None"}, "larger": {"model": "laion/larger_clap_music", "sampling_rate": 48000, "device": "mps", "enable_fusion": false, "sha256": "5c289311f4a030d768af7ffbfdecd01b008aa64824211899a4e59f4f9d154fd1", "snapshot": "None"}}
Czystość losowa (Σp², ten sam materiał po dedupie, 124 utwory z gatunkiem, 26 klas): 0,0542.
