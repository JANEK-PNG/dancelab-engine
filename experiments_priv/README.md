# experiments_priv — dane prywatne badań

Wszystko, co powstaje z **własnych nagrań Janka** albo z jego licencjonowanej
biblioteki, ląduje tutaj — nigdy w `/tmp`, nigdy na Desktopie (Desktop to
fizycznie iCloud), nigdy w gicie.

Powód nie jest kosmetyczny. Katalogi tymczasowe znikają razem z sesją, więc
wynik, którego nie da się odtworzyć bez godzin liczenia, przepada w momencie,
w którym przestaje być potrzebny na ekranie. A materiał audio nie może trafić
do repozytorium ani do chmury — to nagrania i utwory objęte prawami.

## Układ

```
experiments_priv/
  _cache/stems/<hash>/          rozdzielone ślady Demucsa, klucz = hash ścieżki
  RRRR-MM-DD_<nazwa>/           jeden eksperyment = jeden katalog
      report.json               surowe liczby
      *.png                     wykresy
      *.wav                     wycinki do odsłuchu
      diag*.py                  ślepe uliczki, zostawione świadomie (patrz niżej)
```

`_cache/stems` jest wspólny i **wart pieniędzy**: separacja jednego utworu to
minuty na MPS, a klucz jest po ścieżce pliku, więc ten sam utwór w kolejnym
eksperymencie liczy się raz.

## Dlaczego skrypty diagnostyczne zostają

Każdy `diag*.py` to hipoteza, która została **obalona pomiarem** — większy FFT
nie rozdziela basu, lepszy resampling nic nie zmienia, widmo amplitudowe nie
sumuje się. Bez nich następna osoba (albo ja za miesiąc) spróbuje tego samego
i straci ten sam dzień. Wynik negatywny jest tu wynikiem, nie śmieciem.

## Czego tu NIE ma

Cudzego audio z korpusu. Korpus mieszka na dysku `MY_PC/DanceLabCorpus` i tam
zostaje.
