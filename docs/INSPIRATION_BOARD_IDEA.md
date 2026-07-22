# Inspiration Board — "graj jak najlepsi" (backlog, po walidacji)

Status: IDEA, zaparkowana świadomie. Wchodzi PO: kalibracji bramki oktawy →
pełnej analizie korpusu → influence packu. Decyzja Janka + Klaris 2026-07-16.

## Koncept (słowa Janka)

Kafelki/karty DJ-ów jak kolekcjonerskie: użytkownik wybiera swoją talię
inspiracji (u Janka: Four Tet, Jamie xx, Ben UFO, O'Flynn, Anish Kumar),
a apka podpowiada zestawienia i przejścia "jak twoi mistrzowie" — bo każdy
DJ kopiuje swoich ulubionych, zanim znajdzie własny język.

## Zasady twarde

1. Pod packagingiem tylko ZMIERZONE dane: prawdziwe przejścia z korpusu
   (alignmenty DTW), liczniki dowodów na każdej karcie ("na podstawie N
   przejść z M setów"), linki do źródłowych setów. Zero iluzji wiedzy.
2. Audio korpusu NIGDY nie gra w apce (ripy badawcze). Gra tylko biblioteka
   użytkownika. Board linkuje do legalnych źródeł setów.
3. Silnik globalnie neutralny; talia inspiracji = jawna warstwa profilu
   (context/style_profile), nie ukryty bias.

## Karta DJ-a = portret z danych (zamiast zdjęcia)

Fotki DJ-ów = prawa do wizerunku + prawa fotografów. Zamiast tego: unikalny
wizualny fingerprint generowany z jego statystyk przejść — pierścień
rozkładu temp, histogram długości blendów, paleta gatunków. DJ narysowany
własnym stylem. Zero licencji, spójne z marką "mierzymy, nie zgadujemy".

## Funkcje v0 (statyczny raport HTML, jeden wieczór, zero ryzyka dla apki)

- realne przejścia wybranych DJ-ów (A→B, kiedy, jak długo, link do setu)
- ich najczęściej grane tracki
- "mosty": tracki łączące światy dwóch ulubionych DJ-ów
- digging list: tracki powtarzające się u mistrzów, których user nie ma
  w bibliotece (lista zakupów)

## Dane

Już produkowane: alignments/*.json + djmix-dataset metadane + biblioteka
usera. Anish Kumar poza datasetem (za nowy) — osobne źródła później.
