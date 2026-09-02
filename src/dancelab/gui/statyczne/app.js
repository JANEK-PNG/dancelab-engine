/* Ekran SEAM/CUE. Cała logika muzyczna siedzi w Pythonie (dancelab.stan) —
   ten plik rysuje i przekazuje zdarzenia. Gdyby zaczął cokolwiek liczyć,
   terminal i okno zaczęłyby pokazywać co innego. */
'use strict';

const $ = s => document.querySelector(s);
const api = () => window.pywebview && window.pywebview.api;

const KOLORY_SEKCJI = {
  intro: '#5aa9e6', build: '#e0a458', drop: '#9ede73',
  breakdown: '#8a94a2', outro: '#5e6773',
};
const NAZWY_PADOW = ['A', 'B', 'C', 'D'];

let stan = {
  trackId: null, przebieg: null, pady: {}, wybrany: null, bpm: null,
  ostatniBlad: null, spis: [], filtr: '',
  // biblioteka: filtrowanie robi Python, tu trzymamy tylko wynik i ustawienia
  widoczne: [], znalezione: 0, wszystkich: 0,
  tylkoUlubione: false, sortowanie: '', sekcja: '', okladki: false,
  // Filary AKTYWNEJ PLAYLISTY: obiekty {track_id, rola, tytul} do panelu.
  filaryPlaylisty: [], role: {},
  djGrupy: null, djKolekcja: [], djFiltr: 'wszyscy', rbDozwolony: null,
  // ekran Set: zaznaczona pozycja, wiersze setu, otwarty panel kandydatów.
  // `filarySetu` to SAME identyfikatory użyte przy budowie — inny kształt
  // niż panel, i do 02.09 oba siedziały pod jednym kluczem `filary`
  // (zdublowanym w tym literale): po każdym ruchu w panelu kolumna FILAR
  // w tabeli setu gasła, bo `Set` z obiektów nie zawiera napisu.
  set: [], filarySetu: [], pozycja: null, ostatniSet: null,
  kandydaci: null, kandCel: null, kandTryb: 'smart', kandWybor: null,
  // co gra: {gra, pozycja_sec, dlugosc_sec, rodzaj, track_id, opis, skad}
  gra: {gra: false, pozycja_sec: 0},
};

/* ---------- pomocnicze ---------- */
const mmss = ms => {
  const s = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
};
function pokazBlad(gdzie, tekst) {
  stan.ostatniBlad = tekst;
  const a = $('#kontekst');
  a.innerHTML = `<h2>Coś nie zadziałało</h2>
    <div class="powod zle"><b>${gdzie}</b><br>${tekst}</div>`;
}
function czyBlad(odp, gdzie) {
  if (odp && odp.blad) { pokazBlad(gdzie, odp.blad); return true; }
  return false;
}

/* ---------- rysowanie fali ---------- */
function rysujFale() {
  const c = $('#fala'), p = stan.przebieg;
  if (!p) return;
  const dpr = window.devicePixelRatio || 1;
  const w = c.clientWidth, h = c.clientHeight;
  c.width = w * dpr; c.height = h * dpr;
  const g = c.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);

  // siatka taktów — pod falą, żeby jej nie zasłaniać
  g.strokeStyle = 'rgba(36,42,50,.9)'; g.lineWidth = 1;
  (p.takty_sec || []).forEach((t, i) => {
    const x = Math.round(t / p.dlugosc_sec * w) + .5;
    g.globalAlpha = i % 4 === 0 ? 1 : .45;
    g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke();
  });
  g.globalAlpha = 1;

  // fala: lustrzana względem środka
  const n = p.obwiednia.length, srodek = h / 2;
  for (let i = 0; i < n; i++) {
    const x = i / n * w, sz = Math.max(1, w / n);
    const a = p.obwiednia[i] * (h / 2 - 3);
    // brak pomiaru rysowany INACZEJ niż cisza — ADR-005
    g.fillStyle = p.ma_dane[i] ? 'rgba(90,169,230,.62)' : 'rgba(94,103,115,.30)';
    if (!p.ma_dane[i]) { g.fillRect(x, srodek - 1, sz, 2); continue; }
    g.fillRect(x, srodek - a, sz, a * 2);
  }
}

function rysujSekcje() {
  const el = $('#pas-sekcji'), p = stan.przebieg;
  el.innerHTML = '';
  if (!p || !p.sekcje.length) return;
  p.sekcje.forEach(s => {
    const d = document.createElement('div');
    d.className = 'sek';
    d.style.flex = String(Math.max(.001, (s.do - s.od) / p.dlugosc_sec));
    d.style.background = KOLORY_SEKCJI[s.typ] || '#3a434e';
    d.textContent = s.nazwa;
    d.title = `${s.nazwa} · ${mmss(s.od * 1000)}–${mmss(s.do * 1000)}`;
    el.appendChild(d);
  });
}

function rysujPady() {
  const w = $('#pady'), p = stan.przebieg;
  w.innerHTML = '';
  if (!p) return;
  Object.entries(stan.pady || {}).forEach(([nazwa, dane]) => {
    const ms = dane && (dane.position_ms ?? dane);
    if (typeof ms !== 'number') return;
    const d = document.createElement('div');
    d.className = 'pad' + (stan.wybrany === nazwa ? ' wybrany' : '');
    d.style.left = (ms / 1000 / p.dlugosc_sec * 100) + '%';
    d.dataset.pad = nazwa;
    d.title = `pad ${nazwa} · ${mmss(ms)}`;
    d.addEventListener('mousedown', e => { e.stopPropagation(); zaznacz(nazwa); });
    w.appendChild(d);
  });
}

function rysujOs() {
  const p = stan.przebieg, el = $('#os-czasu');
  el.innerHTML = '';
  if (!p) return;
  for (let i = 0; i <= 6; i++) {
    const s = document.createElement('span');
    s.textContent = mmss(p.dlugosc_sec * 1000 * i / 6);
    el.appendChild(s);
  }
}

function rysujListe() {
  const el = $('#lista-padow');
  const wpisy = Object.entries(stan.pady || {});
  if (!wpisy.length) {
    el.innerHTML = '<div class="pusto">Brak padów — kliknij falę, żeby postawić pierwszy.</div>';
    return;
  }
  el.innerHTML = `<table><thead><tr>
      <th style="width:44px">pad</th><th style="width:70px">czas</th>
      <th style="width:80px">uderzenie</th><th>skąd</th>
    </tr></thead><tbody>${
    wpisy.map(([n, d]) => {
      const ms = d && (d.position_ms ?? d);
      const ud = stan.bpm ? Math.round(ms / 1000 / (60 / stan.bpm)) : '—';
      const skad = (d && d.zrodlo) || (d && d.reczne ? 'ręcznie' : 'silnik');
      return `<tr data-pad="${n}" ${stan.wybrany === n ? 'aria-selected="true"' : ''}>
        <td>${n}</td><td class="num czas-pada" data-czas="${n}" title="klik albo T: wpisz czas">${mmss(ms)}</td>
        <td class="num">${ud}</td><td style="color:var(--cichszy)">${skad}</td></tr>`;
    }).join('')}</tbody></table>`;
  el.querySelectorAll('tr[data-pad]').forEach(tr =>
    tr.addEventListener('click', () => zaznacz(tr.dataset.pad)));
  el.querySelectorAll('td[data-czas]').forEach(td =>
    td.addEventListener('click', e => {
      if (stan.wybrany === td.dataset.czas) { e.stopPropagation(); edytujCzasPada(); }
    }));
  rysujFrazy();
}

/* ---------- precyzja cue: T (czas), A–D (litera), frazy ----------
   Wszystko z terminala (09.08). Kwantyzacja do taktu jest ZAWSZE — pad
   ląduje na czerwonej linii Rekordboxa, jeśli ją znamy; powód wraca słowami. */

function cueNotka(tekst, zle) {
  const el = $('#cue-notka');
  el.textContent = tekst || '';
  el.classList.toggle('zle', !!zle);
}

function edytujCzasPada() {
  if (!stan.wybrany || !stan.pady[stan.wybrany]) return;
  const td = $(`td[data-czas="${stan.wybrany}"]`);
  if (!td || td.querySelector('input')) return;
  const d = stan.pady[stan.wybrany];
  const pole = document.createElement('input');
  pole.value = mmss(d.position_ms ?? d);
  pole.style.width = '62px';
  td.textContent = '';
  td.appendChild(pole);
  pole.focus(); pole.select();
  const zostaw = () => rysujListe();
  pole.addEventListener('keydown', async e => {
    e.stopPropagation();                        // litery nie są skrótami w polu
    if (e.key === 'Escape') { zostaw(); return; }
    if (e.key !== 'Enter') return;
    const odp = await api().ustaw_czas_pada(stan.trackId, stan.wybrany, pole.value);
    if (odp && odp.blad) { cueNotka(odp.blad, true); zostaw(); return; }
    stan.pady = odp.pady || {}; przerysuj(); odloz();
    cueNotka(odp.powod);
  });
  pole.addEventListener('blur', zostaw);
}

async function literaPada(n) {
  if (!api() || !stan.trackId) return;
  if (!(n in (stan.pady || {}))) {
    // brak pada: nowy, ręczny — na głowicy, gdy gra TEN utwór; inaczej w środku
    const g = stan.gra || {};
    const naTym = g.gra && g.rodzaj === 'utwor' && g.track_id === stan.trackId;
    const ms = Math.round((naTym ? g.pozycja_sec : (stan.przebieg.dlugosc_sec / 2)) * 1000);
    const odp = await api().postaw_pad(stan.trackId, n, ms);
    if (czyBlad(odp, 'Stawianie pada')) return;
    stan.pady = odp.pady || {}; stan.wybrany = n; przerysuj(); odloz();
    return;
  }
  if (stan.wybrany !== n) { zaznacz(n); return; }         // pierwsze: wybór
  // drugie naciśnięcie tej samej litery: PRZENIEŚ do głowicy (Z cofa)
  const odp = await api().przenies_pad_na_glowice(stan.trackId, n);
  if (odp && odp.blad) { cueNotka(odp.blad, true); return; }
  stan.pady = odp.pady || {}; przerysuj(); odloz();
  cueNotka(`${odp.powod} · ⌘Z cofa`);
}

async function rysujFrazy() {
  const el = $('#frazy');
  const d = stan.wybrany && stan.pady[stan.wybrany];
  if (!d || !api()) { el.hidden = true; return; }
  const odp = await api().propozycje(stan.trackId, d.silnik_ms ?? null);
  const lista = (odp && odp.propozycje) || [];
  if (!lista.length) { el.hidden = true; return; }
  el.hidden = false;
  el.innerHTML = 'frazy: ' + lista.map(p =>
    `<button class="btn maly" data-fraza="${p.sec}" title="przenieś pad ${stan.wybrany} tutaj">${
      p.nazwa.replace(/</g, '&lt;')} ${mmss(p.sec * 1000)}</button>`).join(' ');
  el.querySelectorAll('button[data-fraza]').forEach(b =>
    b.addEventListener('click', async () => {
      const odp = await api().ustaw_czas_pada(stan.trackId, stan.wybrany, b.dataset.fraza);
      if (odp && odp.blad) { cueNotka(odp.blad, true); return; }
      stan.pady = odp.pady || {}; przerysuj(); odloz();
      cueNotka(odp.powod);
    }));
}

