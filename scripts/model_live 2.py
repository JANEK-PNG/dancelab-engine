"""Live terminal dashboard for the H + E model-gate passes — Bitek is back.

Pure stdlib + ANSI. Bitek and crew dance while H (engine analysis) and E (CLAP
embeddings) grind toward the 2881-track universe. Ctrl+C exits the viewer only.

Usage: python3 scripts/model_live.py
"""

from __future__ import annotations

import json
import random
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H_DIR = ROOT / "data/reports/corpus_ordering/h_analysis"
E_PARTIAL = ROOT / "data/reports/corpus_ordering/embeddings.partial.json"
E_FINAL = ROOT / "data/reports/corpus_ordering/embeddings.json"
TARGET = 2881
FRAME_SEC = 0.4
DATA_SEC = 3.0

DIM = "\033[2m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; RED = "\033[31m"
CYAN = "\033[36m"; MAGENTA = "\033[35m"; BLUE = "\033[34m"; BOLD = "\033[1m"; RESET = "\033[0m"
HOME = "\033[H\033[J"; HIDE = "\033[?25l"; SHOW = "\033[?25h"

VINYL = "◐◓◑◒"; DISCO = ["✦", "✧", "☆", "✧"]; EQC = " ▁▂▃▄▅▆▇█"; NOTES = "♪♫♬♩"
BITEK = [r"\(•‿•)  ", r" (•‿•)/ ", r"\(•‿•)/ ", r" (•‿•)~ ", r"~(•‿•)  ", r" (>‿•)/ "]
BITKA = [r" (^‿^)/ ", r"\(^‿^)  ", r" (^‿^)~ ", r"\(^‿^)/ ", r" (^‿-)/ ", r"~(^‿^)  "]
GRUBY = [r" [•_•]  ", r" [•_•]> ", r" <[•_•] ", r" [•_■]  ", r" [■_■]  ", r" [■_■]> "]
PARTY = [r"\(^o^)/", r"\(^▽^)/", r"\(≧▽≦)/", r"\(^o^)/"]
QUOTES = [
    "H liczy grid, E czuje wibe", "512 wymiarów jednego brzmienia",
    "webm już nie jest wrogiem", "CLAP słyszy to, czego BPM nie widzi",
    "2881 tracków, jedna prawda", "bramka fail-closed, spokój ducha",
    "Bitek nie zgaduje. Bitek liczy.", "embedding to podpis, nie ozdoba",
]


def alive(pat: str) -> bool:
    return subprocess.run(["pgrep", "-f", pat], capture_output=True).returncode == 0


def h_count() -> int:
    if not H_DIR.is_dir():
        return 0
    return sum(1 for p in H_DIR.iterdir() if p.suffix == ".json" and not p.name.startswith("._"))


def e_count() -> int:
    for path in (E_FINAL, E_PARTIAL):
        try:
            data = json.loads(path.read_text())
            return len(data.get("tracks", data)) if isinstance(data, dict) else 0
        except (OSError, json.JSONDecodeError):
            continue
    return 0


def bar(done: int, total: int, color: str, width: int = 46) -> str:
    frac = min(1.0, done / total) if total else 0.0
    fill = int(round(frac * width))
    return f"{color}{'█' * fill}{DIM}{'░' * (width - fill)}{RESET} {done}/{total} ({frac:5.1%})"


class Eq:
    def __init__(self, n=30):
        self.h = [random.randint(2, 7) for _ in range(n)]

    def step(self):
        out = []
        for i, v in enumerate(self.h):
            v = max(1, min(8, v + random.choice((-2, -1, -1, 1, 1, 2))))
            self.h[i] = v
            c = CYAN if v <= 4 else (GREEN if v <= 6 else YELLOW)
            out.append(f"{c}{EQC[v]}{RESET}")
        return "".join(out)


def crew(frame, party, eq):
    v = f"{MAGENTA}{VINYL[frame % 4]}{RESET}"
    if party:
        p = f"{YELLOW}{PARTY[frame % 4]}{PARTY[(frame + 1) % 4]}{PARTY[(frame + 2) % 4]}{RESET}"
        return f"  {v} {p} {eq.step()}  {YELLOW}{BOLD}+25 TRACKÓW!{RESET}"
    trio = (f"{GREEN}{BITEK[frame % 6]}{RESET}{MAGENTA}{BITKA[(frame + 2) % 6]}{RESET}"
            f"{CYAN}{GRUBY[(frame + 4) % 6]}{RESET}")
    return f"  {v} {trio} {eq.step()}"


def render(frame, celebrate, eq, h, e):
    L = []
    now = time.strftime("%H:%M:%S")
    L.append(f"{BOLD}DanceLab — warstwa modelowa (H + E){RESET}  {DIM}{now} · Ctrl+C wychodzi{RESET}")
    ball = f"{YELLOW}{DISCO[frame % 4]}({'☼' if frame % 2 else '◉'}){DISCO[(frame + 1) % 4]}{RESET}"
    L.append("  " + DIM + "═" * 22 + "╤" + "═" * 22 + RESET)
    L.append(" " * 24 + ball)
    L.append(crew(frame, celebrate > 0, eq))
    L.append(f"  {DIM}Bitek mówi: „{QUOTES[(frame // 40) % len(QUOTES)]}”{RESET}")
    L.append("")
    hs = f"{GREEN}● DZIAŁA{RESET}" if alive("corpus_h_analysis") else f"{DIM}● gotowe/stop{RESET}"
    es = f"{GREEN}● DZIAŁA{RESET}" if alive("corpus_e_embeddings") else f"{DIM}● gotowe/stop{RESET}"
    L.append(f"{BOLD}H  analiza silnika (BPM/klucz/energia){RESET} {hs}")
    L.append("  " + bar(h, TARGET, GREEN))
    L.append(f"{BOLD}E  embedding CLAP (512-dim){RESET} {es}")
    L.append("  " + bar(e, TARGET, CYAN))
    L.append("")
    total = h + e
    L.append(f"  {DIM}razem policzone: {BOLD}{total}{RESET}{DIM} / {2 * TARGET} cech modelowych{RESET}")
    if h >= TARGET and e >= TARGET:
        L.append(f"  {YELLOW}{BOLD}H i E KOMPLETNE — zostaje DJ-mapping + obserwacje{RESET}")
    return "\n".join(L)


def main() -> int:
    eq = Eq()
    frame = 0
    celebrate = 0
    last_pull = 0.0
    h = e = 0
    last_total = 0
    try:
        print(HIDE, end="")
        while True:
            if time.time() - last_pull >= DATA_SEC:
                h, e = h_count(), e_count()
                last_pull = time.time()
                if h + e >= last_total + 25:
                    celebrate = 12
                    last_total = h + e
            print(HOME + render(frame, celebrate, eq, h, e), flush=True)
            celebrate = max(0, celebrate - 1)
            frame += 1
            time.sleep(FRAME_SEC)
    except KeyboardInterrupt:
        print(SHOW + "\n" + DIM + "Bitek wraca do tańca w tle — H i E mielą dalej." + RESET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
