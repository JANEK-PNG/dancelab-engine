/* PORTRET SZWU — Design in Between, narysowany wzorem.

   P = (C, D, Syn, U)  liczone PRZEZ RAMĘ F, na horyzoncie tau, z progiem theta.

   Nie mierzymy utworu A ani utworu B. Mierzymy TO, CO MIĘDZY NIMI — dlatego
   utwory są tu tylko BRZEGAMI (cienkie krawędzie), a całym ciałem obrazu jest
   pole relacji między nimi:

   · C   = i_HS + i_SH — całkowite sprzężenie. Ile w ogóle materii jest
           pomiędzy. Niskie C = dwa równoległe monologi, choćby trwały godzinę.
   · D   = ln(i_HS / i_SH) — kto prowadzi. Przechylenie pola ku brzegowi.
           GDY C < theta, D NIE JEST LICZONE: pole zostaje nierozstrzygnięte,
           a nie „symetryczne" — brak relacji to nie jest relacja symetryczna.
   · Syn = to, czego nie ma w żadnej stronie osobno. Włókna, które nie dotykają
           żadnego brzegu: powstały w środku i nigdzie indziej nie istnieją.
   · U   = C / K — ile z osiągalnego w tej ramie naprawdę się dzieje.
           Kontur K rysujemy zawsze: widać, ile było możliwe, a ile zaszło.

   Rama F to to, co DJ ustawia przy deckach: co słychać, co wyciszone, jak
   długo trwa nakładanie. Zmiana ramy przesuwa CAŁY profil (Delta_F P).

   Głębia: każdy przebyty szew odpływa w tył, nigdy nie znika. Przed nami
   próżnia — przyszłość istnieje tylko jako zakrzywiona zapowiedź. */

function hash(s){let h=7; for(const c of s) h=(h*31+c.charCodeAt(0))|0; return h>>>0||1}
function rnd(seed){let s=seed; return ()=>{s^=s<<13; s^=s>>>17; s^=s<<5; return (s>>>0)/4294967296}}

let SZWY = {};
const THETA = 0.18;                       // próg: poniżej D nieokreślone
const T01 = v => Math.max(0, Math.min(1, (v - 95) / 95));
const CHLODNY = [96, 196, 228], CIEPLY = [235, 166, 72], VOLT = [214, 245, 73];
const BARWA = t => {
  const s = t * t * (3 - 2 * t);
  return CHLODNY.map((v, i) => Math.round(v + (CIEPLY[i] - v) * s));
};

/* Profil relacji jednego szwu — z tego, co mapa NAPRAWDĘ ma: tonacje,
   tempa, energie, groove i bas obu stron. Czego nie zmierzyliśmy, tego
   nie zgadujemy — brak wchodzi jako nieznane, nie jako wartość. */
