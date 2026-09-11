/* Zgłoś błąd prosto z okna (⌘⇧B albo przycisk „Zgłoś" w pasku u góry).
 *
 * Kolejność ma znaczenie: stan ekranu i zrzut okna są brane W CHWILI
 * naciśnięcia, zanim otworzy się okienko — inaczej zrzut pokazywałby
 * okienko zgłoszenia, a nie problem. Tester dopisuje jedno zdanie i wagę;
 * resztę (ekran, utwór, set, notki silnika, pasek odtwarzacza, ostatnie
 * błędy konsoli, commit) zgłoszenie ma samo. Zapis idzie do
 * ~/.dancelab/zgloszenia/ (gui/zgloszenia.py), nie do publicznego repo.
 *
 * Skrypt ładuje się PRZED app.js: łapie błędy konsoli od pierwszej linii,
 * a ⌘⇧B przechwytuje w fazie capture — app.js buduje set na samo „B".
 */
(function () {
  'use strict';
  const bledy = [];
  const zapamietaj = t => {
    bledy.push(`${new Date().toTimeString().slice(0, 8)} ${String(t).slice(0, 500)}`);
    if (bledy.length > 40) bledy.shift();
  };
  const oryginalny = console.error.bind(console);
  console.error = (...a) => {
    try { zapamietaj(a.map(x => (x && x.stack) ? x.stack : String(x)).join(' ')); } catch (e) { /* nic */ }
    oryginalny(...a);
  };
  window.addEventListener('error', e =>
    zapamietaj(`${e.message} @ ${String(e.filename || '').split('/').pop()}:${e.lineno}`));
  window.addEventListener('unhandledrejection', e =>
    zapamietaj('Promise: ' + String(e.reason && (e.reason.message || e.reason))));

  const api = () => window.pywebview && window.pywebview.api;
  const tekst = sel => {
    const el = document.querySelector(sel);
    return el ? el.textContent.trim().replace(/\s+/g, ' ').slice(0, 300) : null;
  };

  function stanOkna() {
    let s = {};
    try { if (typeof stan !== 'undefined') s = stan; } catch (e) { /* app.js jeszcze nie wstał */ }
    const ekran = document.querySelector('nav button[aria-pressed="true"]');
    const g = s.gra || null;
    return {
      ekran: document.documentElement.dataset.ekran || (ekran && ekran.textContent.trim()) || null,
      track_id: s.trackId || null,
      tytul: tekst('#tytul'),
      odtwarzanie: g ? {gra: !!g.gra, pozycja_sec: g.pozycja_sec ?? null, rodzaj: g.rodzaj || null,
                        track_id: g.track_id || null, skad: g.skad || null} : null,
      opis_gry: tekst('#opis-gry'),
      set: Array.isArray(s.set) ? s.set.slice(0, 80).map(u => ({track_id: u.track_id, tytul: u.tytul})) : [],
      pozycja_w_secie: s.pozycja ?? null,
      notki: [...document.querySelectorAll('#notki-box div:not(.glowa)')]
        .map(d => d.textContent.trim()).filter(Boolean).slice(0, 20),
      licznik: tekst('#licznik'),
      okno: {w: window.innerWidth, h: window.innerHeight},
      bledy_konsoli: bledy.slice(),
    };
  }

  let otwarte = false, stanZChwili = null, tlo = null;

  async function otworz() {
    if (otwarte || !api()) return;
    otwarte = true;
    stanZChwili = stanOkna();
    let zrzut;
    try { zrzut = await api().zrzut_do_zgloszenia(); }
    catch (e) { zrzut = {ok: false, blad_zrzutu: String((e && e.message) || e)}; }
    pokaz(zrzut || {});
  }

  function pokaz(zrzut) {
    tlo = document.createElement('div');
    tlo.className = 'zgl-tlo';
    const info = zrzut.ok
      ? 'Zrzut okna i stan ekranu z chwili naciśnięcia są już zapisane. Napisz jednym zdaniem, co się stało.'
      : `Zrzutu okna nie udało się zrobić (${zrzut.blad_zrzutu || 'brak powodu'}). Stan ekranu jest zapisany — zgłoszenie pójdzie bez obrazka.`;
    tlo.innerHTML = `
      <div class="zgl-okno" role="dialog" aria-modal="true" aria-labelledby="zgl-tytul">
        <h3 id="zgl-tytul">Zgłoś błąd</h3>
        <p class="zgl-info"></p>
        <label>Co się stało
          <textarea id="zgl-opis" rows="4"
            placeholder="np. po skoku strzałką strumień gra dalej zamiast się zatrzymać"></textarea></label>
        <label>Waga
          <select id="zgl-waga">
            <option value="blokujacy">blokujący — nie da się pracować</option>
            <option value="powazny" selected>poważny — działa źle</option>
            <option value="drobny">drobny — wygląd, tekst</option>
          </select></label>
        <p class="zgl-blad" hidden></p>
        <div class="zgl-akcje">
          <button type="button" class="btn" data-zgl="anuluj">Anuluj</button>
          <button type="button" class="btn glowny" data-zgl="zapisz">Zapisz zgłoszenie <kbd>⌘↵</kbd></button>
        </div>
      </div>`;
    tlo.querySelector('.zgl-info').textContent = info;
    document.body.appendChild(tlo);
    tlo.querySelector('#zgl-opis').focus();
    tlo.addEventListener('click', e => {
      const b = e.target.closest('[data-zgl]');
      if (b && b.dataset.zgl === 'anuluj') zamknij(true);
      else if (b && b.dataset.zgl === 'zapisz') zapisz();
      else if (e.target === tlo) zamknij(true);
    });
  }

  async function zapisz() {
    const opis = tlo.querySelector('#zgl-opis').value;
    const waga = tlo.querySelector('#zgl-waga').value;
    const blad = tlo.querySelector('.zgl-blad');
    const przycisk = tlo.querySelector('[data-zgl="zapisz"]');
    przycisk.disabled = true;
    let odp;
    try { odp = await api().zapisz_zgloszenie(opis, waga, stanZChwili); }
    catch (e) { odp = {blad: String((e && e.message) || e)}; }
    przycisk.disabled = false;
    if (!odp || odp.blad) {
      blad.hidden = false;
      blad.textContent = (odp && odp.blad) || 'zapis nie wyszedł';
      tlo.querySelector('#zgl-opis').focus();
      return;
    }
    zamknij(false);
    komunikat(`Zgłoszenie ${odp.id} zapisane${odp.zrzut ? ' ze zrzutem okna' : ''} — ${odp.sciezka}`);
  }

  function zamknij(porzuc) {
    if (porzuc && api()) api().porzuc_zgloszenie();
    if (tlo) tlo.remove();
    tlo = null;
    otwarte = false;
    stanZChwili = null;
  }

  function komunikat(t) {
    const el = document.createElement('div');
    el.className = 'zgl-toast';
    el.setAttribute('role', 'status');
    el.textContent = t;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 7000);
  }

  // capture: przed skrótami app.js (tam samo „B" buduje set)
  window.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'b' || e.key === 'B')) {
      e.preventDefault(); e.stopImmediatePropagation(); otworz(); return;
    }
    if (!otwarte) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); zamknij(true); return; }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); e.stopImmediatePropagation(); zapisz(); return; }
    // w otwartym okienku żaden skrót aplikacji nie ma prawa zadziałać
    e.stopImmediatePropagation();
  }, true);

  function dodajPrzycisk() {
    const prawa = document.querySelector('.stan .prawa');
    if (!prawa || prawa.querySelector('.btn-zglos')) return;
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn-zglos';
    b.title = 'Zgłoś błąd — zrzut okna, stan ekranu i Twój opis (⌘⇧B)';
    b.textContent = 'Zgłoś';
    b.addEventListener('click', otworz);
    prawa.prepend(b);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', dodajPrzycisk);
  else dodajPrzycisk();

  window.zgloszenie = {otworz, stanOkna};
})();
