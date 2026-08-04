"""Krzywe energii stemów — liczone NA ŻĄDANIE, zapamiętywane na zawsze.

Decyzja Janka (2026-08-03): stemy zostają wyłączone w zwykłej analizie.
Rozdzielanie utworu Demucsem trwa dziesiątki sekund, a analiza ma trwać sekundy.
Liczymy je dopiero wtedy, gdy coś ich naprawdę potrzebuje.

A potrzebuje ich jedna rzecz: reguła wejścia Janka — „utwór opiera się tu na
perkusji i schodzi z basu", zmierzona 2026-07-30 na 21 szwach (71% jego wejść
wobec 18% losowych momentów). Żeby to policzyć, trzeba wiedzieć, ile w danej
sekundzie jest perkusji, a ile basu — w zmiksowanym pliku tego nie widać.

CO ZOSTAJE NA DYSKU. Nie stemy, tylko krzywe. Zmierzone: cache surowych śladów
waży 5860 MB przy 31 utworach, czyli ~190 MB na utwór — biblioteka 243 utworów
zajęłaby ~47 GB, a wolnego jest 37. Krzywa energii w rozdzielczości sekundowej
to kilkadziesiąt kilobajtów: cała biblioteka mieści się w kilkunastu megabajtach.
Surowe ślady zostają wyłącznie tam, gdzie ktoś potrzebuje audio — przy rozkładzie
szwu (`scripts/seam_decompose.py` ma własny cache i on się nie zmienia).

ADR-005: brak Demucsa albo nieczytelny plik → `None` i powód. Nigdy krzywa
zmyślona z pełnego miksu udająca perkusję.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import dataclass

import numpy as np

STEMS = ("drums", "bass", "other", "vocals")
HZ = 1.0                      # jedna wartość na sekundę — tyle, ile potrzebuje reguła
SCHEMA = "stem-envelopes-v1"


@dataclass(frozen=True)
class StemEnvelopes:
    """Energia każdego stemu, sekunda po sekundzie, plus jego średnia z całości."""

    stems: tuple[str, ...]
    hz: float
    curves: dict[str, np.ndarray]      # nazwa -> energia w oknach 1 s
    whole: dict[str, float]            # nazwa -> średnia energia całego utworu
    duration_sec: float
    model: str

    def share_delta(self, t0: float, t1: float) -> dict[str, float] | None:
        """Udział stemu w oknie MINUS jego udział w całym utworze.

        Udział, a nie poziom — inaczej pozycja fadera zapisałaby się jako zmiana
        treści. Odjęcie własnej średniej utworu odpowiada na pytanie „co ten
        utwór robi TUTAJ nietypowo dla siebie", a nie „jak generalnie brzmi".
        Tak samo liczy `scripts/seam_content.py`, którym zmierzono regułę.
        """
        a, b = int(t0 * self.hz), int(t1 * self.hz)
        if b <= a or a < 0 or b > len(next(iter(self.curves.values()))):
            return None
        here = np.array([float(self.curves[s][a:b].mean()) for s in self.stems])
        whole = np.array([self.whole[s] for s in self.stems])
        if here.sum() <= 0 or whole.sum() <= 0:
            return None
        d = here / here.sum() - whole / whole.sum()
        return dict(zip(self.stems, (float(x) for x in d)))


def _key(path: str | pathlib.Path) -> str:
    p = pathlib.Path(path)
    st = p.stat()
    raw = f"{p.resolve()}|{st.st_size}|{int(st.st_mtime)}|{SCHEMA}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


def cache_dir(root: str | pathlib.Path = "data/cache") -> pathlib.Path:
    d = pathlib.Path(root) / "stem_envelopes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load(f: pathlib.Path) -> StemEnvelopes | None:
    try:
        d = json.loads(f.read_text())
    except Exception:
        return None
    if d.get("schema") != SCHEMA:
        return None
    return StemEnvelopes(
        stems=tuple(d["stems"]), hz=float(d["hz"]),
        curves={k: np.asarray(v, dtype=np.float32) for k, v in d["curves"].items()},
        whole={k: float(v) for k, v in d["whole"].items()},
        duration_sec=float(d["duration_sec"]), model=d.get("model", "?"))


def _save(f: pathlib.Path, e: StemEnvelopes) -> None:
    f.write_text(json.dumps({
        "schema": SCHEMA, "stems": list(e.stems), "hz": e.hz,
        "curves": {k: [round(float(x), 9) for x in v] for k, v in e.curves.items()},
        "whole": e.whole, "duration_sec": e.duration_sec, "model": e.model,
    }))


def stem_envelopes(
    path: str | pathlib.Path,
    *,
    cache_root: str | pathlib.Path = "data/cache",
    separate=None,
    sr: int = 44100,
) -> tuple[StemEnvelopes | None, str]:
    """(krzywe, powód). Krzywe z cache'u albo policzone raz i zapamiętane.

    `separate` wstrzykuje rozdzielacz (path -> {nazwa: sygnał}); domyślnie
    bierzemy ten, którym policzono szwy, żeby nie mieć dwóch różnych Demucsów
    dających różne liczby.
    """
    p = pathlib.Path(path)
    if not p.exists():
        return None, "brak pliku"

    f = cache_dir(cache_root) / f"{_key(p)}.json"
    if f.exists():
        got = _load(f)
        if got is not None:
            return got, "cache"

    if separate is None:
        try:
            import sys
            root = pathlib.Path(__file__).resolve().parents[3]
            sys.path.insert(0, str(root / "scripts"))
            import seam_decompose as S
            separate, sr = S.separate, S.SR
        except Exception as exc:                     # noqa: BLE001
            return None, f"brak rozdzielacza: {type(exc).__name__}"

    try:
        parts = separate(str(p))
    except Exception as exc:                         # noqa: BLE001
        return None, f"rozdzielanie nie powiodło się: {type(exc).__name__}"

    win = int(sr / HZ)
    curves, whole = {}, {}
    n = min(len(parts[s]) for s in STEMS if s in parts) if all(
        s in parts for s in STEMS) else 0
    if n < win:
        return None, "utwór krótszy niż okno"
    for s in STEMS:
        y = np.asarray(parts[s], dtype=np.float32)[:n]
        k = n // win
        e = (y[: k * win].reshape(k, win) ** 2).mean(axis=1)
        curves[s] = e.astype(np.float32)
        whole[s] = float((y ** 2).mean())

    out = StemEnvelopes(stems=STEMS, hz=HZ, curves=curves, whole=whole,
                        duration_sec=n / sr, model="htdemucs")
    _save(f, out)
    return out, "policzone"