/* ---------- gatunki (Ctrl+G) i szkic z filarów (G) ---------- */
let odpytywanieGatunkow = null;

async function przelaczGatunki() {
  const box = $('#gatunki-box');
  if (!box.hidden) { box.hidden = true; clearInterval(odpytywanieGatunkow); return; }
  box.hidden = false;
  $('#tabela-gatunkow').innerHTML = '<div class="pusto">liczę gatunki w puli…</div>';
  const odp = await api().gatunki($('#p-gatunki').value);
  if (odp && odp.ruszylo) {
    clearInterval(odpytywanieGatunkow);
    odpytywanieGatunkow = setInterval(async () => {
      const s = await api().postep_gatunkow();
      if (!s || s.stan === 'trwa' || s.stan === 'bezczynny') return;
      clearInterval(odpytywanieGatunkow);
      rysujGatunki(s);
    }, 400);
    return;
  }
  rysujGatunki(odp);
}

function rysujGatunki(odp) {
  const el = $('#tabela-gatunkow');
  if (!odp || odp.blad) {
    el.innerHTML = `<div class="pusto">${(odp && odp.blad) || 'gatunków nie policzyłem'}</div>`;
    return;
  }
  $('#gatunki-tytul').textContent =
    `Gatunki — masz ${odp.mam} z ${odp.wszystkich} Beatportu` +
    (odp.bez_tagu ? ` · ${odp.bez_tagu} bez tagu` : '');
  el.innerHTML = odp.sekcje.map(s => `
    <div class="dj-grupa"><div class="dj-glowa">${s.sekcja.replace(/</g, '&lt;')}</div>
    ${s.gatunki.map(g => `
      <div class="dj-karta" data-gatunek="${g.nazwa.replace(/"/g, '&quot;')}">
        <b>${g.wybrany ? '✓ ' : ''}${g.nazwa.replace(/</g, '&lt;')}</b>
        <span class="drobne">${g.ile}</span></div>`).join('')}
    </div>`).join('');
  el.querySelectorAll('[data-gatunek]').forEach(k =>
    k.addEventListener('click', async () => {
      const odp2 = await api().przelacz_gatunek($('#p-gatunki').value, k.dataset.gatunek);
      if (czyBlad(odp2, 'Gatunki')) return;
      $('#p-gatunki').value = odp2.wybrane;
      rysujNotki([`gatunki: ${odp2.wybrane || '(puste — bez filtra)'}`]);
      rysujGatunki(await api().gatunki(odp2.wybrane));      // ✓ na żywo, lista zostaje
    }));
}

async function szkicZFilarow() {
  if (!api()) return;
  const odp = await api().szkic_z_filarow({
    minuty: $('#p-minuty').value, tempo_okno: $('#p-tempo').value,
    dj: $('#p-dj').value.trim(), luk: $('#p-luk').value, planer: $('#p-planer').value,
  });
  if (odp && odp.blad) { rysujNotki([`ODMOWA: ${odp.blad}`, ...(odp.notki || [])]); return; }
  stan.pozycja = null;
  stan.ostatniSet = null;                                  // szkic to nie wynik budowy
  rysujTabeleSetu(odp.utwory, odp.filary);
  rysujKrzywa(odp.utwory);
  rysujNotki(odp.notki || []);
  kontekstSet(null);
  odswiezZapis();
}

function rysujKontekst() {
  const a = $('#kontekst'), p = stan.przebieg;
  if (!p) { a.innerHTML = '<div class="pusto">wczytuję…</div>'; return; }
  const ile = Object.keys(stan.pady || {}).length;
  const bezDanych = p.ma_dane.filter(x => !x).length;
  a.innerHTML = `<h2>Utwór</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="pole"><div class="et">długość</div>
        <div class="wa duza">${mmss(p.dlugosc_sec * 1000)}</div></div>
      <div class="pole"><div class="et">tempo</div>
        <div class="wa duza">${p.bpm ? p.bpm.toFixed(1) : '—'}</div></div>
    </div>
    <div class="rozdziel"></div>
    <div class="pole"><div class="et">pady</div><div class="wa">${ile} z 4</div></div>
    <div class="pole"><div class="et">sekcje</div>
      <div class="wa">${p.sekcje.map(s => s.nazwa).join(' · ') || '—'}</div></div>
    ${bezDanych ? `<div class="powod"><b>Miejsca bez pomiaru:</b>
      ${bezDanych} z ${p.ma_dane.length} punktów fali. Rysuję je szarą kreską,
      nie ciszą — to dwie różne rzeczy.</div>` : ''}`;
}

function przerysuj() {
  rysujSekcje(); rysujFale(); rysujPady(); rysujOs(); rysujListe(); rysujKontekst();
  rysujGrajka();
}

/* ---------- działania (każde idzie do Pythona) ---------- */
function zaznacz(nazwa) { stan.wybrany = nazwa; rysujPady(); rysujListe(); cueNotka(''); }

function wolnyPad() {
  return NAZWY_PADOW.find(n => !(n in (stan.pady || {})));
}

async function odloz() {
  // Po każdej zmianie, nie na zamknięciu okna: zamknięcie bywa nagłe,
  // a edycje mają przeżyć także wtedy. Odpowiedź CZYTAMY: odrzucony zapis
  // (zły `cwd`, katalog bez prawa zapisu) wyglądał jak sukces, a pady
  // znikały razem z oknem.
  if (!api()) return;
  czyBlad(await api().zapisz_edycje(), 'Zapis edycji na dysk');
}

async function postawZKlikniecia(ev) {
  if (!stan.przebieg || !api()) return;
  const r = $('#fala-obszar').getBoundingClientRect();
  const ulamek = Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width));
  const ms = Math.round(ulamek * stan.przebieg.dlugosc_sec * 1000);
  const pad = stan.wybrany || wolnyPad();
  if (!pad) { pokazBlad('Pady', 'Wszystkie cztery pady zajęte — zdejmij któryś (⌫).'); return; }
  const odp = await api().postaw_pad(stan.trackId, pad, ms);
  if (czyBlad(odp, 'Stawianie pada')) return;
  stan.pady = odp.pady || {}; stan.wybrany = pad; przerysuj(); odloz();
}

async function przesun(uderzenia) {
  if (!stan.wybrany || !api()) return;
  const odp = await api().przesun_pad(stan.trackId, stan.wybrany, uderzenia,
                                      stan.bpm || 128);
  if (czyBlad(odp, 'Przesuwanie pada')) return;
  stan.pady = odp.pady || {}; przerysuj(); odloz();
}

async function zdejmij() {
  if (!stan.wybrany || !api()) return;
  const odp = await api().zdejmij_pad(stan.trackId, stan.wybrany);
  if (czyBlad(odp, 'Zdejmowanie pada')) return;
  stan.pady = odp.pady || {}; stan.wybrany = null; przerysuj(); odloz();
}

async function cofnij() {
  if (!api()) return;
  const odp = await api().cofnij(stan.trackId);
  if (czyBlad(odp, 'Cofanie')) return;
  stan.pady = odp.pady || {}; przerysuj(); odloz();
}

async function odswiezStanRb() {
  if (!api()) return;
  const s = await api().stan_rekordboxa();
  const el = $('#stan-rb');
  if (s.blad) { el.innerHTML = `<span class="kropka zle"></span> ${s.blad}`; return; }
  el.innerHTML = `<span class="kropka ${s.zapis_dozwolony ? 'ok' : 'zle'}"></span> ${s.powod}`;

  // Zamknięcie Rekordboxa musi ODBLOKOWAĆ przyciski zapisu, a nie tylko
  // zmienić kropkę u góry. Bez tego DJ zamykał Rekordboxa, widział „zapis
  // dostępny" i dalej miał wyszarzony guzik playlisty — wyglądało to tak,
  // jakby playlista się nie oddawała.
  if (stan.rbDozwolony !== s.zapis_dozwolony) {
    stan.rbDozwolony = s.zapis_dozwolony;
    if (!$('#ekran-set').hidden) odswiezZapis();
  }
}

/* ---------- lista utworów ---------- */
let szukanieWToku = null;

/* Filtrowanie robi PYTHON, nie przeglądarka: te same reguły co w terminalu
   (okno tempa odrzuca utwory bez tempa, tonacja dokładna, fraza po tytule,
   wykonawcy i gatunku). Filtrowanie tutaj rozjechałoby obie skóry. */
function odswiezSpis() {
  clearTimeout(szukanieWToku);
  szukanieWToku = setTimeout(async () => {
    if (!api()) return;
    const odp = await api().szukaj(
      stan.filtr, $('#filtr-ton').value, $('#filtr-bpm').value,
      false, stan.sortowanie, 400, stan.sekcja);
    if (odp.blad) {
      $('#licznik').innerHTML = `<span class="ostroznie">${odp.blad}</span>`;
      return;
    }
    stan.widoczne = odp.utwory || [];
    stan.znalezione = odp.znalezione;
    stan.wszystkich = odp.wszystkich;
    rysujSpis();
  }, 160);
}

function rysujSpis() {
  const el = $('#spis');
  const widoczne = stan.widoczne || [];
  const filtrowane = stan.znalezione !== stan.wszystkich || !!stan.sekcja;
  $('#licznik').textContent = filtrowane
    ? `${stan.znalezione} z ${stan.wszystkich}`
    : `${stan.wszystkich} utworów`;

  if (!widoczne.length) {
    el.innerHTML = '<div class="pusto">nic nie pasuje</div>';
    return;
  }
  el.innerHTML = widoczne.map(u => {
    const znaki = (u.ulubiony ? '<span class="znak-ulub">♥</span>' : '')
                + (u.filar ? '<span class="znak-filar">⚑</span>' : '')
                // 7935 z 8261 utworów to strumienie bez pliku — DJ ma to
                // wiedzieć z listy, a nie dopiero po naciśnięciu P
                + (u.grywalny === false
                   ? '<span class="nagra" title="strumień — bez pliku na dysku, nie zagrasz tu">STR</span>'
                   : '');
    return `
    <div class="utwor" data-id="${u.track_id}"
         ${stan.trackId === u.track_id ? 'aria-selected="true"' : ''}>
      ${stan.okladki ? `<img class="okl" data-okl="${u.track_id}" alt="">` : ''}
      <div class="tresc">
      <div class="t">${(u.tytul || u.track_id).replace(/</g, '&lt;')}
        <span class="znaki">${znaki}</span></div>
      <div class="d">${u.bpm ? u.bpm.toFixed(1) : '—'} · ${u.tonacja || '—'}${
        u.tonacja_zrodlo === 'rekordbox' ? ' RB' : ''}</div>
      </div>
    </div>`;
  }).join('') +
    (stan.znalezione > widoczne.length
      ? `<div class="pusto">…i ${stan.znalezione - widoczne.length} dalszych — zawęź szukaniem</div>`
      : '');

  el.querySelectorAll('.utwor').forEach(d =>
    d.addEventListener('click', () => wybierzUtwor(d.dataset.id)));
  if (stan.okladki) dociagnijOkladkiWidoczne();
}

/* ---------- okładki (K) ----------
   Z tagów plików, jak mozaika w terminalu; brak = pusta kratka. Ładowane
   LENIWIE po jednej dla widocznych wierszy — lista ma do 400 pozycji, a
   data URI okładki waży dziesiątki kB. */
