/* Odsłuch strumieni Apple Music w oknie — MusicKit JS v3 (Janek 10.09).
 *
 * 82 % puli to strumienie bez pliku na dysku; tutejszy odtwarzacz (afplay /
 * ffplay w moście) ich nie zagra. MusicKit zagra — zmierzone 10.09 w oknie
 * pywebview na file://: FairPlay jest, pełny utwór (434 s, nie próbka 30 s).
 *
 * Logowanie: gdy jest zapisany token użytkownika, most oddaje go przez js_api,
 * a MusicKit czyta go z adresu strony (#base64-JSON — jego własny kanał
 * powrotu z logowania, `_processLocationHash`); adres jest czyszczony od razu.
 * Gdy tokenu nie ma, `authorize()` otwiera okienko Apple — pywebview sam go
 * nie otwiera, robi to gui/apple_logowanie.py — a token wraca do mostu
 * (`apple_zapisz_token`), bo tryb prywatny okna gubi zapis MusicKit.
 *
 * Kraj sklepu: MusicKit trzyma go w localStorage pod `music.<team>.itua`;
 * bez wpisu bierze `us`, a sztywne storefrontId przy innym wpisie kończy się
 * błędem CONTENT_EQUIVALENT. Wpisujemy kraj z konta DJ-a przed konfiguracją.
 *
 * Stan oddajemy w TYM SAMYM kształcie co most (`stan_odtwarzania`), żeby
 * pasek grania, głowica i auto-następny działały bez rozgałęzień.
 * Dźwięk rusza wyłącznie z `grajLubPauza`, a tę woła tylko `graj()` z app.js.
 */
