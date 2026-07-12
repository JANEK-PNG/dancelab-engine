# DJ Validation Benchmark

Status: **NOT READY FOR TUNING**

- Sessions: 1/5 complete (1 CSV file(s) found)
- Minimum per session: 30 rated transitions
- Additional complete sessions needed: 4
- Rated transitions: 36
- Comments: 30
- Mean DJ rating: 2.778
- Mean engine score: 0.653
- Pearson r: 0.302
- Spearman rho: 0.330
- Kendall tau: 0.248
- False positives (engine >= 0.70 and DJ <= 2): 3

## Sessions

### Janek

- Status: complete
- Rated: 36
- Comments: 30
- Blind ratings: 0
- Mean DJ rating: 2.778
- Pearson r: 0.302
- Spearman rho: 0.330
- Kendall tau: 0.248
- False positives: 3
- Duplicate pair rows: 1
- Source: `/Users/jantrybus/Library/Application Support/DanceLab/cache/validation/Janek_transition_ratings.csv`

## Issue Topics

- style_genre_mood: 15
- transition_timing: 14
- bpm_grid_sync: 12
- energy_curve: 8
- playlist_context: 6
- duplicates_same_album: 2

## Top False Positives

- Janek row 18: engine 0.827, DJ 1/5, `09d7ab7363292cf2__accae828e67e6c7f` — oj tutaj niedopuszczalny bład. Nie porównany chyba zostały waveformy bo sa dwa te same utwory. Czasem tak sie dziele ze ktos nie wie i kupi paczke i na dysku bedzie mial duplikaty.
- Janek row 25: engine 0.715, DJ 1/5, `439e6c9e233bdec6__afa186e74bdee374` — zaczeło nam sie robic znowu melancholinie i bardziej electronic a tutaj wchodzi Tessela - With Patsy utwór i zabija cały klimat.
- Janek row 15: engine 0.733, DJ 2/5, `a704f54cbf31a22d__642d7e50ff06a522` — OK kolejny przypadek gdzie utwory sa z tej samej plłyty. Tutaj już może być ryzyko że ktoś nas oskarzy o puszczanie całych płyt zamiast robienia orginalnych setów. No te utwory super do siebie pasuja. Przejscie jako takie do nasladowania ale problem lezy gdzie indziej.
