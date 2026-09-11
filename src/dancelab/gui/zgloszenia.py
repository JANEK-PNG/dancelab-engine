"""Bug reports filed from inside the window ("Zgłoś", ⌘⇧B).

A tester presses one key where something went wrong; the window keeps a
screenshot taken at that moment, the state of the screen and the last
console errors, and asks for one sentence. This module turns that into a
ticket folder a developer (or Claude) can read without asking follow-up
questions:

    ~/.dancelab/zgloszenia/DL-20260911-153210/
        zgloszenie.json   everything, machine-readable
        ZGLOSZENIE.md     the same for a human, description first
        zrzut.png         the window as it was when the key was pressed

Why a local folder and not a GitHub issue: the repository is public and a
screenshot shows the owner's library. Tickets stay on the machine until
someone decides what leaves it.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

WAGI = {"blokujacy": "blokujący — nie da się pracować",
        "powazny": "poważny — działa źle",
        "drobny": "drobny — wygląd, tekst"}
REPO = Path(__file__).resolve().parents[3]


def katalog_zgloszen() -> Path:
    """Where tickets go: $DANCELAB_ZGLOSZENIA, else ~/.dancelab/zgloszenia."""
    return Path(os.environ.get("DANCELAB_ZGLOSZENIA") or Path.home() / ".dancelab" / "zgloszenia")


def commit_repo() -> str | None:
    """Short commit of the running code, or None outside a git checkout."""
    if not (REPO / ".git").exists():
        return None
    try:
        out = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, timeout=2)
        brudne = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"],
                                capture_output=True, text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return None
    sha = out.stdout.strip() or None
    return f"{sha}+zmiany" if sha and brudne.stdout.strip() else sha


def _jedna_linia(tekst: str, n: int = 72) -> str:
    t = " ".join(str(tekst or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def zapisz(opis: str, waga: str, stan_okna: dict[str, Any], zrzut_png: bytes | None,
           srodowisko: dict[str, Any] | None = None, katalog: Path | None = None,
           teraz: float | None = None) -> dict[str, Any]:
    """Write one ticket folder; return {"id", "sciezka", "zrzut"} or {"blad"}."""
    opis = str(opis or "").strip()
    if not opis:
        return {"blad": "napisz jednym zdaniem, co się stało — bez tego zgłoszenie nic nie mówi"}
    if waga not in WAGI:
        return {"blad": f"nieznana waga zgłoszenia: {waga!r}"}
    ts = time.localtime(teraz if teraz is not None else time.time())
    zid = time.strftime("DL-%Y%m%d-%H%M%S", ts)
    baza = Path(katalog) if katalog is not None else katalog_zgloszen()
    cel = baza / zid
    n = 2
    while cel.exists():                                   # two reports in one second
        cel = baza / f"{zid}-{n}"
        n += 1
    cel.mkdir(parents=True)
    stan_okna = dict(stan_okna or {})
    bledy = [str(b)[:500] for b in (stan_okna.pop("bledy_konsoli", None) or [])][-20:]
    dane = {
        "id": cel.name, "czas": time.strftime("%Y-%m-%d %H:%M:%S", ts),
        "opis": opis, "waga": waga,
        "commit": commit_repo(), "system": f"macOS {platform.mac_ver()[0]}" if platform.mac_ver()[0] else platform.platform(),
        "srodowisko": srodowisko or {}, "okno": stan_okna, "bledy_konsoli": bledy,
        "zrzut": "zrzut.png" if zrzut_png else None,
    }
    if zrzut_png:
        (cel / "zrzut.png").write_bytes(zrzut_png)
    (cel / "zgloszenie.json").write_text(json.dumps(dane, ensure_ascii=False, indent=1), encoding="utf-8")
    (cel / "ZGLOSZENIE.md").write_text(_markdown(dane), encoding="utf-8")
    return {"id": cel.name, "sciezka": str(cel), "zrzut": bool(zrzut_png)}


def _markdown(d: dict[str, Any]) -> str:
    okno = d.get("okno") or {}
    linie = [
        f"# {d['id']} · {WAGI[d['waga']]}", "",
        d["opis"], "",
        f"- **Kiedy:** {d['czas']}",
        f"- **Wersja:** commit {d.get('commit') or 'nieznany'}, {d.get('system')}",
        f"- **Ekran:** {okno.get('ekran') or '?'}"
        + (f", utwór „{_jedna_linia(okno.get('tytul'), 60)}”" if okno.get("tytul") else ""),
    ]
    if okno.get("opis_gry"):
        linie.append(f"- **Pasek odtwarzacza:** {_jedna_linia(okno['opis_gry'], 100)}")
    if okno.get("notki"):
        linie += ["", "## Co silnik zgłosił", *[f"- {_jedna_linia(x, 140)}" for x in okno["notki"][:10]]]
    if d.get("bledy_konsoli"):
        linie += ["", "## Błędy konsoli (ostatnie)", "```", *d["bledy_konsoli"][-10:], "```"]
    linie += ["", "Zrzut okna: `zrzut.png`" if d.get("zrzut") else "Zrzutu okna nie ma — patrz `srodowisko.zrzut` w JSON."]
    return "\n".join(linie) + "\n"


def lista(katalog: Path | None = None) -> list[dict[str, Any]]:
    """Tickets on disk, newest first: id, when, weight, one-line description."""
    baza = Path(katalog) if katalog is not None else katalog_zgloszen()
    out = []
    for p in sorted(baza.glob("DL-*/zgloszenie.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"id": d.get("id"), "czas": d.get("czas"), "waga": d.get("waga"),
                    "opis": _jedna_linia(d.get("opis"), 90)})
    return out