const okladkiCache = new Map();
let okladkiKolejka = 0;
async function okladkaDla(trackId) {
  if (okladkiCache.has(trackId)) return okladkiCache.get(trackId);
  const odp = await api().okladka(trackId);
  const dane = (odp && odp.dane) || null;
  okladkiCache.set(trackId, dane);
  return dane;
}
async function dociagnijOkladkiWidoczne() {
  const moja = ++okladkiKolejka;                 // nowa lista unieważnia starą pętlę
  for (const img of document.querySelectorAll('img.okl[data-okl]')) {
    if (moja !== okladkiKolejka) return;
    const dane = await okladkaDla(img.dataset.okl);
    if (dane) img.src = dane; else img.removeAttribute('src');
  }
}
async function przelaczOkladki() {
  const odp = await api().przelacz_okladki();
  if (czyBlad(odp, 'Okładki')) return;
  ustawOkladki(!!odp.wlaczone);
  rysujSpis();
}
function ustawOkladki(wlaczone) {
  stan.okladki = wlaczone;
  $('#btn-okladki').setAttribute('aria-pressed', String(wlaczone));
  $('#btn-dociagnij').hidden = !wlaczone;
}
async function rysujOkladkeGry() {
  const g = stan.gra || {}, img = $('#okladka-gry');
  const tid = g.rodzaj === 'utwor' ? g.track_id : null;
  if (!tid || !stan.okladki) { img.hidden = true; return; }
  const dane = await okladkaDla(tid);
  img.hidden = !dane; if (dane) img.src = dane;
}
let odpytywanieOkladek = null;
async function dociagnijOkladki() {
  const el = $('#skan-postep');
  const odp = await api().dociagnij_okladki();
  if (odp && odp.blad) { el.textContent = odp.blad; el.classList.add('zle'); return; }
  el.classList.remove('zle');
  $('#btn-dociagnij').disabled = true;
  clearInterval(odpytywanieOkladek);
  odpytywanieOkladek = setInterval(async () => {
    const s = await api().postep_okladek();
    if (s.stan === 'trwa') { el.textContent = s.etap || 'Artwork…'; return; }
    clearInterval(odpytywanieOkladek);
    $('#btn-dociagnij').disabled = false;
    if (s.stan !== 'gotowe') { el.textContent = s.blad || 'Artwork: nie wyszło'; el.classList.add('zle'); return; }
    el.textContent = `Artwork: osadzone ${s.osadzone} · niejednoznaczne ${s.niejednoznaczne} · ` +
      `nieznalezione ${s.nieznalezione} · błędy ${s.bledy} · miały już ${s.mialy_juz} — ${s.uwaga}`;
    okladkiCache.clear(); rysujSpis(); rysujOkladkeGry();
  }, 700);
}

/* ---------- ulubione i filary ---------- */

async function przelaczUlubiony() {
  if (!api() || !stan.trackId) return;
  const odp = await api().przelacz_ulubiony(stan.trackId);
  if (czyBlad(odp, 'Ulubione')) return;
  odswiezSpis();
}

async function przypnijFilar(rola) {
  if (!api() || !stan.trackId) return;
  const juz = (stan.widoczne || []).find(u => u.track_id === stan.trackId);
  const odp = juz && juz.filar
    ? await api().zdejmij_filar(stan.trackId)
    : await api().ustaw_filar(stan.trackId, rola || '');
  if (czyBlad(odp, 'Filary')) return;
  stan.filaryPlaylisty = odp.filary || [];
  rysujFilary();
  odswiezSpis();
}

function rysujFilary() {
  const lista = stan.filaryPlaylisty || [];
  $('#filary-licznik').textContent = lista.length
    ? `${lista.length} z 10`
    : '— brak, silnik ułoży set sam';
  const el = $('#filary-lista');
  if (!lista.length) {
    el.innerHTML = '<div class="pusto">Filar to utwór, który MUSI zagrać. '
      + 'Wybierz go na ekranie <b>1</b> (lista utworów) i naciśnij <b>F</b>.</div>';
    return;
  }
  const role = stan.role || {'': 'bez roli'};
  el.innerHTML = lista.map(f => `
    <div class="filar-wiersz" data-id="${f.track_id}">
      <span class="nazwa">${(f.tytul || f.track_id).replace(/</g, '&lt;')}</span>
      <select data-rola="${f.track_id}">${Object.entries(role).map(([k, opis]) =>
        `<option value="${k}" ${f.rola === k ? 'selected' : ''}>${opis}</option>`
      ).join('')}</select>
      <button class="zdejmij" data-zdejmij="${f.track_id}" title="zdejmij filar">✕</button>
    </div>`).join('');
  el.querySelectorAll('select[data-rola]').forEach(sel =>
    sel.addEventListener('change', async () => {
      const odp = await api().ustaw_filar(sel.dataset.rola, sel.value);
      if (czyBlad(odp, 'Rola filara')) return;
      stan.filaryPlaylisty = odp.filary || [];
      rysujFilary();
    }));
  el.querySelectorAll('button[data-zdejmij]').forEach(b =>
    b.addEventListener('click', async () => {
      const odp = await api().zdejmij_filar(b.dataset.zdejmij);
      if (czyBlad(odp, 'Filary')) return;
      stan.filaryPlaylisty = odp.filary || [];
      rysujFilary(); odswiezSpis();
    }));
}

async function odswiezPlaylisty() {
  if (!api()) return;
  const p = await api().playlisty();
  if (p.blad) return;
  stan.role = p.role;
  const sel = $('#wybor-playlisty');
  sel.innerHTML = (p.playlisty || []).length
    ? p.playlisty.map((pl, i) =>
        `<option value="${i}" ${p.aktywna === i ? 'selected' : ''}>${
          pl.nazwa.replace(/</g, '&lt;')} (${pl.filarow})</option>`).join('')
    : '<option value="">— brak playlist —</option>';
  document.querySelectorAll('#tryb-filarow button').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.tf === p.tryb_filarow)));
  const f = await api().filary();
  stan.filaryPlaylisty = f.filary || [];
  rysujFilary();
}

async function wybierzUtwor(trackId, opcje) {
  if (!api()) return;
  if (!(opcje && opcje.bezPodazania)) podazajZaKursorem(trackId);
  stan.trackId = trackId;
  $('#tytul').textContent = 'wczytuję…';
  const p = await api().wczytaj_utwor(trackId);
  if (czyBlad(p, 'Wczytywanie utworu')) { $('#tytul').textContent = 'nie wczytano'; return; }
  stan.przebieg = p;
  stan.bpm = p.bpm;
  stan.wybrany = null;
  $('#tytul').textContent = p.tytul || trackId;
  $('#podtytul').textContent =
    [p.wykonawca, p.bpm ? p.bpm.toFixed(1) + ' BPM' : null].filter(Boolean).join(' · ');
  const pd = await api().pady(trackId);
  stan.pady = (pd && pd.pady) || {};
  rysujSpis();
  przerysuj();
}

/* ---------- ekran Set ---------- */
let odpytywanie = null;

const EKRANY = {szew: 'szew', set: 'ekran-set', dj: 'ekran-dj'};

function pokazEkran(nazwa) {
  document.querySelectorAll('main > section').forEach(x =>
    x.hidden = x.id !== (EKRANY[nazwa] || 'szew'));
  document.querySelectorAll('#nawigacja button').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.ekran === nazwa)));
  /* Sam `display:none` na liście NIE wystarczy: siatka ma cztery kolumny,
     więc zniknięcie listy przesuwa główny obszar w jej wąską kolumnę, a panel
     kontekstu rozlewa się na resztę. Złapane na zrzucie — ekran Set ściskał
     się do 264 px z uciętą tabelą. Kolumny przełącza CSS po tym atrybucie. */
  document.documentElement.dataset.ekran = nazwa;
  // Skróty pod ręką muszą pasować do ekranu — inaczej pas na dole obiecuje
  // klawisze, które tu nic nie robią.
  $('#skroty-szew').hidden = nazwa !== 'szew';
  $('#skroty-set').hidden = nazwa !== 'set';
  if (nazwa !== 'set') zamknijKandydatow();
  if (nazwa === 'set') { kontekstSet(); odswiezZapis(); }
  if (nazwa === 'dj') rysujDjow();
  // guzik odsłuchu dotyczy INNEGO utworu na każdym ekranie — po przełączeniu
  // musi od razu wiedzieć, czy da się go zagrać
  rysujGrajka();
}

/* ---------- DJ-e: kotwice brzmienia ----------
   Grupy liczy Python (klastry centroidów z ich własnych setów). „Odważny"
   i „gładki" to mediana skoku między utworami — zmierzona, nie opisowa. */

async function rysujDjow() {
  if (!api()) return;
  const el = $('#dj-sciana');
  if (!stan.djGrupy) {
    el.innerHTML = '<div class="pusto">liczę grupy brzmieniowe…</div>';
    const odp = await api().djs();
    if (odp.blad) {
      el.innerHTML = `<div class="pusto">${odp.blad}</div>`;
      $('#dj-licznik').textContent = '';
      return;
    }
    stan.djGrupy = odp.grupy || [];
    stan.djKolekcja = odp.kolekcja || [];
    stan.mojeUlubione = odp.moje_ulubione;
    stan.ulubionychUtworow = odp.ulubionych_utworow;
  }
  const tylkoKolekcja = stan.djFiltr === 'kolekcja';
  const grupy = stan.djGrupy
    .map(g => ({...g, djs: tylkoKolekcja ? g.djs.filter(d => d.w_kolekcji) : g.djs}))
    .filter(g => g.djs.length);
  const ilu = grupy.reduce((n, g) => n + g.djs.length, 0);
  $('#dj-licznik').textContent =
    `${ilu} DJ-ów w ${grupy.length} grupach · w kolekcji ${stan.djKolekcja.length}`;

  // „moje ulubione" to kotwica policzona z Twoich ♥ — stoi osobno, bo nie
  // pochodzi z księgi, tylko z Twojej biblioteki
  let html = `<div class="dj-grupa"><div class="dj-glowa">— twoje brzmienie —</div>
    <div class="dj-karta" data-dj="${stan.mojeUlubione}">
      <b>${stan.mojeUlubione}</b>
      <span class="drobne">kotwica z Twoich ♥ (${stan.ulubionychUtworow} utworów)</span>
    </div></div>`;
  html += grupy.map(g => `
    <div class="dj-grupa">
      <div class="dj-glowa">${g.etykieta.replace(/</g, '&lt;')} · ${g.djs.length}</div>
      ${g.djs.map(d => `
        <div class="dj-karta" data-dj="${d.nazwa.replace(/"/g, '&quot;')}">
          <b>${d.nazwa.replace(/</g, '&lt;')}</b>
          <span class="drobne">${d.wektorow} wekt.${
            d.odwaga ? ' · ' + d.odwaga : ''}</span>
          <button class="kolekcja" data-kol="${d.nazwa.replace(/"/g, '&quot;')}"
            title="${d.w_kolekcji ? 'w kolekcji' : 'dodaj do kolekcji'}"
            >${d.w_kolekcji ? '✓' : '+'}</button>
        </div>`).join('')}
    </div>`).join('');
  el.innerHTML = html;

  el.querySelectorAll('.dj-karta').forEach(k =>
    k.addEventListener('click', () => {
      $('#p-dj').value = k.dataset.dj;      // kotwica idzie do briefu
      pokazEkran('set');
      rysujNotki([`kotwica ustawiona: ${k.dataset.dj} — teraz Buduj set`]);
    }));
  el.querySelectorAll('button.kolekcja').forEach(b =>
    b.addEventListener('click', async ev => {
      ev.stopPropagation();
      const odp = await api().przelacz_kolekcje_dj(b.dataset.kol);
      if (czyBlad(odp, 'Kolekcja DJ-ów')) return;
      stan.djGrupy = null;                  // przelicz z nowym ✓
      await rysujDjow();
    }));
}