function profilP(s, poprz){
  const H = {idealna: 1, sasiednia: 0.8, rownolegla: 0.74, wzgledna: 0.5,
             zadna: 0.12}[s.h] ?? 0.3;
  const tempoBl = 1 - Math.min(Math.abs(s.d || 0) / 24, 1);
  const eA = poprz.eb, eB = s.eb, gA = poprz.gb, gB = s.gb, bA = poprz.bb, bB = s.bb;
  const zn = (x, y) => (x == null || y == null) ? null
    : 1 - Math.min(Math.abs(y - x) * 1.5, 1);
  const enBl = zn(eA, eB), grBl = zn(gA, gB), baBl = zn(bA, bB);
  const znane = [enBl, grBl, baBl].filter(v => v != null);
  const cialo = znane.length ? znane.reduce((a, b) => a + b, 0) / znane.length : 0.5;

  // i_HS / i_SH — ile każda strona wnosi w pole; utwór o wyższej energii
  // i gęstszym groovie naciska mocniej. To jest kierunek prowadzenia.
  const sila = (e, g, b) => 0.45 * (e ?? 0.5) + 0.35 * (g ?? 0.5)
                          + 0.20 * (b ?? 0.5) + 0.05;
  const iHS = sila(eA, gA, bA), iSH = sila(eB, gB, bB);

  const C = Math.min(1, 0.42 * H + 0.33 * tempoBl + 0.25 * cialo);
  const okreslone = C >= THETA;
  const D = okreslone ? Math.log(iHS / iSH) : null;

  // Syn — powstaje, gdy strony są DALEKIE od siebie, a mimo to trzymają się
  // harmonicznie: wtedy w szwie jest coś, czego nie ma w żadnej z osobna.
  const odleglosc = Math.min(1, (Math.abs(s.d || 0) / 22) * 0.6
                              + (1 - (grBl ?? 0.5)) * 0.4);
  const Syn = Math.max(0, Math.min(1, odleglosc * H * 1.35));

  const K = Math.max(0.12, 0.42 * H + 0.58);      // osiągalne w tej ramie
  const U = Math.min(1, C / K);
  return {C, D, Syn, U, K, okreslone,
          cA: BARWA(T01(s.a || 128)), cB: BARWA(T01(s.b || 128))};
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
    : vol <= 0.8 ? 0.3 + 2.2 * vol : 2.06 + (vol - 0.8) * 14.7;
  const wszystkie = SZWY[d.ksywa] || [];
  const szwy = (frakcja != null && d.grany != null)
    ? wszystkie.filter(s => s.set === d.grany) : wszystkie;
  const cx = W / 2, cy = H / 2, MIN = Math.min(W, H);

  if (!szwy.length){
    ctx.strokeStyle = "rgba(58,55,48,0.5)"; ctx.setLineDash([5, 6]);
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(W * 0.1, cy); ctx.lineTo(W * 0.9, cy); ctx.stroke();
    ctx.setLineDash([]); return;
  }
  const n = szwy.length;
  const teraz = frakcja != null ? frakcja * n : ((czas / 26) % 1) * n;
  const rt = rnd(hash(d.ksywa + "pole"));

  // przebyte szwy odpływają w głąb — ślad relacji, nigdy wymazany
  const OKO = MIN * 1.2;
  // tunel w głąb: dawne relacje maleją ku środkowi i przygasają,
  // lekko odchylone spiralą — nigdy nie znikają całkiem
  const ILE_WSTECZ = 34;
  for (let k = Math.floor(teraz) - 1; k >= Math.max(0, Math.floor(teraz) - ILE_WSTECZ); k--){
    const wiek = teraz - k;
    const persp = OKO / (OKO + Math.pow(wiek, 0.85) * MIN * 0.42);
    if (persp < 0.05) break;
    const P = profilP(szwy[k], szwy[k - 1] || szwy[k]);
    const kat = k * 0.42 + czas * 0.06;
    const prom = MIN * 0.16 * (1 - persp);
    poleRelacji(ctx, cx + Math.cos(kat) * prom, cy + Math.sin(kat) * prom * 0.6,
                MIN * 0.36 * persp, P, Math.max(0.05, persp * 0.85),
                czas, rt, gr * persp, false);
  }

  // TERAZ — relacja w pełnej skali, w centrum
  const i0 = Math.max(0, Math.min(n - 1, Math.floor(teraz)));
  const P = profilP(szwy[i0], szwy[i0 - 1] || szwy[i0]);
  poleRelacji(ctx, cx, cy, MIN * 0.36, P, 1, czas, rt, gr, true);
}

