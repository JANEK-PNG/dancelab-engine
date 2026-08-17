# Plan przebudowy bazy pod uczenie maszynowe

Spisane 2026-08-14, po pytaniu Janka o normy budowania dużej bazy pod ML.
Kolejność nie jest dowolna — każda faza odblokowuje następną, a dwie pierwsze
tanieją tylko wtedy, gdy zrobi się je przed kolejnym dużym zaciągnięciem.

## Stan wyjściowy, zmierzony

```
wierszy w miksach                      5 117
pozycji tracklist                    147 964
  ze znacznikiem czasu                 4 022   2,7%
setów, z których da się policzyć przejście  414   ← REALNY zbiór uczący
encji artysty                          2 331
  z trwałym identyfikatorem              601   26%
  wyłącznie jako łańcuch znaków        1 730   74%
```

Dwie liczby, które trzeba mieć przed oczami przy każdej decyzji: **414** i **74%**.

---

## Faza 0 — zatrzymać utratę historii

**Kiedy:** natychmiast, przed jakimkolwiek kolejnym zaciągnięciem.
**Koszt:** jeden wieczór.
**Dlaczego pierwsza:** to jedyna faza, której opóźnienie powoduje stratę
NIEODWRACALNĄ. Każdy dzień bez daty pobrania to dzień, którego nie odtworzymy.

1. Zamrozić dzisiejszy stan jako `surowe/2026-08-14/` — kopia wszystkich
   JSON-ów, tylko do odczytu, nigdy więcej nienadpisywana.
2. Do każdego zapisu w runnerach dołożyć trzy pola: `pobrano_utc`,
   `zrodlo_wersja` (np. `soundcloud api-v2`), `hash_odpowiedzi`.
3. Runnery przestają nadpisywać — dopisują do warstwy surowej, a warstwę
   uzgodnioną budują od nowa przy każdym przebiegu.

**Sprawdzian:** da się powiedzieć, jak wyglądał wiersz tydzień temu.

---

## Faza 1 — klucz artysty

**Kiedy:** zaraz po fazie 0, PRZED następnym dużym zaciągnięciem.
**Koszt:** dwa, trzy wieczory.
**Dlaczego druga:** blokuje wszystko. Każdy kolejny milion wierszy zwiększa
koszt tej migracji i nie zmniejsza ryzyka.

1. `encje/artysta.json` — jeden wiersz na człowieka:
   `artysta_id` (nadany raz, nigdy niezmieniany) · `nazwa_kanoniczna` ·
   `ra_id` · `soundcloud` · `bandcamp` · `apple` · `kraj` · `kraj_zamieszkania`
2. `encje/alias.json` — `ksywa → artysta_id`, WIELE DO JEDNEGO.
   Tu trafiają warianty pisowni, duety rozbite na osoby, ksywy z literówkami.
3. Wszystkie tabele dostają `artysta_id` OBOK `ksywa`.
   **`ksywa` przestaje być kluczem, zostaje atrybutem.**
4. Cztery kolizje po normalizacji, które już wykryliśmy, rozstrzyga człowiek.

**Sprawdzian:** zmiana pisowni ksywy nie rozspaja żadnego wiersza.

---

## Faza 2 — tabela szwów

**Kiedy:** po fazie 1.
**Koszt:** dwa wieczory.
**Dlaczego trzecia:** to jest jednostka analizy DanceLab, a dziś nie istnieje
jako tabela — jest wyliczana od nowa w trzech miejscach, innym kodem.

`fakty/szew.json`:

```
szew_id · set_id · artysta_id
pozycja_z · pozycja_do            (numery w tracklistcie)
utwor_z · utwor_do                (nazwy, gdy znane)
czas_ms                           (moment przejścia)
zrodlo_czasu                      zmierzony | z_kotwic | brak
waga                              0.0-1.0, patrz faza 4
```

Po tej fazie po raz pierwszy zobaczymy uczciwą liczbę przykładów uczących.
Podejrzewam, że wyjdzie kilkaset, nie kilkadziesiąt tysięcy — i lepiej
wiedzieć to teraz niż po trenowaniu.