function rysujNotki(notki, stanFilarow, zgloszone) {
  const box = $('#notki-box');
  const wpisy = [...(notki || [])];
  // Trzy stany filarów wymagają od użytkownika czegoś innego, więc mówimy
  // który zaszedł, zamiast milczeć albo pisać jedno na wszystkie.
  if (stanFilarow === 'wypadly')
    wpisy.unshift(`UWAGA: zaznaczyłeś ${zgloszone} filarów, ale żaden nie wszedł — ` +
                  'sprawdź okno tempa poniżej');
  else if (stanFilarow === 'brak')
    wpisy.push('set bez wymuszonych utworów (nie masz zaznaczonych filarów)');
  if (!wpisy.length) { box.hidden = true; return; }
  box.hidden = false;
  box.innerHTML = '<div class="glowa">co silnik zgłosił</div>' +
    wpisy.map(n => `<div class="${/UWAGA|ODMOWA|poza oknem/i.test(n) ? 'zle' : ''}">${
      String(n).replace(/</g, '&lt;')}</div>`).join('');
}

function rysujKrzywa(utwory) {
  const box = $('#krzywa-box');
  if (!utwory || utwory.length < 2) { box.hidden = true; return; }
  box.hidden = false;
  const sumaMin = utwory.reduce((a, u) => a + (u.dlugosc_sec || 0), 0) / 60;
  $('#krzywa-tytul').textContent =
    `Krzywa tempa · ${utwory.length} utworów · ${sumaMin.toFixed(0)} min`;
  const tempa = utwory.map(u => u.bpm || 0);
  const lo = Math.min(...tempa), hi = Math.max(...tempa);
  const zakres = (hi - lo) || 1;
  const pkt = tempa.map((t, i) => [
    i * (600 / Math.max(1, tempa.length - 1)),
    62 - ((t - lo) / zakres) * 50,
  ]);
  const d = pkt.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  $('#krzywa').innerHTML =
    `<path d="${d} L600 70 L0 70 Z" fill="rgba(224,164,88,.10)"/>
     <path d="${d}" fill="none" stroke="var(--bursztyn)" stroke-width="1.7"/>` +
    pkt.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="2.5"
       fill="var(--tlo)" stroke="var(--bursztyn)" stroke-width="1.5"/>`).join('');
}

function rysujTabeleSetu(utwory, filary) {
  const el = $('#tabela-set');
  stan.set = utwory || [];
  if (filary !== undefined) stan.filarySetu = filary || [];
  if (!utwory || !utwory.length) {
    el.innerHTML = '<div class="pusto">Silnik nie zbudował setu — powód wyżej.</div>';
    stan.pozycja = null;
    return;
  }
  if (stan.pozycja !== null && stan.pozycja >= utwory.length) {
    stan.pozycja = utwory.length - 1;
  }
  const zbior = new Set(stan.filarySetu);
  let suma = 0;
  el.innerHTML = `<table><thead><tr>
      <th style="width:34px">#</th><th style="width:54px">BPM</th>
      <th style="width:60px">ton</th><th style="width:56px">Σ min</th>
      <th>wykonawca</th><th>tytuł</th><th style="width:44px" title="czy da się posłuchać w oknie">gra</th><th style="width:70px">filar</th>
    </tr></thead><tbody>${utwory.map((u, i) => {
      suma += (u.dlugosc_sec || 0) / 60;
      // źródło tonacji jest częścią prawdy o niej — „RB" to niezależny sędzia
      const ton = u.tonacja
        ? `<span class="ton">${u.tonacja}</span>` +
          (u.tonacja_zrodlo === 'rekordbox' ? ' <span class="drobne">RB</span>' : '')
        : '<span class="pusto">—</span>';
      return `<tr data-poz="${i}" ${stan.pozycja === i ? 'aria-selected="true"' : ''}>
        <td class="num">${i + 1}</td>
        <td class="num">${u.bpm ? u.bpm.toFixed(1) : '—'}</td>
        <td>${ton}</td>
        <td class="num">${suma.toFixed(0)}</td>
        <td>${(u.wykonawca || '—').replace(/</g, '&lt;')}</td>
        <td>${(u.tytul || '').replace(/</g, '&lt;')}</td>
        <td class="nagra" title="${u.grywalny === false
          ? 'strumień — nie ma pliku na dysku' : 'ma plik — P zagra'}">${
          u.grywalny === false ? 'STR' : '♪'}</td>
        <td style="color:var(--bursztyn)">${zbior.has(u.track_id) ? 'FILAR' : ''}</td>
      </tr>`;
    }).join('')}</tbody></table>`;
  el.querySelectorAll('tr[data-poz]').forEach(tr =>
    tr.addEventListener('click', () => zaznaczPozycje(Number(tr.dataset.poz))));
}

/* ---------- edycja setu ----------
   Ten sam wzór dwóch kroków co w terminalu: zaznaczasz pozycję, klawisz
   otwiera panel kandydatów, dopiero potwierdzenie zmienia set. Wszystko
   liczy Python — tu tylko klikanie. */

function zaznaczPozycje(i, opcje) {
  stan.pozycja = i;
  rysujTabeleSetu(stan.set);
  const u = stan.set[i];
  if (u) $('#czas-kursora').textContent = `#${i + 1} ${u.tytul || ''}`.slice(0, 60);
  rysujGrajka();
  if (u && !(opcje && opcje.bezPodazania)) podazajZaKursorem(u.track_id);
}

function zamknijKandydatow() {
  clearInterval(odpytywanieKand);
  const bylOtwarty = !$('#kandydaci-box').hidden;
  stan.kandydaci = null; stan.kandCel = null; stan.kandWybor = null;
  $('#kandydaci-box').hidden = true;
  // Python też ma zapomnieć rangi zamkniętego panelu — inaczej późniejszy
  // wybór inną drogą odziedziczyłby ją w dzienniku.
  if (bylOtwarty && api() && api().zamknij_kandydatow) api().zamknij_kandydatow();
}

let odpytywanieKand = null;

async function otworzKandydatow(cel) {
  if (!api()) return;
  if (stan.pozycja === null) {
    rysujNotki(['zaznacz pozycję w secie — kliknij wiersz']);
    return;
  }
  stan.kandCel = cel;
  const box = $('#kandydaci-box');
  box.hidden = false;
  // Ocena 8 tysięcy kandydatów trwa około czterech sekund (pomiar 01.09),
  // więc Python liczy w wątku, a okno odpytuje — inaczej zamarza na ten czas.
  $('#tabela-kandydatow').innerHTML =
    '<div class="pusto">liczę kandydatów w tej szczelinie…</div>';
  const start = await api().kandydaci(stan.pozycja, stan.kandTryb, cel);
  if (czyBlad(start, 'Kandydaci')) { zamknijKandydatow(); return; }
  clearInterval(odpytywanieKand);
  odpytywanieKand = setInterval(async () => {
    const s = await api().postep_kandydatow();
    // „bezczynny" to NIE wynik, tylko brak startu — potraktowanie go jak
    // wyniku dawało puste liczby zamiast czekania.
    if (!s || s.stan === 'trwa' || s.stan === 'bezczynny') return;
    clearInterval(odpytywanieKand);
    if (czyBlad(s, 'Kandydaci')) { zamknijKandydatow(); return; }
    stan.kandydaci = s.kandydaci || [];
    stan.kandWybor = null;
    rysujKandydatow(s.uwaga);
  }, 300);
}

function rysujKandydatow(uwaga) {
  const el = $('#tabela-kandydatow');
  const poz = stan.pozycja === null ? '' : `#${stan.pozycja + 1}`;
  $('#kandydaci-tytul').textContent = stan.kandCel === 'podmiana'
    ? `Podmiana ${poz} — wybierz i potwierdź`
    : `Dopisanie za ${poz} — wybierz i potwierdź`;
  if (!stan.kandydaci || !stan.kandydaci.length) {
    el.innerHTML = `<div class="pusto">${uwaga || 'brak kandydatów'}</div>`;
    return;
  }
  el.innerHTML = `<table><thead><tr>
      <th style="width:30px">#</th><th style="width:54px">BPM</th>
      <th style="width:50px">ton</th><th style="width:52px">ocena</th>
      <th>utwór</th>
    </tr></thead><tbody>${stan.kandydaci.map((k, i) => `
      <tr data-kand="${i}" ${stan.kandWybor === i ? 'aria-selected="true"' : ''}>
        <td class="ranga">${k.ranga}</td>
        <td class="num">${k.bpm ? k.bpm.toFixed(1) : '—'}</td>
        <td>${k.tonacja || '—'}</td>
        <td class="wynik">${k.score.toFixed(2)}</td>
        <td>${(k.wykonawca ? k.wykonawca + ' — ' : '').replace(/</g, '&lt;')}${
          (k.tytul || '').replace(/</g, '&lt;')}
          <div class="why">${(k.why || '').replace(/</g, '&lt;')}</div></td>
      </tr>`).join('')}</tbody></table>`;
  el.querySelectorAll('tr[data-kand]').forEach(tr =>
    tr.addEventListener('click', () => {
      const i = Number(tr.dataset.kand);
      // pierwszy klik zaznacza, drugi w ten sam wiersz potwierdza
      if (stan.kandWybor === i) { potwierdzKandydata(); return; }
      stan.kandWybor = i;
      rysujKandydatow();
    }));
}

async function potwierdzKandydata() {
  if (!api() || stan.kandWybor === null) return;
  const k = stan.kandydaci[stan.kandWybor];
  const cel = stan.kandCel, poz = stan.pozycja;
  const odp = cel === 'podmiana'
    ? await api().podmien(poz, k.track_id)
    : await api().dopisz_utwor(poz, k.track_id);
  if (czyBlad(odp, cel === 'podmiana' ? 'Podmiana' : 'Dopisanie')) return;
  zamknijKandydatow();
  if (cel !== 'podmiana') stan.pozycja = poz + 1;
  poEdycjiSetu(odp, cel === 'podmiana'
    ? `PODMIANA #${poz + 1}: ${k.tytul || k.track_id}`
    : `DOPISANE #${poz + 2}: ${k.tytul || k.track_id}`);
}

async function wytnijPozycje() {
  if (!api() || stan.pozycja === null) return;
  const u = stan.set[stan.pozycja];
  const odp = await api().wytnij(stan.pozycja);
  if (czyBlad(odp, 'Wycięcie')) return;
  zamknijKandydatow();
  poEdycjiSetu(odp, `WYCIĘTE: ${u ? (u.tytul || u.track_id) : ''}`);
}

