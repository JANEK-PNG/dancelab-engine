# GUI DanceLab — decyzje projektowe

Punkt wyjścia: TUI w Textual (`src/dancelab/tui/`, 6248 linii, 4 zakładki).
Zrzuty stanu obecnego zrobione narzędziem Textual do SVG i obejrzane, nie
przeczytane z kodu.

## Co TUI robi dobrze i czego NIE WOLNO stracić

Zanim cokolwiek zmienię — spis rzeczy, za które TUI zasługuje na szacunek:

1. **Wszystko działa z klawiatury.** Dolny pasek pokazuje cały zestaw skrótów
   w kontekście: `b Buduj · w Wyślij do RB · z Zamień · x Wytnij · a Dopisz ·
   ^s Zapisz plan · s Zagraj szew · c Porównaj · ^p paleta`. GUI, które
   wymusza mysz, byłoby regresem.
2. **Gęstość bez rozrzedzania.** Tabela biblioteki mieści 12 kolumn
   (♥, F, BPM, ton, pewność, energia, LUFS, gatunek, min, wykonawca, tytuł,
   źródło) i to jest zaleta, nie wada — DJ porównuje wzrokiem.
3. **Karty DJ-ów są już bento.** Ściana kart, każda z dwoma mikro-wykresami,
   medianą tempa, paskiem zakresu, trzema wskaźnikami i podsumowaniem z mapy.
   To jest najlepszy ekran w aplikacji i wzorzec dla całej reszty.
4. **Stan systemu zawsze widoczny.** Pasek na dole: „Rekordbox zamknięty —
   W dostępne · backupy: 36 · notki: 0 · pula: …". Nigdy nie trzeba zgadywać,
   czy zapis przejdzie.
5. **Puste stany mówią, co zrobić.** „Brak setu — zbuduj go w zakładce Set (B);
   wtedy zobaczysz tu propozycje padów."

## Skąd wzięty język wizualny

**Nie zaczynam od zera.** Projekt ma siedem paneli w spójnym języku, które
Janek oglądał i akceptował — model FLX4 jest wprost nazwany benchmarkiem.
GUI kontynuuje ten język zamiast wprowadzać ósmy.

| rola | wartość | skąd |
|---|---|---|
| tło | `#0e1013` | panele |
| karta | `#161a1f` | panele |
| kreska | `#242a32` | panele |
| tekst | `#e8ecf1` / cichy `#8a94a2` | panele |
| bursztyn (deck A, uwaga) | `#e0a458` | model FLX4 — kolor diod sprzętu |
| błękit (deck B) | `#5aa9e6` | model FLX4 |
| volt (akcja, gra) | `#9ede73` | TUI — przycisk „Buduj set" |
| alarm | `#e06c75` | panele |

Czcionki: **systemowa** dla interfejsu, **monospace** dla liczb. Bez pobierania
z sieci — aplikacja ma działać bez internetu, tak jak wszystkie nasze panele.

### Czego ze skilla NIE biorę i dlaczego

Skill `ui-ux-pro-max` zaproponował **Orbitron** (cyberpunk/sci-fi) i paletę
indigo `#1E1B4B`. Odrzucone:

* Orbitron to font do gier i kryptowalut. W narzędziu, którym DJ przygotowuje
  set przed graniem, wygląda jak przebranie. Ton, który ustaliliśmy dla
  DanceLabu, to „kumpel pokazujący coś fajnego", nie stacja kosmiczna.
* Indigo nie ma nic wspólnego z bursztynem i błękitem, którymi od miesiąca
  oznaczamy decki — a te kolory są wzięte wprost z diod prawdziwego sprzętu.

Ze skilla biorę: OLED dark jako bazę, wymóg kontrastu, widoczne stany focusu,
zakaz emoji jako ikon, czasy animacji 150–300 ms.

## Trendy 2026, które faktycznie pasują

Sprawdzone, nie zgadnięte (wyszukiwanie: bento grid, adaptive density,
spatial interfaces).

**Bento grid** — modułowe karty o różnych proporcjach, do gęstych danych bez
przeciążenia. **Już to mamy** na ekranie DJ-ów; rozciągam wzorzec na resztę.

**Adaptacyjna gęstość** — układ dostosowany do kontekstu pracy. Konkretnie u
Janka: inaczej pracuje przy laptopie w domu, inaczej przy pulpicie na stojąco.
Trzy tryby gęstości przełączane jednym klawiszem, nie ustawieniem w menu.

**Spatial** — odrzucone. Vision Pro i gogle nie mają nic wspólnego z tym, jak
przygotowuje się set. Trend istnieje, ale nie dla tego produktu.

## Układ

Zamiast czterech zakładek: **jedno okno z trzema strefami**.

```
┌─ pasek stanu ─────────────────────────────────────────┐
├──────────┬────────────────────────────────┬───────────┤
│ nawigacja│      obszar główny (bento)     │ kontekst  │
│  56 px   │            1fr                 │  320 px   │
│ ikona +  │  ekran zależny od nawigacji    │ szczegół  │
│  skrót   │                                │ zaznaczo- │
│          │                                │  nego     │
├──────────┴────────────────────────────────┴───────────┤
│ odtwarzacz + pasek skrótów kontekstowych              │
└───────────────────────────────────────────────────────┘
```

Prawa kolumna to jedyna nowa rzecz względem TUI: **szczegół zaznaczonego
elementu bez zmiany ekranu**. Dziś porównanie utworów otwiera panel, który
zasłania tabelę.

## Cztery ekrany

1. **Biblioteka** — tabela gęsta jak w TUI, ale z sortowaniem po kliknięciu i
   z mikro-wykresem energii w wierszu. Filtry jako pole tekstowe z podpowiedzią
   składni (`bpm:125-140 ton:8A`), nie trzy osobne pola.
2. **DJ-e** — ściana kart bento, bez zmian koncepcyjnych. Karty dostają
   prawdziwe wykresy zamiast znaków blokowych.
3. **Set** — formularz zwinięty do jednego paska u góry; wynik zajmuje całą
   szerokość, bo to on jest treścią. Krzywa energii setu nad tabelą.
4. **Cue** — oś utworu z padami, przeciąganie punktów, podgląd przed zapisem.

## Czego GUI NIE zmienia

* **Skróty klawiszowe zostają te same.** Kto zna TUI, umie GUI.
* **Pasek stanu zostaje na dole** z tą samą treścią.
* **Zakaz zapisu bez zamkniętego Rekordboxa** i cała logika bezpieczeństwa
  zapisu — bez zmian, to nie jest sprawa wyglądu.
