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
        <td>${n}</td><td class="num">${mmss(ms)}</td>
        <td class="num">${ud}</td><td style="color:var(--cichszy)">${skad}</td></tr>`;
    }).join('')}</tbody></table>`;
  el.querySelectorAll('tr[data-pad]').forEach(tr =>
    tr.addEventListener('click', () => zaznacz(tr.dataset.pad)));
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
}

/* ---------- działania (każde idzie do Pythona) ---------- */
function zaznacz(nazwa) { stan.wybrany = nazwa; rysujPady(); rysujListe(); }

function wolnyPad() {
  return NAZWY_PADOW.find(n => !(n in (stan.pady || {})));
}

async function odloz() {
  // Po każdej zmianie, nie na zamknięciu okna: zamknięcie bywa nagłe,
  // a edycje mają przeżyć także wtedy.
  if (api()) await api().zapisz_edycje();
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

}

/* ---------- lista utworów ---------- */
function rysujSpis() {
  const el = $('#spis');
  const f = stan.filtr.toLowerCase();
  const widoczne = f
    ? stan.spis.filter(u => ((u.tytul || '') + ' ' + (u.wykonawca || '')).toLowerCase().includes(f))
    : stan.spis;

  $('#licznik').textContent = f
    ? `${widoczne.length} z ${stan.spis.length}`
    : `${stan.spis.length} utworów`;

  if (!widoczne.length) {
    el.innerHTML = '<div class="pusto">nic nie pasuje</div>';
    return;
  }
  // Renderujemy najwyżej 300 wierszy: przy ośmiu tysiącach pozycji reszta i tak
  // nie jest widoczna, a pełna lista zabija płynność przewijania.
  el.innerHTML = widoczne.slice(0, 300).map(u => `
    <div class="utwor" data-id="${u.track_id}"
         ${stan.trackId === u.track_id ? 'aria-selected="true"' : ''}>
      <div class="t">${(u.tytul || u.track_id).replace(/</g, '&lt;')}</div>
      <div class="d">${u.bpm ? u.bpm.toFixed(1) : '—'} · ${u.tonacja || '—'}</div>
    </div>`).join('') +
    (widoczne.length > 300
      ? `<div class="pusto">…i ${widoczne.length - 300} dalszych — zawęź szukaniem</div>`
      : '');

  el.querySelectorAll('.utwor').forEach(d =>
    d.addEventListener('click', () => wybierzUtwor(d.dataset.id)));
}

async function wybierzUtwor(trackId) {
  if (!api()) return;
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

function pokazEkran(nazwa) {
  document.querySelectorAll('main > section').forEach(x =>
    x.hidden = x.id !== (nazwa === 'set' ? 'ekran-set' : 'szew'));
  document.querySelectorAll('#nawigacja button').forEach(b =>
    b.setAttribute('aria-pressed', String(b.dataset.ekran === nazwa)));
  /* Sam `display:none` na liście NIE wystarczy: siatka ma cztery kolumny,
     więc zniknięcie listy przesuwa główny obszar w jej wąską kolumnę, a panel
     kontekstu rozlewa się na resztę. Złapane na zrzucie — ekran Set ściskał
     się do 264 px z uciętą tabelą. Kolumny przełącza CSS po tym atrybucie. */
  document.documentElement.dataset.ekran = nazwa;
  if (nazwa === 'set') { kontekstSet(); odswiezZapis(); }
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
  if (!utwory || !utwory.length) {
    el.innerHTML = '<div class="pusto">Silnik nie zbudował setu — powód wyżej.</div>';
    return;
  }
  const zbior = new Set(filary || []);
  let suma = 0;
  el.innerHTML = `<table><thead><tr>
      <th style="width:34px">#</th><th style="width:54px">BPM</th>
      <th style="width:60px">ton</th><th style="width:56px">Σ min</th>
      <th>wykonawca</th><th>tytuł</th><th style="width:70px">filar</th>
    </tr></thead><tbody>${utwory.map((u, i) => {
      suma += (u.dlugosc_sec || 0) / 60;
      // źródło tonacji jest częścią prawdy o niej — „RB" to niezależny sędzia
      const ton = u.tonacja
        ? `<span class="ton">${u.tonacja}</span>` +
          (u.tonacja_zrodlo === 'rekordbox' ? ' <span class="drobne">RB</span>' : '')
        : '<span class="pusto">—</span>';
      return `<tr>
        <td class="num">${i + 1}</td>
        <td class="num">${u.bpm ? u.bpm.toFixed(1) : '—'}</td>
        <td>${ton}</td>
        <td class="num">${suma.toFixed(0)}</td>
        <td>${(u.wykonawca || '—').replace(/</g, '&lt;')}</td>
        <td>${(u.tytul || '').replace(/</g, '&lt;')}</td>
        <td style="color:var(--bursztyn)">${zbior.has(u.track_id) ? 'FILAR' : ''}</td>
      </tr>`;
    }).join('')}</tbody></table>`;
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
  const box = $('#zapis-box');
  if (!s || s.blad || !s.set) { box.hidden = true; return; }
  box.hidden = false;
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
    + `<span class="ostroznie">${w.uwaga}</span>`;
}

/* ---------- start ---------- */
async function start() {
  await odswiezStanRb();
  setInterval(odswiezStanRb, 5000);

  if (!api()) { $('#tytul').textContent = 'brak mostu do Pythona'; return; }

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
  rysujSpis();
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
$('#filtr').addEventListener('input', e => { stan.filtr = e.target.value; rysujSpis(); });
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
$('#btn-wyslij').addEventListener('click', wyslijZapis);
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === '1') { pokazEkran('szew'); return; }
  if (e.key === '2') { pokazEkran('set'); return; }
  if (e.key === 'b' && !$('#ekran-set').hidden) { budujSet(); return; }
  if (e.key === 'ArrowLeft') { przesun(-1); e.preventDefault(); }
  if (e.key === 'ArrowRight') { przesun(1); e.preventDefault(); }
  if (e.key === 'Backspace' || e.key === 'Delete') { zdejmij(); e.preventDefault(); }
  if ((e.metaKey || e.ctrlKey) && e.key === 'z') { cofnij(); e.preventDefault(); }
});
window.addEventListener('resize', () => requestAnimationFrame(rysujFale));
window.addEventListener('pywebviewready', start);
if (window.pywebview) start();
