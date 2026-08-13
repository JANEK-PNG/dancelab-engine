/* ═══════════════════════════════════════════════════════════════════════
   PORTRET — SYSTEM VJ  ·  DanceLab
   ═══════════════════════════════════════════════════════════════════════

   Portret brzmienia DJ-a rysowany WYŁĄCZNIE z pomiarów: mapa DJ-ów
   (utwory zagrane na festiwalach i kolejność, w jakiej poszły) plus
   liczby policzone przez silnik DanceLaba. Nic tu nie jest ozdobą.

   TRZY WARSTWY (budowane pod dyktando Janka, 13.08):

   1 · POLE MOŻLIWOŚCI — każde włókno to jeden utwór. Wysokość niesie
       tempo (grubo) i energię (rozsyp w obrębie tempa), jasność to
       rzeczywista gęstość 9 750 zmierzonych utworów mapy.

   2 · SPLATANIE — węzły biorą się z PRAWDZIWYCH przejść setu: miejsce
       w paśmie z tempa i energii utworu wchodzącego, ile włosów garnie
       z C (sprzężenie policzone przez silnik), kiedy dojrzewa — gdy
       dojdzie do niego kropka. Oś nie jest narzucona: to środek
       ciężkości włosów, które węzeł sam przygarnął. Trzy pasma po
       0°/120°/240° naprawdę przechodzą jedno przez drugie.

   3 · RAMA — przejście przelicza CAŁE pole: gdy A gra, możliwe jest to,
       co osiągalne STĄD. W szwie grają oba utwory, więc rama jest sumą
       ram A i B i pole się POSZERZA. Po szwie zaciska się wokół B.
       Osiągalność liczy silnik (`set_builder.bpm_score`, świadomy
       oktawy), nie odległość temp.

   KROPKA = DJ w chwili decyzji. Działa jak magnes: przy niej promień
   oplotu schodzi do zera, więc każda nić potrzebna do setu przez nią
   przechodzi — moment bezpośredniej interakcji, już po in between.
   Magnes jest wybiórczy: bierze nić tylko gdy NALEŻY do sznura i jest
   OSIĄGALNA z tego, co gra.

   CZEGO TU NIE MA I DLACZEGO: długości szwu ani tego, czy DJ przytrzymał
   bas. Mapa ma zerowe pokrycie tych pól — są w niej utwory i kolejność,
   nie nagranie. Dorysowanie tego byłoby zmyśleniem.

   KOLOR mówi językiem aplikacji (paleta TERRAIN):
     zimny grafit — poza ramą, stąd tego nie zagrasz
     bursztyn     — osiągalne z tego, co GRA        (talia A)
     błękit       — co dopiero WCHODZĄCY utwór OTWIERA (talia B)
     volt         — rdzeń sznura: to zaistniało

   UŻYCIE:
     await PortretVJ.wczytaj("./");           // dane raz na stronę
     const p = PortretVJ.stworz(canvas, {ksywa: "Tim Reaper"});
     function klatka(ts){ p.rysuj(ts / 1000, {frakcja, glosnosc});
                          requestAnimationFrame(klatka); }

   Stan jest PER INSTANCJA — kilka portretów na jednym ekranie (ściana
   kart DJ-ów) nie kasuje sobie nawzajem wypalonego profilu sznura.
   ═════════════════════════════════════════════════════════════════════ */

