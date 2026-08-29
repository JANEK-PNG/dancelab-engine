# Runda 2 ślepego odsłuchu — OCENA K–U (zarejestrowane 2026-08-29 PRZED odsłuchem)

## Po co

Runda 1 dała wynik na najmniejszym możliwym marginesie: różnica 0,632 przy
progu 0,5 i p = 0,0476 przy progu 0,05 — czyli 10 z 210 możliwych układów
dałoby taką przewagę przypadkiem. Do tego jedna playlista (OCENA C, same
piątki) niosła sporą część efektu: bez niej różnica spada do 0,426.

Taki wynik ma dokładnie jedno sensowne dokończenie: **powtórkę na nowej
dziesiątce, z tymi samymi progami**. To nie jest nowy eksperyment. To jest
sprawdzenie, czy tamten się utrzyma.

## Co zostaje identyczne

* 6 playlist = pełne wyjście silnika, 4 = te same utwory w kolejności
  **przetasowanej**; przydział zapieczętowany w `PRZYDZIAL_NIE_OTWIERAC.json`
  do czasu wpisania wszystkich ocen.
* Te same długości i pasma tempa, więc każda sesja ma ≥30 przejść.
* Ten sam formularz, ta sama skala 1–5, te same kategorie zgrzytu.
* **Te same progi:** H1 — różnica średnich ≥ 0,5 przy p < 0,05 (permutacja po
  wszystkich 210 układach); H2 — zgodność wyniku silnika z uchem rho ≥ 0,30
  przy p < 0,05.

## Co się zmienia, świadomie

* Inne ziarno (29.08): inne losowanie kontroli, inne sety.
* **Utwory z rundy 1 są wykluczone z puli** — 155 pozycji. Bez tego powtórka
  nie byłaby niezależna: te same utwory przeniosłyby ze sobą efekt jednej
  mocnej playlisty. Pula po wykluczeniu: 7807 utworów.

## Zakup zwycięskiej playlisty — i uczciwe ostrzeżenie

Janek kupuje utwory ze **zwycięskiej playlisty**, żeby mieć jedną playlistę
z kompletem audio, wektorów i deskryptorów, a do niej gotowe oceny ucha.

**Tabela kosztów per playlista została z tego planu USUNIĘTA 29.08** (przegląd
`/in-between`). Powód policzony, nie przeczuty: koszt playlisty koreluje z jej
długością na poziomie **0,979**, więc opublikowanie kosztów było w praktyce
opublikowaniem cennika „krótsza playlista = taniej". To jest zachęta, która
RÓŻNICUJE playlisty, a nie podnosi wszystkich ocen równo — a tylko na to drugie
H1 jest odporne, bo liczy różnicę średnich.

**Ostrzeżenie, które musi tu stać:** w rundzie 1 ocena niczego nie kosztowała
i niczego nie dawała. Teraz wyższa ocena playlisty oznacza, że jej utwory
zostaną kupione — a to jest zachęta, której w rundzie 1 nie było. Jeśli oceny
runda 2 wyjdą systematycznie wyższe od rundy 1, będziemy wiedzieli, skąd to
się bierze, i nie wolno tego przypisać silnikowi.

**Zakup jest decyzją poza statystyką.** Nie wchodzi do H1 ani H2, nie zmienia
progów i nie jest powodem, żeby którąkolwiek ocenę poprawić po fakcie.

## Bramka

Analiza nie rusza i pieczęć nie pęka, dopóki wszystkie przejścia nie mają
oceny 1–5 — dokładnie jak w rundzie 1. Wynik przeciwny progom idzie do
`OBALONE.md` i **unieważnia ogłoszenie sukcesu z rundy 1**, bo replikacja
jest właśnie po to.

---

## KOREKTA PLANU (29.08, przegląd `/in-between`, PRZED pierwszą sesją)

Trzy rzeczy w tym planie były błędne. Zapisuję je, zanim pieczęć pęknie.

### 1. „Nietrafienie w progi unieważnia rundę 1" — NIEPRAWDA, wykreślone

Policzona moc testu (`moc_testu.py`, rozrzut międzyplaylistowy 0,563 wzięty
z rundy 1, ten sam test permutacyjny co w `analiza.py`):

```
prawdziwa różnica     szansa, że runda 2 zda OBA progi
        0,632 (jak w rundzie 1)                45%
        0,500 (dokładnie na progu)             34%
        0,430 (bez OCENA C)                    26%
```

Przy prawdziwym efekcie z rundy 1 runda 2 **przegrywa częściej, niż wygrywa**.
Nietrafienie w progi jest więc zdarzeniem spodziewanym także wtedy, gdy silnik
naprawdę działa, i **nie unieważnia rundy 1**. Wpis do `OBALONE.md` na tej
podstawie byłby nieprawdą zapisaną w dobrej wierze.

### 2. Test główny to ŁĄCZNA analiza obu rund, nie sama runda 2

Dwadzieścia playlist zamiast dziesięciu, za tę samą cenę pięciu sesji
słuchania. Permutacja **warstwowana w obrębie rundy** (4 kontrolne z 10
w każdej rundzie osobno), czyli C(10,4)² = 44 100 układów zamiast 210 —
minimalne osiągalne p spada z 0,0048 do rzędu 2·10⁻⁵.

```
prawdziwa różnica     szansa zdania OBU progów, obie rundy razem
        0,632                                   66%
        0,500                                   48%
        0,430                                   37%
```

*(liczby z permutacji łącznej po 20 playlistach; wersja warstwowana ma moc
zbliżoną, dokładna wartość policzona zostanie razem z wynikiem)*

Sama runda 2 zostaje testem **pomocniczym**, raportowanym obok.

### 3. Pieczęć na przydziale była ozdobą — naprawione

Wynik silnika leżał w tych samych arkuszach, w których wpisuje się oceny,
i zdradzał przydział bezbłędnie. Sprawdzone na rundzie 1: **żadne** ze 111
przejść z grupy silnika nie miało wyniku poniżej 1,0, a w kontroli miało go
53% z 47. W rundzie 2 przerwa jest równie czytelna: sześć playlist ma poniżej
4% takich przejść, cztery ponad 70%.

Na papier to nigdy nie trafiło (sprawdzone: `formularz_oceny.html` drukuje
wykonawcę, tytuł i tempo, bez wyników) — więc **ocenom Janka to nie zagrażało**.
Zagrażało każdemu, kto zajrzy do arkusza przed analizą: mnie i każdemu skryptowi
pomocniczemu. Od teraz wyniki silnika leżą w `WYNIKI_SILNIKA_NIE_OTWIERAC.json`
i `analiza.py` dokleja je **dopiero po przejściu bramki kompletności**.

### Do rozstrzygnięcia przez Janka

Reguła zakupu. Dopóki nie zdecyduje, obowiązuje zapis pierwotny, ale przegląd
wskazał tańszą i czystszą alternatywę: lista zakupowa pod oceny z rundy 1
(`experiments_priv/2026-08-29_lista_zakupow/`) odblokowuje **2,3× więcej
ocenionych przejść na kupiony utwór** i dotyczy ocen już zebranych, więc nie
może niczego skazić.
