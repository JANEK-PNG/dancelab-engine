/* PORTRET BRZMIENIA — WSPÓLNY KOD karty i sceny.
   Decyzja Janka 13.08: „nie możesz zrobić inspekcji kafelka i skopiować?"
   Zamiast kopii — jedno źródło: kafelek i pełny ekran rysują TĄ SAMĄ
   funkcją portret(), więc nie da się ich rozjechać. Portret jest rysowany
   WYŁĄCZNIE z pomiarów DJ-a (nić = jedno przejście między utworami). */

let SZWY = {};   // sekwencje szwów doładowują się z pliku
const PLAN_CACHE = {};
function nicY(nic, x){
  const i = Math.max(1, Math.min(nic.length - 1,
    Math.round(x / nic[nic.length-1].x * (nic.length - 1))));
  return nic[i].y;
}
function planPortretu(ksywa, szwy, W, H, p){
  const kl = ksywa + "|" + W + "x" + H;
  if (PLAN_CACHE[kl]) return PLAN_CACHE[kl];
  const r = rnd(hash(ksywa + "plachta"));
  const t01 = v => Math.max(0, Math.min(1, (v - 95) / 95));
  const ZG = new Set(["idealna","sasiednia","rownolegla"]);
  const cool = [96,196,228], warm = [235,166,72];
  const mix = t => cool.map((v,i)=>Math.round(v + (warm[i]-v)*t));
  // nić przewodnia: łagodny meander ciągnięty PRAWDZIWYM przebiegiem temp
  const nic = [];
  for (let i = 0; i <= 120; i++){
    const s = szwy[Math.min(szwy.length - 1, Math.floor(i / 120 * szwy.length))];
    const cel = H * (0.62 - 0.22 * t01((s.a + s.b) / 2));
    const poprz = nic.length ? nic[nic.length-1].y : H * 0.5;
    nic.push({x: i / 120 * W, y: poprz + (cel - poprz) * 0.055});
  }
  const zdarzenia = szwy.map((s, i) => {
    const x = (i + 0.5) / szwy.length * W;
    const y = nicY(nic, x);
    const c = mix(t01((s.a + s.b) / 2));
    if (s.h === "idealna") return {typ:"warkocz", x, y, c};
    if (ZG.has(s.h) && Math.abs(s.d) <= 10) return {typ:"opad", x, y, c};
    if (ZG.has(s.h)) return {typ:"wbicie", x, y, dl: 26 + Math.min(s.d,30),
                             y2: nicY(nic, x + 26 + Math.min(s.d,30)), c};
    return {typ:"rozdarcie", x, y, c};
  });
  // tkanina: gęstość z energii, temperatura z temp DJ-a
  const watki = [];
  const ile = Math.round(30 + p.en * 22);
  for (let j = 0; j < ile; j++){
    const t = j / ile;
    watki.push({y: 6 + t * (H - 12), faza: r() * 6.28,
      c: mix(Math.max(0, Math.min(1, p.cieplo + (r() - 0.5) * 0.5))),
      a: 0.09 + r() * 0.08, g: 0.6 + r() * p.bas * 1.9});
  }
  return PLAN_CACHE[kl] = {nic, zdarzenia, watki};
}


/* PORTRET BRZMIENIA — grzbiet terenu rysowany WYŁĄCZNIE z pomiarów DJ-a.
   Deterministyczny: ta sama karta zawsze wygląda tak samo (ziarno = ksywa).
   energia → wysokość szczytów · typowy skok tempa → poszarpanie grani ·
   mediana tempa → ile ciepła w kolorze · bas → ciemność pierwszego planu. */
function hash(s){let h=7; for(const c of s) h=(h*31+c.charCodeAt(0))|0; return h>>>0||1}
function rnd(seed){let s=seed; return ()=>{s^=s<<13; s^=s>>>17; s^=s<<5; return (s>>>0)/4294967296}}

