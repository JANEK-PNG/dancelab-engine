"""Probe 2 (warm start): does a WARMED second MusicKit player start predictably?

    .venv/bin/python experiments_priv/2026-09-10_musickit_okno/szew_sonda.py

A seam from files is rendered by ffmpeg; a stream gives no audio to mix
(FairPlay). The live alternative: two MusicKit instances
(``MusicKit.enableMultipleInstances``), A playing into its out-point while B
starts at its in-point at ``rate_b`` with a volume ramp. That only works if
Apple lets one account play two streams at once and if B starts predictably.

SILENT by construction: both instances run at volume 0.

Probe 1 killed the cold version (spread 3166 ms). Probe 2 criterion, written
before the run in PROGI_szew.md: per pair, after one silent warm-up start of
B, 5 starts with spread <= 469 ms and none > 3000 ms.

Kill criteria, written before the first run:
(a) the second instance cannot play while the first plays (error such as
    DEVICE_LIMIT / 403, or A stops when B starts) → no live seam;
(b) across 5 starts of B (queued, seeked, paused, then play()), the spread of
    play()-to-moving latency exceeds one beat at 128 bpm (469 ms) → B cannot
    be placed on a beat; a live seam would misrepresent the pairing.

Tokens cross js_api only (in memory); nothing is served over HTTP.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

TU = pathlib.Path(__file__).resolve().parent
ROOT = TU.parents[1]
sys.path.insert(0, str(ROOT / "src"))

SONG_A = "1687954211"      # Jinjé — A Ship Full of Ghosts (library)
SONG_B = "1893195285"      # Daniel Avery & bdrmm (library)
CUE_B = 30.0
TRIES = 5

JS = r"""
window.__WYNIK__ = null;
(async () => {
  const w = {tries: []};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const within = (p, ms, what) => Promise.race([p, sleep(ms).then(() => {
    throw new Error(what + ' > ' + ms + ' ms'); })]);
  let A = null, B = null;
  try {
    await new Promise(res => (window.pywebview && window.pywebview.api) ? res()
      : window.addEventListener('pywebviewready', res, {once: true}));
    const t = await window.pywebview.api.tokeny();
    if (t.storefront && t.team) localStorage.setItem(`music.${t.team}.itua`, t.storefront);
    await new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = 'https://js-cdn.music.apple.com/musickit/v3/musickit.js';
      s.onload = res; s.onerror = () => rej(new Error('musickit.js did not load'));
      document.head.appendChild(s);
    });
    if (!window.MusicKit || !MusicKit.configure) {
      await new Promise(res => document.addEventListener('musickitloaded', res, {once: true}));
    }
    MusicKit.enableMultipleInstances();
    const base = location.href.split('#')[0];
    const hash = '#' + btoa(JSON.stringify({itre: '0', musicUserToken: t.user, cid: ''}));
    const cfg = {developerToken: t.dev, app: {name: 'DanceLab', build: '1'}};
    if (t.storefront) cfg.storefrontId = t.storefront;
    history.replaceState(null, '', base + hash);
    A = await within(MusicKit.configure(cfg), 15000, 'configure A');
    history.replaceState(null, '', base + hash);
    B = await within(MusicKit.configure(cfg), 15000, 'configure B');
    history.replaceState(null, '', base);
    w.two_instances = A !== B;
    w.auth = [A.isAuthorized, B.isAuthorized];
    A.volume = 0; B.volume = 0;
    w.pairs = [];
    for (const [sa, sb] of %PAIRS%) {
      const pr = {a: sa, b: sb, tries: []};
      try {
        await within(A.setQueue({song: sa, startPlaying: false}), 15000, 'queue A');
        await within(A.play(), 15000, 'play A');
        await within(B.setQueue({song: sb, startPlaying: false}), 15000, 'queue B');
        // warm-up: one silent start of B, not timed
        await within(B.seekToTime(%CUE%), 10000, 'seek B warm');
        const tw = performance.now(); const pw = B.currentPlaybackTime || 0;
        await within(B.play(), 10000, 'play B warm');
        while (performance.now() - tw < 8000 && (B.currentPlaybackTime || 0) <= pw + 0.05) await sleep(20);
        pr.warmup_ms = Math.round(performance.now() - tw);
        await B.pause(); await sleep(400);
        for (let i = 0; i < %TRIES%; i++) {
          const r = {};
          try {
            await within(B.seekToTime(%CUE%), 10000, 'seek B');
            const p0 = B.currentPlaybackTime || 0;
            const t0 = performance.now();
            await within(B.play(), 10000, 'play B');
            while (performance.now() - t0 < 8000 && (B.currentPlaybackTime || 0) <= p0 + 0.05) await sleep(20);
            r.latency_ms = Math.round(performance.now() - t0);
            r.moved = (B.currentPlaybackTime || 0) > p0 + 0.05;
            r.a_playing = A.playbackState === 2;
            await sleep(600); await B.pause(); await sleep(400);
          } catch (e) { r.error = String(e && (e.message || e.name || e.reason) || e); }
          pr.tries.push(r);
        }
        await A.pause();
      } catch (e) { pr.error = String(e && (e.message || e.name || e.reason) || e); }
      w.pairs.push(pr);
    }
  } catch (e) { w.error = String(e && (e.message || e.name || e.reason) || e); }
  finally {
    for (const x of [A, B]) { if (x) { try { await x.stop(); } catch (e) {} } }
    w.states_after = [A && A.playbackState, B && B.playbackState];
  }
  window.__WYNIK__ = w;
})();
"""


class Api:
    """Tokens for the probe page only, in memory."""

    def tokeny(self) -> dict:
        from dancelab.ingestion.apple_music_api import (
            AppleMusicClient, developer_token, load_config, read_user_token,
        )
        cfg = load_config()
        dev = developer_token(pathlib.Path(cfg["klucz"]), cfg["key_id"], cfg["team_id"], 3600)
        user = read_user_token()
        sf = AppleMusicClient(dev, user).get("/v1/me/storefront").get("data", [{}])[0].get("id")
        return {"dev": dev, "user": user, "team": str(cfg["team_id"]).lower(), "storefront": sf}


def main() -> None:
    """Run the silent two-player probe and print the verdict data."""
    import webview

    page = TU / "szew_sonda2.html"
    js = (JS.replace("%A%", SONG_A).replace("%B%", SONG_B)
          .replace("%CUE%", str(CUE_B)).replace("%TRIES%", str(TRIES))
          .replace("%PAIRS%", sys.argv[1] if len(sys.argv) > 1 else "[]"))
    page.write_text("<!doctype html><meta charset='utf-8'><body style='font:14px system-ui;"
                    "background:#0e1013;color:#ccc;padding:1rem'>sonda szwu — głośność 0"
                    f"<script>{js}</script>", encoding="utf-8")
    win = webview.create_window("DanceLab sonda szwu", url=page.as_uri(), js_api=Api(),
                                width=420, height=140)
    wynik: dict = {}

    def run() -> None:
        end = time.time() + 240
        while time.time() < end:
            try:
                raw = win.evaluate_js("JSON.stringify(window.__WYNIK__ || null)")
            except Exception:  # noqa: BLE001
                raw = None
            if raw and raw != "null":
                wynik.update(json.loads(raw))
                break
            time.sleep(1)
        else:
            wynik["timeout_s"] = 240
            try:
                win.evaluate_js("try { MusicKit.getInstance().stop(); } catch (e) {}")
            except Exception:  # noqa: BLE001
                pass
        win.destroy()

    webview.start(run)
    page.unlink(missing_ok=True)
    for pr in wynik.get("pairs", []):
        lat = [t["latency_ms"] for t in pr["tries"] if t.get("moved")]
        if lat:
            pr["spread_ms"], pr["max_ms"] = max(lat) - min(lat), max(lat)
            pr["zdane"] = pr["spread_ms"] <= 469 and pr["max_ms"] <= 3000 and len(lat) == len(pr["tries"])
    text = json.dumps(wynik, ensure_ascii=False, indent=1)
    (TU / "wynik_szew2.json").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
