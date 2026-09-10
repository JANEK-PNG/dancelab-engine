/* Odsłuch strumieni Apple Music w oknie — MusicKit JS v3 (Janek 10.09).
 *
 * 82 % puli to strumienie bez pliku na dysku; tutejszy odtwarzacz (afplay /
 * ffplay w moście) ich nie zagra. MusicKit zagra — zmierzone 10.09 w oknie
 * pywebview na file://: FairPlay jest, pełny utwór (434 s, nie próbka 30 s).
 *
 * Logowanie: wyskakujące okno Apple w pywebview się NIE otwiera (window.open
 * zwraca null). Dlatego okno używa tokenu, który DJ dał raz w Safari
 * (scripts/apple_music_biblioteka.py autoryzuj): most oddaje go przez js_api,
 * a MusicKit czyta go z adresu strony (#base64-JSON — jego własny kanał
 * powrotu z logowania, `_processLocationHash`). Adres jest czyszczony od razu.
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
  let biezacy = null;          // {trackId, appleId, opis}
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
      if (!t || t.blad) throw new Error((t && t.blad) || 'most nie oddał tokenów');
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

  async function grajLubPauza(appleId, trackId, opis) {
    await init();
    if (biezacy && biezacy.trackId === trackId) {
      if (m.playbackState === 2) await m.pause();
      else await m.play();
      return stan();
    }
    skonczyl = false;
    await m.setQueue({song: String(appleId), startPlaying: false});
    biezacy = {trackId, appleId: String(appleId), opis: opis || ''};
    await m.play();
    return stan();
  }

  async function przewin(sek) {
    if (!m || !biezacy) return stan();
    await m.seekToTime(Math.max(0, Number(sek) || 0));
    return stan();
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
    init, grajLubPauza, przewin, porzuc, stan,
    aktywny: trackId => !!(m && biezacy && (!trackId || biezacy.trackId === trackId)),
    blad: () => ostatniBlad,
  };
})();
