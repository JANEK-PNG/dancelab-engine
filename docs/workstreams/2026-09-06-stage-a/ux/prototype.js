'use strict';
// Fictional music metadata, used only to review the preparation journey.
const tracks = [
  {id:'t1', title:'Soft Arrival', artist:'Studio Example', bpm:122, key:'8A', available:true},
  {id:'t2', title:'Between Rooms', artist:'North Demo', bpm:123, key:'9A', available:true},
  {id:'t3', title:'Late Geometry', artist:'Studio Example', bpm:124, key:'9A', available:true},
  {id:'t4', title:'A Different Corner', artist:'Field Example', bpm:125, key:'2A', available:true},
  {id:'t5', title:'Open Window', artist:'North Demo', bpm:124, key:null, available:true},
  {id:'t6', title:'Last Light', artist:'Field Example', bpm:121, key:'8A', available:true},
  {id:'t7', title:'Unmapped Memory', artist:'Archive Demo', bpm:null, key:null, available:false},
];
const storageKey = 'dancelab-stage-a-prototype-v1';
const $ = selector => document.querySelector(selector);
const html = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state = {name:'Piątek, po zmroku', order:[], anchors:[], dirty:false};
const countLabel = (n, one, few, many) => `${n} ${n === 1 ? one : [2,3,4].includes(n % 10) && ![12,13,14].includes(n % 100) ? few : many}`;
const trackCount = n => countLabel(n, 'utwór', 'utwory', 'utworów');
const anchorCount = n => countLabel(n, 'filar', 'filary', 'filarów');
let undo = [];
let filter = '';
let saved = readSaved();

