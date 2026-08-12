/* PORTRET BRZMIENIA — WSPÓLNY KOD karty i sceny (jedno źródło, zero kopii).

   Przestrzeń, nie oś (Janek 13.08): „w przestrzeni nie ma góry ani dołu,
   lewa ani prawa. Mixowanie odbywa się zawsze TU I TERAZ. Przeszłość
   zostawia ślad, przyszłość może być tylko zakrzywioną predykcją."

   Stąd:
   · cisza to PRÓŻNIA — zanim dźwięk padnie, nie ma tam nic (nie „ciemno");
   · DJ jest w centrum, nieruchomy w swoim teraz; to noc przez niego płynie;
   · każde przejście rodzi się BLISKO (jasne, duże) i odpływa W GŁĄB,
     malejąc i gasnąc — ślad przeszłości, nigdy wymazany do zera;
   · włókna dryfują wokół osi jak pył gwiezdny — raz bliżej, raz dalej;
   · przyszłość istnieje tylko jako zakrzywiona zapowiedź tuż przed DJ-em.

   Wszystko z pomiarów: nić = jedno przejście między utworami, kolor = jego
   tempo, volt = tonacje idealne, strzęp = zgrzyt, promień = tempo,
   głośność = grubość pędzla. Deterministyczne: ziarno z ksywy DJ-a. */

function hash(s){let h=7; for(const c of s) h=(h*31+c.charCodeAt(0))|0; return h>>>0||1}
function rnd(seed){let s=seed; return ()=>{s^=s<<13; s^=s>>>17; s^=s<<5; return (s>>>0)/4294967296}}

let SZWY = {};                 // sekwencje przejść doładowują się z pliku
const PRZESTRZEN = {};

const T01 = v => Math.max(0, Math.min(1, (v - 95) / 95));
const ZGODNE = new Set(["idealna", "sasiednia", "rownolegla"]);
const CHLODNY = [96, 196, 228], CIEPLY = [235, 166, 72], VOLT = [214, 245, 73];
const BARWA = t => {
  const s = t * t * (3 - 2 * t);
  return CHLODNY.map((v, i) => Math.round(v + (CIEPLY[i] - v) * s));
};

/* Rozkład przejść w przestrzeni: kąt złoty rozsypuje je równomiernie
   po sferze (żadna strona nie jest wyróżniona), promień niesie tempo,
   a własne ziarno daje każdemu jego dryf. */
function przestrzen(ksywa, szwy){
  const kl = ksywa + "#" + szwy.length;
  if (PRZESTRZEN[kl]) return PRZESTRZEN[kl];
  const r = rnd(hash(ksywa + "przestrzen"));
  const skoki = szwy.map(s => Math.abs(s.d || 0));
  const srSkok = skoki.reduce((a, b) => a + b, 0) / Math.max(1, skoki.length);
  const wzburzenie = 0.35 + Math.min(srSkok / 20, 1) * 1.5;
  const ziarna = szwy.map((s, i) => {
    const perf = s.h === "idealna", czysty = ZGODNE.has(s.h);
    return {
      kat: i * 0.34 + (r() - 0.5) * 0.22,     // spirala: ciąg, nie zygzak
      przechyl: (r() - 0.5) * 0.9,
      promien: 0.30 + 0.85 * T01((s.a + s.b) / 2),
      dryf: (r() - 0.5) * 0.22,
      perf, czysty,
      c: perf ? VOLT : BARWA(T01((s.a + s.b) / 2)),
      nitek: perf ? 7 : czysty ? 5 : 3,
      dl: perf ? 46 : czysty ? 38 : 12,
      rozrzut: (perf ? 0.05 : czysty ? 0.08 : 0.22) + Math.min(Math.abs(s.d || 0), 30) / 160,
      f: r() * 6.28,
      jedyny: (s.uni ?? 1) === 1,
    };
  });
  return PRZESTRZEN[kl] = {ziarna, wzburzenie, n: szwy.length};
}

