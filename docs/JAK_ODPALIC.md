# DanceLab — jak samemu odpalić aplikację (TUI)

Stan: 2026-08-04. Ta instrukcja jest dla Ciebie (i dla Barta) — zero wiedzy
technicznej nie przeszkadza.

## Sposób 1 — podwójne kliknięcie (polecany)

1. Otwórz Finder → folder domowy → `Developer` → `dancelab-engine`.
2. Kliknij dwa razy plik **`DanceLab.command`**. Otworzy się okno Terminala
   i po chwili wstanie aplikacja.
3. Wygodniej na co dzień: kliknij ten plik prawym przyciskiem → **Utwórz alias**
   i przeciągnij alias na biurko. Od tej pory startujesz z biurka.

Przy pierwszym uruchomieniu macOS może zapytać, czy na pewno otworzyć —
kliknij prawym → **Otwórz**, potem już nie pyta.

## Sposób 2 — ręcznie w Terminalu

```bash
cd ~/Developer/dancelab-engine && .venv/bin/dancelab tui
```

## Co robisz w środku

1. **Formularz** (góra): pula utworów, długość w minutach, okno tempa
   (np. `130-135`), gatunki (Twoje tagi z Rekordboxa), DJ z listy kotwic
   („graj jak X"), kontur skoków.
2. **B** — buduje set. Postęp leci na żywo, wynik ląduje w tabeli.
3. Klikasz utwór w tabeli i **Z** — po prawej otwiera się panel z 10 propozycjami
   podmiany, ocenianymi w TYM miejscu setu (jak wchodzi po poprzednim i jak
   wychodzi w następny). Klikasz propozycję i znów **Z** — podmiana zrobiona.
4. **W** — wgrywa playlistę do Rekordboxa. **Rekordbox musi być ZAMKNIĘTY** —
   inaczej aplikacja odmówi i nic nie dotknie. Przed każdym zapisem sama robi
   kopię bazy (`DanceLab_backups/`), a po zapisie sprawdza odczytem, czy w bazie
   jest dokładnie to, co miało być.
5. **Esc** — zamyka panel podmian albo przerywa budowę. **Q** — wyjście.

## Jak czytać ekran (zasada uczciwości)

- Przygaszony wiersz = silnik nie jest pewny tonacji (pewność poniżej 0,5).
- Panel ostrzeżeń na dole nigdy się nie chowa — tam silnik mówi, czego nie wie.
- Pasek statusu pokazuje, czy Rekordbox chodzi i ile jest kopii zapasowych.

## Gdy coś nie działa

- **Krzywo wygląda / ucięte kolumny** → powiększ okno Terminala, aplikacja
  sama się przerysuje.
- **„command not found"** → uruchamiasz spoza folderu silnika; użyj Sposobu 1.
- **W odmawia** → to nie błąd: Rekordbox jest otwarty. Zamknij go i spróbuj
  jeszcze raz.
