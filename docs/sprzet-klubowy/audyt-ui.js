/* Audytor UI — sprawdza to, czego oko nie łapie.
 *
 * Wpięcie: dodaj do strony
 *     <script src="../audyt-ui.js"></script>
 * i otwórz ją z ?audyt=1. Bez tego parametru plik nic nie robi.
 *
 * Powód istnienia. Janek wyłapywał zrzutami ekranu zawsze te same cztery klasy
 * błędu — teksty wyjeżdżające poza ramkę, napisy niewycentrowane, elementy
 * odsunięte od wspólnej osi, nierówne odstępy — i podsumował to zdaniem
 * „coś masz problemy z designem jeśli chodzi o takie podstawowe rzeczy jak
 * centrowanie, wyrównanie do osi x czy y". Miał rację. To są rzeczy, przy
 * których oko zawodzi, a maszyna nie, więc od teraz sprawdza je maszyna.
 *
 * Dlaczego w przeglądarce, a nie w Pythonie: wymiary tekstu w SVG zna wyłącznie
 * silnik składu. getBBox() to jedyne uczciwe źródło — poza przeglądarką
 * trzeba by go zgadywać.
 *
 * Wyjątki: element z atrybutem data-audyt="pomin" jest pomijany, a powód
 * podaje się w data-audyt-powod. Wyjątek bez powodu jest zgłaszany jako usterka
 * — inaczej atrybut stałby się sposobem na uciszenie audytora.
 */
