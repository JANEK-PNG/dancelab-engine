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
  // liczby policzone PRZEZ SILNIK (profil_in_between.py) mają pierwszeństwo —
  // wizualizacja nie liczy własnej prawdy obok maszyny
  if (s.C != null){
    return {C: s.C, D: s.D, Syn: s.Syn, U: s.U, K: s.K,
            okreslone: s.okreslone !== false, zSilnika: true,
            iDJ: s.iDJ, iM: s.iM, Cdj: s.Cdj, Ddj: s.Ddj,
            cA: BARWA(T01(s.a || 128)), cB: BARWA(T01(s.b || 128))};
  }
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
                czas, rt, gr * persp, false, d.ksywa + "#" + k);
  }

  // NIĆ CIĄGŁA: jedno pasmo przewleczone przez WSZYSTKIE pola relacji —
  // szew nie urywa się na granicy utworu, tylko biegnie dalej (Janek:
  // „znowu mamy pocięty makaron")
  const wezly = [];
  for (let k = Math.max(0, Math.floor(teraz) - ILE_WSTECZ); k <= Math.floor(teraz); k++){
    const wiek = teraz - k;
    const persp = OKO / (OKO + Math.pow(Math.max(0, wiek), 0.85) * MIN * 0.42);
    const kat = k * 0.42 + czas * 0.06;
    const prom = MIN * 0.16 * (1 - persp);
    wezly.push({x: cx + Math.cos(kat) * prom, y: cy + Math.sin(kat) * prom * 0.6,
                persp, P: profilP(szwy[k], szwy[k - 1] || szwy[k])});
  }
  for (let pas = 0; pas < 3; pas++){
    for (let k = 1; k < wezly.length; k++){
      const a = wezly[k - 1], b = wezly[k];
      const c = b.P.cB;
      const alfa = (0.10 + b.P.C * 0.35) * b.persp * (pas === 1 ? 1.3 : 0.6);
      if (alfa < 0.01) continue;
      ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${alfa.toFixed(3)})`;
      ctx.lineWidth = Math.max(0.35, (0.6 + b.P.C * 1.4) * gr * b.persp
                                     * (pas === 1 ? 1.3 : 0.7));
      const roz = (pas - 1) * MIN * 0.012;
      const mx = (a.x + b.x) / 2 + (a.y - b.y) * 0.2;
      const my = (a.y + b.y) / 2 + (b.x - a.x) * 0.2 + roz;
      ctx.beginPath(); ctx.moveTo(a.x, a.y + roz * a.persp);
      ctx.quadraticCurveTo(mx, my, b.x, b.y + roz * b.persp);
      ctx.stroke();
    }
  }

  // TERAZ — relacja w pełnej skali, w centrum
  const i0 = Math.max(0, Math.min(n - 1, Math.floor(teraz)));
  const P = profilP(szwy[i0], szwy[i0 - 1] || szwy[i0]);
  poleRelacji(ctx, cx, cy, MIN * 0.36, P, 1, czas, rt, gr, true,
              d.ksywa + "#" + i0);

  // === PĘTLA DJ ↔ MUZYKA (Janek: „to jest właśnie in between") ===
  // DJ nie jest widzem — jest DRUGĄ STRONĄ relacji. Puszcza muzykę,
  // a muzyka zmienia jego następny ruch. Rysujemy oba kierunki:
  // ku środkowi — ile DJ NARZUCIŁ (i_DJ→M), na zewnątrz — ile MUZYKA
  // go poprowadziła (i_M→DJ). Grubsza strona prowadzi.
  petlaDJ(ctx, cx, cy, MIN, P, czas, rt, gr,
          (szwy[i0].b || 128) / 60, d.ksywa + "#" + i0);
}

function petlaDJ(ctx, cx, cy, MIN, P, czas, rt, gr, hz, ziarno){
  const iDJ = P.iDJ ?? 0.5, iM = P.iM ?? 0.5;
  const Rd = MIN * 0.46;
  const bit = 0.86 + 0.14 * Math.sin(czas * hz * 6.283);   // puls granego tempa

  // obecność DJ-a: pierścień wokół pola relacji, oddycha rytmem utworu
  ctx.strokeStyle = `rgba(232,228,218,${(0.035 + iDJ * 0.05).toFixed(3)})`;
  ctx.lineWidth = Math.max(0.4, (0.4 + iDJ * 1.0) * gr);
  ctx.beginPath();
  ctx.ellipse(cx, cy, Rd * bit, Rd * 0.66 * bit, 0, 0, 6.283);
  ctx.stroke();

  // oba kierunki pętli jako WŁÓKNA SPIRALNE, nie szprychy
  for (const nurt of [{ile: Math.round(2 + iDJ * 11), do_: true, c: [255,255,255], si: iDJ},
                      {ile: Math.round(2 + iM * 11), do_: false, c: P.cB, si: iM}]){
    for (let k = 0; k < nurt.ile; k++){
      const rk = rnd(hash((ziarno || "x") + (nurt.do_ ? "|dj" : "|mu") + k));
      const kat0 = rk() * 6.283;
      let r = nurt.do_ ? Rd * (0.82 + rk() * 0.2) : MIN * (0.10 + rk() * 0.06);
      let kat = kat0;
      const a2 = (0.025 + nurt.si * 0.10) * (0.4 + rk() * 0.7);
      ctx.strokeStyle = `rgba(${nurt.c[0]},${nurt.c[1]},${nurt.c[2]},${a2.toFixed(3)})`;
      ctx.lineWidth = Math.max(0.25, (0.3 + nurt.si * 0.6) * gr);
      ctx.beginPath();
      ctx.moveTo(cx + Math.cos(kat) * r, cy + Math.sin(kat) * r * 0.64);
      const cel = nurt.do_ ? MIN * 0.1 : Rd;
      for (let j = 0; j < 40; j++){
        r += (cel - r) * 0.06;
        kat += 0.11 + Math.sin(czas * 0.4 + kat0 + j * 0.2) * 0.05;
        ctx.lineTo(cx + Math.cos(kat) * r, cy + Math.sin(kat) * r * 0.64);
      }
      ctx.stroke();
    }
  }
  // kto prowadzi: łuk po stronie silniejszego kierunku
  if (P.Ddj != null){
    const prowadziDJ = P.Ddj > 0;
    const moc = Math.min(1, Math.abs(P.Ddj) / 1.6);
    ctx.strokeStyle = prowadziDJ
      ? `rgba(255,255,255,${(0.25 * moc).toFixed(3)})`
      : `rgba(${VOLT[0]},${VOLT[1]},${VOLT[2]},${(0.3 * moc).toFixed(3)})`;
    ctx.lineWidth = Math.max(0.5, 1.1 * moc * gr);
    ctx.beginPath();
    ctx.ellipse(cx, cy, Rd * bit * (prowadziDJ ? 1.06 : 0.9),
                Rd * 0.66 * bit * (prowadziDJ ? 1.06 : 0.9), 0,
                prowadziDJ ? -0.9 : 2.24, prowadziDJ ? 0.9 : 4.04);
    ctx.stroke();
  }
}

/* POLE RELACJI — brzegi są tylko krawędziami; ciałem jest to, co pomiędzy. */
function poleRelacji(ctx, cx, cy, R, P, moc, czas, rt, gr, pelne, ziarno){
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

  // 3 · C — materia sprzężenia JAKO JEDWAB (Janek: „to mają być takie
  //     włókna cały czas"): nici płyną po wspólnym polu sił wewnątrz pola
  //     relacji. Ile ich = C. Jak wysoko sięgają = U. Ku której stronie
  //     dryfują = D. Jak bardzo się plączą = 1−C (słabe sprzężenie szarpie).
  const ile = Math.round((5 + P.C * 46) * (pelne ? 1 : 0.28));
  const turb = 0.45 + (1 - P.C) * 1.8;
  const f1 = 0.9 + P.U * 1.6, f2 = 1.7 + P.Syn * 2.2;
  const polePola = (dx, dy) =>
    (Math.sin(dx / R * f1 * 3.1 + czas * 0.35)
     + Math.cos(dy / R * f2 * 3.1 - czas * 0.22)
     + Math.sin((dx + dy) / R * 2.2 + czas * 0.13)) * turb + przechyl * 1.4;
  for (let k = 0; k < ile; k++){
    const rk = rnd(hash((ziarno || "x") + "|c" + k));   // stałe ziarno nici
    const zLewej = rk() < 0.5 - przechyl * 0.28;
    let x = cx + (zLewej ? -1 : 1) * R * (0.35 + rk() * 0.62);
    let y = cy + (rk() - 0.5) * R * 1.05 * P.U;
    const c = zLewej ? P.cA : P.cB;
    const a = (0.05 + P.C * 0.34) * moc * (0.35 + rk() * 0.8);
    if (a < 0.006) continue;
    ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${a.toFixed(3)})`;
    ctx.lineWidth = Math.max(0.3, (0.45 + P.C * 1.3) * gr);
    const dlug = Math.round(26 + P.C * 74);
    const krok = R * 0.035;
    ctx.beginPath(); ctx.moveTo(x, y);
    for (let j = 0; j < dlug; j++){
      const kier = polePola(x - cx, y - cy) + (rk() - 0.5) * (1 - P.C) * 0.5;
      x += Math.cos(kier) * krok; y += Math.sin(kier) * krok * 0.75;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // 4 · Syn — włókna, które NIE DOTYKAJĄ brzegów: powstały w środku
  const ileS = Math.round(P.Syn * 30 * (pelne ? 1 : 0.25));
  for (let k = 0; k < ileS; k++){
    const rk = rnd(hash((ziarno || "x") + "|s" + k));
    let x = cx + (rk() - 0.5) * R * 0.85, y = cy + (rk() - 0.5) * R * 0.5;
    const a = (0.1 + P.Syn * 0.55) * moc;
    ctx.strokeStyle = `rgba(${VOLT[0]},${VOLT[1]},${VOLT[2]},${a.toFixed(3)})`;
    ctx.lineWidth = Math.max(0.4, (0.55 + P.Syn) * gr);
    ctx.beginPath(); ctx.moveTo(x, y);
    let kier = rk() * 6.283;
    for (let j = 0; j < 18; j++){
      kier += (rk() - 0.5) * 0.65 + Math.sin(czas * 0.5 + j * 0.3) * 0.09;
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