/* POLE RELACJI — brzegi są tylko krawędziami; ciałem jest to, co pomiędzy. */
function poleRelacji(ctx, cx, cy, R, P, moc, czas, rt, gr, pelne){
  const oddech = 0.94 + 0.06 * Math.sin(czas * 0.9);
  const przechyl = P.okreslone ? Math.max(-0.6, Math.min(0.6, P.D * 0.9)) : 0;

  // 1 · kontur K — ile sprzężenia było w tej ramie OSIĄGALNE
  ctx.setLineDash([3, 5]);
  ctx.strokeStyle = `rgba(140,136,126,${(0.22 * moc).toFixed(3)})`;
  ctx.lineWidth = 0.7;
  ctx.beginPath();
  ctx.ellipse(cx, cy, R * P.K * oddech, R * 0.6 * P.K * oddech, 0, 0, 6.283);
  ctx.stroke(); ctx.setLineDash([]);

  // 2 · brzegi — utwory jako krawędzie pola, nie bohaterowie
  for (const [znak, c] of [[-1, P.cA], [1, P.cB]]){
    ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${(0.5 * moc).toFixed(3)})`;
    ctx.lineWidth = Math.max(0.6, 1.3 * gr);
    ctx.beginPath();
    ctx.ellipse(cx + znak * R * 0.97, cy, R * 0.09, R * 0.48, 0,
                znak > 0 ? 1.95 : -1.19, znak > 0 ? 4.33 : 1.19);
    ctx.stroke();
  }

  // 3 · C — materia sprzężenia: włókna biegnące MIĘDZY brzegami; ich liczba
  //     to C, rozpiętość w pionie to U, przechylenie ku prowadzącemu to D
  const ile = Math.round((4 + P.C * 60) * (pelne ? 1 : 0.3));
  for (let k = 0; k < ile; k++){
    const u = rt();
    const y0 = cy + (rt() - 0.5) * R * 0.95 * P.U;
    const wyg = (rt() - 0.5) * R * 0.3 + przechyl * R * 0.42;
    const c = u < 0.5 ? P.cA : P.cB;
    const a = (0.05 + P.C * 0.32) * moc * (0.35 + rt() * 0.85);
    ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${a.toFixed(3)})`;
    ctx.lineWidth = Math.max(0.3, (0.45 + P.C * 1.2) * gr);
    ctx.beginPath();
    ctx.moveTo(cx - R * 0.94, y0 + (rt() - 0.5) * R * 0.08);
    ctx.quadraticCurveTo(cx + wyg, cy + (y0 - cy) * 0.3 + wyg * 0.5,
                         cx + R * 0.94, y0 + (rt() - 0.5) * R * 0.08);
    ctx.stroke();
  }

  // 4 · Syn — włókna, które NIE DOTYKAJĄ brzegów: powstały w środku
  const ileS = Math.round(P.Syn * 30 * (pelne ? 1 : 0.25));
  for (let k = 0; k < ileS; k++){
    let x = cx + (rt() - 0.5) * R * 0.85, y = cy + (rt() - 0.5) * R * 0.5;
    const a = (0.1 + P.Syn * 0.55) * moc;
    ctx.strokeStyle = `rgba(${VOLT[0]},${VOLT[1]},${VOLT[2]},${a.toFixed(3)})`;
    ctx.lineWidth = Math.max(0.4, (0.55 + P.Syn) * gr);
    ctx.beginPath(); ctx.moveTo(x, y);
    let kier = rt() * 6.283;
    for (let j = 0; j < 18; j++){
      kier += (rt() - 0.5) * 0.65 + Math.sin(czas * 0.5 + j * 0.3) * 0.09;
      x += Math.cos(kier) * R * 0.032; y += Math.sin(kier) * R * 0.026;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  if (!pelne) return;

  // 5 · próg theta — obraz raczej odmówi odpowiedzi, niż poda ładną liczbę
  if (!P.okreslone){
    ctx.setLineDash([2, 4]);
    ctx.strokeStyle = "rgba(224,116,88,0.6)"; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(cx, cy, R * 0.48, R * 0.28, 0, 0, 6.283); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "rgba(224,116,88,0.8)";
    ctx.font = `${Math.max(9, R * 0.07)}px "JetBrains Mono", monospace`;
    ctx.textAlign = "center";
    ctx.fillText("C < θ · kierunek nieokreślony", cx, cy + R * 0.42);
  }
}