(function () {
  'use strict';
  // MusicKit.PlaybackStates: 1 loading, 2 playing, 3 paused, 4 stopped,
  // 5 ended, 6 seeking, 8 waiting, 9 stalled, 10 completed
  const GRA = new Set([1, 2, 6, 8, 9]);
  const KONIEC = new Set([5, 10]);
  let m = null;
  let ladowanie = null;
  let ostatniBlad = null;
  let biezacy = null;          // {trackId, appleId, opis, bpm}
  let skonczyl = false;

  function zaladujSkrypt() {
    if (window.MusicKit && window.MusicKit.configure) return Promise.resolve();
    return new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js';
      s.onload = () => {
        if (window.MusicKit && window.MusicKit.configure) { res(); return; }
        document.addEventListener('musickitloaded', () => res(), {once: true});
      };
      s.onerror = () => rej(new Error('nie wczytałem MusicKit (brak sieci?)'));
      document.head.appendChild(s);
    });
  }

  async function init() {
    if (m) return m;
    if (ladowanie) return ladowanie;
    ladowanie = (async () => {
      const t = await window.pywebview.api.apple_odtwarzacz();
      if (!t || (t.blad && !t.brak_tokenu)) throw new Error((t && t.blad) || 'most nie oddał tokenów');
      if (t.brak_tokenu) return await zaloguj(t);
      if (t.storefront && t.team) localStorage.setItem(`music.${t.team}.itua`, t.storefront);
      const bezHasha = location.href.split('#')[0];
      const paczka = btoa(JSON.stringify({itre: '0', musicUserToken: t.user, cid: ''}));
      history.replaceState(null, '', bezHasha + '#' + paczka);
      let inst;
      try {
        await zaladujSkrypt();
        const cfg = {developerToken: t.dev, app: {name: 'DanceLab', build: '1'}};
        if (t.storefront) cfg.storefrontId = t.storefront;
        inst = await MusicKit.configure(cfg);
      } finally {
        history.replaceState(null, '', bezHasha);          // token znika z adresu
      }
      if (!inst.isAuthorized) throw new Error('MusicKit nie przyjął logowania — autoryzuj ponownie');
      inst.addEventListener('playbackStateDidChange', e => {
        if (e && KONIEC.has(e.state)) skonczyl = true;
      });
      m = inst;
      return m;
    })();
    try {
      const inst = await ladowanie;
      ostatniBlad = null;
      return inst;
    } catch (e) {
      ostatniBlad = String((e && e.message) || e);
      ladowanie = null;
      throw e;
    }
  }

  // Pierwsze logowanie w oknie: okienko Apple, potem token do mostu.
  async function zaloguj(t) {
    await zaladujSkrypt();
    const cfg = {developerToken: t.dev, app: {name: 'DanceLab', build: '1'}};
    if (t.storefront) cfg.storefrontId = t.storefront;
    const inst = await MusicKit.configure(cfg);
    const tok = await inst.authorize();
    if (!tok || !inst.isAuthorized) throw new Error('logowanie do Apple Music przerwane');
    const zap = await window.pywebview.api.apple_zapisz_token(tok);
    if (zap && zap.blad) throw new Error(zap.blad);
    inst.addEventListener('playbackStateDidChange', e => {
      if (e && KONIEC.has(e.state)) skonczyl = true;
    });
    m = inst;
    return m;
  }

  function stan() {
    if (!m || !biezacy) return {gra: false, pozycja_sec: 0};
    if (skonczyl) {
      skonczyl = false;
      const k = biezacy;
      biezacy = null;
      return {gra: false, pozycja_sec: 0, skonczyl_sie: true, rodzaj: 'utwor',
              track_id: k.trackId, opis: ''};
    }
    const dl = m.currentPlaybackDuration;
    return {
      gra: GRA.has(m.playbackState),
      pozycja_sec: Math.round((m.currentPlaybackTime || 0) * 100) / 100,
      dlugosc_sec: dl && dl > 0 ? dl : null,
      rodzaj: 'utwor',
      track_id: biezacy.trackId,
      opis: biezacy.opis,
      skad: 'Apple Music',
      skonczyl_sie: false,
    };
  }

  async function grajLubPauza(appleId, trackId, opis, bpm) {
    await init();
    if (biezacy && biezacy.trackId === trackId) {
      // Po skoku/przewinięciu MusicKit bywa w stanie „szuka"/„czeka", nie „gra" —
      // drugie P ma wtedy PAUZOWAĆ (próba pełnej aplikacji 11.09: grało dalej).
      if (GRA.has(m.playbackState)) await m.pause();
      else await m.play();
      return stan();
    }
    skonczyl = false;
    await m.setQueue({song: String(appleId), startPlaying: false});
    biezacy = {trackId, appleId: String(appleId), opis: opis || '',
               bpm: Number(bpm) > 0 ? Number(bpm) : null};
    await m.play();
    return stan();
  }

  async function przewin(sek) {
    if (!m || !biezacy) return stan();
    await m.seekToTime(Math.max(0, Number(sek) || 0));
    return stan();
  }

  // Skok o N uderzeń wg tempa utworu — ta sama arytmetyka co w moście
  // (`skocz`: „wg tempa, nie wg sekund"). Bez tempa nie zgadujemy.
  async function skocz(uderzenia) {
    if (!m || !biezacy) return stan();
    if (!biezacy.bpm) return Object.assign(stan(), {uwaga: 'brak tempa strumienia — skok niemożliwy'});
    const dl = m.currentPlaybackDuration || 0;
    let cel = (m.currentPlaybackTime || 0) + Number(uderzenia) * 60 / biezacy.bpm;
    cel = Math.max(0, dl > 0 ? Math.min(cel, dl - 0.5) : cel);
    await m.seekToTime(cel);
    return stan();
  }

  // Okładka tego, co gra — adres z CDN Apple, obok strumienia, który i tak
  // idzie z sieci. Przed startem odtwarzania `nowPlayingItem` bywa pusty.
  function okladka(px) {
    const it = m && biezacy ? m.nowPlayingItem : null;
    const art = it && (it.artwork || (it.attributes && it.attributes.artwork));
    if (!art || !art.url) return null;
    try { return MusicKit.formatArtworkURL(art, px, px); } catch (e) { return null; }
  }

  // Zagrał plik z dysku: strumień milknie i oddaje głos mostowi.
  async function porzuc() {
    if (m && biezacy) {
      try { await m.pause(); } catch (e) { /* nic nie grało */ }
    }
    biezacy = null;
    skonczyl = false;
  }

  window.appleGra = {
    init, grajLubPauza, przewin, skocz, okladka, porzuc, stan,
    aktywny: trackId => !!(m && biezacy && (!trackId || biezacy.trackId === trackId)),
    blad: () => ostatniBlad,
  };
})();
