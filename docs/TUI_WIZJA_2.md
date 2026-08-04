# DanceLab TUI 2.0 — wizja (spisane ze słów Janka, 05.08)

Stan: **ZATWIERDZONE przez Janka 05.08** („filary wchodzą, układ i kolejność
zatwierdzam"). Postęp: kroki **(a) zakładki+Biblioteka, (b) ulubione+filary,
(c) filary w silniku — ZROBIONE 05.08**; zostały (d) porównanie pary wizualne,
(e) dźwięk (szczebel do wyboru przez Janka), (f) edytor cue w Export.
Inspiracja: [rmpc](https://rmpc.mierak.dev/) — „czyste złoto", zwłaszcza system
zakładek. Ten dokument porządkuje dyktat Janka; rozstrzygnięcia na końcu.

## 0 · Szkielet: zakładki jak w rmpc

- Przełączanie zakładek: **Ctrl+Tab** (i skróty numeryczne jak w rmpc).
- Proponowany układ: **1 BIBLIOTEKA · 2 SET · 3 EXPORT/CUE** (+ ewentualnie
  4 KOTWICE DJ z obecnej mapy).
- **Porównanie pary NIE jest zakładką** — wysuwa się od dołu nad bieżący widok
  i po odsłuchu się chowa.

## 1 · BIBLIOTEKA (nowa zakładka — obecny priorytet Janka)

### Pierwsze uruchomienie (onboarding)
- Użytkownik dodaje ścieżkę/ścieżki do skanowania: konkretne foldery z muzyką
  albo jeden folder ogólny.
- Przycisk **ANALIZUJ** → istniejący potok analizy z postępem etapów
  (to już mamy: tryb Folder, `stage_progress`, anulowanie).
- Po analizie pierwszy użytkownik widzi to samo, co stały: pełną bibliotekę.

### Widok codzienny
- **Pasek szukania** + **pasek filtrów**: konkretna tonacja, zakres BPM itd.
- Środek: tabela utworów ze wszystkim, co silnik wie po analizie:
  BPM, tonacje, poziomy energii „i tak dalej".

### Akcje na utworze (klik)
- **Ulubione** — jak przypinanie w Apple Music, ale w DWÓCH kategoriach:
  pin na utwory i pin na playlisty.
- **Punkt kotwiczny setu** (nazwa robocza, patrz „Rozstrzygnięcia"):
  utwór staje się obowiązkowym punktem dla generatora playlist.
  - Limit: **maksymalnie 10** punktów (przy 15-utworowej playliście
    z samych punktów obowiązkowych generator nie ma czego projektować).
  - Pomysł „minimum 3 + powiadomienie" — **WYCOFANY przez Janka** w trakcie.
  - Po wygenerowaniu nadal wolno wszystko: podmiana, usunięcie, dopisanie.

## 2 · SET (istniejące, zostaje)

- Generacja playlisty — od teraz **wokół punktów kotwicznych** z Biblioteki.
- Podmiana w szczelinie, wycinanie, przesuwanie, dopisywanie, plan S/O,
  werdykt V, karta INFO — wszystko już działa.
- Podsłuch utworu (preview) — patrz drabinka dźwięku w „Rozstrzygnięciach".

## 3 · PORÓWNANIE PARY (wysuwane od dołu)

- Wzorzec: zakładka **EXPORT w Rekordboksie** — dwa waveformy nad sobą.
- **Bez** dwóch przycisków play i dwóch cue: **jeden przycisk „graj oba"**.
- Beat sync i kwantyzacja **włączone z automatu** — użytkownik nie ustawia nic.
- Po odsłuchu panel się zamyka.

## 4 · EXPORT / HOT CUE (osobna zakładka — instynkt Janka: cue przy eksporcie)

- Edycja hot cue: **dodaj · usuń · przesuń · scal**, plus **auto-generacja**
  (z planu przejść silnika — to już istnieje i jest udowodnione E2E).
- Zapis do master.db jak dziś: backup → zapis → weryfikacja odczytem,
  wyłącznie przy zamkniętym Rekordboksie.

## Pytania Janka zadane przy tej wizji

1. Czy mamy analizę struktury utworu (frazy: intro, up, down, drop, break)?
2. Czy mamy dodawanie / usuwanie / przesuwanie / auto-generację hot cue?
3. Czy w TUI da się przyzwoity podgląd waveformu — jakie są ograniczenia?
4. Prośba o pomoc w logice: krok 1 Biblioteka → krok 2 generacja (obecne).

## Rozstrzygnięcia do podjęcia (propozycje Klaris — czekają na decyzję)

- **Nazwa punktów kotwicznych.** „Kotwica" jest już zajęta przez brzmienie
  („graj jak X"). Propozycja: **FILARY** setu — filar to utwór, który MUSI
  zagrać; silnik projektuje drogę MIĘDZY filarami (dosłownie „Design In
  Between" w skali całego setu).
- **Układ zakładek** jak w sekcji 0 — potwierdzić.
- **Kolejność robót** (propozycja): (a) szkielet zakładek + Biblioteka
  tylko-do-czytania z szukaniem i filtrami — wszystkie dane już są;
  (b) ulubione + filary (magazyn); (c) filary w `build_set` (zmiana silnika:
  obowiązkowe punkty trasy); (d) porównanie pary WIZUALNE (paski energii
  ze stemów, bez dźwięku); (e) dźwięk wg drabinki (spacja-podsłuch →
  P-przejście na żywo → cały set na żywo); (f) edytor cue w zakładce Export.
- **Dźwięk**: każde odtworzenie wyłącznie od jawnego klawisza użytkownika.
