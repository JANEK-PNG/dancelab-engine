"""KROK 3 · dostrojenie modelu korpusowego na historii grania Janka.

Model uczony na 772 cudzych miksach osiąga na korpusie percentyl 0,621
(przypadek 0,500, n=23 432 — sygnał niewątpliwy), ale przeniesiony na
28 przejść Janka daje 0,539, czyli w szumie. Korpus uczy cudzego gustu.

Ten skrypt robi to, po co w ogóle jest pretrening: bierze model korpusowy
jako JEDNĄ cechę i uczy na jej podstawie mały model osobisty na historii
grania Janka z Rekordboxa. To jest transfer learning w najprostszej,
uczciwej postaci — duży model daje punkt wyjścia, mały go koryguje.

DANE OSOBISTE: pary A→B z `DjmdSongHistory`, gdzie OBIE strony mają plik
lokalny z analizą, siatką i wektorem CLAP. Zmierzone: 451 par w 35 sesjach.
Walidacja: GroupKFold po SESJACH. Podział losowy dałby wyciek.
TEST KOŃCOWY: 28 przejść z nagranych setów — nie biorą udziału w treningu.
"""

from __future__ import annotations

import json
import pathlib
import sys
import unicodedata as U
from collections import defaultdict

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from krok3_ranking import CTX, build, global_bpm, load_corpus  # noqa: E402
from krok3_bramka_janek import COLS, fold_bpm                  # noqa: E402

from cue_parse import parse_cue          # noqa: E402
from grid_cache import grid_for          # noqa: E402
from dancelab.storage.repositories import FileAnalysisRepository  # noqa: E402

PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
LIB_EMB = ROOT / "data/reports/library_embeddings.json"
CUES = [
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Unknown Album/01 Premier.cue",
    "/Users/jantrybus/Music/rekordbox/Recording/Jan Trybus/Spring/01 Open Deck.cue",
]
MIN_TRACKS = 5
N_NEG = 20
SEED = 20260801
N = lambda s: U.normalize("NFC", str(s))  # noqa: E731


PREVIEW_EMB = ROOT / "data/reports/apple_preview_embeddings.json"


def janek_library():
    """Biblioteka Janka: pliki lokalne + strumienie Apple Music z próbek.

    Dwa źródła w jednej przestrzeni, i trzeba wiedzieć, czym się różnią:
      * pliki lokalne — wektor z 5 okien rozłożonych po CAŁYM utworze,
        tempo ze sztywnej siatki (błąd 1,7 milibitu wobec Rekordboksa)
      * strumienie — wektor z 30 s ze ŚRODKA (próbka iTunes), tempo
        z Rekordboksa (jego własny algorytm)
    Kolumna `bpm_known` już rozróżnia „znamy / nie znamy"; różnicy ŹRÓDŁA
    model nie widzi i to jest świadomy kompromis, wypisany w raporcie.
    """
    repo = FileAnalysisRepository(PROCESSED)
    an = [repo.get(t) for t in repo.list_track_ids()]
    bpm, vec, by_path = {}, {}, {}
    d = json.loads(LIB_EMB.read_text())
    root = N(d.get("library_root", ""))
    for a in an:
        tid = a.track.track_id
        p = N(a.track.source_path)
        by_path[p] = a
        g = grid_for(a.track.source_path)
        bpm[tid] = float(g["bpm"]) if g else 0.0
        v = d["tracks"].get(p[len(root):].lstrip("/"))
        if v is not None:
            w = np.asarray(v, dtype=np.float32)
            vec[tid] = w / (np.linalg.norm(w) + 1e-9)

    prev_of_cid = {}
    if PREVIEW_EMB.exists():
        pv = json.loads(PREVIEW_EMB.read_text())["tracks"]
        for _itid, rec in pv.items():
            cid = rec.get("content_id")
            if not cid:
                continue
            pid = f"ap:{cid}"
            w = np.asarray(rec["vector"], dtype=np.float32)
            vec[pid] = w / (np.linalg.norm(w) + 1e-9)
            prev_of_cid[str(cid)] = pid
        print(f"  próbki iTunes wpięte: {len(prev_of_cid)} utworów", flush=True)
    return an, by_path, bpm, vec, prev_of_cid


TRACK_FEATS = pathlib.Path(__file__).parent / "krok2b_cechy.json"


