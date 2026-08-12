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
      kat: i * 2.39996 + r() * 0.5,          // kąt złoty — brak stron świata
      przechyl: (r() - 0.5) * 0.9,
      promien: 0.24 + 0.66 * T01((s.a + s.b) / 2),
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
  widoczne.sort((a, b) => b.wiek - a.wiek);   // od najgłębszych

  const rt = rnd(hash(d.ksywa + "klatka"));
  for (const {i, wiek} of widoczne){
    const z = ziarnoZ(wiek);
    const s = P.ziarna[i];
    const persp = OKO / (OKO + z * SKALA * 0.9);
    if (persp < 0.03) continue;
    const kat = s.kat + obrot + s.dryf * Math.sin(czas * 0.3 + s.f);
    const prom = s.promien * SKALA * (0.55 + 0.45 * Math.sin(czas * 0.22 + s.f));
    const X = cx + Math.cos(kat) * prom * persp;
    const Y = cy + Math.sin(kat) * prom * persp * (0.62 + s.przechyl * 0.2);
    // zapowiedź przyszłości: zakrzywiona, ledwie zarysowana
    const zapowiedz = wiek < 0;
    const swiezosc = Math.max(0, 1 - Math.abs(wiek) / 1.6);
    const zycie = zapowiedz ? swiezosc * 0.22
      : Math.max(0.10, Math.pow(1 - Math.min(1, wiek / P.n), 0.55));
    const alfa = zycie * (0.32 + swiezosc * 0.6) * (s.perf ? 1.25 : 1);
    if (alfa < 0.008) continue;
    ctx.strokeStyle = `rgba(${s.c[0]},${s.c[1]},${s.c[2]},${Math.min(0.95, alfa).toFixed(3)})`;
    ctx.lineWidth = Math.max(0.35, (s.perf ? 1.15 : 0.85) * gr * persp);
    const drzenie = s.czysty ? 0.12 : 0.9;
    for (let k = 0; k < s.nitek; k++){
      let x = X + (rt() - 0.5) * SKALA * s.rozrzut * persp;
      let y = Y + (rt() - 0.5) * SKALA * s.rozrzut * persp;
      const krok = 2.4 * persp * (Math.min(W, H) / 300);
      ctx.beginPath(); ctx.moveTo(x, y);
      for (let j = 0; j < s.dl; j++){
        const kier = pole(x - cx, y - cy, czas, P.wzburzenie, s.f)
                     + (rt() - 0.5) * drzenie;
        x += Math.cos(kier) * krok; y += Math.sin(kier) * krok;
        ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    // splot: dwa tempa związane w chwili miksu — tylko gdy blisko teraz
    if (!zapowiedz && wiek < 0.9){
      const moc = (1 - wiek / 0.9) * persp;
      const dlS = 16 * persp * (1 + moc);
      for (const znak of [1, -1]){
        ctx.strokeStyle = `rgba(255,255,255,${(0.3 * moc).toFixed(3)})`;
        ctx.lineWidth = 0.8 * persp * gr;
        ctx.beginPath();
        for (let t = 0; t <= 18; t++){
          const u = t / 18;
          const px = X - dlS + dlS * 2 * u;
          const py = Y + Math.sin(u * 12.6 + (znak > 0 ? 0 : 3.14))
                         * dlS * 0.34 * znak * Math.sin(u * 3.14);
          t === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
        }
        ctx.stroke();
      }
      if (s.jedyny && moc > 0.5){       // splot jedyny w całej mapie
        ctx.strokeStyle = `rgba(255,255,255,${(0.45 * (moc - 0.5) * 2).toFixed(3)})`;
        ctx.lineWidth = 0.7;
        ctx.beginPath(); ctx.arc(X, Y, dlS * 0.75, 0, 6.283); ctx.stroke();
      }
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
  return wiek >= 0 ? Math.pow(wiek, 0.62) * 0.085 : wiek * 0.4;
}

/* wspólne pole ruchu — po nim płyną wszystkie włókna, dlatego układają
   się w jedną tkaninę zamiast w osobne wstęgi */
function pole(x, y, czas, wzburzenie, faza){
  return (Math.sin(x * 0.0055 + faza) + Math.cos(y * 0.0061 + czas * 0.25)
          + Math.sin((x + y) * 0.0037 + czas * 0.15)) * wzburzenie;
}