function portret(cv, d, czas = 0, frakcja = null, vol = null){
  // pomysł Janka: głośność = grubość włókien (0.8 głośności = grubość 1.0)
  const gr = vol == null ? 1
    : vol <= 0.8 ? 0.3 + 2.2 * vol            // do 80%: znana grubość
    : 2.06 + (vol - 0.8) * 14.7;              // szczyt: ×2 na maksie
  const ctx = cv.getContext("2d");
  // rozdzielczość NATYWNA elementu (Janek 13.08: „zeszliśmy z jakości" —
  // sztywne płótno 600×208 rozciągane na szeroką kartę dawało rozmycie)
  const DPR = Math.min(2, devicePixelRatio || 1);
  const W = Math.max(240, Math.round(cv.clientWidth || 600));
  const H = Math.max(90, Math.round(cv.clientHeight || 208));
  if (cv.width !== Math.round(W * DPR) || cv.height !== Math.round(H * DPR)){
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
  }
  ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  ctx.clearRect(0, 0, W, H);
  const gest = Math.max(1, Math.min(2.4, W / 300));   // gęstość rośnie z kartą
  if (d.wbudowie){
    ctx.strokeStyle = "#3a3730"; ctx.setLineDash([5,6]); ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(0, H*0.68); ctx.lineTo(W, H*0.68); ctx.stroke();
    return;
  }
  const r = rnd(hash(d.ksywa));
  const cieplo = Math.min(Math.max(((d.bpm_med ?? 140) - 95) / 95, 0), 1);
  const en = d.energia ?? 0.45, skok = Math.min((d.skok ?? 8) / 20, 1), bas = d.bas ?? 0.45;
  const groove = d.groove ?? 0.35;
  const cool = [96,196,228], warm = [235,166,72], volt = [214,245,73];
  const mix = t => cool.map((v,i)=>Math.round(v + (warm[i]-v)*t));
  // pole sił z agregatów (charakter DJ-a) — po nim płyną nitki
  const a1 = 0.008 + r()*0.006, a2 = 0.010 + r()*0.008, a3 = 0.006 + r()*0.005;
  const p1 = r()*6.28, p2 = r()*6.28, p3 = r()*6.28;
  const turb = 0.5 + skok*2.2 + groove*0.8;
  const kat = (x,y) =>
    (Math.sin(x*a1 + p1 + czas*0.45) + Math.cos(y*a2*(1+groove) + p2 + czas*0.3)
     + Math.sin((x+y)*a3 + p3 + czas*0.22)) * turb;
  const ZG = new Set(["idealna","sasiednia","rownolegla"]);
  const t01 = v => Math.max(0, Math.min(1, (v-95)/95));
  const szwy = (SZWY[d.ksywa] || []);

  const grane = (frakcja != null && d.grany != null)
    ? szwy.filter(s => s.set === d.grany) : szwy;
  if (grane.length){
    // JEDWAB + CZAS (korekta Janka: poprzednia wersja niosła emocje —
    // wraca jedwab; czas zostaje jako NIEWIDZIALNA ścieżka nocy,
    // po której przez tkaninę wędruje światło-emocja i reaguje na to,
    // co DJ zrobił w tym miejscu setu).
    const plan = planPortretu(d.ksywa + (grane === szwy ? "" : "#gra"), grane, W, H, {cieplo, en, groove, bas, r});
    // tło: cienka tkanina z charakteru DJ-a
    const T = 15, PODROZ = 0.86, KONIEC = 0.88;
    const faza = frakcja != null ? frakcja * PODROZ : (czas / T) % 1;
    const xs = Math.min(faza / PODROZ, 1) * W;
    const wyg = faza > KONIEC ? (faza - KONIEC) / (1 - KONIEC) : 0;
    for (let s = 0; s < Math.round(120 * gest); s++){
      let x = r()*W, y = r()*H;
      const c = mix(Math.min(Math.max(cieplo + (r()-0.5)*0.9, 0), 1));
      const cicho = x > xs ? 0.35 : 1;           // przed kropką: cisza
      ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${(0.07*cicho).toFixed(3)})`;
      ctx.lineWidth = (0.6 + r()*bas*1.6) * gr;
      ctx.beginPath(); ctx.moveTo(x, y);
      for (let i = 0; i < Math.round(60 * gest); i++){
        const t2 = kat(x, y);
        x += Math.cos(t2)*2.6; y += Math.sin(t2)*2.6;
        ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
    // linia artysty: grubieje w miarę doczepiania utworów — mix nabiera
    // całości; w finale przejmuje wszystko i zostaje sama
    for (let i = 1; i < plan.nic.length; i++){
      const a = plan.nic[i-1], b = plan.nic[i];
      if (a.x > xs) break;
      const udzial = a.x / W;
      ctx.lineWidth = 0.8 + 2.6 * udzial;
      ctx.strokeStyle = `rgba(232,228,218,${(0.18 * (1 - wyg)).toFixed(3)})`;
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }
    // UTWORY DOCZEPIANE STOPNIOWO: nić istnieje dopiero, gdy noc
    // do niej doszła; świeżo doczepiona wyrasta z linii przez chwilę
    ctx.save();
    ctx.globalAlpha = 1 - wyg * 0.85;
    grane.forEach((s, idx) => {
      const xN = (idx + 0.5) / grane.length * W;
      if (xN > xs) return;
      const wzrost = Math.min(1, (xs - xN) / 26);
      const zaplon = 1 + 1.6 * (1 - wzrost);       // odkrycie = rozbłysk
      // OŚ Z: przeszłość osuwa się w głąb — dawniej odkryte nici są
      // mniejsze, ciemniejsze i wyżej (czas jako czwarty wymiar)
      const zT = Math.max(0, Math.min(1, (xs - xN) / (W * 0.9)));
      const skala = 1 - 0.45 * zT;
      const glab = 1 - 0.5 * zT;
      const rt = rnd(hash(d.ksywa + ":" + idx));   // ziarno TEJ nitki
      const perf = s.h === "idealna";
      const czysty = ZG.has(s.h);
      // DJ JEST PODMIOTEM (Janek 13.08): każda nić wychodzi Z JEGO RĘKI —
      // z punktu, w którym stał, gdy podejmował tę decyzję
      let x = xN + (rt()-0.5)*10;
      let y = nicY(plan.nic, xN) + (rt()-0.5)*14 - zT*16;
      if (perf){
        ctx.strokeStyle = `rgba(${volt[0]},${volt[1]},${volt[2]},${(Math.min(0.9, 0.4*zaplon)*glab).toFixed(2)})`;
        ctx.lineWidth = 1.0 * gr * skala;
        ctx.shadowColor = "rgba(214,245,73,0.25)"; ctx.shadowBlur = 2;
        ctx.beginPath();
        for (let i = 0; i < Math.round(120*wzrost*gest); i++){
          const t2 = kat(x, y);
          x += Math.cos(t2)*2.6; y += Math.sin(t2)*2.6;
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke(); ctx.shadowBlur = 0;
      } else if (czysty){
        const c = mix(t01((s.a + s.b) / 2));
        ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${(Math.min(0.95,(0.4+rt()*0.2)*zaplon)*glab).toFixed(2)})`;
        ctx.lineWidth = (1.0 + bas*1.8) * gr * skala;
        ctx.beginPath();
        const dl = Math.round((55 + Math.min(Math.abs(s.d),30)*2.5)*wzrost*gest);
        for (let i = 0; i < dl; i++){
          const t2 = kat(x, y) + (rt()-0.5)*0.1;
          x += Math.cos(t2)*2.6; y += Math.sin(t2)*2.6;
          i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
      } else {
        const c = mix(t01((s.a + s.b) / 2)).map(v => Math.round(v*0.55 + 60));
        ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${(Math.min(0.8, 0.34*zaplon)*glab).toFixed(2)})`;
        ctx.lineWidth = 0.7 * gr * skala;
        for (let seg = 0; seg < Math.max(1, Math.round(3*wzrost)); seg++){
          ctx.beginPath();
          for (let i = 0; i < 6; i++){
            const t2 = kat(x, y) + (rt()-0.5)*1.4;
            x += Math.cos(t2)*2.6; y += Math.sin(t2)*2.6;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
          }
          ctx.stroke();
          x += (rt()-0.5)*14; y += (rt()-0.5)*14;
        }
      }
    });
    ctx.restore();
    // ROZWAŻANIA DJ-a: w chwili decyzji z jego ręki wychodzi wachlarz
    // możliwości — jedna zostaje nicią, reszta gaśnie. Im większy skok
    // tempa musiał pokonać, tym szerzej sięgał (i tym więcej odrzucił).
    grane.forEach((s, idx) => {
      const xN = (idx + 0.5) / grane.length * W;
      if (xN > xs || xs - xN > 46) return;
      const swiezosc = 1 - (xs - xN) / 46;
      const rw = rnd(hash(d.ksywa + "wybor" + idx));
      const ile = 3 + Math.round(Math.min(Math.abs(s.d), 30) / 8);
      const yN = nicY(plan.nic, xN);
      for (let k = 0; k < ile; k++){
        const kat = (rw() - 0.5) * (1.1 + Math.min(Math.abs(s.d), 30) / 22);
        const dl = (16 + rw() * 44) * swiezosc;
        ctx.strokeStyle = `rgba(232,228,218,${(0.16 * swiezosc * (0.3 + rw() * 0.7)).toFixed(3)})`;
        ctx.lineWidth = 0.5;
        ctx.beginPath(); ctx.moveTo(xN, yN);
        let px = xN, py = yN, kk = kat;
        for (let j = 0; j < 8; j++){
          kk += (rw() - 0.5) * 0.5;
          px += Math.cos(kk) * dl / 8; py += Math.sin(kk) * dl / 8;
          ctx.lineTo(px, py);
        }
        ctx.stroke();
      }
    });
    // SPLOT NIEROZERWALNY (Janek 13.08): w chwili miksu dwa utwory
    // zostają związane węzłem, którego wcześniej nie było. 99,8% splotów
    // w mapie zdarzyło się DOKŁADNIE RAZ — jedyny w historii 21 tysięcy
    // przejść; taki węzeł dostaje pełny splot i sygnaturę światła.
    grane.forEach((s, idx) => {
      const xN = (idx + 0.5) / grane.length * W;
      if (xN > xs || xs - xN > W * 0.16) return;
      const swiez = 1 - (xs - xN) / (W * 0.16);
      const yN = nicY(plan.nic, xN);
      const jedyny = (s.uni ?? 1) === 1;
      const rs = rnd(hash(d.ksywa + "splot" + idx));
      const dlS = (34 + Math.min(Math.abs(s.d), 30) * 1.6) * (0.5 + swiez * 0.9);
      const skretow = jedyny ? 5 : 3;
      const cA = mix(t01(s.a)), cB = mix(t01(s.b));
      for (const [znak, c] of [[1, cA], [-1, cB]]){
        ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${(0.5 * swiez).toFixed(3)})`;
        ctx.lineWidth = 1.0 + swiez * 1.8;
        ctx.beginPath();
        for (let i = 0; i <= 26; i++){
          const u = i / 26;
          const px = xN - dlS * 0.5 + dlS * u;
          const py = yN + Math.sin(u * 6.283 * skretow + (znak > 0 ? 0 : 3.14))
                          * (9 + swiez * 9) * znak * Math.sin(u * 3.14);
          i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
        }
        ctx.stroke();
      }
      if (jedyny && swiez > 0.55){        // sygnatura: splot jedyny w mapie
        const a = (swiez - 0.55) / 0.45;
        ctx.strokeStyle = `rgba(255,255,255,${(0.5 * a).toFixed(3)})`;
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.arc(xN, yN, dlS * 0.42, 0, 6.283);
        ctx.stroke();
      }
    });
    // iskry zapłonu: nitki odkryte w tej chwili świecą u nasady
    grane.forEach((s, idx) => {
      const xN = (idx + 0.5) / grane.length * W;
      if (xN > xs || xs - xN > 26) return;
      const sila = 1 - (xs - xN) / 26;
      const yN = nicY(plan.nic, xN);
      const gi = ctx.createRadialGradient(xN, yN, 0, xN, yN, 9);
      gi.addColorStop(0, `rgba(232,228,218,${(0.7*sila).toFixed(2)})`);
      gi.addColorStop(1, "rgba(232,228,218,0)");
      ctx.fillStyle = gi;
      ctx.fillRect(xN-9, yN-9, 18, 18);
    });
    // ŚWIATŁO-EMOCJA: pióro artysty na końcu wytyczanej linii
    if (faza < KONIEC && czas > 0){
      let ys = nicY(plan.nic, xs), alfa = 0.8 * (1 - wyg), kolor = [232,228,218],
        rr = 15;
      for (const z of plan.zdarzenia){
        if (z.typ === "wbicie" && xs > z.x && xs < z.x + z.dl){
          alfa = 0.28; rr = 8;                     // schodzi pod tkaninę
        } else if (z.typ === "rozdarcie" && Math.abs(xs - z.x) < 11){
          alfa = 0.35 + 0.5*Math.abs(Math.sin(czas*23));   // migot
        } else if (z.typ === "warkocz" && Math.abs(xs - z.x) < 16){
          kolor = volt; alfa = 0.95; rr = 20;      // symbioza: rozbłysk
        }
      }
      // warkocz emocji: gasnący ogon za światłem, wzdłuż ścieżki
      for (let o = 8; o >= 1; o--){
        const ox = xs - o*7;
        if (ox < 0) continue;
        const oy = nicY(plan.nic, ox);
        const g2 = ctx.createRadialGradient(ox, oy, 0, ox, oy, rr*0.55);
        const a2 = alfa * 0.10 * (1 - o/9);
        g2.addColorStop(0, `rgba(${kolor[0]},${kolor[1]},${kolor[2]},${a2.toFixed(3)})`);
        g2.addColorStop(1, `rgba(${kolor[0]},${kolor[1]},${kolor[2]},0)`);
        ctx.fillStyle = g2;
        ctx.fillRect(ox-rr, oy-rr, rr*2, rr*2);
      }
      const g = ctx.createRadialGradient(xs, ys, 0, xs, ys, rr);
      g.addColorStop(0, `rgba(${kolor[0]},${kolor[1]},${kolor[2]},${alfa})`);
      g.addColorStop(1, `rgba(${kolor[0]},${kolor[1]},${kolor[2]},0)`);
      ctx.fillStyle = g;
      ctx.fillRect(xs-rr, ys-rr, rr*2, rr*2);
      // rdzeń DJ-a — ostry punkt decyzji w miękkiej aurze uwagi
      ctx.fillStyle = `rgba(255,255,255,${Math.min(1, alfa * 1.15).toFixed(2)})`;
      ctx.beginPath(); ctx.arc(xs, ys, 2.2, 0, 7); ctx.fill();
    }
    return;
  }
  // brak sekwencji szwów w danych — jedwab z samych agregatów (jak dotąd)
  const n = Math.round(170 + en*190);
  for (let s = 0; s < n; s++){
    let x = r()*W, y = r()*H;
    const akcent = s < 14;
    const c = akcent ? volt
      : mix(Math.min(Math.max(cieplo + (r()-0.5)*0.9, 0), 1));
    const alfa = akcent ? 0.38 + r()*0.22 : 0.13 + r()*0.18;
    ctx.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},${alfa.toFixed(2)})`;
    ctx.lineWidth = (akcent ? 0.9 : 0.6 + r()*bas*2.2) * gr;
    ctx.beginPath(); ctx.moveTo(x, y);
    const dl = 40 + en*80;
    for (let i = 0; i < dl; i++){
      const t = kat(x, y);
      x += Math.cos(t)*2.6; y += Math.sin(t)*2.6;
      ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
}