async function przesunPozycje(kierunek) {
  if (!api() || stan.pozycja === null) return;
  const odp = await api().przesun_utwor(stan.pozycja, kierunek);
  if (czyBlad(odp, 'Przesunięcie')) return;
  if (odp.na !== undefined) stan.pozycja = odp.na;
  poEdycjiSetu(odp, null);
}

function poEdycjiSetu(odp, komunikat) {
  rysujTabeleSetu(odp.utwory, odp.filary);
  rysujKrzywa(odp.utwory);
  const uwagi = [odp.uwaga, odp.dziennik, komunikat].filter(Boolean);
  if (uwagi.length) rysujNotki(uwagi);
  // Liczby po prawej muszą dotyczyć setu PO edycji — inaczej panel mówi
  // „8 utworów / 42 min" nad krzywą, która pokazuje już co innego.
  if (stan.ostatniSet) {
    stan.ostatniSet.utwory = odp.utwory;
    if (odp.filary) stan.ostatniSet.filary = odp.filary;
    kontekstSet(stan.ostatniSet);
  }
  if (stan.pozycja !== null && stan.set[stan.pozycja]) {
    const u = stan.set[stan.pozycja];
    $('#czas-kursora').textContent =
      `#${stan.pozycja + 1} ${u.tytul || ''}`.slice(0, 60);
  }
  // Kolejność się zmieniła, więc policzony plan zapisu przestał obowiązywać.
  odswiezZapis();
}

function kontekstSet(s) {
  const a = $('#kontekst');
  if (!s || s.stan !== 'gotowe') {
    a.innerHTML = `<h2>Budowa setu</h2>
      <div class="powod">Parametry na górze, wynik pod spodem. Plan zapisuje się
      sam i <b>widać go w terminalu</b> — obie skóry czytają ten sam plik.</div>`;
    return;
  }
  const min = s.utwory.reduce((x, u) => x + (u.dlugosc_sec || 0), 0) / 60;
  a.innerHTML = `<h2>Zbudowany set</h2>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
      <div class="pole"><div class="et">utworów</div>
        <div class="wa duza">${s.utwory.length}</div></div>
      <div class="pole"><div class="et">minut</div>
        <div class="wa duza">${min.toFixed(0)}</div></div>
    </div>
    <div class="rozdziel"></div>
    <div class="pole"><div class="et">kotwica</div>
      <div class="wa">${s.kotwica || '— bez kotwicy —'}</div></div>
    <div class="pole"><div class="et">filary</div>
      <div class="wa">${s.filary_stan === 'uzyte'
        ? `${s.filary.length} (tryb: ${s.tryb_filarow})`
        : s.filary_stan === 'wypadly' ? `${s.filary_zgloszone} wypadło` : 'brak'}</div></div>
    <div class="powod"><b>Plan zapisany.</b> Otwórz go w terminalu
      (<span class="mono">dancelab tui</span>, klawisz <b>o</b>) — to ten sam plik.</div>`;
}

async function budujSet() {
  if (!api()) return;
  const odp = await api().buduj_set({
    minuty: $('#p-minuty').value,
    tempo_okno: $('#p-tempo').value,
    dj: $('#p-dj').value.trim(),
    ziarno: $('#p-ziarno').value.trim(),
    zrodlo_puli: $('#p-pula').value,
    folder: $('#p-folder').value.trim(),
    style: $('#p-gatunki').value,
    luk: $('#p-luk').value,
    tempo: $('#p-tempo-plan').value,
    planer: $('#p-planer').value,
    nowosc: $('#p-nowosc').value,
    kontur: $('#p-kontur').checked,
  });
  if (odp && odp.blad) { rysujNotki([`ODMOWA: ${odp.blad}`]); return; }

  $('#postep-box').hidden = false;
  $('#btn-buduj').disabled = true;
  clearInterval(odpytywanie);
  odpytywanie = setInterval(async () => {
    const s = await api().postep_budowy();
    $('#postep-tekst').textContent = s.etap || '…';
    if (s.stan === 'trwa') return;
    clearInterval(odpytywanie);
    $('#postep-box').hidden = true;
    $('#btn-buduj').disabled = false;
    if (s.stan === 'gotowe') {
      // Ostatni wynik budowy zostaje: panel kontekstu po edycji setu musi
      // przeliczyć utwory i minuty, a kotwicę i filary bierze stąd.
      stan.ostatniSet = s;
      rysujNotki(s.notki, s.filary_stan, s.filary_zgloszone);
      rysujKrzywa(s.utwory);
      rysujTabeleSetu(s.utwory, s.filary);
      kontekstSet(s);
      odswiezZapis();
    } else {
      rysujNotki([`${s.stan === 'odmowa' ? 'ODMOWA' : 'BŁĄD'}: ${s.blad}`]);
      rysujTabeleSetu([]);
    }
  }, 500);
}

/* ---------- zapis do Rekordboksa ---------- */
/* Dwa stopnie i tak zostaje. Pierwszy tylko CZYTA bazę i pokazuje liczby,
   drugi dopiero pisze. Jednym kliknięciem nie wysyłamy nic do biblioteki. */

function liczba(etykieta, ile, klasa) {
  return `<span class="${klasa || ''}">${etykieta} <b>${ile}</b></span>`;
}

async function odswiezZapis() {
  const s = await api().zapis_stan();
  const box = $('#zapis-box'), boxPl = $('#playlista-box');
  if (!s || s.blad || !s.set) { box.hidden = true; boxPl.hidden = true; return; }
  box.hidden = false;
  // Playlista jest drugą, niezależną drogą na sprzęt — ma własne dwa stopnie.
  boxPl.hidden = false;
  $('#btn-pl-wyslij').hidden = !s.playlista_policzona;
  $('#btn-pl-policz').disabled = s.rekordbox_otwarty;
  $('#playlista-warunek').textContent = s.rekordbox_otwarty
    ? 'Rekordbox jest otwarty — zamknij go, żeby zapisać'
    : `${s.set} utworów w kolejności z ekranu`;
  // Powód blokady musi stać TAM, gdzie DJ patrzy, czyli przy liczbach —
  // drobny druk w nagłówku ginie i wygląda to jak zepsuty przycisk.
  if (s.rekordbox_otwarty) {
    $('#playlista-liczby').innerHTML = '<span class="ostroznie">Zamknij '
      + 'Rekordboxa — przy otwartym jego własny bufor nadpisałby zapis.</span>';
    $('#zapis-liczby').innerHTML = $('#zapis-liczby').innerHTML
      || '<span class="ostroznie">Zamknij Rekordboxa, żeby zapisać cue.</span>';
  } else {
    // blokada minęła — obie sekcje muszą przestać o niej mówić
    for (const id of ['#playlista-liczby', '#zapis-liczby']) {
      if ($(id).textContent.startsWith('Zamknij')) $(id).textContent = '';
    }
  }
  $('#btn-wyslij').hidden = !s.policzone;
  $('#btn-policz').disabled = s.rekordbox_otwarty;
  $('#zapis-warunek').textContent = s.rekordbox_otwarty
    ? 'Rekordbox jest otwarty — zamknij go, żeby zapisać'
    : (s.propozycje ? 'pady z silnika plus Twoje zmiany'
                    : 'silnik nie policzył propozycji — pójdą same Twoje pady');
}

async function policzZapis() {
  $('#btn-policz').disabled = true;
  $('#zapis-liczby').textContent = 'liczę plan i sprawdzam Twoje cue…';
  const w = await api().przygotuj_zapis_cue();
  $('#btn-policz').disabled = false;
  if (w.blad) {
    $('#zapis-liczby').innerHTML = `<span class="ostroznie">${w.blad}</span>`;
    $('#btn-wyslij').hidden = true;
    return;
  }
  const czesci = [
    liczba('padów do zapisu', w.do_zapisu),
    liczba('na utworach', w.utworow),
  ];
  if (w.odswiezone) czesci.push(liczba('odświeżamy po sobie', w.odswiezone));
  /* To zdanie musi paść zawsze, także przy zerze: DJ ma wiedzieć, że jego
     własne cue są nietykalne, a nie domyślać się tego z ciszy. */
  czesci.push(liczba('Twoich cue nie ruszam — nasze ustąpiły',
                     w.ustapilo_twoim, 'ostroznie'));
  if (w.spoza_kolekcji && w.spoza_kolekcji.length) {
    czesci.push(liczba('utworów spoza kolekcji RB',
                       w.spoza_kolekcji.length, 'ostroznie'));
  }
  $('#zapis-liczby').innerHTML = czesci.join('');
  $('#btn-wyslij').hidden = w.do_zapisu === 0;
}

/* ---------- info o utworze i porównanie pary ---------- */

async function pokazInfo() {
  if (!api() || !stan.trackId) return;
  const box = $('#info-box');
  if (!box.hidden) { box.hidden = true; return; }   // I zamyka, jak w terminalu
  box.hidden = false;
  $('#info-tekst').textContent = 'czytam metadane i master.db…';
  const odp = await api().info_utworu(stan.trackId);
  if (czyBlad(odp, 'Info o utworze')) { box.hidden = true; return; }
  $('#info-tekst').textContent = odp.tekst;
}

async function porownajPare() {
  if (!api()) return;
  const box = $('#szew-box');
  if (!box.hidden) { box.hidden = true; return; }
  if (stan.pozycja === null) {
    rysujNotki(['zaznacz pozycję w secie — porównanie dotyczy PARY']);
    return;
  }
  const odp = await api().porownaj_pare(stan.pozycja);
  if (czyBlad(odp, 'Porównanie pary')) return;
  box.hidden = false;
  const nazwa = u => [u.wykonawca, u.tytul].filter(Boolean).join(' — ').slice(0, 42);
  $('#szew-tytul').textContent =
    `Szew #${odp.pozycja + 1} ⇄ #${odp.pozycja + 2}`;
  // nieznane rysujemy jako kreskę, jak wszędzie — nie jako TypeError w konsoli
  const sek = x => (typeof x === 'number' ? mmss(x * 1000) : '—');
  $('#szew-info').innerHTML =
    `${nazwa(odp.a).replace(/</g, '&lt;')} → ${nazwa(odp.b).replace(/</g, '&lt;')}<br>` +
    `<b>${odp.uderzen ?? '—'}</b> uderzeń @ ${
      typeof odp.bpm === 'number' ? odp.bpm.toFixed(1) : '—'} BPM · ` +
    `wyjście z A ${sek(odp.cue_a_sec)} · wejście w B ${sek(odp.cue_b_sec)}` +
    ` <span class="ostroznie">— tu się patrzy; słucha się z Twoich padów</span>`;
}

/* ---------- zapisane plany ---------- */
/* Każda budowa zapisuje plan sama, ale do dziś okno nie miało jak do niego
   wrócić. Dopasowanie planu do puli robi Python i trwa (potrzebuje całej
   puli), więc tu odpytujemy — tak jak przy budowie i kandydatach. */

let odpytywaniePlanu = null;

