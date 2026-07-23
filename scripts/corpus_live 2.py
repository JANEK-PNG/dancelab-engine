"""Live terminal dashboard for the DanceLab corpus pipeline — BITEK DELUXE.

Pure stdlib + ANSI. Animation ~2.5 fps; pipeline data re-read every
DATA_REFRESH_SEC; per-report stats cached so nothing is parsed twice.
Bitek and his crew dance under the disco ball while the machines grind;
every freshly matched mix throws confetti. Ctrl+C exits the viewer only.

Usage:
  python3 scripts/corpus_live.py            # live
  python3 scripts/corpus_live.py --once     # single static frame
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import time
from pathlib import Path

ROOT = Path("/Volumes/MY_PC/DanceLabCorpus")
QUEUE_TOTAL = 1857
BAR_W = 58
DATA_REFRESH_SEC = 3.0
FRAME_SEC = 0.4
CELEBRATE_FRAMES = 14
DECK_ROTATE_FRAMES = 12  # ~5 s per track on the deck line

DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
BOLD = "\033[1m"
RESET = "\033[0m"
HOME = "\033[H\033[J"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

VINYL = "◐◓◑◒"
EQ_BLOCKS = " ▁▂▃▄▅▆▇█"
SPARK = "▁▂▃▄▅▆▇█"
DISCO = ["✦", "✧", "☆", "✧"]
NOTES = "♪♫♬♩"

BITEK = [r"\(•‿•)  ", r" (•‿•)/ ", r"\(•‿•)/ ", r" (•‿•)~ ", r"~(•‿•)  ", r" (>‿•)/ "]
BITKA = [r" (^‿^)/ ", r"\(^‿^)  ", r" (^‿^)~ ", r"\(^‿^)/ ", r" (^‿-)/ ", r"~(^‿^)  "]
GRUBY = [r" [•_•]  ", r" [•_•]> ", r" <[•_•] ", r" [•_■]  ", r" [■_■]  ", r" [■_■]> "]
RAVKA = [r"~(o‿o)~ ", r" (o‿o)/ ", r"\(o‿o)~ ", r"~(o‿o)/ ", r" (o‿~)  ", r"\(o‿o)/ "]
SWIR = [r" (ಠ‿ಠ)/ ", r"\(ಠ‿ಠ)  ", r"~(ಠ‿ಠ)~ ", r" (ಠ‿ಠ)> ", r"<(ಠ‿ಠ)  ", r"\(ಠ‿ಠ)/ "]
PARTY = [r"\(^o^)/ ", r"\(^▽^)/ ", r"\(≧▽≦)/ ", r"\(^o^)/ "]
CROWD_FRONT = [BITEK, BITKA, GRUBY]
CROWD_BACK = [RAVKA, SWIR, BITKA]
BALL_SWING = [-3, -2, -1, 0, 1, 2, 3, 2, 1, 0, -1, -2]
FADER_PATH = [0, 1, 2, 3, 4, 3, 2, 1]
STAGE_W = 68

ONELINERS = [
    "kwantyzacja to stan umysłu",
    "88 czy 175? Bitek zna prawdę",
    "DTW przesuwa, Bitek czuje",
    "phrase co 32 beaty, jak w naturze",
    "match 1.00 — Maribou State approved",
    "jungle nie gada z house'em",
    "cue-in, cue-out, cue-życie",
    "evidence-gated, mordo",
    "Bitek nie zgaduje. Bitek mierzy.",
    "beatgrid reliable = spokój ducha",
]


def alive(pattern: str) -> bool:
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def count_real(dir_: Path, suffix: str = "") -> int:
    if not dir_.is_dir():
        return 0
    return sum(
        1 for p in dir_.iterdir()
        if not p.name.startswith("._") and (not suffix or p.name.endswith(suffix))
    )


def progress_bar(done: int, total: int, width: int = BAR_W, color: str = GREEN) -> str:
    frac = 0.0 if total <= 0 else min(1.0, done / total)
    fill = int(round(frac * width))
    return f"{color}{'█' * fill}{DIM}{'░' * (width - fill)}{RESET} {done}/{total} ({frac:5.1%})"


def mix_title(dataset: dict, mix_id: str) -> str:
    title = dataset.get(mix_id, {}).get("title", mix_id)
    return re.sub(r"^\d{4}(-\d{2}){0,2} - ", "", title)[:52]


def mini_timeline(report: dict, width: int = BAR_W) -> tuple[str, str]:
    placements = []
    end_max = 0.0
    for result in report.get("results", []):
        if not result["alignment"]["matched"]:
            continue
        cues = [c for c in result.get("cue_candidates", []) if c.get("mix_cue_in_sec") is not None]
        if not cues:
            continue
        start = float(cues[0]["mix_cue_in_sec"])
        end = float(cues[0]["mix_cue_out_sec"] or start)
        placements.append((start, max(end, start + 1.0), float(result["alignment"]["match_rate"])))
        end_max = max(end_max, end)
    if not placements or end_max <= 0:
        return DIM + "·" * width + RESET, "0 matched"
    cells = [" "] * width
    for start, end, rate in sorted(placements):
        a = min(width - 1, int(start / end_max * width))
        b = min(width - 1, max(a, int(end / end_max * width)))
        ch = "█" if rate >= 0.5 else "▒"
        for i in range(a, b + 1):
            cells[i] = ch
    line = "".join(cells).replace("█", f"{CYAN}█{RESET}").replace("▒", f"{DIM}▒{RESET}")
    n_tr = sum(1 for t in report.get("transitions", []) if t.get("valid"))
    return line, f"{len(placements)} matched · {n_tr} valid trans."


def matched_tracks(report: dict, dataset: dict) -> list[tuple[float, float, float, str]]:
    titles = {
        t["id"]: t.get("title", "")
        for t in dataset.get(report["mix_id"], {}).get("tracklist", [])
        if t.get("id")
    }
    rows = []
    for result in report.get("results", []):
        if not result["alignment"]["matched"]:
            continue
        cues = [c for c in result.get("cue_candidates", []) if c.get("mix_cue_in_sec") is not None]
        if not cues:
            continue
        title = re.sub(r"^\s*\[[^\]]*\]\s*", "", titles.get(result["youtube_id"], result["youtube_id"]))
        rows.append((
            float(cues[0]["mix_cue_in_sec"]),
            float(cues[0]["mix_cue_out_sec"] or 0.0),
            float(result["alignment"]["match_rate"]),
            title,
        ))
    return sorted(rows)


class ReportStats:
    """Cached per-file stats so the totals never re-parse old reports."""

    def __init__(self) -> None:
        self.by_file: dict[str, tuple[int, int]] = {}  # name -> (matched, valid_transitions)

    def refresh(self) -> tuple[int, int]:
        align_dir = ROOT / "alignments"
        if align_dir.is_dir():
            for path in align_dir.glob("*.json"):
                if path.name.startswith("._") or path.name in self.by_file:
                    continue
                try:
                    report = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                matched = sum(1 for r in report.get("results", []) if r["alignment"]["matched"])
                valid = sum(1 for t in report.get("transitions", []) if t.get("valid"))
                self.by_file[path.name] = (matched, valid)
        total_m = sum(m for m, _ in self.by_file.values())
        total_t = sum(t for _, t in self.by_file.values())
        return total_m, total_t


def latest_reports(n: int = 3) -> list[Path]:
    align_dir = ROOT / "alignments"
    if not align_dir.is_dir():
        return []
    files = [p for p in align_dir.glob("*.json") if not p.name.startswith("._")]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:n]


def collect_snapshot(stats: ReportStats, dataset: dict) -> dict:
    reports = []
    deck: list[str] = []
    for path in latest_reports():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        reports.append((path, report))
        for _, _, rate, title in matched_tracks(report, dataset):
            if rate >= 0.5:
                deck.append(title)
    total_matched, total_trans = stats.refresh()
    spark_vals = [m for m, _ in list(stats.by_file.values())[-24:]]
    return {
        "dl": alive("corpus_downloader.py"),
        "al": alive("corpus_align.py"),
        "mixes": count_real(ROOT / "mixes"),
        "tracks": count_real(ROOT / "tracks"),
        "aligned": count_real(ROOT / "alignments", ".json"),
        "reports": reports,
        "deck": deck or ["cisza przed dropem…"],
        "total_matched": total_matched,
        "total_trans": total_trans,
        "spark": spark_vals,
    }


class Equalizer:
    def __init__(self, bars: int = 34) -> None:
        self.heights = [random.randint(2, 7) for _ in range(bars)]

    def step(self) -> str:
        out = []
        for i, h in enumerate(self.heights):
            h = max(1, min(8, h + random.choice((-2, -1, -1, 1, 1, 2))))
            self.heights[i] = h
            color = CYAN if h <= 4 else (GREEN if h <= 6 else YELLOW)
            out.append(f"{color}{EQ_BLOCKS[h]}{RESET}")
        return "".join(out)


def sparkline(values: list[int]) -> str:
    if not values:
        return ""
    peak = max(max(values), 1)
    return "".join(f"{CYAN}{SPARK[min(7, int(v / peak * 7))]}{RESET}" for v in values)


def _confetti(frame: int, width: int = STAGE_W) -> str:
    rng = random.Random(frame)
    cells = [" "] * width
    for _ in range(20):
        pos = rng.randrange(width)
        color = rng.choice((MAGENTA, CYAN, YELLOW, GREEN, RED))
        cells[pos] = f"{color}{rng.choice('✦✧*•' + NOTES)}{RESET}"
    return "  " + "".join(cells)


def _lasers(frame: int, width: int = STAGE_W) -> list[str]:
    cells = [" "] * width
    for beam in range(4):
        pos = (frame * (3 + beam * 2) + beam * 15) % width
        color = (MAGENTA, CYAN, BLUE, GREEN)[beam]
        cells[pos] = f"{color}╱{RESET}" if (frame + beam) % 2 else f"{color}╲{RESET}"
    note_pos = (frame * 5 + 7) % width
    cells[note_pos] = f"{CYAN}{NOTES[frame % len(NOTES)]}{RESET}"
    return cells


def _crowd_row(dancers: list[list[str]], frame: int, colors: tuple, party: bool) -> str:
    out = []
    for i in range(6):
        frames = PARTY if party else dancers[i % len(dancers)]
        pose = frames[(frame + i * 2) % len(frames)]
        out.append(f"{colors[i % len(colors)]}{pose}{RESET}")
    return "".join(out)


def _speaker(frame: int, seed: int) -> str:
    rng = random.Random(frame // 2 + seed)
    lit = rng.random() > 0.4
    return f"{YELLOW if lit else DIM}▮▮{RESET}"


def stage_lines(frame: int, celebrating: int, eq: Equalizer) -> list[str]:
    lines: list[str] = []
    mid = STAGE_W // 2
    # ceiling + swinging disco ball
    lines.append("  " + DIM + "═" * (mid - 1) + "╤" + "═" * (STAGE_W - mid) + RESET)
    swing = BALL_SWING[frame % len(BALL_SWING)]
    ball = f"{YELLOW}{DISCO[frame % len(DISCO)]}({'☼' if frame % 2 else '◉'}){DISCO[(frame + 1) % len(DISCO)]}{RESET}"
    lines.append(" " * (2 + mid - 2 + swing) + ball)
    # laser field / confetti during celebration
    lines.append(_confetti(frame) if celebrating > 0 else "  " + "".join(_lasers(frame)))
    # DJ booth: two spinning decks + travelling crossfader
    fader_slots = ["─"] * 5
    fader_slots[FADER_PATH[frame % len(FADER_PATH)]] = f"{YELLOW}▣{RESET}{DIM}"
    fader = f"{DIM}A ─{''.join(fader_slots)}─ B{RESET}"
    deck_a = f"{MAGENTA}{VINYL[frame % 4]}{RESET}"
    deck_b = f"{MAGENTA}{VINYL[(frame + 2) % 4]}{RESET}"
    booth_label = f"{BOLD}B I T E K{RESET}" if celebrating == 0 else f"{YELLOW}{BOLD}N O W Y  S E T !{RESET}"
    inner_w = STAGE_W - 14
    lines.append("      " + DIM + "┌" + "─" * inner_w + "┐" + RESET)
    lines.append(f"      {DIM}│{RESET}  {deck_a}   {booth_label}   {fader}   {deck_b}  {DIM}│{RESET}")
    lines.append("      " + DIM + "└" + "─" * inner_w + "┘" + RESET)
    # crowd rows flanked by speakers
    party = celebrating > 0
    back = _crowd_row(CROWD_BACK, frame + 3, (DIM + CYAN, DIM + MAGENTA, DIM + GREEN), party)
    front = _crowd_row(CROWD_FRONT, frame, (GREEN, MAGENTA, CYAN), party)
    lines.append(f"  {_speaker(frame, 1)}   {back}   {_speaker(frame, 2)}")
    lines.append(f"  {_speaker(frame, 3)}  {front}  {_speaker(frame, 4)}")
    # full-width dance floor equalizer
    lines.append("  " + eq.step())
    return lines


def deck_line(snap: dict, frame: int) -> str:
    deck = snap["deck"]
    track = deck[(frame // DECK_ROTATE_FRAMES) % len(deck)][:56]
    note = f"{CYAN}{NOTES[frame % len(NOTES)]}{RESET}"
    return f"  {note} {DIM}na deckach:{RESET} {BOLD}{track}{RESET}"


def quote_line(frame: int) -> str:
    quote = ONELINERS[(frame // 40) % len(ONELINERS)]
    return f"  {DIM}Bitek mówi: „{quote}”{RESET}"


def render(dataset: dict, snap: dict, frame: int, celebrating: int, eq: Equalizer) -> str:
    lines: list[str] = []
    now = time.strftime("%H:%M:%S")
    lines.append(f"{BOLD}DanceLab Corpus — live{RESET}   {DIM}{now} · Ctrl+C wychodzi (pipeline zostaje){RESET}")
    lines.extend(stage_lines(frame, celebrating, eq))
    lines.append(deck_line(snap, frame))
    lines.append(quote_line(frame))
    lines.append("")

    dl_state = f"{GREEN}● DZIAŁA{RESET}" if snap["dl"] else f"{RED}● STOP{RESET}"
    al_state = f"{GREEN}● DZIAŁA{RESET}" if snap["al"] else f"{RED}● STOP{RESET}"
    lines.append(
        f"{BOLD}POBIERANIE{RESET} {dl_state}   mixy: {BOLD}{snap['mixes']}{RESET}"
        f"   tracki: {BOLD}{snap['tracks']}{RESET}"
    )
    lines.append("  " + progress_bar(snap["mixes"], QUEUE_TOTAL, color=GREEN))
    lines.append(f"{BOLD}MATCHING (pełne DTW){RESET} {al_state}   "
                 f"dopasowane tracki: {BOLD}{snap['total_matched']}{RESET}"
                 f"   przejścia (valid): {BOLD}{YELLOW}{snap['total_trans']}{RESET}")
    lines.append("  " + progress_bar(snap["aligned"], snap["mixes"], color=CYAN))
    if snap["spark"]:
        lines.append(f"  {DIM}matched/mix (ostatnie {len(snap['spark'])}):{RESET} {sparkline(snap['spark'])}")
    lines.append("")
    lines.append(f"{BOLD}OSTATNIO ZMATCHOWANE{RESET}  {DIM}█ pewne (≥0.5) ▒ słabsze · szerokość = pozycja w micie{RESET}")

    for index, (path, report) in enumerate(snap["reports"]):
        bar, meta = mini_timeline(report)
        age = int(time.time() - path.stat().st_mtime)
        age_s = f"{age // 60}m temu" if age >= 60 else f"{age}s temu"
        lines.append(f"  {YELLOW}{report['mix_id']}{RESET} {mix_title(dataset, report['mix_id'])}  {DIM}({age_s}){RESET}")
        lines.append(f"  |{bar}| {DIM}{meta}{RESET}")
        if index < 3:
            for start, end, rate, title in matched_tracks(report, dataset):
                color = CYAN if rate >= 0.5 else DIM
                lines.append(
                    f"      {color}{start / 60:5.1f}–{end / 60:5.1f} min{RESET}  "
                    f"{DIM}match {rate:.2f}{RESET}  {title[:46]}"
                )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    dataset = {m["id"]: m for m in json.loads((ROOT / "djmix-dataset.json").read_text())}
    eq = Equalizer()
    stats = ReportStats()
    snap = collect_snapshot(stats, dataset)
    if args.once:
        print(render(dataset, snap, 0, 0, eq))
        return 0

    frame = 0
    celebrating = 0
    last_pull = time.time()
    last_aligned = snap["aligned"]
    try:
        print(HIDE_CURSOR, end="")
        while True:
            if time.time() - last_pull >= DATA_REFRESH_SEC:
                snap = collect_snapshot(stats, dataset)
                last_pull = time.time()
                if snap["aligned"] > last_aligned:
                    celebrating = CELEBRATE_FRAMES
                    last_aligned = snap["aligned"]
            print(HOME + render(dataset, snap, frame, celebrating, eq), flush=True)
            celebrating = max(0, celebrating - 1)
            frame += 1
            time.sleep(FRAME_SEC)
    except KeyboardInterrupt:
        print(SHOW_CURSOR + "\n" + DIM + "Bitek, Bitka i Gruby idą spać — maszyny mielą dalej." + RESET)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