function readSaved() {
  try {
    const record = JSON.parse(localStorage.getItem(storageKey));
    if (!record || record.version !== 1 || !Array.isArray(record.order) || typeof record.name !== 'string') return null;
    const allowed = new Set(tracks.filter(t => t.available).map(t => t.id));
    const order = [...new Set(record.order.filter(id => allowed.has(id)))];
    if (!order.length) return null;
    return {version:1, name:record.name.slice(0,120), order,
      anchors:(Array.isArray(record.anchors) ? record.anchors : []).filter(id => order.includes(id)),
      savedAt:typeof record.savedAt === 'string' ? record.savedAt : ''};
  } catch { return null; }
}
function notice(text) { $('#status').textContent = text; }
function landing() {
  $('#app').innerHTML = `<div class="landing"><section class="hero"><div><div class="eyebrow">${saved ? 'Wróć do swojego rytmu' : 'Od kolekcji do kolejności'}</div><h1>${saved ? 'Twój set.<br>Dokładnie tam,<br>gdzie skończyłeś.' : 'Znasz te utwory.<br>Znajdź ich<br>wspólną historię.'}</h1><p>${saved ? 'Zachowana kolejność, wybrane filary i przestrzeń na kolejny pomysł.' : 'Wybierz muzykę ze swojej biblioteki, ułóż set i zostaw sobie miejsce na zmianę zdania.'}</p><div class="actions"><button id="import" class="${saved ? '' : 'primary'}">${saved ? 'Zacznij nowy set' : 'Wczytaj bibliotekę demo'} →</button></div><p class="micro">Próba interfejsu na fikcyjnych utworach. Twoje pliki pozostają nietknięte.</p></div>${saved ? `<aside class="resume"><div class="eyebrow">Ostatnio zapisany set</div><h2>${html(saved.name)}</h2><p>${trackCount(saved.order.length)} · ${anchorCount(saved.anchors.length)}</p><p>Zapis: ${html(saved.savedAt ? new Date(saved.savedAt).toLocaleString('pl-PL') : 'brak daty')}</p><button class="primary" id="resume">Wróć do setu →</button></aside>` : `<aside class="score"><div class="score-label">TY WYBIERASZ KIERUNEK</div><div class="score-row"><span>01</span><div><b>Twoja kolekcja</b><small>Muzyka, którą chcesz zagrać.</small></div></div><div class="score-row"><span>02</span><div><b>Twoja kolejność</b><small>Układaj, porównuj, zmieniaj zdanie.</small></div></div><div class="score-row"><span>03</span><div><b>Gotowy punkt wyjścia</b><small>Zapisz i wróć, kiedy przyjdzie pomysł.</small></div></div></aside>`}</section><section class="principles"><div><b>Kontrola pozostaje u Ciebie.</b><p>Dodanie utworu i oznaczenie go jako filaru to dwie osobne decyzje.</p></div><div><b>Brak danych jest widoczny.</b><p>Nieznana tonacja i brakujący plik mają własne, czytelne oznaczenia.</p></div><div><b>Zapis to spokojny powrót.</b><p>Najpierw zachowujesz swoją pracę. Eksportujesz ją, kiedy jest gotowa.</p></div></section></div>`;
  $('#import').onclick = () => {
    state = {name:'Piątek, po zmroku', order:[], anchors:[], dirty:false}; undo=[]; filter='';
    workspace(); notice('Biblioteka demo: 6 dostępnych utworów, 1 brakujący plik. Nic nie zostało pominięte po cichu.');
  };
  if (saved) $('#resume').onclick = () => {
    state = {...saved, order:[...saved.order], anchors:[...saved.anchors], dirty:false}; undo=[];
    workspace(); notice('Przywrócono zapisany set. Odsłuch ani eksport nie uruchamiają się automatycznie.');
  };
}
function workspace() {
  $('#app').innerHTML = `<div class="workspace"><div class="work-heading"><div><h1>Ułóż to po swojemu.</h1><p>Twoja kolekcja po lewej. Historia, którą budujesz — po prawej.</p></div><div class="step"><strong>01 Wybierz</strong> &nbsp;/&nbsp; 02 Ułóż &nbsp;/&nbsp; 03 Sprawdź</div></div><div class="columns"><section class="library" aria-labelledby="library-heading"><div class="section-head"><h2 id="library-heading">Biblioteka</h2><span>DEMO / 7 UTWORÓW</span></div><label class="screen-reader" for="search">Szukaj w bibliotece</label><input class="search" id="search" type="search" placeholder="Utwór lub wykonawca…"><div class="note">1 plik niedostępny. Pozostaje na liście, żebyś wiedział, czego brakuje.</div><div id="library-rows"></div></section><section class="set" aria-label="Twój set"><div id="set-panel"></div></section></div></div>`;
  $('#search').value = filter;
  $('#search').oninput = e => { filter=e.target.value; renderLibrary(); };
  renderLibrary(); renderSet();
}
function renderLibrary() {
  const visible=tracks.filter(t => `${t.title} ${t.artist}`.toLowerCase().includes(filter.toLowerCase()));
  $('#library-rows').innerHTML = visible.length ? `<table><thead><tr><th>Utwór</th><th class="num">BPM</th><th class="num">Tonacja</th><th><span class="screen-reader">Dodaj</span></th></tr></thead><tbody>${visible.map(t => `<tr class="${t.available ? '' : 'unavailable'}"><td><span class="track-title">${html(t.title)}</span><span class="artist">${html(t.artist)}</span>${t.available ? '' : '<span class="tag">Brak pliku · nie można dodać</span>'}</td><td class="num">${t.bpm ?? '—'}</td><td class="num">${t.key ?? '—'}</td><td class="row-actions"><button class="small" data-add="${t.id}" ${!t.available || state.order.includes(t.id) ? 'disabled' : ''} aria-label="Dodaj ${html(t.title)} do setu">${state.order.includes(t.id) ? 'Dodany ✓' : 'Dodaj +'}</button></td></tr>`).join('')}</tbody></table>` : '<div class="empty"><h3>Nie ma takiego utworu.</h3><p>Spróbuj krótszego tytułu lub nazwy wykonawcy.</p></div>';
  document.querySelectorAll('[data-add]').forEach(button => button.onclick=()=>{
    remember(); state.order.push(button.dataset.add); changed('Dodano utwór. Filar możesz oznaczyć osobno.');
  });
}
function remember() { undo.push({order:[...state.order], anchors:[...state.anchors]}); if(undo.length>20)undo.shift(); }
function changed(message) { state.dirty=true; renderSet(); renderLibrary(); notice(message); }
function renderSet() {
  $('#set-panel').innerHTML = `<div class="section-head"><h2>Twój set</h2><span>${trackCount(state.order.length).toUpperCase()}</span></div><label class="screen-reader" for="set-name">Nazwa setu</label><input id="set-name" class="set-name" maxlength="120" value="${html(state.name)}"><div class="save-state" id="save-state">${state.dirty ? '● Niezapisane zmiany' : state.savedAt ? '✓ Wersja zapisana' : 'Nowy szkic'}</div>${state.order.length ? `<div>${state.order.map((id,i)=>{const t=tracks.find(x=>x.id===id);return `<div class="set-row"><span class="position">${String(i+1).padStart(2,'0')}</span><div><span class="track-title">${html(t.title)}</span><div class="artist">${html(t.artist)} · ${t.bpm ?? '—'} BPM · ${t.key ?? 'tonacja nieznana'}</div>${state.anchors.includes(id) ? '<span class="anchor">Filar · ma pozostać w propozycjach setu</span>' : ''}</div><div class="controls"><button class="small" data-anchor="${id}" aria-pressed="${state.anchors.includes(id)}" title="Filar to utwór wymagany w przyszłych propozycjach setu">Filar</button><button class="small" data-move="${i},-1" ${i===0?'disabled':''} aria-label="Przesuń ${html(t.title)} wyżej">↑</button><button class="small" data-move="${i},1" ${i===state.order.length-1?'disabled':''} aria-label="Przesuń ${html(t.title)} niżej">↓</button><button class="small quiet" data-remove="${id}" aria-label="Usuń ${html(t.title)} z setu">×</button></div></div>`;}).join('')}</div>` : '<div class="empty"><h3>Zacznij od jednego utworu.</h3><p>Dodaj coś z biblioteki. Kolejność możesz zmienić w dowolnym momencie.</p></div>'}<div class="set-footer"><button id="undo" ${undo.length?'':'disabled'}>Cofnij</button><button id="save" ${state.order.length?'':'disabled'}>Zapisz set</button><button id="export" class="primary" ${state.order.length?'':'disabled'}>Sprawdź eksport →</button></div><div class="playback"><button disabled aria-label="Odsłuch niedostępny: utwory demonstracyjne nie zawierają audio">▷</button><span>Odsłuch niedostępny w tym przykładzie.<br>Utwory demo nie zawierają audio.</span></div><p class="hint">Układasz ręcznie. To podgląd pracy z setem; nie pokazuje wyników ani rekomendacji modelu.</p>`;
  $('#set-name').oninput=e=>{state.name=e.target.value;state.dirty=true;$('#save-state').textContent='● Niezapisane zmiany';};
  $('#save').onclick=save;
  $('#undo').onclick=()=>{const previous=undo.pop();if(previous){Object.assign(state,previous);changed('Cofnięto ostatnią zmianę kolejności lub filaru.');}};
  $('#export').onclick=reviewExport;
  document.querySelectorAll('[data-anchor]').forEach(b=>b.onclick=()=>{
    remember();const id=b.dataset.anchor;state.anchors=state.anchors.includes(id)?state.anchors.filter(x=>x!==id):[...state.anchors,id];changed('Zmieniono oznaczenie filaru. Kolejność pozostaje pod Twoją kontrolą.');
  });
  document.querySelectorAll('[data-move]').forEach(b=>b.onclick=()=>{
    const [index,delta]=b.dataset.move.split(',').map(Number);remember();
    [state.order[index],state.order[index+delta]]=[state.order[index+delta],state.order[index]];changed('Zmieniono kolejność. Zapisz, aby zachować ją po powrocie.');
  });
  document.querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{
    remember();state.order=state.order.filter(id=>id!==b.dataset.remove);state.anchors=state.anchors.filter(id=>id!==b.dataset.remove);changed('Usunięto z setu. Utwór pozostał w bibliotece. Możesz cofnąć tę zmianę.');
  });
}
function save() {
  if (!state.order.length)return;
  const record={version:1,name:state.name.trim()||'Nowy set',order:[...state.order],anchors:[...state.anchors],savedAt:new Date().toISOString()};
  try { localStorage.setItem(storageKey,JSON.stringify(record)); }
  catch {notice('Nie udało się zapisać szkicu w tej przeglądarce. Set nadal jest na ekranie; możesz pobrać kopię JSON.');return;}
  saved=record;state={...record,dirty:false};renderSet();notice('Zapisano szkic demo. „Sprawdź powrót do pracy” pokaże kolejny start.');
}
function reviewExport() {
  const dialog=$('#export-dialog');
  dialog.innerHTML=`<div class="eyebrow">Sprawdź przed eksportem</div><h2 id="export-title">${html(state.name)}</h2><p>W tej próbie pobierzesz szkic JSON z fikcyjnymi utworami. Plik jest oznaczony jako demo i nie jest eksportem do Rekordboxa.</p><div class="review-list">${state.order.map((id,i)=>`${i+1}. ${html(tracks.find(t=>t.id===id).title)}`).join('<br>')}</div><p>${trackCount(state.order.length)} · ${anchorCount(state.anchors.length)} · bez plików audio</p><div class="actions"><button id="cancel-export">Wróć do edycji</button><button class="primary" id="download">Pobierz szkic JSON</button></div>`;
  $('#cancel-export').onclick=()=>dialog.close();
  $('#download').onclick=()=>{
    const data={schema:'dancelab.prototype.set.v1',demo:true,name:state.name,tracks:state.order.map(id=>({...tracks.find(t=>t.id===id),anchor:state.anchors.includes(id)}))};
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='dancelab-szkic-demo.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);dialog.close();notice('Przygotowano szkic JSON do pobrania. Biblioteka Rekordboxa pozostaje nietknięta.');
  };dialog.showModal();
}
function restart() {
  if(state.dirty && !window.confirm('Masz niezapisane zmiany. Wrócić do ostatnio zapisanego szkicu?'))return;
  saved=readSaved();state={name:'Piątek, po zmroku',order:[],anchors:[],dirty:false};undo=[];landing();notice(saved?'Oto kolejny start: możesz wrócić do zapisanego setu.':'Oto pierwszy start: nie ma jeszcze zapisanego setu.');
}
$('#restart').onclick=restart;$('#home').onclick=e=>{e.preventDefault();restart();};
landing();
