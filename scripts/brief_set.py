"""Set z briefu DJ-a: pasmo tempa, wykluczone style, łuk energii, plan tempa.

Brief Janka na środę 2026-08-05 (00:00–01:00, po innym DJ-u, peak time):

    tempo 130–135 · energetycznie · krzywa tylko w górę · żadnego rozgrzewania
    NIE: house, „dzienne" · TAK: breaks, bas, UK bass, twardziej

Silnik ma już wszystkie potrzebne wejścia (`bpm_min`, `bpm_max`, `preferred_styles`,
`arc`, `tempo_shape`), ale komenda `zagraj` bierze FOLDER, a brief nie jest folderem
— utwory na 132 leżą w dziesięciu różnych katalogach. Więc kandydaci lecą stąd:
z biblioteki Rekordboxa, po tempie i po gatunku, który DJ sam im nadał.

Gatunek z Rekordboxa, nie z naszego klasyfikatora — bo klasyfikatora stylu nie mamy
(patrz rejestr: „klasyfikator stylu na 958 płytach z Discogs" wciąż niezrobiony),
a tagi Beatportu w bibliotece Janka są uzupełnione mniej więcej w połowie. Utwór bez
gatunku NIE jest odrzucany: nie wiemy, czym jest, a niewiedza nie jest powodem do
wykluczenia (ADR-005). Jest za to zaznaczony w wypisie, żeby DJ widział, co przeszło
bez sprawdzenia.
"""

from __future__ import annotations

import argparse
import pathlib
import unicodedata as U

# Style, które brief wyklucza. Dopasowanie po fragmencie nazwy, bo Beatport pisze
# „Melodic House & Techno" i „Afro House" — jedno słowo „house" łapie oba.
DAYTIME = ("house", "afro", "melodic", "mainstage", "dance / pop", "pop", "loop samples")

# Style, które brief chce. Nie są wymagane — są premiowane w wypisie, żeby DJ
# widział, ile z jego kierunku pula naprawdę ma.
WANTED = ("breaks", "breakbeat", "uk bass", "uk garage", "bassline", "bass / club",
          "dubstep", "techno", "electronica")


