# Wysiłek rąk jako miara jakości zestawienia

**Zarejestrowane 27.08.2026, ZANIM zobaczyłem oceny Janka z papieru.**
Ten plik powstaje przed pomiarem, żeby próg nie dopasował się do wyniku —
tak samo jak przy każdej innej hipotezie w tym projekcie.

## Skąd się wzięła

Janek, grając przedostatnią playlistę do oceny (OCENA I, 24 utwory):
„ten set będzie przykładem, jak nie grać… silnik nie wie, co jest chujowe…
w życiu nie słyszałem gorszego zestawienia utworów".

Grał ją w całości z włączonym rejestratorem: 73,5 min, 150 564 zdarzenia,
24 załadowania utworów.

## Teza

**Złe zestawienie zdradza się wysiłkiem DJ-a.** Jeśli dwa utwory do siebie nie
pasują, ręce muszą to nadrabiać: więcej szukania punktu (CUE), więcej
dociągania jogiem, więcej ratowania korektorem. Jeśli pasują — przejście
kosztuje kilka ruchów.

Gdyby to się potwierdziło, silnik dostałby miarę jakości pary **bez pytania
człowieka o zdanie** — liczoną z samego zapisu MIDI.

## Co już zmierzone (bez zaglądania w oceny)

Rozrzut między przejściami jest ogromny — to nie jest szum:

| przejście | CUE | ruchy jogiem | ruchy basem |
|---|---|---|---|
| #12 (36 min) | **58** | 978 | 268 |
| #7 (19 min) | 34 | **11 644** | 530 |
| #14 (44 min) | 1 | 166 | 31 |
| #17 (50 min) | 1 | 896 | 141 |

## PRÓG (rejestrowany przed sprawdzeniem)

Gdy Janek przepisze oceny z papieru dla OCENA I (23 przejścia, skala 1–5):

* **Sukces**: Spearman rho ≤ −0,45 między wysiłkiem a oceną (więcej pracy =
  niższa ocena), p < 0,05 przy permutacji 10 000, ziarno 20260827.
* **Słaby sygnał**: rho ≤ −0,25 przy p < 0,05 — raportować, nie ogłaszać.
* **Poniżej**: hipoteza umiera i idzie do OBALONE.md.

Wskaźnik wysiłku liczony z rejestru jako liczba ruchów na minutę odcinka:
`CUE × 8 + jog/50 + bas/8 + tempo/5`, znormalizowana długością odcinka.
Wzór zamrożony teraz, żeby nie było dopasowywania po fakcie.

## Trzy powody, dla których to może nie wyjść — spisane z góry

1. **Wysiłek ≠ walka.** Janek może dużo kręcić, bo mu się chce bawić, a nie
   dlatego, że musi ratować przejście.
2. **Jedna osoba, jeden set.** Nawet mocny wynik to obserwacja o Janku, nie
   prawo o DJ-ach.
3. **Oceny dotyczą przejść, wysiłek — odcinków między załadowaniami.**
   Przypisanie jednego do drugiego wymaga dopasowania, które samo może mylić.

---

## KOREKTA JANKA (27.08, tego samego wieczoru) — hipoteza była naiwna

Janek po przeczytaniu powyższego: *„DJ set to suma elementów. Nie znałem
tych utworów — dostałem playlistę od ciebie i grałem ją pierwszy raz.
Nie wiedziałem, gdzie utwór się zaczyna, gdzie kończy, gdzie zrobić dobre
przejście. Musiałem iść na żywca."*

To rozbija mój wskaźnik. **Wysiłek rąk miesza co najmniej trzy różne rzeczy:**

1. **Nieznajomość materiału.** Pierwszy raz na oczy. Szukanie punktu wejścia,
   dociąganie jogiem — to koszt POZNAWANIA utworu, nie dowód, że para jest zła.
   To prawdopodobnie WIĘKSZOŚĆ zmierzonych 58 naciśnięć CUE.
2. **Jakość zestawienia** — jedyne, co chciałem mierzyć.
3. **Stan DJ-a.** Janek: *„byłem zmęczony, sfrustrowany, nie czułem tego.
   To jest ludzka rzecz."* Zmęczenie mnoży liczbę ruchów niezależnie od muzyki.

Wskaźnik w obecnej postaci mierzy sumę tych trzech i **nie da się z niego
wyczytać jakości zestawienia**. Próg zostaje zarejestrowany, ale wynik —
jakikolwiek — będzie mówił o sumie, nie o materiale.

### Trzy warunki dobrego setu według Janka (jego słowa, jego kolejność)

Zanim DJ zagra set, powinien: **znać utwory** (przesłuchać każdy choć raz),
**znać ich ułożenie** (przesłuchać w dokładnej kolejności) i **zgodzić się
z tą playlistą jako osoba**. Przy OCENA I nie było spełnione żadne z trzech.

### Test, który rozdziela nieznajomość od zestawienia

**Ten sam set zagrany DRUGI raz**, gdy utwory są już znane. Wysiłek z
nieznajomości spada, wysiłek z materiału zostaje. Różnica między przebiegami
jest miarą tego, ile kosztowała sama nieznajomość — a to, co przetrwa, jest
kandydatem na sygnał o zestawieniu.

Dopóki tego nie zrobimy, wysiłek NIE jest miarą jakości pary i tak trzeba
o nim mówić.

### Zdanie, które warto zapamiętać osobno

Janek: *„Nie mogę nienawidzić pojedynczych utworów. Pojedyncze utwory nic nie
znaczą. To KOLEJNOŚĆ tych utworów względem siebie była najgorsza."*
To jest doktryna in between wypowiedziana wprost, przy realnym secie.
