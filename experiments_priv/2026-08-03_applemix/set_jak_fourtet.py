"""Set szyty JAK Four Tet — nie z jego utworów, tylko jego sposobem prowadzenia.

Brief Janka (03.08): „inspirowane nim, ale nie wsadzaj go w każdy utwór —
ma być inspirowane jego sposobem miksowania".

ZMIERZONY PODPIS (WHP Manchester, 19 utworów, wektory CLAP z próbek):
    podobieństwo sąsiadów   0,71   (kwartyle 0,61–0,79, najdalszy skok 0,44)
    szerokość palety        0,69
    mediana trwania utworu  291 s
Na tle 125 miksów z korpusu Four Tet stoi na **8. percentylu podobieństwa
sąsiadów** — skacze dalej niż 92% DJ-ów — i na 21. percentylu palety.

CO TO ZMIENIA W ALGORYTMIE. Poprzednie sety maksymalizowały podobieństwo:
brały kandydata najbliższego temu, co gra. Wychodziło gładko, sąsiedzi na 0,85
i wyżej — czyli NIE tak, jak gra Four Tet. Tutaj celem nie jest „najbliżej",
tylko **trafienie w jego rozrzut**: kolejny utwór ma być oddalony mniej więcej
tak, jak on oddala, ani bliżej, ani dalej.

Do tego dwa hamulce, żeby „daleko" nie znaczyło „byle co":
  * paleta — kara za zbliżanie się do środka tego, co już zagrane, żeby set
    nie zwijał się w jedno brzmienie;
  * grywalność — produkcyjny `transition_score` dalej ma głos, bo skok
    stylistyczny nie zwalnia z tego, żeby dało się to zmiksować.

Reguły Janka bez zmian: okno tempa, nigdy w dół, max 1 utwór na artystę.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from set_na_piatek import anchor_centroid, energy, library      # noqa: E402


def genre_map():
    """Gatunki z tagów Janka w Rekordboksie — NIE z iTunes.

    Zmierzone 03.08: tagi iTunes są bezużyteczne (wszystko wpada w „Dance"),
    ale Janek opisał część biblioteki własną taksonomią i ona jest trafna.
    Uwaga: 145 z 243 utworów NIE MA tagu (60%), więc to jest preferencja,
    nigdy filtr — inaczej wycięlibyśmy większość skrzynki.
    """
    import unicodedata as _U
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables
    db = Rekordbox6Database()
    gm = {g.ID: g.Name for g in db.session.query(tables.DjmdGenre).all()}
    out = {_U.normalize("NFC", r.FolderPath or ""): gm.get(r.GenreID)
           for r in db.session.query(tables.DjmdContent).all()}
    db.close()
    return out
from dancelab.core.config import load_config, load_weights      # noqa: E402
from dancelab.decision.set_builder import transition_score      # noqa: E402

# Zmierzone na jego miksie — nie dobrane ręcznie.
FT = {"cos_target": 0.71, "cos_lo": 0.61, "cos_hi": 0.79, "palette": 0.69}

# JEGO KONTUR: kolejne skoki w miksie WHP, po kolei. Styl to nie średnia,
# tylko ROZKŁAD i jego kształt — celowanie w samą medianę 0,71 gasi rozrzut
# (zmierzone: dawało kwartyle 0,71–0,82 zamiast jego 0,61–0,79). Tutaj każdy
# krok dostaje własny cel, wzięty z tego, co on zrobił w tym miejscu setu.
# Widać w nim prowadzenie napięcia: otwarcie skokiem 0,60, trzy ciasne
# przejścia, rozluźnienie, największy wyskok 0,44 i natychmiastowy powrót
# do 0,82.
CONTOUR = [0.60, 0.79, 0.80, 0.84, 0.70, 0.62, 0.58, 0.44, 0.82, 0.74,
           0.80, 0.55, 0.61, 0.76, 0.61, 0.65, 0.71, 0.78]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lo", type=float, default=135.0)
    ap.add_argument("--hi", type=float, default=140.0)
    ap.add_argument("--minutes", type=float, default=120.0)
    ap.add_argument("--w-jump", type=float, default=1.0, help="waga trafienia w rozrzut")
    ap.add_argument("--w-play", type=float, default=0.6, help="waga grywalności")
    ap.add_argument("--w-pal", type=float, default=0.5, help="waga szerokości palety")
    ap.add_argument("--plan-tempa", type=float, default=0.0,
                    help="waga trzymania się planu tempa (0 = bez planu)")
    ap.add_argument("--szczyt", type=float, default=0.65,
                    help="od którego miejsca setu wchodzimy na górę okna")
    ap.add_argument("--gatunki", default="",
                    help="preferowane tagi, po przecinku, np. 'garage,breaks,bass'")
    ap.add_argument("--w-gatunek", type=float, default=1.5)
    ap.add_argument("--kontur", action="store_true",
                    help="cel z konturu Four Teta zamiast jego mediany")
    ap.add_argument("--out")
    args = ap.parse_args()

    import unicodedata as _U
    c, n, _ = anchor_centroid()
    lib = library()
    gmap = genre_map() if args.gatunki else {}
    lubie = [x.strip().lower() for x in (args.gatunki or "").split(",") if x.strip()]
    for t in lib:
        g = (gmap.get(_U.normalize("NFC", t["a"].track.source_path)) or "")
        t["genre"] = g
        t["gfit"] = 1.0 if any(k in g.lower() for k in lubie) else (
            0.0 if not g else -1.0)          # nieznany gatunek = neutralnie
    win = [t for t in lib if args.lo <= t["bpm"] <= args.hi]
    for t in win:
        t["sim"] = float(t["vec"] @ c) if c is not None else 0.0
    print(f"biblioteka w oknie {args.lo:.0f}-{args.hi:.0f}: {len(win)} utworów")
    print(f"cel: sąsiedzi ~{FT['cos_target']:.2f} (jak Four Tet), "
          f"paleta ~{FT['palette']:.2f}\n")

    cfg = load_config(str(ROOT / "configs/default.yaml"))
    W = load_weights(cfg.weights_file)
    E = {id(t): (energy(t["a"]) or 0.5) for t in win}
    er = (max(E.values()) - min(E.values())) or 1.0

    # start: coś z dolnej połowy okna, blisko brzmienia kotwicy
    lo_half = [t for t in win if t["bpm"] <= (args.lo + args.hi) / 2] or win
    def album_of(t):
        """Folder liczy się jako ALBUM, gdy jego nazwa wygląda jak „Artysta -
        Tytuł" — tak wyglądają zgrane płyty i składanki. Foldery-skrzynki
        Janka (PLAYLIST, debYOU, SET_1, LEKCJA nr5, DEBIUTY) nie mają myślnika
        i mają po kilkanaście utworów; potraktowanie ich jako albumu ścinało
        set z 28 na 16. Sprawdzone na jego drzewie 03.08.
        """
        f = pathlib.Path(t["a"].track.source_path)
        return str(f.parent).lower() if " - " in f.parent.name else f"__luz__{f.stem.lower()}"

    def album_cap(n_so_far: int) -> int:
        """Reguła Janka z 22.07: 1 na ~10 utworów, 2/20, 3/30, twardy sufit 4."""
        return min(4, 1 + n_so_far // 10)

    order = [max(lo_half, key=lambda t: t["sim"])]
    used = {order[0]["artist"].lower()}
    albums = {album_of(order[0]): 1}
    total = order[0]["a"].track.duration_sec or 291
    jumps: list[float] = []
    # ile utworów planujemy — potrzebne, żeby rozłożyć tempo po długości setu
    med_dur = float(np.median([t["a"].track.duration_sec or 291 for t in win]))
    target_n = max(8, int(args.minutes * 60 / med_dur))

    while total < args.minutes * 60 and len(order) < len(win):
        cur = order[-1]
        centre = np.mean([t["vec"] for t in order], axis=0)
        centre = centre / (np.linalg.norm(centre) + 1e-9)
        best, bs = None, -1e9
        for t in win:
            if t in order or t["artist"].lower() in used:
                continue
            if t["bpm"] < cur["bpm"] - 0.05:            # nigdy w dół
                continue
            if albums.get(album_of(t), 0) >= album_cap(len(order)):
                continue                                 # reguła albumowa
            cos = float(cur["vec"] @ t["vec"])
            # 1. trafienie w cel TEGO kroku — z konturu albo w medianę
            tgt = CONTOUR[(len(order) - 1) % len(CONTOUR)] if args.kontur \
                else FT["cos_target"]
            jump = -abs(cos - tgt)
            # 2. paleta — im dalej od środka dotychczasowego setu, tym lepiej
            pal = -float(centre @ t["vec"])
            # 3. grywalność
            play, _, _ = transition_score(cur["a"], t["a"], W, "build",
                                          E[id(cur)], E[id(t)], er)
            s = args.w_jump * jump + args.w_pal * pal + args.w_play * play
            if lubie:
                s += args.w_gatunek * t.get("gfit", 0.0)
            if args.plan_tempa:
                # PLAN TEMPA — zmierzone na jego secie „Sroda peak" (24 utwory):
                # wchodzi na górę okna dopiero w 17. utworze, największy stopień
                # +2 BPM, 16 z 23 przejść bez zmiany tempa. Bez tego członu
                # łańcuch zachłanny wjeżdżał na 140 w 7. utworze i siedział tam
                # przez 24 — 89% setu na jednym tempie zamiast jego 33%.
                frac = len(order) / max(1, target_n - 1)
                want = args.lo + (args.hi - args.lo) * min(1.0, frac / args.szczyt)
                s -= args.plan_tempa * abs(t["bpm"] - want) / max(1.0, args.hi - args.lo)
            if s > bs:
                best, bs = t, s
        if best is None:
            break
        jumps.append(float(cur["vec"] @ best["vec"]))
        order.append(best)
        used.add(best["artist"].lower())
        albums[album_of(best)] = albums.get(album_of(best), 0) + 1
        total += best["a"].track.duration_sec or 291

    print("=" * 74)
    print(f"SET · {len(order)} utworów · {total/60:.0f} min")
    print("=" * 74)
    print(f"{'#':>3} {'BPM':>6} {'ton':>4} {'skok':>5}  utwór")
    for i, t in enumerate(order, 1):
        j = f"{jumps[i-2]:.2f}" if i > 1 else "  — "
        print(f"{i:>3} {t['bpm']:6.1f} {t['a'].track.key_estimate or '?':>4} {j:>5}  "
              f"{t['name'][:54]}")

    if jumps:
        V = np.array([t["vec"] for t in order])
        G = V @ V.T
        pal = float((G.sum() - np.trace(G)) / (len(V) * (len(V) - 1)))
        print(f"\n  PODPIS TEGO SETU vs FOUR TET")
        print(f"    sąsiedzi mediana  {np.median(jumps):.2f}   ·  jego {FT['cos_target']:.2f}")
        print(f"    kwartyle          {np.percentile(jumps,25):.2f}–{np.percentile(jumps,75):.2f}"
              f"   ·  jego {FT['cos_lo']:.2f}–{FT['cos_hi']:.2f}")
        print(f"    najdalszy skok    {min(jumps):.2f}   ·  jego 0.44")
        print(f"    szerokość palety  {pal:.2f}   ·  jego {FT['palette']:.2f}")

    if args.out:
        pathlib.Path(args.out).write_text(
            "\n".join(t["a"].track.source_path for t in order), encoding="utf-8")
        print(f"\n  ścieżki: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
