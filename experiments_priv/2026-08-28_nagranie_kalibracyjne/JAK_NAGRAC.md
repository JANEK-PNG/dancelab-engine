# Jak nagrać set, który naprawdę sprawdzi model

Poprzednie nagranie (`test_1`, 24.08) potwierdziło głównie to, że plik gra.
Zgodność w oknie szwu stanęła na 0,56, a próba poprawienia echa okazała się
**bezprzedmiotowa**, bo przełącznik kanału FX ruszył się dopiero pod koniec.
Ta kartka istnieje po to, żeby następne nagranie miało czym sprawdzić model.

## Zanim zaczniesz

1. **Podłącz FLX4** i sprawdź kropkę u góry panelu: `http://localhost:8655/`.
   Ma być zielona. Jeśli panel nie chodzi:
   `cd ~/Developer/dancelab-engine && ./scripts/panele.sh start`

2. **Poruszaj każdą gałką i suwakiem po kolei** — EQ, trim, fadery, crossfader,
   CFX, LEVEL/DEPTH, tempo. To nie jest kaprys: rejestr zapisuje **ruchy**, nie
   stan, więc bez tego nie wiem, skąd startowały. Panel pokazuje pasek
   „pozycje startowe" — dopchnij go do kompletu, zanim wciśniesz nagrywanie.

3. **Włącz nasz rejestrator** (przycisk REC w panelu) i dopiero potem
   **REC w Rekordboxie**. Kolejność nieistotna dla wyniku — przesunięcie
   znajduję korelacją — ale oba muszą lecieć przez cały set.

## Co koniecznie zrobić w trakcie

Nie musisz grać dobrze. Musisz **użyć rzeczy, których model jeszcze nie umie
sprawdzić**. Piętnaście minut wystarczy.

* **Przełącz kanał BEAT FX w trakcie grania** — CH1, potem CH2, potem CH1&2,
  przy WŁĄCZONYM efekcie. To jedyna rzecz, której poprzednie nagranie nie
  zawierało, a od której zależy, czy wczorajsza poprawka cokolwiek daje.
* **Pokręć LEVEL/DEPTH** przy każdej pozycji przełącznika.
* **Zrób pełne przejście**: bas w dół na wchodzącym, fader w górę, oddanie basu.
  Najlepiej dwa albo trzy, żeby nie stało na jednym przypadku.
* **Użyj CFX** na obu deckach, w obie strony (filtr dolno- i górnoprzepustowy).
* **Ruszaj tempem** — model liczy je jako zmianę prędkości odtwarzania i to
  jest miejsce, gdzie łatwo mu się rozjechać.

* **Wróć do jednego utworu** — tak jak robisz normalnie: zagraj, wpuść jeden
  inny, wróć na krócej, skacząc po nim hot cue'ami. To załatwia drugą rzecz
  naraz: mamy tylko dwa nagrania z powrotami, oba Twoje, więc trzecie
  sprawia, że przestaje to być n=2. Nie graj tego „pod pomiar" — jeśli
  naturalnie nie wrócisz, to też jest wynik.

## Czego NIE używać

* **SMART FADER i SMART CFX.** Model ich nie emuluje i nie będzie — to
  automatyka, której nie ma na klubowym sprzęcie. Jeśli ich użyjesz, rozjazd
  będzie mój, ale z powodu, którego nie da się naprawić.

## Po nagraniu

Powiedz mi tylko: **które utwory grały na deckach** (albo zostaw plik cue —
Rekordbox zapisuje go obok nagrania i tam to jest). Reszta jest po mojej
stronie: render z rejestru, porównanie z nagraniem, raport gdzie się rozjeżdża.

Nagranie Rekordboxa ląduje w `~/Music/rekordbox/Recording/Jan Trybus/…`,
nasz rejestr w `experiments_priv/2026-08-24_rejestry_konsoli/`.