async function otworzPlany() {
  if (!api()) return;
  const box = $('#plany-box');
  box.hidden = false;
  $('#tabela-planow').innerHTML = '<div class="pusto">czytam listę planów…</div>';
  const odp = await api().lista_planow();
  if (czyBlad(odp, 'Plany')) { box.hidden = true; return; }
  const plany = odp.plany || [];
  if (!plany.length) {
    $('#tabela-planow').innerHTML =
      '<div class="pusto">Nie ma zapisanych planów — zbuduj pierwszy set.</div>';
    return;
  }
  $('#tabela-planow').innerHTML = `<table><thead><tr>
      <th style="width:150px">zapisano</th><th style="width:44px">n</th>
      <th style="width:80px">BPM</th><th>nazwa</th>
    </tr></thead><tbody>${plany.map((p, i) => `
      <tr data-plan="${i}">
        <td class="num">${(p.zapisano || '?').replace(/</g, '&lt;')}</td>
        <td class="num">${p.n}</td>
        <td class="num">${p.bpm || '—'}</td>
        <td>${(p.nazwa || '').replace(/</g, '&lt;')}${
          p.biezacy ? ' <span class="drobne">— bieżący</span>' : ''}${
          p.dj ? ` <span class="drobne">jak ${p.dj}</span>` : ''}
          <button class="zdejmij" data-usun="${i}" title="do kosza (obok planów, nic nie znika)">✕</button></td>
      </tr>`).join('')}</tbody></table>`;
  $('#tabela-planow').querySelectorAll('tr[data-plan]').forEach(tr =>
    tr.addEventListener('click', () => wczytajPlan(plany[Number(tr.dataset.plan)])));
  $('#tabela-planow').querySelectorAll('button[data-usun]').forEach(b =>
    b.addEventListener('click', e => {
      e.stopPropagation();                 // klik w ✕ nie wczytuje planu
      usunPlan(plany[Number(b.dataset.usun)]);
    }));
}

async function usunPlan(p) {
  // Usunięcie MIĘKKIE — plik idzie do kosza obok planów; bez potwierdzenia,
  // bo nic nie znika bez śladu (ta sama reguła co X w terminalu).
  const odp = await api().usun_plan(p.path);
  if (czyBlad(odp, 'Usuwanie planu')) return;
  rysujNotki([`plan przeniesiony do kosza: ${(p.nazwa || p.path).slice(0, 48)}`]);
  otworzPlany();                           // świeża lista
}

async function zapiszPlan() {
  if (!api()) return;
  const odp = await api().zapisz_plan($('#p-nazwa-planu').value);
  if (czyBlad(odp, 'Zapis planu')) return;
  $('#p-nazwa-planu').value = odp.nazwa || '';
  rysujNotki([`PLAN ZAPISANY: ${odp.nazwa} (${odp.utworow} utworów, ${odp.edycji} edycji)`,
              odp.historia, odp.dziennik].filter(Boolean));
}

async function wczytajPlan(p) {
  $('#tabela-planow').innerHTML =
    '<div class="pusto">wczytuję plan i dopasowuję go do puli…</div>';
  const start = await api().wczytaj_plan(p.path);
  if (czyBlad(start, 'Wczytywanie planu')) return;
  clearInterval(odpytywaniePlanu);
  odpytywaniePlanu = setInterval(async () => {
    const s = await api().postep_planu();
    if (!s || s.stan === 'trwa' || s.stan === 'bezczynny') return;
    clearInterval(odpytywaniePlanu);
    if (czyBlad(s, 'Wczytywanie planu')) return;
    $('#plany-box').hidden = true;
    if (!s.utwory || !s.utwory.length) {
      rysujNotki([s.powod || 'plan pusty']);
      return;
    }
    stan.pozycja = null;
    rysujTabeleSetu(s.utwory, []);
    rysujKrzywa(s.utwory);
    // Notki dopasowania to nie ozdoba: utwór, którego nie ma już w puli,
    // został POMINIĘTY, a DJ musi o tym wiedzieć przed wysyłką.
    rysujNotki([`WCZYTANY PLAN: ${s.nazwa || ''} (${s.utwory.length} z ${
      s.zapisanych}）`, ...(s.notki || [])]);
    stan.ostatniSet = {stan: 'gotowe', utwory: s.utwory, filary: [],
                       kotwica: (s.parametry || {}).dj || null,
                       filary_stan: 'brak', filary_zgloszone: 0};
    kontekstSet(stan.ostatniSet);
    odswiezZapis();
  }, 400);
}

/* ---------- playlista do Rekordboxa ---------- */
/* Ta sama zasada dwóch stopni co przy cue, z własnego powodu: dopasowanie
   idzie po ścieżce pliku, a przy jej braku po tytule i tylko gdy kandydat
   jest jeden. Lista utworów, które WYPADNĄ, jest właściwym wynikiem
   pierwszego stopnia — DJ ma ją zobaczyć przed zapisem, nie po. */

function pokazLiczbyPlaylisty(w, poZapisie) {
  const czesci = [liczba(poZapisie ? 'zapisane utwory' : 'utworów wejdzie',
                         poZapisie ? w.zapisane : w.dopasowane)];
  const wypadlo = (w.zgloszone || 0) - (poZapisie ? w.zapisane : w.dopasowane);
  if (wypadlo > 0) czesci.push(liczba('wypadnie', wypadlo, 'ostroznie'));
  if (w.bez_sciezki && w.bez_sciezki.length) {
    czesci.push(liczba('bez pliku na dysku', w.bez_sciezki.length, 'ostroznie'));
  }
  if (w.kopia) czesci.push('<span class="ostroznie">kopia bazy zrobiona</span>');
  if (w.uwaga) czesci.push(`<span class="ostroznie">${w.uwaga}</span>`);
  let html = czesci.join('');
  // Powody pominięć własnymi słowami warstwy publikującej — te same, które
  // widzi terminal; przepisanie ich tutaj rozjechałoby obie skóry.
  const notki = (w.notki || []).filter(n => /POMINI|bliźniak|historia świeżości/i.test(n));
  if (notki.length) {
    html += '<div style="width:100%;margin-top:6px">' + notki.map(n =>
      `<div class="ostroznie">${n.replace(/</g, '&lt;')}</div>`).join('') + '</div>';
  }
  $('#playlista-liczby').innerHTML = html;
}

async function policzPlayliste() {
  $('#btn-pl-policz').disabled = true;
  $('#playlista-liczby').textContent = 'sprawdzam, które utwory Rekordbox zna…';
  const w = await api().podglad_playlisty($('#p-nazwa-playlisty').value);
  $('#btn-pl-policz').disabled = false;
  if (w.blad) {
    $('#playlista-liczby').innerHTML = `<span class="ostroznie">${w.blad}</span>`;
    $('#btn-pl-wyslij').hidden = true;
    return;
  }
  $('#p-nazwa-playlisty').value = w.nazwa || '';
  pokazLiczbyPlaylisty(w, false);
  $('#btn-pl-wyslij').hidden = w.dopasowane === 0;
}

async function wyslijPlayliste() {
  $('#btn-pl-wyslij').disabled = true;
  $('#playlista-liczby').textContent = 'zakładam playlistę (kopia bazy przed zmianą)…';
  const w = await api().wyslij_playliste($('#p-nazwa-playlisty').value);
  $('#btn-pl-wyslij').disabled = false;
  $('#btn-pl-wyslij').hidden = true;
  if (w.blad) {
    $('#playlista-liczby').innerHTML =
      `<span class="ostroznie">ZAPIS NIEUDANY: ${w.blad}</span>`;
    return;
  }
  pokazLiczbyPlaylisty(w, true);
}

async function wyslijZapis() {
  $('#btn-wyslij').disabled = true;
  $('#zapis-liczby').textContent = 'zapisuję (kopia zapasowa przed zmianą)…';
  const w = await api().zapisz_cue();
  $('#btn-wyslij').disabled = false;
  $('#btn-wyslij').hidden = true;
  if (w.blad) {
    $('#zapis-liczby').innerHTML = `<span class="ostroznie">ZAPIS NIEUDANY: ${w.blad}</span>`;
    return;
  }
  $('#zapis-liczby').innerHTML =
    liczba('zapisane pady', w.zapisane)
    + (w.usuniete ? liczba('usunięte', w.usuniete) : '')
    + `<span class="ostroznie">${w.uwaga}</span>`
    // historia świeżości karmiona przy UŻYCIU setu — jak S/W w terminalu,
    // i tak samo widoczna, nie po cichu
    + (w.historia ? `<span class="drobne">${w.historia}</span>` : '');
}

/* ---------- start ---------- */
async function start() {
  await odswiezStanRb();
  setInterval(odswiezStanRb, 5000);

  if (!api()) { $('#tytul').textContent = 'brak mostu do Pythona'; return; }

  const okl = await api().okladki_stan();
  if (okl && !okl.blad) ustawOkladki(!!okl.wlaczone);
  const wersja = await api().wersja();
  if (wersja && wersja.dancelab) $('#wersja').textContent = `v${wersja.dancelab}`;
  const b = await api().biblioteka(100000);   // spis to same nagłówki
  if (b.blad) {
    $('#spis').innerHTML = `<div class="pusto">${b.blad}</div>`;
    $('#tytul').textContent = 'Brak analiz';
    $('#kontekst').innerHTML = `<h2>Nic do pokazania</h2>
      <div class="powod zle"><b>${b.blad}</b><br>${b.podpowiedz || ''}</div>`;
    return;
  }
  pokazEkran('szew');            // jawnie, zamiast polegać na kolejności w HTML
  stan.spis = b.utwory || [];
  const w = await api().wczytaj_edycje();
  if (w && w.wczytano) console.log(`[gui] wczytano ${w.wczytano} padów z poprzedniej sesji`);
  await odswiezPlaylisty();
  odswiezSpis();
  if (stan.spis.length) await wybierzUtwor(stan.spis[0].track_id);
}

$('#fala-obszar').addEventListener('click', postawZKlikniecia);
$('#fala-obszar').addEventListener('mousemove', e => {
  if (!stan.przebieg) return;
  const r = e.currentTarget.getBoundingClientRect();
  const u = (e.clientX - r.left) / r.width;
  $('#czas-kursora').textContent = mmss(u * stan.przebieg.dlugosc_sec * 1000);
});
$('#btn-cofnij').addEventListener('click', cofnij);
$('#filtr').addEventListener('input', e => { stan.filtr = e.target.value; odswiezSpis(); });
$('#filtr-ton').addEventListener('input', odswiezSpis);
$('#filtr-bpm').addEventListener('input', odswiezSpis);
document.querySelectorAll('#sekcje button').forEach(b =>
  b.addEventListener('click', () => {
    stan.sekcja = b.dataset.sekcja;
    document.querySelectorAll('#sekcje button').forEach(x =>
      x.setAttribute('aria-pressed', String(x === b)));
    odswiezSpis();
  }));
/* Sortowanie jak w tabeli terminala (`_cycle_sort`): pierwszy klik rosnąco,
   drugi malejąco, trzeci kasuje. Kierunek widać na chipie. */
document.querySelectorAll('#sortowanie button').forEach(b =>
  b.addEventListener('click', () => {
    const kol = b.dataset.s;
    stan.sortowanie = stan.sortowanie === kol ? '-' + kol
                    : stan.sortowanie === '-' + kol ? '' : kol;
    document.querySelectorAll('#sortowanie button').forEach(x => {
      const aktywny = stan.sortowanie.replace('-', '') === x.dataset.s && stan.sortowanie;
      x.setAttribute('aria-pressed', String(!!aktywny));
      x.textContent = x.dataset.s === 'dlugosc' ? 'czas' : x.dataset.s === 'bpm' ? 'BPM'
                    : x.dataset.s === 'tonacja' ? 'ton' : x.dataset.s === 'tytul' ? 'tytuł' : x.dataset.s;
      if (aktywny) x.textContent += stan.sortowanie.startsWith('-') ? ' ↑' : ' ↓';
    });
    odswiezSpis();
  }));