def load_track_feats():
    """entry_score i runway_in per utwór (krok2b). Braki zostają brakami."""
    if not TRACK_FEATS.exists():
        return {}
    return json.loads(TRACK_FEATS.read_text())


def feats(va, ba, ctx, cid, bpm, vec, pos):
    bb = bpm.get(cid, 0.0)
    return [float(va @ vec[cid]), fold_bpm(ba, bb),
            (bb / ba) if (bb and ba) else 1.0, pos,
            float(ctx @ vec[cid]), 1.0 if bb else 0.0]


PHRASE_FEATS = pathlib.Path(__file__).parent / "frazy_cechy_all.json"


def load_phrase_feats():
    """Cechy struktury z analizy Rekordboxa (`ingestion/rekordbox_phrases`).

    Dwie rzeczy zmierzone 03.08, obie ważne:

    (1) Etykiety SKRAJNE nie niosą informacji — każdy utwór zaczyna się od
    INTRO i prawie każdy kończy OUTRO. Rekordbox etykietuje tak zawsze.
    Informacja siedzi w DŁUGOŚCIACH: intro ma medianę 14 s, kwartyle 7–21.

    (2) Pierwsza wersja liczyła cechy tylko dla plików lokalnych i wyglądało
    to na przeciek (13,6% pokrycia wśród odpowiedzi wobec 69,9% w puli).
    Janek to złapał: **Rekordbox analizuje też strumienie Apple Music** —
    i robi to LEPIEJ (100% z frazami wobec 78% dla plików). Braku nie było
    w danych, tylko w moim wyciąganiu. Klucz to ContentID Rekordboxa,
    nie ścieżka pliku.
    """
    if not PHRASE_FEATS.exists():
        return {}
    return json.loads(PHRASE_FEATS.read_text())


def extra(cid, tf):
    """Cechy kandydata z kroku 2b. Brak → 0 + flaga „nie wiem", nigdy podstawiona
    wartość udająca pomiar (ADR-005): model dostaje osobną kolumnę mówiącą,
    że tej liczby nie było."""
    v = tf.get(cid) or {}
    e, r = v.get("entry_score"), v.get("runway_in")
    out = [e if e is not None else 0.0, 1.0 if e is not None else 0.0,
           np.log1p(r) if r is not None else 0.0, 1.0 if r is not None else 0.0]
    # FRAZY WYŁĄCZONE Z RANKINGU — zmierzone 2026-08-03, przy POPRAWNYM
    # pokryciu 88,8% puli (pierwsza próba miała 13,6% i to był mój błąd
    # wyciągania, złapany przez Janka — Rekordbox analizuje też strumienie).
    # Wynik: historia 0,678 → 0,677, bramka 0,575 → 0,518. Trzeci raz z rzędu
    # dołożenie cech nic nie daje. Loader zostaje, kolumny nie wchodzą.
    return out


_CID: dict = {}


_PH: dict = {}


PLAY_LO, PLAY_HI = 90.0, 600.0     # okno odstępu zgodne z zagranym utworem


def history_pairs(by_path, vec, gap_filter: bool = False, prev_of_cid=None):
    """Pary A→B z historii Rekordboxa, obie strony z kompletem cech.

    gap_filter: zostaw tylko pary, między którymi minęło 90–600 s. Zmierzone
    (`krok1_historia_vs_sety.py`): 19,7% odstępów jest krótszych niż 30 s,
    czyli poprzedni utwór na pewno nie został zagrany — to jest przeglądanie
    w słuchawkach, nie przejście. Filtr zostawia 63,2% par.
    """
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables

    db = Rekordbox6Database()
    content = {str(r.ID): (r.FolderPath or "") for r in
               db.session.query(tables.DjmdContent).all()}
    plays = defaultdict(list)
    for r in (db.session.query(tables.DjmdSongHistory)
              .order_by(tables.DjmdSongHistory.TrackNo).all()):
        plays[str(r.HistoryID)].append((r.TrackNo, str(r.ContentID), r.created_at))
    rb_bpm = {}
    for r in db.session.query(tables.DjmdContent).all():
        b = float(r.BPM or 0)
        if b > 300:            # Rekordbox trzyma BPM x100
            b /= 100.0
        rb_bpm[str(r.ID)] = b
    db.close()

    tid_of = {}
    for cid, fp in content.items():
        a = by_path.get(N(fp))
        if a is not None and a.track.track_id in vec:
            tid_of[cid] = a.track.track_id
        elif prev_of_cid and str(cid) in prev_of_cid:
            tid_of[cid] = prev_of_cid[str(cid)]

    out = []
    for hid, rows in plays.items():
        if len(rows) < MIN_TRACKS:
            continue
        rows = sorted(rows)
        seq = []                       # (track_id, czas załadowania)
        for _no, c, ts in rows:
            t = tid_of.get(c)
            if t and (not seq or seq[-1][0] != t):
                seq.append((t, ts))
        for i in range(len(seq) - 1):
            if gap_filter:
                ta, tb = seq[i][1], seq[i + 1][1]
                if not (ta and tb):
                    continue
                gap = (tb - ta).total_seconds()
                if not (PLAY_LO <= gap <= PLAY_HI):
                    continue
            hist = [t for t, _ in seq[max(0, i - CTX + 1): i + 1]]
            out.append((hid, hist, seq[i][0], seq[i + 1][0],
                        i / max(1, len(seq) - 2)))
    stream_bpm = {prev_of_cid[c]: rb_bpm.get(c, 0.0)
                  for c in (prev_of_cid or {}) if c in rb_bpm}
    cid_map = {t: c for c, t in tid_of.items()}      # track_id -> ContentID
    return out, stream_bpm, cid_map