def candidates(bpm_min: float, bpm_max: float, *, exclude: bool = True):
    from pyrekordbox import Rekordbox6Database

    from dancelab.ingestion.preflight import (
        suspicious_duration_reason, suspicious_path_reason,
    )

    db = Rekordbox6Database()
    out, skipped, nietrack = [], [], []
    for c in db.get_content():
        if not c.FolderPath or not c.BPM:
            continue
        p = pathlib.Path(U.normalize("NFC", c.FolderPath))
        if p.suffix.lower() not in (".aiff", ".aif", ".wav", ".flac", ".mp3", ".m4a"):
            continue
        if not p.exists():
            continue
        bpm = c.BPM / 100.0
        if not (bpm_min <= bpm <= bpm_max):
            continue
        # Najpierw „czy to w ogóle płyta". Janek złapał w pierwszym odsiewie
        # własny set „Open Deck" (52 min) — tempo miał w paśmie, gatunku nie
        # miał, plik jak plik. Długość jest tym, co je odróżnia.
        powod = (suspicious_path_reason(p)
                 or suspicious_duration_reason(float(c.Length) if c.Length else None))
        if powod:
            nietrack.append((bpm, c.Title or p.stem, powod))
            continue
        genre = (getattr(c.Genre, "Name", "") if c.Genre else "") or ""
        low = genre.lower()
        if exclude and any(bad in low for bad in DAYTIME):
            skipped.append((bpm, c.Title or p.stem, genre))
            continue
        out.append((bpm, p, c.Title or p.stem, genre))
    db.close()
    out.sort(key=lambda x: x[0])
    if nietrack:
        print(f"odrzucone jako NIE-PŁYTY ({len(nietrack)}):")
        for bpm, title, powod in nietrack:
            print(f"    {bpm:6.2f}  {title[:40]:40s} — {powod}")
    return out, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bpm-min", type=float, default=130.0)
    ap.add_argument("--bpm-max", type=float, default=135.0)
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--name", default="DanceLab set")
    ap.add_argument("--tempo", default="staircase")
    ap.add_argument("--arc", default="build")
    ap.add_argument("--processed-dir", default="experiments_priv/2026-08-03_brief/processed")
    ap.add_argument("--out", default=None)
    ap.add_argument("--keep-daytime", action="store_true")
    args = ap.parse_args()

    from dancelab.core.config import load_config, load_weights
    from dancelab.decision.set_builder import build_set
    from dancelab.decision.transition_windows import detect_transition_windows
    from dancelab.workflows.smart_playlist import analyze_files, auto_analysis_workers

    pool, skipped = candidates(args.bpm_min, args.bpm_max, exclude=not args.keep_daytime)
    print(f"kandydatów w {args.bpm_min:.0f}-{args.bpm_max:.0f} BPM: {len(pool)}"
          f"  (odrzuconych przez brief: {len(skipped)})", flush=True)
    bez = sum(1 for *_, g in pool if not g)
    print(f"  z tego bez opisanego gatunku: {bez} — przeszły bez sprawdzenia stylu\n", flush=True)
    if len(pool) < 4:
        print("za mało kandydatów — poszerz pasmo tempa albo podłącz dysk z resztą")
        return 2

    cfg = load_config("configs/default.yaml")
    processed = pathlib.Path(args.processed_dir)
    processed.mkdir(parents=True, exist_ok=True)
    files = [p for _, p, _, _ in pool]
    print(f"analizuję {len(files)} plików (kolejne uruchomienie użyje cache)…", flush=True)
    analyses, failures = analyze_files(
        files, cfg, processed_dir=processed, workers=auto_analysis_workers(),
        progress=lambda done, total, path: (
            print(f"  {done}/{total} {pathlib.Path(path).name[:52]}", flush=True)
            if done % 5 == 0 or done == total else None
        ),
    )
    for f in failures[:6]:
        print(f"  nie udało się: {pathlib.Path(f.source_path).name[:46]} — {f.error}")
    if not analyses:
        print("nic się nie policzyło")
        return 1

    known = [a.track.duration_sec for a in analyses if a.track.duration_sec]
    per = (sum(known) / len(known)) if known else None
    if per is None:
        print("żaden utwór nie ma znanej długości — podaj liczbę utworów ręcznie")
        return 1
    count = max(2, min(round(args.minutes * 60 / per), len(analyses)))
    print(f"\nśrednia długość {per / 60:.1f} min → {count} utworów na {args.minutes:.0f} minut")

    weights = load_weights(cfg.weights_file)
    plan = build_set(
        analyses, weights, arc=args.arc, target_track_count=count,
        tempo_shape=args.tempo, bpm_min=args.bpm_min, bpm_max=args.bpm_max,
    )
    by_id = {a.track.track_id: a for a in analyses}
    print(f"\n{args.name} · {len(plan.track_order)} utworów\n")
    for i, tid in enumerate(plan.track_order, 1):
        t = by_id[tid].track
        gen = next((g for _, p, _, g in pool if p.name == pathlib.Path(t.source_path).name), "")
        print(f"  {i:2d}. {t.bpm_estimate:6.2f}  {(t.title or '?')[:44]:44s} "
              f"{(t.key_estimate or '?'):>4s}  {gen[:26]}")
    for w in plan.warnings:
        print(f"  ⚠ {w}")

    windows = {
        a.track.track_id: detect_transition_windows(a, weights)
        for a in analyses if a.track.track_id in set(plan.track_order)
    }
    out = pathlib.Path(args.out or f"data/exports/{args.name}.cues.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    import json
    out.write_text(json.dumps({
        "set_plan": plan.model_dump(mode="json"),
        "analyses": {tid: by_id[tid].model_dump(mode="json") for tid in plan.track_order},
        "windows": {k: [w.model_dump(mode="json") for w in v] for k, v in windows.items()},
        "playlist_name": args.name,
    }, ensure_ascii=False))
    print(f"\npaczka cue: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