**Sprawdzian:** `SELECT COUNT(*) FROM szew WHERE zrodlo_czasu='zmierzony'`
odpowiada na pytanie „ile mamy danych" jedną liczbą.

---

## Faza 3 — kontrakt wykonywalny

**Kiedy:** po fazie 2, zanim dołożymy kolejne źródła.
**Koszt:** jeden wieczór.
**Dlaczego tu:** `NAZEWNICTWO.md` jest dziś obietnicą, nie bramką. Dzisiaj
zbudowałam pięć zbiorów poza konwencją i wyszło to dopiero, gdy Janek zapytał.

1. Schemat na każdą tabelę — typy, słowniki zamknięte, pola wymagane.
2. Wiersz spoza słownika jest ODRZUCANY, nie poprawiany po cichu.
3. Test uruchamiany przy każdym przebiegu runnera.

**Sprawdzian:** nie da się zapisać `scena="Sala"`, gdy słownik mówi `scena`.

---

## Faza 4 — podziały i wagi

**Kiedy:** przed pierwszym uczeniem, nie wcześniej.
**Koszt:** jeden wieczór.

1. **Podział grupowy po `artysta_id`** — ten sam DJ nigdy po obu stronach.
   Bez tego model nauczy się osoby, nie zjawiska. DJ ma swój nawyk.
2. **Podział chronologiczny** — uczenie 2016-2023, test 2024-2026.
   Odpowiada na inne pytanie: czy nie uczymy się mody.
3. **`pewnosc` → waga liczbowa.** Dziś to napis. Propozycja:
   `link`/`zmierzony` = 1,0 · `tytul+rok`/`z_kotwic` = 0,4 · `nowy` = 0,0
   (do inspekcji, nie do uczenia).
4. **Wagi klas** wobec rozkładu: Niemcy 33%, Polska 15%. To nie błąd zbierania,
   tak wygląda scena — ale bez wag model uzna Garbicz za wyjątek od Berlina.

**Sprawdzian:** żaden `artysta_id` nie występuje w train i test naraz.

---

## Faza 5 — kontrprzykłady

**Kiedy:** po fazie 4.
**Koszt:** jeden, dwa wieczory.

Model widzący wyłącznie udane przejścia nie wie, czym jest złe. Generujemy
pary, których DJ NIE zestawił, choć miał oba utwory w TYM SAMYM secie —
to jest kontrprzykład mocny, bo kontrolujemy kontekst, wieczór i człowieka.

**Ostrzeżenie:** „nie zestawił" nie znaczy „nie dało się". To jest etykieta
słaba i musi mieć niższą wagę niż przejście zaobserwowane.

---

## Faza 6 — warstwy katalogów

**Kiedy:** równolegle, wraz z fazami 0-2.

```
surowe/     odpowiedzi serwerów, niezmienne, z datą pobrania
encje/      artysta · wydarzenie · scena · utwór — każde z ID
fakty/      set · pozycja · szew
cechy/      wyliczone, wersjonowane, z gotowymi podziałami
```

Dziś wszystko leży w jednej warstwie i każda poprawka parsera niszczy oryginał.

---

## Czego NIE robić

**Nie przepisywać wszystkiego naraz.** Fazy 0 i 1 są pilne, reszta nie.

**Nie budować magazynu cech** (*feature store*) na tym etapie. Przy 414
przykładach to jest narzędzie do problemu, którego nie mamy.

**Nie zbierać więcej, dopóki nie ma klucza artysty.** Każde kolejne źródło
dokłada encji, a przy 74% bez identyfikatora dokłada też pracy przy migracji.

**Nie mylić katalogu z danymi uczącymi.** 147 964 pozycje to zasób do
wyszukiwania i do opisu artysty. Zbiór uczący ma 414 pozycji i to jest liczba,
którą trzeba podnosić — a podnosi ją WYŁĄCZNIE zbieranie znaczników czasu.

---

## Kolejność w jednym zdaniu

Zamrozić historię → nadać artystom identyfikatory → zbudować tabelę szwów →
zamknąć konwencję na klucz → dopiero wtedy myśleć o uczeniu.
