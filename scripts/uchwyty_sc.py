"""Dobiera uchwyty SoundCloud artystom, którzy ich jeszcze nie mają.

Dotąd uchwyty brały się UBOCZNIE: konto wrzucające set bywało kontem artysty
i to wystarczało za pewne dopasowanie. Dało 459 uchwytów za darmo, ale zostawiło
778 artystów bez żadnego — a bez uchwytu nie ma jak zajrzeć na ich konto po sety
podcastowe i radiowe. To jest wąskie gardło całej kategorii, którą Janek uznał
za osobną i mocną.

Tu pytamy wprost: wyszukiwarka użytkowników SoundCloud po nazwie.

DOPASOWANIE JEST OSTRE, bo tanie pomyłki są tu drogie — zły uchwyt wciągnie
cudzy katalog pod nazwisko naszego DJ-a i zatruje wszystko, co z niego
policzymy. Warunki:

  * nazwa profilu MUSI zgadzać się z ksywą po normalizacji, znak w znak;
  * profil musi mieć choć jeden wrzut — puste konto o zgodnej nazwie to
    zwykle squat, nie artysta;
  * przy nazwach krótszych niż pięć znaków po normalizacji ODPUSZCZAMY.
    „MIT", „KARI", „Capo" trafiają w setki kont i żadne z nich nie jest
    pewne. Puste pole znaczy „nie wiem" i jest poprawną wartością (ADR-005).

Wynik z zgodną nazwą, ale bez wrzutów albo z jednym, oznaczamy jako
`niepewne` i zostawiamy DJ-owi do rozstrzygnięcia zamiast wpisywać po cichu.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time
import unicodedata as U
import urllib.parse
import urllib.request

OUT = pathlib.Path("experiments_priv/2026-08-03_dj_mapa")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
API = "https://api-v2.soundcloud.com"


def _n(s: str) -> str:
    s = U.normalize("NFKD", s or "")
    s = "".join(c for c in s if not U.combining(c))
    return "".join(c for c in s.lower() if c.isalnum())


def _js(url: str):
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:                                         # noqa: BLE001
        print(f"    {e}", file=sys.stderr)
        return None


def client_id() -> str | None:
    try:
        req = urllib.request.Request("https://soundcloud.com/discover", headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception:                                              # noqa: BLE001
        return None
    for src in re.findall(r'src="(https://a-v2\.sndcdn\.com/assets/[^"]+\.js)"', html):
        try:
            req = urllib.request.Request(src, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                js = r.read().decode("utf-8", "replace")
        except Exception:                                          # noqa: BLE001
            continue
        m = re.search(r'client_id\s*:\s*"([A-Za-z0-9]{20,})"', js)
        if m:
            return m.group(1)
    return None


def znajdz(ksywa: str, cid: str) -> dict | None:
    d = _js(f"{API}/search/users?q={urllib.parse.quote(ksywa)}"
            f"&client_id={cid}&limit=15")
    if not isinstance(d, dict):
        return None
    cel = _n(ksywa)
    for u in d.get("collection") or []:
        if _n(u.get("username", "")) != cel and _n(u.get("permalink", "")) != cel:
            continue
        wrzutow = u.get("track_count") or 0
        return {
            "soundcloud": u.get("permalink"),
            "nazwa_profilu": u.get("username"),
            "wrzutow": wrzutow,
            "obserwujacych": u.get("followers_count") or 0,
            "pewnosc": "potwierdzone" if wrzutow >= 2 else "niepewne",
        }
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pauza", type=float, default=0.35)
    ap.add_argument("--min-znakow", type=int, default=5,
                    help="Krótsze ksywy trafiają w setki kont — odpuszczamy.")
    args = ap.parse_args()

    cid = client_id()
    if not cid:
        print("Brak client_id.")
        return 1

    soc = json.loads((OUT / "socials.json").read_text())
    artysci = [a.strip() for a in (OUT / "artysci_wszyscy.txt").read_text().splitlines()
               if a.strip()]
    braki = [a for a in artysci if not (soc.get(a) or {}).get("soundcloud")]
    krotkie = [a for a in braki if len(_n(a)) < args.min_znakow]
    braki = [a for a in braki if len(_n(a)) >= args.min_znakow]
    print(f"bez uchwytu: {len(braki) + len(krotkie)}  "
          f"(w tym {len(krotkie)} zbyt krótkich, pomijamy)")

    trafione = niepewne = 0
    for i, a in enumerate(braki, 1):
        w = znajdz(a, cid)
        if w:
            soc.setdefault(a, {})["soundcloud"] = w["soundcloud"]
            soc[a]["sc_wrzutow"] = w["wrzutow"]
            soc[a]["sc_pewnosc"] = w["pewnosc"]
            trafione += 1
            niepewne += w["pewnosc"] == "niepewne"
        if i % 50 == 0:
            print(f"  {i}/{len(braki)} — trafionych {trafione}", flush=True)
            (OUT / "socials.json").write_text(json.dumps(soc, ensure_ascii=False, indent=1))
        time.sleep(args.pauza)

    (OUT / "socials.json").write_text(json.dumps(soc, ensure_ascii=False, indent=1))
    print(f"\nnowych uchwytów: {trafione} (z tego niepewnych: {niepewne})")
    print(f"razem w socials.json: "
          f"{sum(1 for v in soc.values() if (v or {}).get('soundcloud'))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
