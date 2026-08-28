# Poprawka echa: na wybrany kanał zamiast na cały miks

**Zapisane 2026-08-28 PRZED renderem.**

## Co jest nie tak

`graj_rejestr.py` dodaje echo do **całego miksu**:

```python
mix = sucho + ogon * ile * 0.9
```

Na FLX4 BEAT FX działa na **wybrany kanał** — przełącznik ma trzy pozycje
(CH1, CH2, CH1&2) i wysyła to jako nuty 16/17 na kanałach 5 i 6. Rejestr to ma,
model tego nie czyta.

W sesji `test_1` największy rozjazd (55 dB) wypada na sekundzie 311, gdzie
w rejestrze widać **152 ruchy LEVEL/DEPTH** i 130 ruchów EQ LOW naraz. To jest
miejsce, w którym efekt pracuje najintensywniej.

## Próg

Punkt odniesienia: render obecnym kodem, ta sama sesja, te same parametry.
Mierzę `zgodnosc_ksztaltu` i zgodność w trzech pasmach (`porownaj.py`).

* **POPRAWKA ZOSTAJE** — zgodność kształtu rośnie o **≥ 0,02**, a żadne pasmo
  nie traci więcej niż 0,02.
* **POPRAWKA WRACA** — zgodność spada albo stoi w miejscu (< 0,01 zmiany).
  Wtedy zapisuję, że kanałowanie echa nic nie dało, i nie zostawiam
  skomplikowania bez pokrycia w pomiarze.
* **NIEROZSTRZYGNIĘTE** — zmiana między 0,01 a 0,02. Zostawiam kod prostszy.

## Czego to NIE naprawi

Model nadal nie zna jogu (fazy), Smart CFX ani Smart Fadera — to są znane
granice, spisane wcześniej. Ta poprawka dotyczy wyłącznie echa.
