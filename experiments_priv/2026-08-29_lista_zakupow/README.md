# Co kupić, żeby oceny z papieru dało się wykorzystać (29.08)

**Problem.** Ze 155 ocenionych utworów **107 to strumienie Apple Music bez
pliku**. Przejście nadaje się do uczenia silnika dopiero wtedy, gdy OBA jego
utwory mają audio. Dziś takich przejść jest **22 ze 158**.

**Sprawdzone: żadnego z tych 107 nie masz już na dysku pod inną nazwą**
(`czy_juz_masz.py` porównał je z 1092 plikami w `~/Music` — zero trafień).

**Kolejność zakupów.** `policz.py` układa listę zachłannie: najpierw utwory,
które odblokowują najwięcej ocenionych przejść. Krzywa:

```
  10 utworów →  43 ze 158 przejść (27%)
  20 utworów →  56 (35%)
  30 utworów →  70 (44%)
  40 utworów →  81 (51%)
  50 utworów →  93 (59%)
  60 utworów → 105 (66%)
  80 utworów → 129 (82%)
 100 utworów → 151 (96%)
 107 utworów → 158 (100%)
```

Pełna lista: `lista_zakupow.csv` (wykonawca, tytuł, tempo, tonacja, ile
przejść odblokowuje).

**Czego zakup NIE naprawia.** Sety z tych playlist i tak zostają niegrywalne
jako całości, dopóki brakuje reszty utworów — kupujemy dane do POMIARU
pojedynczych przejść, nie gotowe sety na imprezę. I nadal jest to jeden DJ,
jedna próbka: 158 ocen to instrument pomiarowy, nie zbiór treningowy.

**Tańsza alternatywa bez wydawania grosza:** powtórka ślepego odsłuchu na
dziesięciu playlistach z puli `library-dysk` (masz 1092 pliki audio, więc jest
z czego budować). Kosztuje pięć sesji słuchania zamiast pieniędzy — i daje
komplet danych od razu, bez łatania starej próbki.