const PortretVJ = (function(){
"use strict";

const THETA = 0.18;            // próg z definicji In Between
const ILE_WLOSOW = 420;
const SKRET = 6.283 / 96;      // jeden pełny oplot sznura na ~96 px

/* deterministyczna losowość — ziarno z tekstu, nigdy Math.random.
   Ziarno rozbijamy lawiną i rozgrzewamy generator: bez tego pierwsza
   liczba po zaszczepieniu przyjmuje garść wartości i włosy zbijają się
   w kilka kępek tempa zamiast próbkować bibliotekę. */
function hash(s){
  let h = 2166136261;
  for (const c of s){ h ^= c.charCodeAt(0); h = Math.imul(h, 16777619); }
  h ^= h >>> 15; h = Math.imul(h, 2246822507);
  h ^= h >>> 13; h = Math.imul(h, 3266489909);
  h ^= h >>> 16;
  return (h >>> 0) || 1;
}
function rnd(seed){
  let s = seed >>> 0 || 1;
  const krok = () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5;
                       return (s >>> 0) / 4294967296; };
  for (let i = 0; i < 6; i++) krok();
  return krok;
}
const gladko = (v) => { const u = Math.max(0, Math.min(1, v));
                        return u * u * (3 - 2 * u); };

/* ── DANE (wspólne dla wszystkich portretów na stronie) ──────────────── */
let POLE = null, ZASIEG = null, SZWY = null;

async function wczytaj(baza = "./"){
  if (POLE && ZASIEG && SZWY) return {POLE, ZASIEG, SZWY};
  const we = (plik) => fetch(baza + plik).then(r => {
    if (!r.ok) throw new Error("brak " + plik + " (" + r.status + ")");
    return r.json();
  });
  const [pole, zas, szwy] = await Promise.all([
    we("mozliwosci.json"), we("zasieg_tempa.json"), we("szwy.json")]);
  POLE = pole; ZASIEG = zas; SZWY = szwy;
  return {POLE, ZASIEG, SZWY};
}

function zasieg(bpmA, bpmB){
  if (!ZASIEG || bpmA == null || bpmB == null) return 1;
  const i = Math.round(Math.max(ZASIEG.od, Math.min(ZASIEG.do, bpmA))) - ZASIEG.od;
  const j = Math.round(Math.max(ZASIEG.od, Math.min(ZASIEG.do, bpmB))) - ZASIEG.od;
  return ZASIEG.siatka[i][j];
}
function gestosc(bpm, en){
  if (!POLE) return 0;
  const ib = Math.max(0, Math.min(POLE.nb - 1,
    Math.floor((bpm - POLE.bpm_od) / (POLE.bpm_do - POLE.bpm_od) * POLE.nb)));
  const ie = Math.max(0, Math.min(POLE.ne - 1, Math.floor(en * POLE.ne)));
  return POLE.siatka[ib][ie];
}
/* czy ten włos jest w zasięgu tego węzła: liczy się i tempo, i energia —
   te same dwie cechy, z których silnik liczy zgodność przejścia */
function przyleglosc(w, bpmCel, enCel, oknoBpm, zasEn){
  const zb = 1 - Math.min(1, Math.abs(w.bpm - bpmCel) / oknoBpm);
  if (zb <= 0) return 0;
  const ze = 1 - Math.min(1, Math.abs(w.en - enCel) / zasEn);
  if (ze <= 0) return 0;
  return zb * ze;
}

function ksywy(){ return SZWY ? Object.keys(SZWY) : []; }

/* ── PORTRET (jedna instancja = jedno płótno) ────────────────────────── */
function stworz(canvas, opcje){
  const o = opcje || {};
  const cv = canvas, ctx = cv.getContext("2d");
  let ksywa = o.ksywa || ksywy()[0] || null;
  let W = 0, H = 0, WLOSY = null, PAM = null, GRUBOSC = 1;
  // pętla własna, gdy nic nie gra: cały wieczór w CYKL sekund. NIE
  // startujemy od zera — na początku setu nic nie jest jeszcze
  // zaplecione i obraz wygląda pusto.
  const CYKL = o.cykl || 180, START = o.start != null ? o.start : 0.38;

  function wymiary(){
    const DPR = Math.min(2, window.devicePixelRatio || 1);
    const nowaW = cv.clientWidth || cv.width;
    const nowaH = cv.clientHeight || cv.height;
    if (nowaW === W && nowaH === H && cv.width) return;
    W = nowaW; H = nowaH;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    WLOSY = null; PAM = null;              // geometria zależy od rozmiaru
  }

  function wlosy(){
    if (WLOSY) return WLOSY;
    const lista = [];
    for (let i = 0; i < ILE_WLOSOW; i++){
      const r = rnd(hash("wlos" + i));
      const bpm = 60 + r() * 140, en = r();
      const g = gestosc(bpm, en);
      if (g < 0.006) continue;
      lista.push({i, bpm, en, g,
        // wysokość niesie OBIE zmierzone cechy: tempo grubo rozstawia
        // włosy w paśmie, energia rozsypuje je w obrębie tempa — dzięki
        // temu włosy pokrewne tempem mają skąd się do siebie zejść
        y0: H * (0.95 - (bpm - 60) / 140 * 0.62 - en * 0.30),
        faza: r() * 6.283, dryf: 0.05 + r() * 0.12,
        amp: H * (0.035 + g * 0.09),
        pasmo: i % 3,                      // jedno z trzech pasm warkocza
        wpasmie: r(),
        skret: 3.2 + r() * 0.8});
    }
    WLOSY = lista;
    return lista;
  }

  /* Geometria sznura NIE zmienia się z klatki na klatkę (zależy od setu
     i rozmiaru płótna), więc wypalamy ją RAZ. Co klatkę zmienia się
     tylko dojrzałość — czyli dokąd doszła kropka. */
  function statyczne(szwy){
    const n = szwy.length;
    if (PAM && PAM.ksywa === ksywa && PAM.W === W && PAM.H === H) return PAM;
    const lista = [];
    const rozstaw = n > 1 ? W * 0.92 / (n - 1) : W * 0.5;
    const wl = wlosy();
    for (let idx = 0; idx < n; idx++){
      const s = szwy[idx];
      const C = s.C != null ? s.C : 0.4;
      if (C < THETA) continue;             // poniżej progu nic nie zaistnieje
      const r = rnd(hash("wezel" + ksywa + idx));
      const x = W * 0.04 + rozstaw * idx;
      const bpmCel = s.b || s.a || 128;
      const enCel = s.eb != null ? s.eb : 0.5;
      const oknoBpm = 9 + 26 * C;          // węzeł garnie WĄSKI pęk włosów
      const zasEn = 0.18 + 0.26 * C;
      // z daleka splot jest ciasny: szerokość skaluje się rozstawem
      // przejść, nie ekranem
      const szer = rozstaw * (1.1 + 1.5 * C);
      let sw = 0, sy = 0;
      for (const w of wl){
        const z = przyleglosc(w, bpmCel, enCel, oknoBpm, zasEn);
        if (z <= 0) continue;
        const wag = z * (0.3 + w.g);
        sw += wag; sy += wag * w.y0;
      }
      if (sw <= 0) continue;
      lista.push({idx, x, bpmA: s.a || bpmCel, bpmB: bpmCel,
        bpmCel, enCel, C, oknoBpm, zasEn, szer,
        yLuzne: sy / sw, yOs: sy / sw, dojrz: 0, Syn: s.Syn || 0,
        promien: Math.min(H * 0.045, rozstaw * 2.0) + H * 0.004,
        skret: 0.8 + r() * 0.7, faz: r() * 6.283});
    }
    // WĘZŁY ODDZIAŁUJĄ NA SIEBIE — sąsiedzi ciągną się nawzajem, aż
    // powstaje jeden sznur. W klatce mieszamy luźne ze związanym wg
    // dojrzałości, więc schodzenie się widać w ruchu.
    const zwiazane = lista.map(w => w.yLuzne);
    for (let it = 0; it < 4; it++){
      const kopie = zwiazane.slice();
      for (let ia = 0; ia < lista.length; ia++){
        let sw = 0, sy = 0;
        for (let ib = Math.max(0, ia - 8);
             ib < Math.min(lista.length, ia + 9); ib++){
          if (ia === ib) continue;
          const dx = Math.abs(lista[ia].x - lista[ib].x) / (rozstaw * 9);
          const dy = Math.abs(kopie[ia] - kopie[ib]) / (H * 0.30);
          const blisko = Math.max(0, 1 - Math.hypot(dx, dy));
          if (blisko <= 0) continue;
          const wag = blisko * (0.35 + lista[ib].C);
          sw += wag; sy += wag * kopie[ib];
        }
        if (sw > 0) zwiazane[ia] = kopie[ia] + (sy / sw - kopie[ia]) * 0.40;
      }
    }
    lista.forEach((w, i) => { w.yZwiazane = zwiazane[i]; });

    /* Przy widoku całej drogi jeden szew ma kilka pikseli — osobnych
       warkoczy nie da się narysować i nie o to chodzi. Właściwy obiekt
       to JEDEN ciągły sznur, zaciskający się tam, gdzie sprzężenie było
       mocne. Wypalamy jego profil wzdłuż płótna: gdzie leży oś, jak jest
       ciasny i który włos do niego należy w którym miejscu. */
    const KROKX = 4, NX = Math.ceil((W + 80) / KROKX) + 1, X0 = -40;
    const osLuzne = new Float32Array(NX), osZwiaz = new Float32Array(NX);
    const cLok = new Float32Array(NX), wagaKol = new Float32Array(NX);
    const rekrut = wl.map(() => new Float32Array(NX));
    const indeks = new Map(); wl.forEach((w, i) => indeks.set(w.i, i));
    for (const wz of lista){
      const zas = wz.szer * 1.7;
      const od = Math.max(0, Math.floor((wz.x - zas - X0) / KROKX));
      const doo = Math.min(NX - 1, Math.ceil((wz.x + zas - X0) / KROKX));
      for (let i = od; i <= doo; i++){
        const x = X0 + i * KROKX;
        const waga = gladko(1 - Math.abs(x - wz.x) / zas);
        if (waga <= 0) continue;
        wagaKol[i] += waga;
        osLuzne[i] += waga * wz.yLuzne;
        osZwiaz[i] += waga * wz.yZwiazane;
        cLok[i] += waga * wz.C;
      }
    }
    for (let i = 0; i < NX; i++){
      if (wagaKol[i] > 0){
        osLuzne[i] /= wagaKol[i]; osZwiaz[i] /= wagaKol[i]; cLok[i] /= wagaKol[i];
      } else { osLuzne[i] = osZwiaz[i] = -1; }
    }
    /* SZNUR MA SZTYWNOŚĆ. Kolejne przejścia potrafią skoczyć ze 140 na
       104 uderzeń, więc surowa oś jest piłą — a jeden sznur nie skręca
       o pół ekranu na dziesięciu pikselach. Po wygładzeniu skoki tempa
       czytają się jako rozluźnienie splotu, nie szarpnięcie w pionie. */
    const wygladz = (tab, promien, razy) => {
      for (let p = 0; p < razy; p++){
        const kop = tab.slice();
        for (let i = 0; i < NX; i++){
          let sum = 0, ile = 0;
          for (let j = Math.max(0, i - promien);
               j <= Math.min(NX - 1, i + promien); j++){
            if (kop[j] < 0) continue;
            sum += kop[j]; ile++;
          }
          if (ile) tab[i] = sum / ile;
        }
      }
    };
    wygladz(osLuzne, 10, 3);
    wygladz(osZwiaz, 16, 3);
    wygladz(cLok, 6, 2);
    // który włos należy do sznura w którym miejscu drogi
    for (const wz of lista){
      const zas = wz.szer * 1.7;
      const od = Math.max(0, Math.floor((wz.x - zas - X0) / KROKX));
      const doo = Math.min(NX - 1, Math.ceil((wz.x + zas - X0) / KROKX));
      for (let hi = 0; hi < wl.length; hi++){
        const z = przyleglosc(wl[hi], wz.bpmCel, wz.enCel, wz.oknoBpm, wz.zasEn);
        if (z <= 0.22) continue;
        const moc = gladko((z - 0.22) / 0.42);
        const tab = rekrut[hi];
        for (let i = od; i <= doo; i++){
          const x = X0 + i * KROKX;
          const waga = gladko(1 - Math.abs(x - wz.x) / zas);
          if (waga > 0) tab[i] = Math.min(1.4, tab[i] + waga * moc);
        }
      }
    }
    /* Przynależność włosa do sznura też musi być CIĄGŁA — surowo liczona
       skacze co przejście i lina wygląda jak grzebień. Pasmo wplecione
       w linę wchodzi w nią i wychodzi powoli. */
    for (const tab of rekrut){
      for (let p = 0; p < 2; p++){
        const kop = tab.slice();
        let suma = 0;
        const R = 12;
        for (let j = 0; j <= Math.min(NX - 1, R); j++) suma += kop[j];
        for (let i = 0; i < NX; i++){
          const od = Math.max(0, i - R), doo = Math.min(NX - 1, i + R);
          tab[i] = suma / (doo - od + 1);
          if (i + R + 1 < NX) suma += kop[i + R + 1];
          if (i - R >= 0) suma -= kop[i - R];
        }
      }
    }
    const wSznurze = new Set();
    rekrut.forEach((tab, hi) => {
      for (let i = 0; i < NX; i++)
        if (tab[i] > 0.02){ wSznurze.add(wl[hi].i); break; }
    });
    PAM = {ksywa, W, H, lista, rozstaw, wSznurze,
           KROKX, NX, X0, osLuzne, osZwiaz, cLok, rekrut, indeks,
           dojrz: new Float32Array(NX)};
    return PAM;
  }

  function wezly(k){
    const szwy = k.szwy;
    if (!szwy.length) return null;
    const st = statyczne(szwy);
    if (!st.lista.length) return null;
    const faza = k.frakcja != null ? Math.max(0, Math.min(1, k.frakcja))
                                   : ((k.czas / CYKL) + START) % 1;
    const punktX = W * faza;
    const OGON = Math.max(40, W * 0.05);
    for (let i = 0; i < st.NX; i++)
      st.dojrz[i] = gladko((punktX - (st.X0 + i * st.KROKX) + OGON) / (OGON * 1.6));
    for (const wz of st.lista){
      wz.dojrz = gladko((punktX - wz.x + OGON) / (OGON * 1.6));
      wz.yOs = wz.yLuzne + (wz.yZwiazane - wz.yLuzne) * wz.dojrz;
    }
    /* KROPKA JAK MAGNES: w jej miejscu sznur zaciska się w jeden punkt,
       więc każda nić potrzebna do setu przez nią przechodzi. */
    const ip = Math.max(0, Math.min(st.NX - 1,
      Math.round((punktX - st.X0) / st.KROKX)));
    const osPunkt = st.osLuzne[ip] >= 0
      ? st.osLuzne[ip] + (st.osZwiaz[ip] - st.osLuzne[ip]) * st.dojrz[ip]
      : null;
    return {st, lista: st.lista, rozstaw: st.rozstaw, punktX, faza,
            osPunkt, promienMagnesu: Math.max(48, H * 0.085)};
  }

  /* RAMA F — co jest osiągalne TERAZ */
  function rama(k){
    const WZ = k.wz;
    if (!WZ || !ZASIEG || !WZ.lista.length) return null;
    const x = WZ.punktX;
    let nast = null, poprz = null;
    for (const wz of WZ.lista){
      if (wz.x >= x){ if (!nast || wz.x < nast.x) nast = wz; }
      else          { if (!poprz || wz.x > poprz.x) poprz = wz; }
    }
    const grajacy = poprz ? poprz.bpmB : (nast ? nast.bpmA : null);
    const nadchodzi = nast ? nast.bpmB : null;
    /* Widać CAŁĄ noc naraz, więc przejścia leżą kilka pikseli od siebie.
       Gdyby rama oddychała przy każdym z osobna, pas bursztynu migałby
       kilka razy na sekundę. Ostrość jest więc stała, a moment przejścia
       niesie sam BŁĘKIT: krótki puls, jeden na szew. */
    const gesto = WZ.rozstaw < W * 0.04;
    const oknoSzwu = gesto ? WZ.rozstaw * 0.15 : (nast ? nast.szer * 0.85 : 1);
    const blisko = nast
      ? 1 - Math.min(1, Math.abs(x - nast.x) / ((nast.szer || 1) * 1.7)) : 0;
    const wSzwie = nast ? gladko(1 - Math.abs(x - nast.x) / oknoSzwu) : 0;
    const ostrosc = gesto ? 1.0 : 0.35 + 1.40 * blisko;
    /* POLE NIE MOŻE ZGASNĄĆ CAŁE. Bezwzględna osiągalność potrafi spaść
       do zera dla wszystkiego naraz — pytanie brzmi „co jest osiągalne
       STĄD", nie „ile tego jest". Skalujemy do najlepszego dostępnego. */
    let szczyt = 0;
    if (grajacy != null)
      for (const w of wlosy()){
        const v = zasieg(grajacy, w.bpm);
        if (v > szczyt) szczyt = v;
      }
    const skala = 1 / Math.max(0.30, szczyt);
    const kres = (v) => Math.pow(Math.max(0, Math.min(1, v * skala)), ostrosc);
    return {grajacy, nadchodzi, blisko, wSzwie, ostrosc,
      dlaWlosa(w){
        if (grajacy == null) return {R: 1, a: 1, b: 0};
        const ra = kres(zasieg(grajacy, w.bpm));
        const rb = (nadchodzi != null && wSzwie > 0)
          ? kres(zasieg(nadchodzi, w.bpm)) * wSzwie : 0;
        return {R: Math.max(ra, rb), a: ra, b: rb};
      }};
  }

  /* zagięcie włosa w sznur — same odczyty z wypalonego profilu */
  function zagnij(k, w, x, wlasna, R){
    const WZ = k.wz;
    if (!WZ) return [wlasna, 0];
    const st = WZ.st;
    const i = Math.round((x - st.X0) / st.KROKX);
    if (i < 0 || i >= st.NX) return [wlasna, 0];
    const hi = st.indeks.get(w.i);
    if (hi === undefined) return [wlasna, 0];
    const nalezy = st.rekrut[hi][i];
    if (nalezy <= 0.002) return [wlasna, 0];
    const dojrz = st.dojrz[i];
    if (dojrz <= 0.01) return [wlasna, 0];
    /* POTRZEBNA znaczy też OSIĄGALNA — ale TYLKO TAM, GDZIE ZAPADA
       DECYZJA. Droga już przebyta jest historią i nie rozplata się
       wstecz dlatego, że DJ wszedł na tempo, z którego mało co widać. */
    const swieze = gladko(1 - (WZ.punktX - x) / (WZ.promienMagnesu * 3));
    const brama = 1 - swieze * (0.85 - 0.85 * (R == null ? 1 : R));
    const moc = nalezy * dojrz * brama;
    const os = st.osLuzne[i] + (st.osZwiaz[i] - st.osLuzne[i]) * dojrz;
    if (os < 0) return [wlasna, 0];
    const promien = H * 0.042 * (1.3 - 0.9 * st.cLok[i]) * (1 - 0.30 * dojrz);
    /* TRZY PASMA, nie sto trzydzieści osobnych helis: faza zależy od
       pasma (0°/120°/240°), a NIE od włosa — inaczej każdy kręci się we
       własnej fazie i zamiast warkocza wychodzi wiązka równoległych
       falek. Włos dostaje tylko odrobinę rozrzutu na grubość pasma. */
    const kat = x * SKRET + w.pasmo * 2.0944 + w.wpasmie * 0.45;
    const potrzebny = gladko((nalezy - 0.30) / 0.35)
                    * (0.30 + 0.70 * (R == null ? 1 : R));
    const magnes = (WZ.osPunkt == null || potrzebny <= 0) ? 0
      : gladko(1 - Math.abs(x - WZ.punktX) / WZ.promienMagnesu) * potrzebny;
    const owin = Math.sin(kat) * promien * (1 - 0.95 * magnes);
    let cel = os + owin + Math.sin(x * 0.004 + k.czas * 0.15) * H * 0.008;
    if (magnes > 0) cel += (WZ.osPunkt - cel) * magnes;
    /* NIE WYRYWAMY WŁOSA Z DRUGIEJ STRONY GŁOWY — ale ten w zasięgu ręki
       wchodzi w sznur DO KOŃCA. Agresja magnesu siedzi w ostrości
       zejścia, nie w tym, jak daleko sięga. */
    const d = Math.abs(wlasna - cel);
    const zasiegRek = H * (0.10 + 0.02 * magnes);
    const kara = 1 - gladko((d - zasiegRek) / (zasiegRek * 0.95));
    if (kara <= 0) return [wlasna, 0];
    const przyciag = Math.min(1, moc * 1.45 + magnes * 0.9) * kara;
    return [wlasna + (cel - wlasna) * przyciag,
            Math.min(1.4, (moc + magnes * 0.5) * kara)];
  }

  function warstwaMozliwosci(k){
    if (!POLE) return;
    const czas = k.czas;
    for (const w of wlosy()){
      const F = k.rama ? k.rama.dlaWlosa(w) : {R: 1, a: 1, b: 0};
      const wRamie = 0.34 + 1.90 * F.R;
      let cr = 112 + (224 - 112) * F.a;
      let cg = 118 + (164 - 118) * F.a;
      let cb = 132 + (88 - 132) * F.a;
      // błękit bierze to, czego NIE dało się zagrać przed wejściem B
      const nb = F.b * (1 - 0.55 * F.a);
      cr += (109 - cr) * nb; cg += (179 - cg) * nb; cb += (201 - cb) * nb;
      const wSznurze = k.wz && k.wz.st.wSznurze.has(w.i);
      const KROK_X = wSznurze ? 4 : 14;
      /* Rysujemy PASMAMI jednego koloru, nie odcinek po odcinku — inaczej
         przy całej drodze wychodzi ~88 tys. pociągnięć na klatkę. */
      const STOPNIE = 6;
      let stopien = -1;
      const zamknij = (st) => {
        const sc = Math.pow((st + 0.5) / STOPNIE, 1.7);
        const sr = (st + 0.5) / STOPNIE;
        const cR = Math.round(cr + (214 - cr) * sc);
        const cG = Math.round(cg + (245 - cg) * sc);
        const cB = Math.round(cb + (73 - cb) * sc);
        // CO SIĘ ZAPLOTŁO, ZOSTAJE — sznur ma jasność niezależną od ramy
        const wR = Math.max(wRamie, 0.45 + 1.25 * sr);
        const a = (0.02 + w.g * 0.22) * (1 + sr * sr * 2.2) * wR
                * (1 + 0.85 * nb);
        ctx.strokeStyle = `rgba(${cR},${cG},${cB},${Math.min(0.8, a).toFixed(3)})`;
        ctx.lineWidth = (0.4 + w.g * 1.8) * (1 + sr * 0.7) * GRUBOSC;
        ctx.stroke();
      };
      ctx.beginPath();
      let ostX = 0, ostY = 0;
      for (let x = -40; x <= W + 40; x += KROK_X){
        const u = x / W;
        const wlasna = w.y0
          + Math.sin(u * 5.2 + w.faza + czas * w.dryf) * w.amp
          + Math.sin(u * 11.7 + w.faza * 2 - czas * w.dryf * 0.6) * w.amp * 0.45;
        const para = wSznurze ? zagnij(k, w, x, wlasna, F.R) : [wlasna, 0];
        const y = para[0], s = para[1];
        const st = Math.min(STOPNIE - 1, Math.floor(Math.min(1, s) * STOPNIE));
        if (st !== stopien){
          if (stopien >= 0){ ctx.lineTo(x, y); zamknij(stopien); }
          ctx.beginPath(); ctx.moveTo(x, y); stopien = st;
        } else ctx.lineTo(x, y);
        ostX = x; ostY = y;
      }
      if (stopien >= 0){ ctx.lineTo(ostX, ostY); zamknij(stopien); }
    }
  }

  function warstwaKropka(k){
    const WZ = k.wz;
    if (!WZ) return;
    // kropka stoi DOKŁADNIE na osi sznura — inaczej magnes ściągałby
    // nici obok niej, a mają się spotkać w niej
    const x = WZ.punktX;
    const y = WZ.osPunkt != null ? WZ.osPunkt : H * 0.5;
    const puls = 0.8 + 0.2 * Math.sin(k.czas * 2.4);
    const rr = H * 0.014 * puls;
    const gg = ctx.createRadialGradient(x, y, 0, x, y, rr * 4);
    gg.addColorStop(0, "rgba(255,255,255,0.6)");
    gg.addColorStop(0.35, "rgba(255,228,150,0.14)");
    gg.addColorStop(1, "rgba(255,228,150,0)");
    ctx.fillStyle = gg;
    ctx.fillRect(x - rr * 4, y - rr * 4, rr * 8, rr * 8);
    ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.beginPath(); ctx.arc(x, y, 2.2, 0, 6.283); ctx.fill();
  }

  function kontekst(czas, stan){
    const szwy = (SZWY && SZWY[ksywa]) || [];
    const k = {czas, szwy, W, H,
               frakcja: stan && stan.frakcja != null ? stan.frakcja : null};
    k.wz = wezly(k);
    k.rama = rama(k);
    return k;
  }

  return {
    get ksywa(){ return ksywa; },
    /* zmiana DJ-a: profil sznura trzeba wypalić od nowa */
    ustawDJ(nowa){ if (nowa && nowa !== ksywa){ ksywa = nowa; PAM = null; } },
    wymiary,
    /* czasSek — zegar w sekundach; stan.frakcja — pozycja w secie (0..1),
       null = pętla własna; stan.glosnosc — 0..1, steruje GRUBOŚCIĄ włókien
       (przy domyślnej 0,8 grubość jest taka jak w spoczynku, do 2× przy
       maksimum), null/undefined = spoczynek */
    rysuj(czasSek, stan){
      wymiary();
      if (!W || !H || !SZWY) return null;
      const vol = stan && stan.glosnosc != null ? stan.glosnosc : null;
      GRUBOSC = vol == null ? 1
        : vol <= 0.8 ? 0.55 + 0.5625 * vol
        : 1 + 5 * (vol - 0.8);
      ctx.clearRect(0, 0, W, H);
      const k = kontekst(czasSek, stan);
      warstwaMozliwosci(k);
      warstwaKropka(k);
      return k;
    },
    /* do testów i podpisów: co gra, co wchodzi, gdzie jest kropka */
    stanChwili(czasSek, stan){
      wymiary();
      if (!W || !H || !SZWY) return null;
      const k = kontekst(czasSek, stan);
      return {gra: k.rama ? k.rama.grajacy : null,
              wchodzi: k.rama ? k.rama.nadchodzi : null,
              wSzwie: k.rama ? k.rama.wSzwie : 0,
              punktX: k.wz ? k.wz.punktX : null,
              wezlow: k.wz ? k.wz.lista.length : 0,
              przejsc: k.szwy.length};
    },
  };
}

return {wczytaj, stworz, ksywy, THETA,
        get dane(){ return {POLE, ZASIEG, SZWY}; }};
})();

if (typeof module !== "undefined") module.exports = PortretVJ;
