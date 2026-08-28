"""Złóż podgląd okna do przeglądarki: PRAWDZIWE pliki + prawdziwe dane.

HTML, CSS i JavaScript są kopiowane bez zmiany jednej litery. Jedyne, co
dochodzi, to `stub.js` — udawany most do Pythona, który oddaje odpowiedzi
zapisane wcześniej przez `zrzut_danych.py`. Dzięki temu w przeglądarce
rysuje się dokładnie ten kod, który rysuje okno; klikanie w zapis do bazy
tu nie działa i ma nie działać.
"""

import json
import pathlib
import shutil

TU = pathlib.Path(__file__).parent
ZRODLO = TU.parents[1] / "src/dancelab/gui/statyczne"
CEL = TU / "podglad"

STUB = """/* Udawany most — TYLKO do oglądania wyglądu w przeglądarce. */
const DANE = window.__DANE__;
const echo = (x) => Promise.resolve(x);
window.pywebview = {api: {
  biblioteka: () => echo(DANE.biblioteka || {utwory: []}),
  wczytaj_utwor: () => echo(DANE.utwor || {}),
  przebieg_utworu: () => echo(DANE.przebieg || {}),
  pady: () => echo(DANE.pady || {pady: {}}),
  stan_rekordboxa: () => echo(DANE.stan_rb || {}),
  wczytaj_edycje: () => echo({wczytano: 0}),
  zapisz_edycje: () => echo({zapisano: 0}),
  postep_budowy: () => echo(DANE.set || {stan: 'bezczynny'}),
  buduj_set: () => echo({ruszylo: true}),
  zapis_stan: () => echo({set: (DANE.set?.utwory || []).length,
                          propozycje: true, policzone: false,
                          rekordbox_otwarty: false}),
  przygotuj_zapis_cue: () => echo(DANE.zapis || {blad: 'brak danych'}),
  zapisz_cue: () => echo({blad: 'podgląd w przeglądarce nie pisze do bazy'}),
  postaw_pad: () => echo(DANE.pady || {pady: {}}),
  przesun_pad: () => echo(DANE.pady || {pady: {}}),
  zdejmij_pad: () => echo(DANE.pady || {pady: {}}),
  cofnij: () => echo(DANE.pady || {pady: {}}),
  kolizje: () => echo({kolizje: []}),
  propozycje: () => echo({propozycje: []}),
  biezacy_plan: () => echo({kolejnosc: []}),
}};
"""


def main() -> int:
    dane = json.loads((TU / "dane.json").read_text(encoding="utf-8"))
    CEL.mkdir(parents=True, exist_ok=True)
    for nazwa in ("styl.css", "app.js"):
        shutil.copy2(ZRODLO / nazwa, CEL / nazwa)

    html = (ZRODLO / "index.html").read_text(encoding="utf-8")
    wstawka = (f'<script>window.__DANE__ = {json.dumps(dane, ensure_ascii=False)};'
               f'</script>\n<script src="stub.js"></script>\n')
    html = html.replace('<script src="app.js"></script>',
                        wstawka + '<script src="app.js"></script>')
    # Dopiero teraz znacznik wersji — wcześniej rozjeżdżał wzorzec, po którym
    # wstawiany jest stub. Przeglądarka trzymała stary app.js mimo poprawki.
    import time as _t
    wersja = int(_t.time())
    html = html.replace('href="styl.css"', f'href="styl.css?v={wersja}"')
    html = html.replace('src="app.js"', f'src="app.js?v={wersja}"')
    html = html.replace('src="stub.js"', f'src="stub.js?v={wersja}"')
    (CEL / "index.html").write_text(html, encoding="utf-8")
    (CEL / "stub.js").write_text(STUB, encoding="utf-8")
    print(f"podgląd → {CEL/'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