function portret(cv, d, czas = 0, frakcja = null, vol = null){
  const ctx = cv.getContext("2d");
  const DPR = Math.min(2, devicePixelRatio || 1);
  const W = Math.max(200, Math.round(cv.clientWidth || 600));
  const H = Math.max(80, Math.round(cv.clientHeight || 208));
  if (cv.width !== Math.round(W * DPR) || cv.height !== Math.round(H * DPR)){
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
  }
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.clearRect(0, 0, W, H);

  const gr = vol == null ? 1
    : vol <= 0.8 ? 0.3 + 2.2 * vol
    : 2.06 + (vol - 0.8) * 14.7;              // szczyt suwaka: pędzel ×2
  const wszystkie = SZWY[d.ksywa] || [];
  const szwy = (frakcja != null && d.grany != null)
    ? wszystkie.filter(s => s.set === d.grany) : wszystkie;
  const cx = W / 2, cy = H / 2;
  const OKO = Math.min(W, H) * 1.15;          // ogniskowa: siła perspektywy
  const SKALA = Math.min(W, H) * 0.46;

  if (!szwy.length){                          // brak sekwencji = uczciwa cisza
    ctx.strokeStyle = "rgba(58,55,48,0.5)"; ctx.setLineDash([5, 6]);
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(W * 0.1, cy); ctx.lineTo(W * 0.9, cy); ctx.stroke();
    ctx.setLineDash([]);
    return;
  }
  const P = przestrzen(d.ksywa, szwy);
  const teraz = frakcja != null ? frakcja * P.n : ((czas / 22) % 1) * P.n;
  const obrot = czas * 0.055;                 // chmura wiecznie w ruchu

  // --- warstwy od najdalszych: przeszłość maluje się pierwsza ---
  const widoczne = [];
  for (let i = 0; i < P.n; i++){
    const wiek = teraz - i;                   // >0 przeszłość, <0 przyszłość
    if (wiek < -1.6) continue;                // dalej niż zapowiedź = PRÓŻNIA
    widoczne.push({i, wiek});
  }
  widoczne.sort((a, b) => b.wiek - a.wiek);   // od najgłębszych ku teraz

  // === JEDEN CIĄG (Janek 13.08: „to nie ma być pocięte spaghetti —
  // to ciąg rozrastających się możliwości skupianych w jedną
  // rzeczywistość"). Nić nie urywa się na przejściu: biegnie przez nie
  // dalej, tylko zmienia barwę i grubość. Z każdego węzła wyrastają
  // możliwości, które gasną — a rzeczywistość płynie nieprzerwanie. ===
  const rt = rnd(hash(d.ksywa + "klatka"));
  const punkty = widoczne.map(({i, wiek}) => {
    const s = P.ziarna[i];
    const z = ziarnoZ(wiek);
    const persp = OKO / (OKO + z * SKALA * 0.9);
    const kat = s.kat + obrot + s.dryf * Math.sin(czas * 0.3 + s.f);
    const prom = s.promien * SKALA * (0.55 + 0.45 * Math.sin(czas * 0.22 + s.f));
    return {
      i, wiek, s, persp,
      x: cx + Math.cos(kat) * prom * persp,
      y: cy + Math.sin(kat) * prom * persp * (0.62 + s.przechyl * 0.2),
      zapowiedz: wiek < 0,
      swiez: Math.max(0, 1 - Math.abs(wiek) / 1.6),
      zycie: wiek < 0 ? 0.22 : Math.max(0.1, Math.pow(1 - Math.min(1, wiek / P.n), 0.55)),
    };
  });

  // 1 · MOŻLIWOŚCI: z każdego węzła rozrastają się i wygasają
  for (const p of punkty){
    if (p.zapowiedz || p.persp < 0.05) continue;
    const ile = 3 + Math.round(p.s.rozrzut * 14);
    const dl = SKALA * 0.16 * p.persp * (0.4 + p.swiez);
    for (let k = 0; k < ile; k++){
      const rozejscie = (rt() - 0.5) * 2.2;
      const a = 0.11 * p.zycie * (0.25 + p.swiez * 0.9);
      if (a < 0.006) continue;
      ctx.strokeStyle = `rgba(${p.s.c[0]},${p.s.c[1]},${p.s.c[2]},${a.toFixed(3)})`;
      ctx.lineWidth = Math.max(0.3, 0.55 * p.persp * gr);
      let x = p.x, y = p.y, kier = rozejscie;
      ctx.beginPath(); ctx.moveTo(x, y);
      for (let j = 0; j < 10; j++){
        kier += (rt() - 0.5) * 0.55
                + pole(x - cx, y - cy, czas, P.wzburzenie, p.s.f) * 0.25;
        x += Math.cos(kier) * dl / 10; y += Math.sin(kier) * dl / 10;
        ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }

  // 2 · RZECZYWISTOŚĆ: nieprzerwany ciąg przez wszystkie węzły,
  //     splecione pasma — grubieje i jaśnieje, im bliżej teraz
  const PASM = 5;
  for (let pas = 0; pas < PASM; pas++){
    const przes = (pas - (PASM - 1) / 2) * 0.9;
    const fazaPas = pas * 1.7;
    for (let k = 0; k < punkty.length - 1; k++){
      const a = punkty[k], b = punkty[k + 1];
      if (a.persp < 0.03) continue;
      const alfa = Math.min(0.95, b.zycie * (0.30 + b.swiez * 0.55)
                                  * (b.s.perf ? 1.3 : 1) * (pas === 2 ? 1.25 : 0.7));
      if (alfa < 0.008) continue;
      const c = b.zapowiedz ? [140, 140, 140] : b.s.c;
      ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${alfa.toFixed(3)})`;
      ctx.lineWidth = Math.max(0.3, (b.s.perf ? 1.5 : 1.0) * gr * b.persp
                                    * (pas === 2 ? 1.35 : 0.8));
      const rozp = SKALA * 0.055;         // rozplot pasm — warkocz nici
      const oa = Math.sin(a.i * 0.7 + fazaPas + czas * 0.4) * przes * rozp * a.persp;
      const ob = Math.sin(b.i * 0.7 + fazaPas + czas * 0.4) * przes * rozp * b.persp;
      const ax = a.x, ay = a.y + oa, bx = b.x, by = b.y + ob;
      const mx = (ax + bx) / 2 + (ay - by) * 0.16;
      const my = (ay + by) / 2 + (bx - ax) * 0.16;
      ctx.beginPath(); ctx.moveTo(ax, ay);
      ctx.quadraticCurveTo(mx, my, bx, by);
      ctx.stroke();
    }
  }

  // 3 · SPLOT w chwili miksu — dwa tempa związane na zawsze
  for (const p of punkty){
    if (p.zapowiedz || p.wiek > 0.9 || p.persp < 0.06) continue;
    const moc = (1 - p.wiek / 0.9) * p.persp;
    const dlS = SKALA * 0.045 * p.persp * (1 + moc);
    for (const znak of [1, -1]){
      ctx.strokeStyle = `rgba(255,255,255,${(0.32 * moc).toFixed(3)})`;
      ctx.lineWidth = 0.8 * p.persp * gr;
      ctx.beginPath();
      for (let q = 0; q <= 18; q++){
        const u = q / 18;
        const px = p.x - dlS + dlS * 2 * u;
        const py = p.y + Math.sin(u * 12.6 + (znak > 0 ? 0 : 3.14))
                         * dlS * 0.4 * znak * Math.sin(u * 3.14);
        q === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
    if (p.s.jedyny && moc > 0.5){
      ctx.strokeStyle = `rgba(255,255,255,${(0.4 * (moc - 0.5) * 2).toFixed(3)})`;
      ctx.lineWidth = 0.7;
      ctx.beginPath(); ctx.arc(p.x, p.y, dlS * 0.85, 0, 6.283); ctx.stroke();
    }
  }

  // --- DJ: nieruchomy w swoim TERAZ, w środku przestrzeni ---
  const puls = 0.82 + 0.18 * Math.sin(czas * 2.2);
  const rr = Math.min(W, H) * 0.05 * puls;
  const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rr * 3);
  g.addColorStop(0, "rgba(255,255,255,0.55)");
  g.addColorStop(0.35, "rgba(232,228,218,0.14)");
  g.addColorStop(1, "rgba(232,228,218,0)");
  ctx.fillStyle = g;
  ctx.fillRect(cx - rr * 3, cy - rr * 3, rr * 6, rr * 6);
  ctx.fillStyle = "rgba(255,255,255,0.9)";
  ctx.beginPath(); ctx.arc(cx, cy, Math.max(1.2, rr * 0.16), 0, 6.283); ctx.fill();
}

/* przeszłość oddala się coraz wolniej — bliskie zdarzenia rozdzielone
   wyraźnie, dawne zbijają się w mgłę pyłu */
function ziarnoZ(wiek){
  return wiek >= 0 ? Math.pow(wiek, 0.78) * 0.16 : wiek * 0.5;
}

/* wspólne pole ruchu — po nim płyną wszystkie włókna, dlatego układają
   się w jedną tkaninę zamiast w osobne wstęgi */
function pole(x, y, czas, wzburzenie, faza){
  return (Math.sin(x * 0.0055 + faza) + Math.cos(y * 0.0061 + czas * 0.25)
          + Math.sin((x + y) * 0.0037 + czas * 0.15)) * wzburzenie;
}
