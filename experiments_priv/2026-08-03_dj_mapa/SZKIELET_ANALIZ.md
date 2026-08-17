# Kolumny czekające na analizę dźwięku

Wypełnia je OSOBNY przebieg, w osobnym miejscu. Tu nie liczymy nic
z dźwięku — ten plik ustala tylko nazwy i jednostki, żeby ten, kto
będzie je wypełniał, nie musiał niczego zgadywać.

## Tabela UTWORY (`encje_utwor.json`) — jedna analiza na utwór

| kolumna | co wpisać |
|---|---|
| `bpm` | tempo w uderzeniach na minutę, jedna liczba |
| `bpm_pewnosc` | 0-1; niska przy podejrzeniu oktawy |
| `tonacja` | zapis Camelot, np. 8A |
| `tonacja_klasyczna` | np. A-moll |
| `tonacja_pewnosc` | 0-1 |
| `energia` | 0-1, umowna skala DanceLab |
| `gestosc_groove` | 0-1 |
| `obecnosc_basu` | 0-1 |
| `dlugosc_s` | długość utworu w sekundach |
| `analiza_wersja` | wersja silnika, która to policzyła |
| `analiza_data` | RRRR-MM-DD |

Utwór jest jednostką analizy, nie wystąpienie. Ten sam kawałek wraca w dziesiątkach setów — tempo i tonacja liczy się raz.

## Tabela SZWY (`fakty_szew.json`) — jedna analiza na przejście

| kolumna | co wpisać |
|---|---|
| `bpm_z` | tempo utworu wychodzącego |
| `bpm_do` | tempo utworu wchodzącego |
| `delta_bpm` | różnica; ujemna = zwolnienie |
| `delta_bpm_proc` | różnica w procentach — to ona decyduje o wykonalności |
| `tonacja_z` | Camelot |
| `tonacja_do` | Camelot |
| `zgodnosc_harmoniczna` | idealna | sasiednia | wzgledna | zadna |
| `dlugosc_przejscia_s` | ile trwa nakładanie |
| `typ_przejscia` | cut | blend | echo | loop | filtr | inne |
| `bas_wstrzymany` | tak | nie — reguła wejścia Janka |
| `energia_z` | 0-1 |
| `energia_do` | 0-1 |
| `delta_energii` | różnica |
| `analiza_wersja` |  |
| `analiza_data` |  |

`delta_bpm_proc` liczy się względem utworu WYCHODZĄCEGO, bo to on
wyznacza tempo, do którego DJ musi dociągnąć następny.

`bas_wstrzymany` odsyła do reguły wejścia Janka: bas wstrzymany
w 86% jego wejść. To jest pole do sprawdzenia tej reguły na cudzych
setach.
