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

  /* Edycja setu (01.09). Podgląd MUSI tu udawać stan, bo inaczej po
     kliknięciu „podmień" tabela wróciłaby niezmieniona i obraz nie
     powiedziałby nic o tym, czy funkcja działa. Kandydaci to utwory
     z biblioteki spoza setu — kolejność i oceny są ZMYŚLONE i tylko
     do oglądania układu; prawdziwe liczy `slot_suggest` w Pythonie. */
  kandydaci: (poz, tryb, cel) => {
    const set = DANE.set?.utwory || [];
    const maja = new Set(set.map(u => u.track_id));
    const pula = (DANE.biblioteka?.utwory || []).filter(u => !maja.has(u.track_id));
    return echo({tryb, cel, kandydaci: pula.slice(0, 10).map((u, i) => ({
      ...u, ranga: i + 1, score: 0.94 - i * 0.06,
      why: `wejście 0,9${9 - i} · wyjście 0,8${9 - i} [PODGLĄD: liczby zmyślone]`,
    }))});
  },
  podmien: (poz, tid) => {
    const set = DANE.set.utwory, kand = (DANE.biblioteka?.utwory || []);
    set[poz] = kand.find(u => u.track_id === tid) || set[poz];
    return echo({utwory: set, filary: DANE.set.filary || []});
  },
  dopisz_utwor: (poz, tid) => {
    const set = DANE.set.utwory, kand = (DANE.biblioteka?.utwory || []);
    const u = kand.find(x => x.track_id === tid);
    if (u) set.splice(poz + 1, 0, u);
    return echo({utwory: set, filary: DANE.set.filary || []});
  },
  wytnij: (poz) => {
    const set = DANE.set.utwory;
    const filar = (DANE.set.filary || []).includes(set[poz]?.track_id);
    set.splice(poz, 1);
    return echo({utwory: set, filary: DANE.set.filary || [],
                 uwaga: filar ? 'wyciąłeś FILAR — set stracił jeden z punktów, '
                              + 'na których był rozpięty' : undefined});
  },
  przesun_utwor: (poz, kier) => {
    const set = DANE.set.utwory, j = poz + (kier > 0 ? 1 : -1);
    if (j < 0 || j >= set.length) {
      return echo({utwory: set, filary: DANE.set.filary || [],
                   uwaga: 'brzeg setu — nie ma dokąd przesunąć'});
    }
    [set[poz], set[j]] = [set[j], set[poz]];
    return echo({utwory: set, filary: DANE.set.filary || [], na: j});
  },
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