def rank_stats(ranks):
    if not ranks:
        return None
    pct = float(np.mean([1 - (r - 1) / p for r, p in ranks]))
    return (pct, 100 * np.mean([r <= 5 for r, _ in ranks]),
            100 * np.mean([r <= 10 for r, _ in ranks]))


def main() -> int:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    from sklearn.preprocessing import StandardScaler

    # ── 1. model korpusowy
    idx, M, mixes = load_corpus()
    X, y, _g, _q = build(idx, M, mixes, global_bpm(mixes), hard=True)
    sc0 = StandardScaler().fit(X[:, COLS])
    base = LogisticRegression(C=1.0, max_iter=1000).fit(sc0.transform(X[:, COLS]), y)
    print(f"model korpusowy: {len(y)} wierszy\n", flush=True)

    # ── 2. dane osobiste
    gap_filter = "--filter-gaps" in sys.argv
    wide_pool = "--wide-pool" in sys.argv
    an, by_path, bpm, vec, prev_of_cid = janek_library()
    pairs, stream_bpm, cid_map = history_pairs(by_path, vec, gap_filter=gap_filter,
                                               prev_of_cid=prev_of_cid)
    bpm.update({k: v for k, v in stream_bpm.items() if v > 0})
    print(f"filtr odstępów: {'WŁĄCZONY (90–600 s)' if gap_filter else 'wyłączony'}")
    lib_loc = [a.track.track_id for a in an if a.track.track_id in vec]
    lib_pre = sorted(set(prev_of_cid.values()) & set(vec))
    lib = lib_loc + lib_pre
    print(f"historia: {len(pairs)} par z kompletem cech · "
          f"{len({s for s, *_ in pairs})} sesji · pula {len(lib)} utworów\n", flush=True)
    if len(pairs) < 100:
        print("za mało par, nie uczę")
        return 1

    tf = load_track_feats()
    _PH.update(load_phrase_feats())
    _CID.update(cid_map)
    cov = sum(1 for t in lib if _PH.get(_CID.get(t, "")))
    print(f"  cechy fraz (Rekordbox): {len(_PH)} utworów · "
          f"pokrycie puli {100*cov/max(1,len(lib)):.1f}%", flush=True)
    rng = np.random.default_rng(SEED)
    rows, lab, grp, qq, ex = [], [], [], [], []
    for k, (sess, hist, a, b, pos) in enumerate(pairs):
        if a not in vec or b not in vec:
            continue
        hv = [vec[t] for t in hist if t in vec] or [vec[a]]
        ctx = np.mean(hv, axis=0)
        ctx /= (np.linalg.norm(ctx) + 1e-9)
        va, ba = vec[a], bpm.get(a, 0.0)
        # NEGATYWY Z TEGO SAMEGO ŹRÓDŁA CO ODPOWIEDŹ PRAWIDŁOWA.
        # Zmierzone: wektor z 30-sekundowej próbki jest odróżnialny od wektora
        # z pełnego pliku (AUC 0,889), a prawidłowe odpowiedzi to w 84% próbki
        # przy 73,8% w puli — więc model dostawał punkty za rozpoznanie ŹRÓDŁA,
        # nie za trafiony wybór. Losowanie w obrębie tego samego rodzaju
        # zabiera mu tę drogę na skróty.
        same = lib_pre if b.startswith("ap:") else lib_loc
        if len(same) < N_NEG + 2:
            same = lib
        negs = [t for t in rng.choice(same, size=N_NEG + 6, replace=False)
                if t not in (a, b)][:N_NEG]
        for cid, is_true in [(b, 1)] + [(t, 0) for t in negs]:
            rows.append(feats(va, ba, ctx, cid, bpm, vec, pos))
            ex.append(extra(cid, tf))
            lab.append(is_true)
            grp.append(sess)
            qq.append(k)

    Xp = np.asarray(rows, dtype=np.float32)
    Ex = np.asarray(ex, dtype=np.float32)
    yp = np.asarray(lab)
    gp = np.asarray(grp)
    qp = np.asarray(qq)
    n_sess = len(set(gp.tolist()))
    print(f"zbiór osobisty: {len(yp)} wierszy · {len(set(qp.tolist()))} przejść · "
          f"{n_sess} sesji\n", flush=True)

    def score_of(P, qarr, yarr):
        r = []
        for u in sorted(set(qarr.tolist())):
            s = qarr == u
            o = np.argsort(-P[s])
            h = np.where(yarr[s][o] == 1)[0]
            if len(h):
                r.append((int(h[0]) + 1, int(s.sum())))
        return r

    # bazowy: model korpusowy bez dostrojenia
    p_base = base.predict_proba(sc0.transform(Xp[:, COLS]))[:, 1]

    # dostrojony: [wynik korpusowy] + cechy, uczone na sesjach Janka
    Zb = np.column_stack([p_base, Xp[:, COLS]])
    Zx = np.column_stack([Zb, Ex])          # + cechy utworu z kroku 2b
    folds = min(5, n_sess)

    def cv(Z):
        p = np.zeros(len(yp))
        for tr, te in GroupKFold(n_splits=folds).split(Z, yp, groups=gp):
            s = StandardScaler().fit(Z[tr])
            m = LogisticRegression(C=1.0, max_iter=1000).fit(s.transform(Z[tr]), yp[tr])
            p[te] = m.predict_proba(s.transform(Z[te]))[:, 1]
        return p

    p_ft, p_fx = cv(Zb), cv(Zx)

    print("═" * 66)
    print(f"NA HISTORII JANKA (GroupKFold po {folds} z {n_sess} sesji)")
    print("═" * 66)
    print(f"\n  {'':<32} {'percentyl':>9} {'top-5':>8} {'top-10':>8}")
    print("  " + "─" * 60)
    print(f"  {'losowo':<32} {0.500:9.3f} {100*5/(N_NEG+1):7.1f}% "
          f"{100.0:7.1f}%")
    for nm, P in [("model korpusowy (bez dostrojenia)", p_base),
                  ("dostrojony", p_ft),
                  ("dostrojony + cechy utworu (2b)", p_fx)]:
        st = rank_stats(score_of(P, qp, yp))
        print(f"  {nm:<32} {st[0]:9.3f} {st[1]:7.1f}% {st[2]:7.1f}%")

    # ── KROK 3 (zasada #2): czy model umie powiedzieć „nie wiem"
    print("\n" + "─" * 66)
    print("KALIBRACJA I PRAWO DO ODMOWY (na historii, bo tam jest sygnał)")
    print("─" * 66)
    edges = [0.0, 0.02, 0.05, 0.10, 0.20, 0.40, 1.01]
    print(f"\n  {'przedział p':<16} {'n':>6} {'przewidziane':>13} {'rzeczywiste':>12}")
    for a, b in zip(edges, edges[1:]):
        m = (p_fx >= a) & (p_fx < b)
        if m.sum() >= 10:
            print(f"  [{a:.2f}, {b:.2f})    {m.sum():6d} {p_fx[m].mean():13.3f} "
                  f"{yp[m].mean():12.3f}")

    print("\n  ODMOWA: odsetek zapytań, w których najlepszy kandydat ma "
          "p poniżej progu")
    for thr in (0.05, 0.10, 0.20, 0.30):
        kept, hit = [], []
        for u in sorted(set(qp.tolist())):
            s = qp == u
            top = p_fx[s].max()
            if top < thr:
                continue
            o = np.argsort(-p_fx[s])
            h = np.where(yp[s][o] == 1)[0]
            kept.append(u)
            hit.append(int(h[0]) + 1 <= 5 if len(h) else False)
        cov = 100 * len(kept) / len(set(qp.tolist()))
        acc = 100 * np.mean(hit) if hit else 0.0
        print(f"    próg {thr:.2f}  pokrycie {cov:5.1f}%  "
              f"top-5 wśród odpowiedzianych {acc:5.1f}%")

    s_x = StandardScaler().fit(Zx)
    mx = LogisticRegression(C=1.0, max_iter=1000).fit(s_x.transform(Zx), yp)
    nms = ["korpus"] + [f"f{c}" for c in COLS] + [
        "entry", "entry_ok", "runway", "runway_ok",
        "intro_dl", "intro_ok", "sekcji", "klubowy"]
    print("\n  wagi warstwy osobistej:")
    for c, w in sorted(zip(nms, mx.coef_[0]), key=lambda t: -abs(t[1]))[:6]:
        print(f"    {c:<10} {w:+.3f}")

    # ── 3. test końcowy: 28 przejść z nagranych setów
    Z = Zx
    s_all = s_x
    final = mx

    ranks = []
    for cue in CUES:
        _, entries = parse_cue(cue)
        order = []
        for e in entries:
            a = by_path.get(N(e.path))
            if a is not None and (not order or order[-1].track.track_id != a.track.track_id):
                order.append(a)
        hist = []
        for i in range(len(order) - 1):
            a, real_b = order[i], order[i + 1]
            hist.append(a.track.track_id)
            played = {t.track.track_id for t in order[: i + 1]}
            pool = [c.track.track_id for c in an
                    if c.track.track_id not in played and c.track.track_id in vec]
            # Pula bramki DOMYSLNIE bez strumieni — inaczej test przestaje byc
            # porownywalny z liczbami z 01.08 (pula ~236). --wide-pool wlacza
            # wariant realistyczny i raportuje go OSOBNO.
            if wide_pool:
                pool += sorted(set(prev_of_cid.values()) & set(vec))
            if real_b.track.track_id not in pool or a.track.track_id not in vec:
                continue
            hv = [vec[t] for t in hist[-CTX:] if t in vec] or [vec[a.track.track_id]]
            ctx = np.mean(hv, axis=0)
            ctx /= (np.linalg.norm(ctx) + 1e-9)
            va, ba = vec[a.track.track_id], bpm.get(a.track.track_id, 0.0)
            pos = i / max(1, len(order) - 2)
            F = np.asarray([feats(va, ba, ctx, c, bpm, vec, pos) for c in pool],
                           dtype=np.float32)
            FE = np.asarray([extra(c, tf) for c in pool], dtype=np.float32)
            pb = base.predict_proba(sc0.transform(F[:, COLS]))[:, 1]
            ZZ = np.column_stack([pb, F[:, COLS], FE])
            p = final.predict_proba(s_all.transform(ZZ))[:, 1]
            o = np.argsort(-p)
            ranks.append((int(np.where(np.asarray(pool)[o] ==
                                       real_b.track.track_id)[0][0]) + 1, len(pool)))

    st = rank_stats(ranks)
    print("\n" + "═" * 66)
    print(f"BRAMKA · {len(ranks)} przejść z nagranych setów (zero w treningu)")
    print("═" * 66)
    print(f"\n  {'':<32} {'percentyl':>9} {'top-5':>8} {'top-10':>8}")
    print("  " + "─" * 60)
    print(f"  {'losowo (rozkład zerowy)':<32} {0.502:9.3f} {2.1:7.1f}% {4.2:7.1f}%")
    print(f"  {'produkcyjny transition_score':<32} {0.597:9.3f} {0.0:7.1f}% {3.6:7.1f}%")
    print(f"  {'najbliższe tempo':<32} {0.606:9.3f} {7.1:7.1f}% {7.1:7.1f}%")
    print(f"  {'model korpusowy':<32} {0.539:9.3f} {7.1:7.1f}% {14.3:7.1f}%")
    print(f"  {'KORPUS + DOSTROJENIE':<32} {st[0]:9.3f} {st[1]:7.1f}% {st[2]:7.1f}%")
    print("\n  95% przedział czystego przypadku przy n=28: 0,396 – 0,609")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
