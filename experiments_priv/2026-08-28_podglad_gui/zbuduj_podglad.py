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
window.__LICZ__ = (poz, tryb, cel) => {
  const set = DANE.set?.utwory || [];
  const maja = new Set(set.map(u => u.track_id));
  const pula = (DANE.biblioteka?.utwory || []).filter(u => !maja.has(u.track_id));
  return {tryb, cel, kandydaci: pula.slice(0, 10).map((u, i) => ({
    ...u, ranga: i + 1, score: 0.94 - i * 0.06,
    why: `wejście 0,9${9 - i} · wyjście 0,8${9 - i} [PODGLĄD: liczby zmyślone]`,
  }))};
};
window.pywebview = {api: {
  biblioteka: () => echo(DANE.biblioteka || {utwory: []}),
  wczytaj_utwor: () => echo(DANE.utwor || {}),
  przebieg_utworu: () => echo(DANE.przebieg || {}),
  pady: () => echo(DANE.pady || {pady: {}}),
  /* Przełączalny stan Rekordboxa: bez tego nie da się OBEJRZEĆ, czy
     zamknięcie programu odblokowuje przyciski zapisu. */
  stan_rekordboxa: () => echo(window.__RB_OTWARTY__
    ? {otwarty: true, zapis_dozwolony: false,
       powod: 'Rekordbox jest otwarty — zapis skorumpowałby bazę'}
    : {otwarty: false, zapis_dozwolony: true,
       powod: 'Rekordbox zamknięty — zapis dostępny'}),
  wczytaj_edycje: () => echo({wczytano: 0}),
  zapisz_edycje: () => echo({zapisano: 0}),
  postep_budowy: () => echo(DANE.set || {stan: 'bezczynny'}),
  buduj_set: () => echo({ruszylo: true}),
  zapis_stan: () => echo({set: (DANE.set?.utwory || []).length,
                          propozycje: true, policzone: false,
                          playlista_policzona: !!window.__PL__,
                          rekordbox_otwarty: !!window.__RB_OTWARTY__}),
  /* Playlista: podgląd zwraca liczby, wysyłka udaje sukces — w przeglądarce
     nic do bazy nie idzie i iść nie może. */
  podglad_playlisty: (nazwa) => {
    const n = (DANE.set?.utwory || []).length;
    window.__PL__ = true;
    return echo({ok: true, nazwa: nazwa || 'DanceLab okno · 90 min',
                 zgloszone: n, dopasowane: Math.max(0, n - 1), zapisane: 0,
                 bez_sciezki: [], kopia: null,
                 notki: ['POMINIĘTY (brak/niejednoznaczny): przykład.aiff']});
  },
  wyslij_playliste: () => echo({blad: 'podgląd w przeglądarce nie pisze do bazy'}),
  /* ODSŁUCH w podglądzie jest NIEMY — i taki ma być: przeglądarka służy do
     oglądania wyglądu, a zasada „dźwięk tylko z gestu w prawdziwym oknie"
     nie ma wyjątku dla wygody. Pozycja tyka udawanym zegarem, żeby dało się
     ZOBACZYĆ, jak jedzie głowica po fali i jak wygląda pasek podczas grania.
     `window.__STRUMIEN__ = true` pokazuje wariant „utwór bez pliku". */
  graj: (tid) => {
    if (window.__STRUMIEN__) {
      return echo({blad: 'Utwór ze strumienia: nie ma pliku na dysku '
                       + '(utwór ze strumienia) — zagrasz go w Rekordboksie, '
                       + 'tutaj policzymy tylko dobór', bez_pliku: true});
    }
    if (window.__GRA__ && window.__GRA__.tid === tid) {
      window.__GRA__ = null;
      return echo({gra: false, pozycja_sec: 12, akcja: 'pauza',
                   rodzaj: 'utwor', track_id: tid, opis: '', skad: ''});
    }
    window.__GRA__ = {tid, od: Date.now(), rodzaj: 'utwor'};
    return echo({gra: true, pozycja_sec: 0, akcja: 'start', rodzaj: 'utwor',
                 track_id: tid, dlugosc_sec: (DANE.przebieg || {}).dlugosc_sec,
                 opis: 'podgląd — bez dźwięku', skad: 'od zera'});
  },
  stan_odtwarzania: () => {
    const g = window.__GRA__;
    if (!g) return echo({gra: false, pozycja_sec: 0, skonczyl_sie: false});
    return echo({gra: true, rodzaj: g.rodzaj, track_id: g.tid,
                 pozycja_sec: (Date.now() - g.od) / 1000,
                 dlugosc_sec: (DANE.przebieg || {}).dlugosc_sec,
                 opis: 'podgląd — bez dźwięku', skad: 'od zera',
                 skonczyl_sie: false});
  },
  skocz: (n) => {
    const g = window.__GRA__;
    if (!g) return echo({blad: 'nic nie gra'});
    g.od -= n * 60000 / 128;
    return echo({gra: true, rodzaj: g.rodzaj, track_id: g.tid,
                 pozycja_sec: (Date.now() - g.od) / 1000,
                 dlugosc_sec: (DANE.przebieg || {}).dlugosc_sec,
                 opis: 'podgląd — bez dźwięku', skad: 'skok'});
  },
  stop_dzwieku: () => { window.__GRA__ = null;
                        return echo({gra: false, pozycja_sec: 0}); },
  graj_szew: () => { window.__SZEW__ = Date.now(); return echo({ruszylo: true}); },
  postep_szwu: () => {
    if (!window.__SZEW__) return echo({stan: 'bezczynny'});
    if (Date.now() - window.__SZEW__ < 1200) return echo({stan: 'trwa'});
    window.__SZEW__ = null;
    window.__GRA__ = {tid: 'szew', od: Date.now(), rodzaj: 'szew'};
    return echo({stan: 'gra', cue_a_sec: 210, cue_b_sec: 14,
                 odtwarzanie: {gra: true, rodzaj: 'szew', track_id: 'szew',
                               pozycja_sec: 0, opis: 'szew silnika: A → B',
                               skad: 'szew silnika', skonczyl_sie: false}});
  },
  przygotuj_zapis_cue: () => echo(DANE.zapis || {blad: 'brak danych'}),
  zapisz_cue: () => echo({blad: 'podgląd w przeglądarce nie pisze do bazy'}),
  postaw_pad: () => echo(DANE.pady || {pady: {}}),
  przesun_pad: () => echo(DANE.pady || {pady: {}}),
  zdejmij_pad: () => echo(DANE.pady || {pady: {}}),
  cofnij: () => echo(DANE.pady || {pady: {}}),
  kolizje: () => echo({kolizje: []}),
  propozycje: () => echo({propozycje: []}),
  biezacy_plan: () => echo({kolejnosc: []}),

  /* Biblioteka z filtrami, filary, playlisty (01.09). Filtrowanie w oknie
     robi Python; tutaj udajemy je na spisie, żeby dało się OBEJRZEĆ układ. */
  szukaj: (fraza, ton, bpm, tylkoUlub, sortuj, limit) => {
    let u = (DANE.biblioteka?.utwory || []).map(x => ({
      ...x, ulubiony: (window.__ULUB__ || []).includes(x.track_id),
      filar: (window.__FIL__ || []).some(f => f.track_id === x.track_id)}));
    const f = (fraza || '').toLowerCase();
    if (f) u = u.filter(x => (x.tytul || '').toLowerCase().includes(f));
    if (ton) u = u.filter(x => (x.tonacja || '').toUpperCase() === ton.toUpperCase());
    if (tylkoUlub) u = u.filter(x => x.ulubiony);
    if (sortuj === 'bpm') u.sort((a, b) => (a.bpm || 0) - (b.bpm || 0));
    if (sortuj === 'tytul') u.sort((a, b) => (a.tytul || '').localeCompare(b.tytul || ''));
    return echo({utwory: u.slice(0, limit || 400), znalezione: u.length,
                 wszystkich: (DANE.biblioteka?.utwory || []).length});
  },
  ulubione: () => echo({ulubione: window.__ULUB__ || []}),
  przelacz_ulubiony: (tid) => {
    window.__ULUB__ = window.__ULUB__ || [];
    const i = window.__ULUB__.indexOf(tid);
    if (i >= 0) window.__ULUB__.splice(i, 1); else window.__ULUB__.push(tid);
    return echo({ulubiony: i < 0, track_id: tid});
  },
  playlisty: () => echo({
    playlisty: [{nazwa: 'Piątek', filarow: (window.__FIL__ || []).length,
                 kotwica: null}],
    aktywna: 0, tryb_filarow: 'rozstaw',
    role: {'': 'bez roli — po prostu musi zagrać', otwarcie: 'pierwszy utwór',
           buildup: 'rozpędza w górę', oddech: 'zejście w środku',
           zamkniecie: 'ostatni utwór'}}),
  nowa_playlista: () => echo({playlisty: [{nazwa: 'Piątek', filarow: 0}],
                              aktywna: 0, role: {}, tryb_filarow: 'rozstaw'}),
  wybierz_playliste: () => echo({playlisty: [], aktywna: 0, role: {}}),
  filary: () => echo({filary: window.__FIL__ || [], tryb_filarow: 'rozstaw',
                      aktywna: 0}),
  ustaw_filar: (tid, rola) => {
    window.__FIL__ = window.__FIL__ || [];
    const u = (DANE.biblioteka?.utwory || []).find(x => x.track_id === tid);
    const i = window.__FIL__.findIndex(f => f.track_id === tid);
    if (i >= 0) window.__FIL__[i].rola = rola;
    else window.__FIL__.push({track_id: tid, rola,
                              tytul: (u && u.tytul) || tid});
    return echo({filary: window.__FIL__, tryb_filarow: 'rozstaw'});
  },
  zdejmij_filar: (tid) => {
    window.__FIL__ = (window.__FIL__ || []).filter(f => f.track_id !== tid);
    return echo({filary: window.__FIL__, tryb_filarow: 'rozstaw'});
  },
  ustaw_tryb_filarow: (t) => echo({tryb_filarow: t}),
  lista_planow: () => echo({plany: [
    {path: '/p/1.json', zapisano: '2026-09-01 14:20', nazwa: 'Piątek 126–134',
     n: 12, bpm: '126-134', dj: 'Ben UFO', biezacy: true},
    {path: '/p/2.json', zapisano: '2026-08-30 22:10', nazwa: 'Sobota',
     n: 18, bpm: '', dj: '', biezacy: false}]}),
  wczytaj_plan: () => { window.__PLAN__ = {stan: 'trwa'};
    setTimeout(() => { window.__PLAN__ = {stan: 'gotowe', nazwa: 'Piątek 126–134',
      zapisanych: 12, utwory: (DANE.set?.utwory || []).slice(0, 6),
      notki: ['BRAK W PULI (pominięty): stary utwór'], parametry: {}}; }, 500);
    return echo({ruszylo: true}); },
  postep_planu: () => echo(window.__PLAN__ || {stan: 'bezczynny'}),
  info_utworu: (tid) => echo({track_id: tid, tekst: [
    'SILNIK:', '  BPM 127.0 · ton 5A (pew. 0.62)', '  gatunek: —',
    '  długość: 4:37', '  wektor brzmienia: brak', '',
    'PLIK:', '  /Users/…/Dub Champion (UKG VIP).aiff', '',
    'REKORDBOX:', '  BPM wg Rekordboxa: 127.0',
    '  poza wszystkimi playlistami'].join(String.fromCharCode(10))}),
  porownaj_pare: (poz) => echo({pozycja: poz,
    a: (DANE.set?.utwory || [])[poz] || {tytul: 'A'},
    b: (DANE.set?.utwory || [])[poz + 1] || {tytul: 'B'},
    uderzen: 64, bpm: 127.0, cue_a_sec: 245.5, cue_b_sec: 12.0}),
  djs: () => echo({moje_ulubione: '★ moje ulubione', ulubionych_utworow: 7,
    kolekcja: window.__KOL__ || [],
    grupy: [{etykieta: 'brzmi jak: Ben UFO · Joy O · Pearson Sound',
             djs: [{nazwa: 'Ben UFO', wektorow: 42, skok: 0.68, odwaga: 'odważny',
                    w_kolekcji: (window.__KOL__ || []).includes('Ben UFO')},
                   {nazwa: 'Joy Orbison', wektorow: 31, skok: 0.77,
                    odwaga: 'pośrodku', w_kolekcji: false}]},
            {etykieta: 'brzmi jak: Sarah Story · Storm Mollison',
             djs: [{nazwa: 'Sarah Story', wektorow: 18, skok: 0.83,
                    odwaga: 'gładki', w_kolekcji: false}]}]}),
  przelacz_kolekcje_dj: (dj) => {
    window.__KOL__ = window.__KOL__ || [];
    const i = window.__KOL__.indexOf(dj);
    if (i >= 0) window.__KOL__.splice(i, 1); else window.__KOL__.push(dj);
    return echo({w_kolekcji: i < 0, dj});
  },

  /* Edycja setu (01.09). Podgląd MUSI tu udawać stan, bo inaczej po
     kliknięciu „podmień" tabela wróciłaby niezmieniona i obraz nie
     powiedziałby nic o tym, czy funkcja działa. Kandydaci to utwory
     z biblioteki spoza setu — kolejność i oceny są ZMYŚLONE i tylko
     do oglądania układu; prawdziwe liczy `slot_suggest` w Pythonie. */
  /* Kandydaci liczą się w wątku (~4 s na pełnej puli), więc most oddaje
     najpierw {ruszylo}, a wynik idzie przez postep_kandydatow — podgląd
     musi udawać obie fazy, inaczej nie sprawdza tej drogi wcale. */
  kandydaci: (poz, tryb, cel) => {
    window.__KAND__ = {stan: 'trwa'};
    setTimeout(() => { window.__KAND__ = {stan: 'gotowe',
      ...window.__LICZ__(poz, tryb, cel)}; }, 450);
    return echo({ruszylo: true});
  },
  postep_kandydatow: () => echo(window.__KAND__ || {stan: 'bezczynny'}),
  zamknij_kandydatow: () => echo({zamkniete: true}),

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