document.querySelectorAll('#tryb-filarow button').forEach(b =>
  b.addEventListener('click', async () => {
    const odp = await api().ustaw_tryb_filarow(b.dataset.tf);
    if (czyBlad(odp, 'Tryb filarów')) return;
    document.querySelectorAll('#tryb-filarow button').forEach(x =>
      x.setAttribute('aria-pressed', String(x === b)));
  }));
$('#wybor-playlisty').addEventListener('change', async e => {
  const odp = await api().wybierz_playliste(Number(e.target.value));
  if (czyBlad(odp, 'Playlisty')) return;
  await odswiezPlaylisty(); odswiezSpis();
});
$('#btn-nowa-playlista').addEventListener('click', async () => {
  const pole = $('#nowa-playlista');
  const odp = await api().nowa_playlista(pole.value);
  if (czyBlad(odp, 'Nowa playlista')) return;
  pole.value = '';
  await odswiezPlaylisty(); odswiezSpis();
});
document.querySelectorAll('#gestosc button').forEach(b =>
  b.addEventListener('click', () => {
    document.querySelectorAll('#gestosc button')
      .forEach(x => x.setAttribute('aria-pressed', 'false'));
    b.setAttribute('aria-pressed', 'true');
    document.documentElement.dataset.gestosc = b.dataset.g;
    requestAnimationFrame(rysujFale);
  }));
document.querySelectorAll('#nawigacja button').forEach(b =>
  b.addEventListener('click', () => pokazEkran(b.dataset.ekran)));
$('#btn-buduj').addEventListener('click', budujSet);
$('#btn-policz').addEventListener('click', policzZapis);
$('#btn-plany').addEventListener('click', otworzPlany);
$('#btn-zapisz-plan').addEventListener('click', zapiszPlan);
$('#p-pula').addEventListener('change', () =>
  { $('#p-folder-pole').hidden = $('#p-pula').value !== 'folder'; });

let odpytywanieSkanu = null;
async function skanujFolder() {
  if (!api()) return;
  const el = $('#skan-postep');
  const odp = await api().skanuj_folder($('#skan-folder').value);
  if (odp && odp.blad) { el.textContent = odp.blad; el.classList.add('zle'); return; }
  el.classList.remove('zle');
  $('#btn-skan').disabled = true;
  clearInterval(odpytywanieSkanu);
  odpytywanieSkanu = setInterval(async () => {
    const s = await api().postep_skanu();
    if (s.stan === 'trwa') { el.textContent = s.etap || 'analizuję…'; return; }
    clearInterval(odpytywanieSkanu);
    $('#btn-skan').disabled = false;
    if (s.stan !== 'gotowe') {
      el.textContent = `${s.stan === 'odmowa' ? 'ODMOWA' : 'BŁĄD'}: ${s.blad}`;
      el.classList.add('zle'); return;
    }
    el.textContent = `✅ przeanalizowane: ${s.przeanalizowane} — biblioteka od nowa`;
    // nowe analizy → spis od nowa, jak `_set_library` w terminalu
    const b = await api().biblioteka(100000);
    if (!b.blad) { stan.spis = b.utwory || []; odswiezSpis(); }
    if (s.notki && s.notki.length && !$('#ekran-set').hidden) rysujNotki(s.notki);
  }, 500);
}
$('#btn-skan').addEventListener('click', skanujFolder);
$('#btn-okladki').addEventListener('click', przelaczOkladki);
$('#btn-dociagnij').addEventListener('click', dociagnijOkladki);
$('#skan-folder').addEventListener('keydown', e => { if (e.key === 'Enter') skanujFolder(); });
$('#btn-szkic').addEventListener('click', szkicZFilarow);
$('#btn-gatunki-zamknij').addEventListener('click', przelaczGatunki);
document.querySelectorAll('#dj-filtry button').forEach(b =>
  b.addEventListener('click', () => {
    stan.djFiltr = b.dataset.df;
    document.querySelectorAll('#dj-filtry button').forEach(x =>
      x.setAttribute('aria-pressed', String(x === b)));
    rysujDjow();
  }));
$('#btn-info-zamknij').addEventListener('click', () => { $('#info-box').hidden = true; });
$('#btn-szew-zamknij').addEventListener('click', () => { $('#szew-box').hidden = true; });
$('#btn-plany-zamknij').addEventListener('click', () => {
  clearInterval(odpytywaniePlanu); $('#plany-box').hidden = true;
});
$('#btn-pl-policz').addEventListener('click', policzPlayliste);
$('#btn-pl-wyslij').addEventListener('click', wyslijPlayliste);
$('#btn-wyslij').addEventListener('click', wyslijZapis);

/* ---------- odsłuch ----------
   Dźwięk startuje WYŁĄCZNIE z gestu: P, S, kliknięcie w guzik. Nigdy przy
   wczytaniu ekranu, nigdy „na sprawdzenie" — to zasada projektu, ta sama co
   w terminalu. Cała maszyneria (proces, pozycja, skoki) siedzi w Pythonie;
   tu jest rysowanie głowicy i pytanie „co gra?" dziesięć razy na sekundę. */

let odpytywanieGry = null;
let odpytywanieSzwu = null;

function utworDoGrania() {
  // Który utwór ma zagrać P: na ekranie Set zaznaczona pozycja, na ekranie
  // szwu — otwarty utwór. Bez tego P na Secie grałoby coś z innego ekranu.
  if (!$('#ekran-set').hidden) {
    const u = stan.set[stan.pozycja];
    return u ? {trackId: u.track_id, tytul: u.tytul, grywalny: u.grywalny} : null;
  }
  if (!stan.trackId) return null;
  const w = stan.spis.find(u => u.track_id === stan.trackId);
  return {trackId: stan.trackId, tytul: (w && w.tytul) || '',
          grywalny: w ? w.grywalny !== false : true};
}

function rysujGrajka() {
  const g = stan.gra || {};
  const cel = utworDoGrania();
  const btn = $('#btn-graj');
  const gra = !!g.gra;
  btn.setAttribute('aria-pressed', String(gra));
  btn.innerHTML = gra
    ? '<svg viewBox="0 0 24 24"><path d="M6 5h4v14H6zM14 5h4v14h-4z"/></svg>'
    : '<svg viewBox="0 0 24 24"><path d="M7 4l13 8-13 8z"/></svg>';
  // Odmowa PRZED kliknięciem: utwór ze strumienia nie ma czego zagrać i to
  // widać, zamiast czekać, aż DJ kliknie i dostanie komunikat.
  const blokada = cel && cel.grywalny === false;
  // To, co GRA, zawsze musi dać się zatrzymać. Wyszarzenie dotyczy startu,
  // nie pauzy — inaczej szew puszczony na secie ze strumieniem grałby do
  // końca bez guzika, którym można go uciszyć.
  btn.disabled = !gra && (!cel || blokada);
  $('#btn-szew-graj').disabled = !cel || blokada;
  $('#btn-tyl').disabled = !gra;
  $('#btn-przod').disabled = !gra;

  const dl = g.dlugosc_sec ? ` / ${mmss(g.dlugosc_sec * 1000)}` : '';
  rysujOkladkeGry();
  $('#czas-gry').textContent = gra || g.pozycja_sec
    ? mmss((g.pozycja_sec || 0) * 1000) + dl : '0:00';
  const opis = $('#opis-gry');
  opis.classList.toggle('zle', !!blokada);
  if (blokada) {
    opis.textContent = 'utwór ze strumienia — nie ma pliku na dysku, ' +
      'zagrasz go w Rekordboksie';
  } else if (gra) {
    opis.textContent = `${g.opis || ''}${g.skad ? ' · ' + g.skad : ''}`.slice(0, 96);
  } else if (g.pozycja_sec) {
    // Spacja wznawia; P od pada, gdy jakiś jest zaznaczony. Tekst musi
    // mówić to, co klawisz naprawdę robi — wcześniej obiecywał wznowienie,
    // a P z zaznaczonym padem startowało od pada.
    opis.textContent = stan.wybrany && $('#ekran-set').hidden
      ? 'pauza — spacja wznawia od tego miejsca, P gra od pada'
      : 'pauza — spacja albo P wznawia od tego miejsca';
  } else {
    opis.textContent = 'dźwięk gra tylko wtedy, gdy sam go włączysz';
  }
  rysujGlowice();
}

function rysujGlowice() {
  const el = $('#glowica'), g = stan.gra || {}, p = stan.przebieg;
  // Głowica należy do TEGO utworu. Gdy gra co innego (albo szew), znika —
  // linia na cudzej fali kłamałaby o tym, gdzie jest dźwięk.
  if (!p || !g.gra || g.rodzaj !== 'utwor' || g.track_id !== stan.trackId) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  el.style.left = `${Math.min(100, (g.pozycja_sec / p.dlugosc_sec) * 100)}%`;
}

function pilnujGry(wlacz) {
  clearInterval(odpytywanieGry);
  odpytywanieGry = null;
  if (!wlacz) return;
  odpytywanieGry = setInterval(async () => {
    const s = await api().stan_odtwarzania();
    if (czyBlad(s, 'odsłuch')) { pilnujGry(false); return; }
    stan.gra = s;
    rysujGrajka();
    if (!s.gra) {
      pilnujGry(false);      // koniec albo pauza — przestań pytać
      if (s.skonczyl_sie && s.rodzaj === 'utwor') autoNastepny(s.track_id);
    }
  }, 250);
}

/* Standard odtwarzaczy (Janek 06.08): koniec utworu = następny z LISTY.
   Bezpieczniki z terminala: tylko gdy skończył się utwór SPOD KURSORA
   (szew/odsłuch spoza listy nie skacze po liście), koniec listy = cisza. */
async function autoNastepny(tid) {
  if (!$('#ekran-set').hidden) {
    const u = stan.set[stan.pozycja];
    if (!u || u.track_id !== tid) return;
    if (stan.pozycja + 1 >= stan.set.length) { rysujNotki(['koniec listy — odsłuch zakończony']); return; }
    zaznaczPozycje(stan.pozycja + 1, {bezPodazania: true});
    await graj();
    return;
  }
  if (!$('#ekran-dj').hidden || stan.trackId !== tid) return;
  const i = (stan.widoczne || []).findIndex(u => u.track_id === tid);
  if (i < 0 || i + 1 >= stan.widoczne.length) { cueNotka('koniec listy — odsłuch zakończony'); return; }
  await wybierzUtwor(stan.widoczne[i + 1].track_id, {bezPodazania: true});
  await graj('');
}

/* Wzorzec Finder Quick Look (Janek 06.08): GDY COŚ GRA, ruch po liście
   działa jak next/previous — przełącza odsłuch na nowo zaznaczony utwór.
   Przy pauzie/ciszy tylko chodzi po liście. 0,12 s, żeby przytrzymana
   strzałka nie restartowała co wiersz. Przebudowa tabeli NIE jest nawigacją. */
