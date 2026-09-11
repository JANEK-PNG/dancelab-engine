"""larger_clap_music vs clap-htsat-unfused on the local file library — see PROGI.md.

Both models get identical clips (5 evenly spaced 10 s windows, mono, the
processor's own sampling rate), `get_audio_features`, mean over windows, L2.
Vectors are cached per model so a crash resumes. Outputs: wynik.json, WYNIK.md,
PARY_DO_ODSLUCHU.md (blind pairs) and klucz.json (the A/B key, kept apart).
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
HERE = Path(__file__).resolve().parent
PROCESSED = ROOT / "experiments_priv/2026-07-30_rebuild/processed"
JULY = ROOT / "data/reports/library_embeddings.json"
MODELS = {"htsat": "laion/clap-htsat-unfused", "larger": "laion/larger_clap_music"}
WINDOW_SEC, N_WINDOWS, K, SEED = 10, 5, 10, 20260910


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def norm_genre(s: str | None) -> str:
    s = (s or "").strip().lower().replace("-", " ")
    return re.sub(r"\s+", " ", s)


def load_tracks() -> list[dict]:
    from dancelab.ingestion.analysis_enrichment import load_rekordbox_genre_map
    gm, note = load_rekordbox_genre_map()
    print(note, flush=True)
    rows = []
    for f in glob.glob(str(PROCESSED / "*.json")):
        try:
            t = json.load(open(f)).get("track", {})
        except Exception:
            continue
        sp = t.get("source_path") or ""
        if not sp or sp.startswith("apple-music") or not os.path.exists(sp):
            continue
        if (t.get("duration_sec") or 0) < 60:
            continue
        rows.append({"id": t["track_id"], "path": sp, "title": t.get("title"), "artist": t.get("artist"),
                     "bpm": t.get("bpm_estimate"), "key": t.get("key_estimate"),
                     "genre": norm_genre(gm.get(nfc(sp)) or t.get("style_label"))})
    rows.sort(key=lambda r: r["id"])
    return rows


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def embed_all(tag: str, model_id: str, tracks: list[dict]) -> tuple[dict[str, list[float]], dict]:
    import librosa
    import torch
    from transformers import ClapModel, ClapProcessor

    cache = HERE / f"wektory_{tag}.json"
    vecs: dict[str, list[float]] = json.load(open(cache)) if cache.exists() else {}
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = ClapModel.from_pretrained(model_id).to(device).eval()
    proc = ClapProcessor.from_pretrained(model_id)
    sr = int(proc.feature_extractor.sampling_rate)
    snap = Path(model.config._name_or_path) if Path(model.config._name_or_path).exists() else None
    weights = next(iter(sorted(glob.glob(str(
        Path.home() / f".cache/huggingface/hub/models--{model_id.replace('/', '--')}/snapshots/*/pytorch_model.bin")))), None)
    info = {"model": model_id, "sampling_rate": sr, "device": device,
            "enable_fusion": bool(getattr(model.config.audio_config, "enable_fusion", False)),
            "sha256": file_sha256(Path(weights)) if weights else "unknown", "snapshot": str(snap)}
    print("model", info, flush=True)
    win = WINDOW_SEC * sr
    t0 = time.time()
    for i, tr in enumerate(tracks):
        if tr["id"] in vecs:
            continue
        wav, _ = librosa.load(tr["path"], sr=sr, mono=True)
        starts = [0] if wav.size <= win else np.linspace(0, wav.size - win, N_WINDOWS, dtype=int)
        clips = [wav[s:s + win].astype(np.float32) for s in starts]
        inputs = proc(audio=clips, sampling_rate=sr, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            out = model.get_audio_features(**inputs)
        feats = getattr(out, "audio_embeds", None)
        if feats is None:
            feats = getattr(out, "pooler_output", out)
        if i == 0 or tr["id"] not in vecs and len(vecs) == 0:
            print("feats", tag, tuple(feats.shape), flush=True)
        v = feats.float().cpu().numpy().mean(axis=0)
        v = v / (np.linalg.norm(v) + 1e-12)
        vecs[tr["id"]] = [float(x) for x in v]
        if (i + 1) % 20 == 0:
            cache.write_text(json.dumps(vecs))
            print(f"{tag}: {i + 1}/{len(tracks)}  {time.time() - t0:.0f}s", flush=True)
    cache.write_text(json.dumps(vecs))
    return vecs, info


def matrix(vecs: dict[str, list[float]], ids: list[str]) -> np.ndarray:
    m = np.array([vecs[i] for i in ids], dtype=np.float64)
    return m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-12)


def neighbours(sim: np.ndarray, k: int) -> np.ndarray:
    s = sim.copy()
    np.fill_diagonal(s, -np.inf)
    return np.argsort(-s, axis=1)[:, :k]


def skew(x: np.ndarray) -> float:
    x = x.astype(float)
    sd = x.std()
    return float(((x - x.mean()) ** 3).mean() / (sd ** 3)) if sd > 0 else 0.0


def main() -> None:
    tracks = load_tracks()
    print("utworów:", len(tracks), "z gatunkiem:", sum(1 for t in tracks if t["genre"]), flush=True)
    vec, info = {}, {}
    for tag, mid in MODELS.items():
        vec[tag], info[tag] = embed_all(tag, mid, tracks)

    ids = [t["id"] for t in tracks]
    M = {tag: matrix(vec[tag], ids) for tag in MODELS}
    S = {tag: M[tag] @ M[tag].T for tag in MODELS}

    # pipeline check against the July htsat vectors (keyed by path under library_root)
    july = json.load(open(JULY))
    root = july["library_root"].rstrip("/") + "/"
    jt = {nfc(k): np.array(v, dtype=float) for k, v in july["tracks"].items()}
    cos_july = []
    for t, row in zip(tracks, M["htsat"]):
        key = nfc(t["path"][len(root):]) if t["path"].startswith(root) else None
        if key in jt:
            j = jt[key] / (np.linalg.norm(jt[key]) + 1e-12)
            cos_july.append(float(row @ j))
    cos_july = np.array(cos_july)

    # dedup: near-identical in BOTH models
    keep = np.ones(len(ids), dtype=bool)
    dups = []
    for i in range(len(ids)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(ids)):
            if keep[j] and S["htsat"][i, j] >= 0.999 and S["larger"][i, j] >= 0.999:
                keep[j] = False
                dups.append((ids[i], ids[j]))
    sel = np.where(keep)[0]
    tr = [tracks[i] for i in sel]
    genres = [t["genre"] for t in tr]
    out = {"n_all": len(ids), "n_after_dedup": int(keep.sum()), "duplicates": dups,
           "pipeline_check_cos_july": {"n": int(cos_july.size), "median": float(np.median(cos_july)) if cos_july.size else None,
                                       "min": float(cos_july.min()) if cos_july.size else None},
           "models": info, "k": K}
    NB = {}
    for tag in MODELS:
        sim = S[tag][np.ix_(sel, sel)]
        nb = neighbours(sim, K)
        NB[tag] = nb
        occ = np.bincount(nb.ravel(), minlength=len(sel))
        pur_num = pur_den = 0
        for a in range(len(sel)):
            if not genres[a]:
                continue
            for b in nb[a]:
                if genres[b]:
                    pur_den += 1
                    pur_num += genres[a] == genres[b]
        out[tag] = {"Nk_max": int(occ.max()), "Nk_skew": round(skew(occ), 3),
                    "Nk_top": sorted(occ.tolist(), reverse=True)[:5],
                    "genre_purity": round(pur_num / pur_den, 4) if pur_den else None,
                    "purity_pairs": pur_den}
    jac = [len(set(NB["htsat"][a]) & set(NB["larger"][a])) / len(set(NB["htsat"][a]) | set(NB["larger"][a]))
           for a in range(len(sel))]
    out["jaccard_top10_mean"] = round(float(np.mean(jac)), 4)

    h, l = out["htsat"], out["larger"]
    a_ok = l["Nk_max"] <= 1.2 * h["Nk_max"] and l["Nk_skew"] <= h["Nk_skew"] + 0.5
    b_ok = (h["genre_purity"] is not None and l["genre_purity"] is not None
            and l["genre_purity"] >= h["genre_purity"] + 0.03)
    out["warunek_a"] = bool(a_ok)
    out["warunek_b"] = bool(b_ok)

    # blind pairs for (c)
    rng = random.Random(SEED)
    cand = [a for a in range(len(sel)) if genres[a]]
    rng.shuffle(cand)
    pairs, anchors, key = [], [], []
    for a in cand:
        if len(anchors) == 6:
            break
        th = [b for b in NB["htsat"][a][:3]]
        tl = [b for b in NB["larger"][a][:3]]
        shared = set(th) & set(tl)
        th = [b for b in th if b not in shared]
        tl = [b for b in tl if b not in shared]
        ps = list(zip(th, tl))
        if not ps:
            continue
        anchors.append(a)
        for rank, (bh, bl) in enumerate(ps, 1):
            flip = rng.random() < 0.5
            A, B = (bl, bh) if flip else (bh, bl)
            pairs.append({"anchor": a, "rank": rank, "A": A, "B": B})
            key.append({"anchor": tr[a]["id"], "rank": rank, "A": "larger" if flip else "htsat",
                        "B": "htsat" if flip else "larger"})
    out["pairs_n"] = len(pairs)
    out["anchors_n"] = len(anchors)
    (HERE / "wynik.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    (HERE / "klucz.json").write_text(json.dumps(key, indent=1))

    def lab(i: int) -> str:
        t = tr[i]
        return f"{t['artist']} — {t['title']}  ({t['bpm']} · {t['key']} · {t['genre'] or '—'})\n    `{t['path']}`"

    md = ["# Pary do ślepego odsłuchu — larger_clap_music vs clap-htsat-unfused", "",
          "Dla każdej kotwicy: która propozycja (A czy B) brzmi BLIŻEJ kotwicy? Wpisz A / B / remis.",
          "Który model dał którą — jest w `klucz.json`; nie otwieraj przed odsłuchem.", ""]
    cur = None
    for p in pairs:
        if p["anchor"] != cur:
            cur = p["anchor"]
            md += [f"## Kotwica: {lab(cur)}", ""]
        md += [f"- para {p['rank']}:", f"  - **A** {lab(p['A'])}", f"  - **B** {lab(p['B'])}", "  - werdykt: ____", ""]
    (HERE / "PARY_DO_ODSLUCHU.md").write_text("\n".join(md))

    rep = ["# Wynik pomiaru (a) i (b) — bez werdyktu o wymianie", "",
           f"Utworów: {out['n_all']}, po dedupie {out['n_after_dedup']} (duplikatów: {len(dups)}).",
           f"Kontrola potoku (mój htsat vs lipcowy htsat, n={out['pipeline_check_cos_july']['n']}): "
           f"mediana kosinusa {out['pipeline_check_cos_july']['median']}, min {out['pipeline_check_cos_july']['min']}.",
           "", "| | htsat | larger | próg |", "|---|---|---|---|",
           f"| N_k max (k=10) | {h['Nk_max']} | {l['Nk_max']} | larger ≤ {1.2 * h['Nk_max']:.1f} |",
           f"| skośność N_k | {h['Nk_skew']} | {l['Nk_skew']} | larger ≤ {h['Nk_skew'] + 0.5:.3f} |",
           f"| top-5 N_k | {h['Nk_top']} | {l['Nk_top']} | — |",
           f"| czystość gatunkowa top-10 | {h['genre_purity']} | {l['genre_purity']} | larger ≥ {(h['genre_purity'] or 0) + 0.03:.4f} |",
           f"| par w mianowniku czystości | {h['purity_pairs']} | {l['purity_pairs']} | — |",
           f"| Jaccard top-10 między modelami | {out['jaccard_top10_mean']} | | opisowa |", "",
           f"(a) hubness: {'SPEŁNIONY' if a_ok else 'NIESPEŁNIONY'} · (b) czystość: {'SPEŁNIONY' if b_ok else 'NIESPEŁNIONY'}",
           f"Pary do (c): {len(pairs)} par na {len(anchors)} kotwicach — `PARY_DO_ODSLUCHU.md`.", "",
           "Modele: " + json.dumps(info, ensure_ascii=False)]
    (HERE / "WYNIK.md").write_text("\n".join(rep))
    print("\n".join(rep), flush=True)


if __name__ == "__main__":
    main()
