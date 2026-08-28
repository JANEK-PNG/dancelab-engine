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
  ostatniBlad: null,
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

async function postawZKlikniecia(ev) {
  if (!stan.przebieg || !api()) return;
  const r = $('#fala-obszar').getBoundingClientRect();
  const ulamek = Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width));
  const ms = Math.round(ulamek * stan.przebieg.dlugosc_sec * 1000);
  const pad = stan.wybrany || wolnyPad();
  if (!pad) { pokazBlad('Pady', 'Wszystkie cztery pady zajęte — zdejmij któryś (⌫).'); return; }
  const odp = await api().postaw_pad(stan.trackId, pad, ms);
  if (czyBlad(odp, 'Stawianie pada')) return;
  stan.pady = odp.pady || {}; stan.wybrany = pad; przerysuj();
}

async function przesun(uderzenia) {
  if (!stan.wybrany || !api()) return;
  const odp = await api().przesun_pad(stan.trackId, stan.wybrany, uderzenia,
                                      stan.bpm || 128);
  if (czyBlad(odp, 'Przesuwanie pada')) return;
  stan.pady = odp.pady || {}; przerysuj();
}

async function zdejmij() {
  if (!stan.wybrany || !api()) return;
  const odp = await api().zdejmij_pad(stan.trackId, stan.wybrany);
  if (czyBlad(odp, 'Zdejmowanie pada')) return;
  stan.pady = odp.pady || {}; stan.wybrany = null; przerysuj();
}

async function cofnij() {
  if (!api()) return;
  const odp = await api().cofnij(stan.trackId);
  if (czyBlad(odp, 'Cofanie')) return;
  stan.pady = odp.pady || {}; przerysuj();
}

async function odswiezStanRb() {
  if (!api()) return;
  const s = await api().stan_rekordboxa();
  const el = $('#stan-rb');
  if (s.blad) { el.innerHTML = `<span class="kropka zle"></span> ${s.blad}`; return; }
  el.innerHTML = `<span class="kropka ${s.zapis_dozwolony ? 'ok' : 'zle'}"></span> ${s.powod}`;
  $('#btn-zapisz').disabled = !s.zapis_dozwolony;
  $('#btn-zapisz').title = s.zapis_dozwolony ? '' : s.powod;
}

/* ---------- start ---------- */
async function start() {
  await odswiezStanRb();
  setInterval(odswiezStanRb, 5000);

  if (!api()) { $('#tytul').textContent = 'brak mostu do Pythona'; return; }
  const p = await api().przebieg_utworu(stan.trackId || '', 900);
  if (p.blad) {
    $('#tytul').textContent = 'Brak wczytanego utworu';
    $('#podtytul').textContent = 'zbuduj set w terminalu (dancelab tui) — plan jest wspólny';
    $('#kontekst').innerHTML = `<h2>Nic nie wczytane</h2>
      <div class="powod">${p.blad}</div>`;
    return;
  }
  stan.przebieg = p; stan.bpm = p.bpm;
  const pd = await api().pady(stan.trackId || '');
  if (!pd.blad) stan.pady = pd.pady || {};
  przerysuj();
}

$('#fala-obszar').addEventListener('click', postawZKlikniecia);
$('#fala-obszar').addEventListener('mousemove', e => {
  if (!stan.przebieg) return;
  const r = e.currentTarget.getBoundingClientRect();
  const u = (e.clientX - r.left) / r.width;
  $('#czas-kursora').textContent = mmss(u * stan.przebieg.dlugosc_sec * 1000);
});
$('#btn-cofnij').addEventListener('click', cofnij);
document.querySelectorAll('#gestosc button').forEach(b =>
  b.addEventListener('click', () => {
    document.querySelectorAll('#gestosc button')
      .forEach(x => x.setAttribute('aria-pressed', 'false'));
    b.setAttribute('aria-pressed', 'true');
    document.documentElement.dataset.gestosc = b.dataset.g;
    requestAnimationFrame(rysujFale);
  }));
document.addEventListener('keydown', e => {
  if (e.key === 'ArrowLeft') { przesun(-1); e.preventDefault(); }
  if (e.key === 'ArrowRight') { przesun(1); e.preventDefault(); }
  if (e.key === 'Backspace' || e.key === 'Delete') { zdejmij(); e.preventDefault(); }
  if ((e.metaKey || e.ctrlKey) && e.key === 'z') { cofnij(); e.preventDefault(); }
});
window.addEventListener('resize', () => requestAnimationFrame(rysujFale));
window.addEventListener('pywebviewready', start);
if (window.pywebview) start();