let zegarPodazania = null;
function podazajZaKursorem(trackId) {
  clearTimeout(zegarPodazania);
  const g = stan.gra || {};
  if (!g.gra || g.rodzaj !== 'utwor' || !trackId || g.track_id === trackId) return;
  zegarPodazania = setTimeout(() => {
    const t = stan.gra || {};
    if (t.gra && t.rodzaj === 'utwor' && t.track_id !== trackId) graj('');
  }, 120);
}

async function graj(pad) {
  // Każdy gest odsłuchu unieważnia czekający render szwu. Bez tego P w
  // trakcie renderu puszczało utwór, a po sekundach gotowy szew go ucinał
  // i startował sam — dźwięk zmieniał się bez gestu, czego zasada projektu
  // zabrania. Dźwięk szwu rusza WYŁĄCZNIE z `postep_szwu`, a `postep_szwu`
  // woła tylko ta pętla — więc jej zdjęcie wystarcza.
  clearInterval(odpytywanieSzwu);
  // Pauza tego, co gra, ma zatrzymywać TO, co gra. Szew nie jest utworem —
  // bez tej gałęzi kliknięcie w pauzę podczas szwu puszczało utwór A od zera.
  if (stan.gra.gra && stan.gra.rodzaj === 'szew') {
    const odp = await api().stop_dzwieku();
    if (czyBlad(odp, 'odsłuch')) return;
    stan.gra = odp;
    rysujGrajka();
    pilnujGry(false);
    return;
  }
  const cel = utworDoGrania();
  if (!cel) return;
  const odp = await api().graj(cel.trackId, pad || '');
  if (odp && odp.blad) {
    // odmowa „bez pliku" nie jest awarią — mówimy ją w pasku, nie na czerwono
    // w panelu błędów, bo to normalny stan większości biblioteki
    if (odp.bez_pliku) {
      stan.gra = {gra: false, pozycja_sec: 0};
      $('#opis-gry').classList.add('zle');
      $('#opis-gry').textContent = odp.blad;
      return;
    }
    pokazBlad('odsłuch', odp.blad);
    return;
  }
  stan.gra = odp;
  rysujGrajka();
  pilnujGry(!!odp.gra);
}

/* Skoki z klawiatury — te same co w terminalu: ←→ 8 uderzeń, z Shiftem 32,
   PageUp/PageDown (albo ⌘⇧←→) 128. Tylko gdy coś gra; poza tym strzałki
   należą do padów albo do listy. */
function skokZKlawisza(e) {
  if (!stan.gra.gra) return false;
  const strona = e.key === 'PageUp' || e.key === 'PageDown';
  const strzalka = e.key === 'ArrowLeft' || e.key === 'ArrowRight';
  if (!strona && !strzalka) return false;
  const krok = strona ? 128 : (e.metaKey && e.shiftKey) ? 128 : e.shiftKey ? 32 : 8;
  const znak = (e.key === 'PageUp' || e.key === 'ArrowLeft') ? -1 : 1;
  skok(znak * krok); e.preventDefault(); return true;
}

async function skok(uderzenia) {
  const odp = await api().skocz(uderzenia);
  if (czyBlad(odp, 'skok')) return;
  stan.gra = odp;
  rysujGrajka();
}

async function graj_szew(zPadow) {
  const cel = utworDoGrania();
  if (!cel) return;
  // Na ekranie 1 ZAZNACZONY pad jest wyjściem z A — jak w terminalu.
  const odp = await api().graj_szew(cel.trackId, '', !!zPadow,
                                    zPadow ? (stan.wybrany || '') : '');
  if (odp && odp.blad) {
    $('#opis-gry').classList.add('zle');
    $('#opis-gry').textContent = odp.blad;
    return;
  }
  $('#opis-gry').classList.remove('zle');
  $('#opis-gry').textContent = 'zszywam parę… (render jest cichy)';
  clearInterval(odpytywanieSzwu);
  odpytywanieSzwu = setInterval(async () => {
    const s = await api().postep_szwu();
    if (s.stan === 'trwa' || s.stan === 'bezczynny') return;
    clearInterval(odpytywanieSzwu);
    if (s.stan === 'blad' || s.blad) {
      $('#opis-gry').classList.add('zle');
      $('#opis-gry').textContent = s.blad || 'szew nie wyszedł';
      return;
    }
    stan.gra = s.odtwarzanie;
    rysujGrajka();
    pilnujGry(true);
  }, 400);
}

document.addEventListener('keydown', e => {
  // SELECT też przechwytuje litery (wybór opcji po pierwszej literze), więc
  // bez niego „ł" w polu Łuk mogło wyciąć utwór z setu. TEXTAREA na zapas.
  if (['INPUT', 'SELECT', 'TEXTAREA'].includes(e.target.tagName)) return;
  // Guzik po kliknięciu myszą zostaje z ogniskiem, a przeglądarka zamienia
  // spację na jego kliknięcie — nasze P/Spacja przełączałoby odsłuch dwa
  // razy (albo, na guziku „Buduj set", grało I przebudowywało set naraz).
  if (e.key === ' ' && e.target.tagName === 'BUTTON') return;
  if (e.key === '1') { pokazEkran('szew'); return; }
  if (e.key === '2') { pokazEkran('set'); return; }
  if (e.key === '3') { pokazEkran('dj'); return; }
  // Ściana DJ-ów nie ma klawiszy poza 1/2/3. Bez tej linii wpadała do
  // bloku ekranu szwu: ⌫ zdejmowało pad utworu, którego nie widać, ←→ go
  // przesuwały — i każdy taki ruch szedł do dziennika decyzji jako Twoja
  // decyzja. Guziki odtwarzacza w stopce działają dalej (mysz, nie klawisz).
  if (!$('#ekran-dj').hidden) return;

  // Ekran Set ma własny komplet — te same litery co w terminalu (Z/A/X).
  if (!$('#ekran-set').hidden) {
    if (e.key === 'Escape') {
      zamknijKandydatow();
      clearInterval(odpytywaniePlanu); $('#plany-box').hidden = true;
      clearInterval(odpytywanieGatunkow); $('#gatunki-box').hidden = true;
      return;
    }
    if (e.key === 'o' || e.key === 'O') { otworzPlany(); return; }
    if ((e.metaKey || e.ctrlKey) && (e.key === 's' || e.key === 'S')) {
      zapiszPlan(); e.preventDefault(); return;
    }
    if (e.key === 'Enter' && stan.kandWybor !== null) {
      potwierdzKandydata(); e.preventDefault(); return;
    }
    if ((e.ctrlKey || e.metaKey) && (e.key === 'g' || e.key === 'G')) {
      przelaczGatunki(); e.preventDefault(); return;
    }
    if (e.key === 'g' || e.key === 'G') { szkicZFilarow(); return; }
    if (e.key === 'b' || e.key === 'B') { budujSet(); return; }
    if (e.key === 'z' || e.key === 'Z') {
      if (!(e.metaKey || e.ctrlKey)) { otworzKandydatow('podmiana'); return; }
    }
    if (e.key === 'a' || e.key === 'A') { otworzKandydatow('dopisanie'); return; }
    if (e.key === 'x' || e.key === 'X') { wytnijPozycje(); return; }
    if (e.key === 'c' || e.key === 'C') { porownajPare(); return; }
    if (e.key === 'p' || e.key === 'P' || e.key === ' ') {
      graj(); e.preventDefault(); return;
    }
    if (e.key === 's' || e.key === 'S') { graj_szew(false); return; }
    // strzałki poziome należą do odtwarzacza TYLKO wtedy, gdy coś gra —
    // ta sama reguła co w terminalu, żeby nie zabrać ich edycji
    if (skokZKlawisza(e)) return;
    if (e.shiftKey && e.key === 'ArrowUp') { przesunPozycje(-1); e.preventDefault(); return; }
    if (e.shiftKey && e.key === 'ArrowDown') { przesunPozycje(1); e.preventDefault(); return; }
    if (e.key === 'ArrowUp' && stan.pozycja !== null) {
      zaznaczPozycje(Math.max(0, stan.pozycja - 1)); e.preventDefault(); return;
    }
    if (e.key === 'ArrowDown' && stan.pozycja !== null) {
      zaznaczPozycje(Math.min(stan.set.length - 1, stan.pozycja + 1));
      e.preventDefault(); return;
    }
    return;                       // reszta skrótów należy do ekranu szwu
  }

  if (['a', 'b', 'c', 'd', 'A', 'B', 'C', 'D'].includes(e.key) && !e.metaKey && !e.ctrlKey) {
    literaPada(e.key.toUpperCase()); return;
  }
  if (e.key === 't' || e.key === 'T') { edytujCzasPada(); return; }
  if (e.key === 'k' || e.key === 'K') { przelaczOkladki(); return; }
  if (e.key === 'i' || e.key === 'I') { pokazInfo(); return; }
  if (e.key === 'u' || e.key === 'U') { przelaczUlubiony(); return; }
  if (e.key === 'f' || e.key === 'F') { przypnijFilar(''); return; }
  // Dwa klawisze, bo to dwie różne rzeczy: SPACJA to przełącznik
  // (graj → pauza → wznów od miejsca pauzy), P gra od ZAZNACZONEGO pada —
  // słyszysz dokładnie to miejsce, które właśnie ustawiasz. Jeden klawisz
  // na oba nie umiał wznowić, gdy pad był zaznaczony: zawsze startował od
  // pada, a pasek obiecywał wznowienie.
  if (e.key === ' ') { graj(''); e.preventDefault(); return; }
  if (e.key === 'p' || e.key === 'P') {
    graj(stan.wybrany || ''); e.preventDefault(); return;
  }
  if (e.key === 's' || e.key === 'S') { graj_szew(true); return; }
  // ←→ to przesuwanie pada; odtwarzacz zabiera je WYŁĄCZNIE podczas grania
  if (skokZKlawisza(e)) return;
  if (e.key === 'ArrowLeft') { przesun(-1); e.preventDefault(); }
  if (e.key === 'ArrowRight') { przesun(1); e.preventDefault(); }
  if (e.key === 'Backspace' || e.key === 'Delete') { zdejmij(); e.preventDefault(); }
  if ((e.metaKey || e.ctrlKey) && e.key === 'z') { cofnij(); e.preventDefault(); }
});

// Guzik to przełącznik graj/pauza — jak spacja. Od pada gra P.
$('#btn-graj').addEventListener('click', () => graj(''));
$('#btn-szew-graj').addEventListener('click', () =>
  graj_szew($('#ekran-set').hidden));       // na ekranie szwu — z Twoich padów
$('#btn-tyl').addEventListener('click', () => skok(-8));
$('#btn-przod').addEventListener('click', () => skok(8));
$('#btn-kand-zamknij').addEventListener('click', zamknijKandydatow);
document.querySelectorAll('#tryb-oceny button').forEach(b =>
  b.addEventListener('click', () => {
    stan.kandTryb = b.dataset.t;
    document.querySelectorAll('#tryb-oceny button').forEach(x =>
      x.setAttribute('aria-pressed', String(x === b)));
    if (stan.kandCel) otworzKandydatow(stan.kandCel);   // przelicz na żywo
  }));
window.addEventListener('resize', () => requestAnimationFrame(rysujFale));
window.addEventListener('pywebviewready', start);
if (window.pywebview) start();