(function () {
  'use strict';

  if (!new URLSearchParams(location.search).has('audyt')) return;

  // Progi w pikselach ekranu. Dobrane przy kalibracji na modelu FLX4 — stronie,
  // o której Janek powiedział "działa git". Strona zaakceptowana definiuje próg;
  // jeśli audytor krzyczy na nią, zły jest próg, nie strona.
  const PROG = {
    wyjscie: 0.75,      // ile tekst może wystawać poza swój kształt
    centrowanie: 1.2,   // odchyłka środka napisu od środka kształtu
    os: 1.0,            // rozjazd elementów, które mają stać na jednej osi
    odstep: 1.5,        // różnica przerw w rzędzie
  };

  const znaleziska = [];

  function zglos(rodzaj, opis, el, waga = 'blad') {
    znaleziska.push({rodzaj, opis, el, waga});
  }

  function prostokat(el) {
    try {
      const r = el.getBoundingClientRect();
      return r.width || r.height ? r : null;
    } catch { return null; }
  }

  const srodekX = r => r.left + r.width / 2;
  const srodekY = r => r.top + r.height / 2;
  const opisz = el => {
    const t = (el.textContent || '').trim().slice(0, 24);
    return `<${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}>` +
           (t ? ` "${t}"` : '');
  };

  // Element niewidzialny nie może z niczym kolidować. Strefy dotyku, obszary
  // trafienia i pomocnicze kształty mają puste albo przezroczyste wypełnienie —
  // pierwsza wersja odrzucała tylko dosłowne fill="none" i zgłaszała napis
  // SHIFT jako kolidujący z niewidoczną strefą joga.
  function widoczny(el) {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden') return false;
    if (parseFloat(st.opacity || '1') < 0.05) return false;
    const f = (st.fill || '').trim();
    if (!f || f === 'none' || f === 'transparent') return false;
    const m = f.match(/rgba?\([^)]*,\s*([\d.]+)\s*\)/);
    if (m && parseFloat(m[1]) < 0.05) return false;
    return true;
  }

  function pomijany(el) {
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      if (n.dataset && n.dataset.audyt === 'pomin') {
        if (!n.dataset.audytPowod) {
          zglos('wyjatek bez powodu',
                `${opisz(n)} wyłączony z audytu, ale nie podano data-audyt-powod`,
                n, 'ostrzezenie');
        }
        return true;
      }
    }
    return false;
  }

  /* --- 1 i 2: tekst wobec swojego kształtu ------------------------------- */
  // Parowanie GEOMETRYCZNE, nie strukturalne. Pierwsza wersja brała poprzednie
  // rodzeństwo w SVG i produkowała bzdury w rodzaju "napis odjechał o 576 px" —
  // bo kolejność elementów w pliku nie ma nic wspólnego z tym, co na czym leży.
  //
  // Tłem napisu jest NAJMNIEJSZY kształt, którego prostokąt zawiera cały napis.
  // Obudowa i duże płyty też go zawierają, więc odrzucamy kandydatów wyraźnie
  // większych od napisu: pudełko etykiety otacza ją ciasno, płyta panelu nie.
  const KROTNOSC_TLA = 6;   // ile razy tło może być szersze/wyższe od napisu

  function ksztaltDla(tekst, rt) {
    const wsk = tekst.dataset && tekst.dataset.audytTlo;
    if (wsk) return document.querySelector(wsk);
    const svg = tekst.ownerSVGElement;
    if (!svg || !rt) return null;

    let najlepszy = null, najmniejsze = Infinity;
    svg.querySelectorAll('rect, circle, ellipse').forEach(k => {
      if (!widoczny(k)) return;
      const rk = prostokat(k);
      if (!rk) return;
      const zawiera = rk.left <= rt.left + 0.5 && rk.right >= rt.right - 0.5 &&
                      rk.top <= rt.top + 0.5 && rk.bottom >= rt.bottom - 0.5;
      if (!zawiera) return;
      // Wystarczy JEDNA oś: pasek sekcji jest niski jak etykieta, ale wielokrotnie
      // od niej szerszy, i przy warunku "i" przechodził jako tło — stąd absurdy
      // w rodzaju "napis odjechał o 150 px od środka".
      if (rk.width > rt.width * KROTNOSC_TLA ||
          rk.height > rt.height * KROTNOSC_TLA) return;   // płyta, nie etykieta
      const pole = rk.width * rk.height;
      if (pole < najmniejsze) { najmniejsze = pole; najlepszy = k; }
    });
    return najlepszy;
  }

  function sprawdzTeksty() {
    document.querySelectorAll('svg text').forEach(t => {
      if (pomijany(t)) return;
      const rt = prostokat(t);
      if (!rt || !(t.textContent || '').trim()) return;

      const k = ksztaltDla(t, rt);
      if (!k) return;
      const rk = prostokat(k);
      if (!rk) return;

      // Tło z definicji zawiera napis, więc "wystaje" sprawdzamy wyłącznie dla
      // tła wskazanego ręcznie — tam autor twierdzi, że para istnieje, i jeśli
      // napis z niej wychodzi, to jest prawdziwy błąd.
      if (t.dataset && t.dataset.audytTlo) {
        const poza = Math.max(
          rk.left - rt.left, rt.right - rk.right,
          rk.top - rt.top, rt.bottom - rk.bottom);
        if (poza > PROG.wyjscie) {
          zglos('tekst poza kształtem',
                `${opisz(t)} wystaje o ${poza.toFixed(1)} px poza ${opisz(k)}`, t);
        }
      }

      // Centrowanie sprawdzamy tylko przy text-anchor="middle" — napis
      // wyrównany do lewej ma prawo nie stać w środku.
      const kotwica = getComputedStyle(t).textAnchor ||
                      t.getAttribute('text-anchor');
      if (kotwica === 'middle') {
        const d = Math.abs(srodekX(rt) - srodekX(rk));
        if (d > PROG.centrowanie) {
          zglos('centrowanie',
                `${opisz(t)} odjechał o ${d.toFixed(1)} px od środka ${opisz(k)}` +
                ' — sprawdź kompensację odstępu międzyliterowego', t);
        }
      }
    });
  }

  /* --- 3 i 4: rzędy i kolumny ------------------------------------------- */
  // Grupy deklaruje się jawnie: data-audyt-rzad="nazwa" albo
  // data-audyt-kolumna="nazwa". Automatyczne zgadywanie, co tworzy rząd,
  // dawało fałszywe alarmy na elementach, które tylko przypadkiem sąsiadują.
  function grupy(atrybut) {
    const mapa = new Map();
    document.querySelectorAll(`[${atrybut}]`).forEach(el => {
      if (pomijany(el)) return;
      const klucz = el.getAttribute(atrybut);
      if (!mapa.has(klucz)) mapa.set(klucz, []);
      mapa.get(klucz).push(el);
    });
    return mapa;
  }

  function sprawdzOsie() {
    grupy('data-audyt-rzad').forEach((el, nazwa) => {
      const r = el.map(prostokat).filter(Boolean);
      if (r.length < 2) return;
      const sr = r.map(srodekY);
      const rozjazd = Math.max(...sr) - Math.min(...sr);
      if (rozjazd > PROG.os) {
        zglos('oś pozioma',
              `rząd "${nazwa}" (${r.length} elementów) rozjeżdża się w pionie ` +
              `o ${rozjazd.toFixed(1)} px`, el[0]);
      }
      sprawdzOdstepy(nazwa, r.slice().sort((a, b) => a.left - b.left),
                     'left', 'right', 'poziomo', el[0]);
    });

    grupy('data-audyt-kolumna').forEach((el, nazwa) => {
      const r = el.map(prostokat).filter(Boolean);
      if (r.length < 2) return;
      const sr = r.map(srodekX);
      const rozjazd = Math.max(...sr) - Math.min(...sr);
      if (rozjazd > PROG.os) {
        zglos('oś pionowa',
              `kolumna "${nazwa}" (${r.length} elementów) rozjeżdża się w poziomie ` +
              `o ${rozjazd.toFixed(1)} px`, el[0]);
      }
      sprawdzOdstepy(nazwa, r.slice().sort((a, b) => a.top - b.top),
                     'top', 'bottom', 'pionowo', el[0]);
    });
  }

  function sprawdzOdstepy(nazwa, r, poczatek, koniec, kierunek, el) {
    if (r.length < 3) return;   // dwa elementy nie tworzą rytmu
    const przerwy = [];
    for (let i = 1; i < r.length; i++) przerwy.push(r[i][poczatek] - r[i - 1][koniec]);
    const roznica = Math.max(...przerwy) - Math.min(...przerwy);
    if (roznica > PROG.odstep) {
      zglos('rytm odstępów',
            `"${nazwa}" ${kierunek}: przerwy ` +
            przerwy.map(p => p.toFixed(1)).join(' / ') +
            ` różnią się o ${roznica.toFixed(1)} px`, el);
    }
  }

  /* --- 5: kolizje ------------------------------------------------------- */
  // Tylko w obrębie jednego SVG i tylko między tekstem a kształtem, który nie
  // jest jego tłem. Porównywanie wszystkiego ze wszystkim dałoby setki trafień
  // na elementach, które mają się nakładać (obudowa, gniazda, poświaty).
  function sprawdzKolizje() {
    document.querySelectorAll('svg').forEach(svg => {
      const teksty = [...svg.querySelectorAll('text')].filter(t => !pomijany(t));
      const ksztalty = [...svg.querySelectorAll('circle, ellipse, rect')]
        .filter(k => !pomijany(k) && widoczny(k));

      teksty.forEach(t => {
        const rt = prostokat(t);
        if (!rt || !(t.textContent || '').trim()) return;
        ksztalty.forEach(k => {
          if (k.contains(t) || t.contains(k)) return;
          const rk = prostokat(k);
          if (!rk) return;
          // Kształt ZAWIERAJĄCY napis to jego tło albo płyta pod nim — jedno i
          // drugie jest w porządku. Kolizja to przecięcie CZĘŚCIOWE: napis
          // wystaje poza kształt z jednej strony, a wchodzi w niego z drugiej.
          // To jest dokładnie "okręgi najeżdżają na teksty" z uwag Janka.
          const zawiera = rk.left <= rt.left && rk.right >= rt.right &&
                          rk.top <= rt.top && rk.bottom >= rt.bottom;
          if (zawiera) return;
          const w = Math.min(rt.right, rk.right) - Math.max(rt.left, rk.left);
          const h = Math.min(rt.bottom, rk.bottom) - Math.max(rt.top, rk.top);
          // Próg w obu osiach: musnięcie krawędzią to nie kolizja. Wymagamy
          // też, żeby zachodzenie objęło zauważalną część napisu.
          if (w > 2 && h > 2 && w * h > rt.width * rt.height * 0.12) {
            zglos('kolizja',
                  `${opisz(t)} nachodzi na ${opisz(k)} (${w.toFixed(1)}×${h.toFixed(1)} px)`,
                  t, 'ostrzezenie');
          }
        });
      });
    });
  }

  /* --- raport ----------------------------------------------------------- */
  function podswietl() {
    const warstwa = document.createElement('div');
    warstwa.id = 'audyt-warstwa';
    warstwa.style.cssText =
      'position:fixed;inset:0;pointer-events:none;z-index:99999';
    znaleziska.forEach(z => {
      const r = prostokat(z.el);
      if (!r) return;
      const b = document.createElement('div');
      const kolor = z.waga === 'blad' ? '#e06c75' : '#e0a458';
      b.style.cssText =
        `position:absolute;left:${r.left - 2}px;top:${r.top - 2}px;` +
        `width:${r.width + 4}px;height:${r.height + 4}px;` +
        `border:1.5px solid ${kolor};border-radius:2px`;
      warstwa.appendChild(b);
    });
    document.body.appendChild(warstwa);
  }

  function raport() {
    sprawdzTeksty();
    sprawdzOsie();
    sprawdzKolizje();

    const bledy = znaleziska.filter(z => z.waga === 'blad');
    const ostrz = znaleziska.filter(z => z.waga === 'ostrzezenie');

    console.log(`[AUDYT] błędów ${bledy.length}, ostrzeżeń ${ostrz.length}`);
    const wg = {};
    znaleziska.forEach(z => { (wg[z.rodzaj] = wg[z.rodzaj] || []).push(z); });
    Object.entries(wg).forEach(([rodzaj, lista]) => {
      console.log(`[AUDYT] ${rodzaj}: ${lista.length}`);
      lista.slice(0, 12).forEach(z => console.log(`[AUDYT]   ${z.opis}`));
      if (lista.length > 12) console.log(`[AUDYT]   …i ${lista.length - 12} więcej`);
    });
    if (!znaleziska.length) console.log('[AUDYT] czysto');

    podswietl();
    window.__audyt = {bledy, ostrzezenia: ostrz, wszystkie: znaleziska};
  }

  // Po pełnym renderze: czcionki muszą być gotowe, inaczej bbox tekstu kłamie.
  if (document.readyState === 'complete') {
    (document.fonts ? document.fonts.ready : Promise.resolve())
      .then(() => setTimeout(raport, 120));
  } else {
    window.addEventListener('load', () =>
      (document.fonts ? document.fonts.ready : Promise.resolve())
        .then(() => setTimeout(raport, 120)));
  }
})();
