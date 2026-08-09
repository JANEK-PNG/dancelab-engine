"""Set Builder v0.2 - order a library of analyzed tracks into a DJ set.

Greedy harmonic/energy chain: start from an opener, then at each step pick the
unplayed track that maximizes a transition score combining
- **harmonic** compatibility on the Camelot wheel (same / adjacent ±1 / relative
  major-minor = good; else dissonant),
- **BPM** proximity (half/double-time aware),
- **energy arc** (default "build": gentle rise; also "flat", "peak"),
- **mixability** (the pairwise engine — tempo/bass/vocal/style/context).

STATUS: candidate — a heuristic ordering, not a proven optimal set. Harmonic
rules are standard DJ practice; the weighting and arc model are DanceLab
inference to be validated against DJ-built sets. cannot_claim: this is the best
possible set order, or that it will work live.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from dancelab.core.config import DescriptorWeights
from dancelab.core.models import (
    AnalysisResult,
    ContextProfile,
    MixabilityInput,
    SetCoherence,
    SetPlan,
    SetTransition,
)
from dancelab.core.provenance import provenance_for
from dancelab.decision._common import nearest_bpm_variant, tempo_proximity_score
from dancelab.decision.dedup import dedupe_by_audio
from dancelab.decision.corpus_priors import transition_prior_lift
from dancelab.decision.sound_affinity import blend, cosine_affinity
from dancelab.decision import premia_gatunku as _premia
from dancelab.decision.harmonic import harmonic_compatibility, harmonic_relation, parse_camelot
from dancelab.decision.history import NoveltyContext, PlaylistFingerprint
from dancelab.decision.library_profile import bpm_in_range, normalize_style_list, style_matches
from dancelab.decision.mixability import (
    MixabilityPrecomputation,
    compute_mixability,
    precompute_mixability_inputs,
)

MODEL_VERSION = "set_builder_v0.2"
PLANNER_MODE_SMART = "smart"
PLANNER_MODE_HARMONIC = "harmonic"
PLANNER_MODE_BPM = "bpm"
PLANNER_MODES = (PLANNER_MODE_SMART, PLANNER_MODE_HARMONIC, PLANNER_MODE_BPM)

# Set-level shape constraints reuse the normalized RMS energy domain already
# used by the long-horizon sequence planner. Pair scoring remains unchanged;
# these constants only bound which energy-near candidates compete at a slot.
_ARC_PROFILE_SLACK = 0.08
_BUILD_MAX_DROP_FRACTION = 0.08

# AUD-M10: every weighted term resolves to a formula_terms.yaml entry (no
# anonymous variables). Test-enforced by test_every_set_builder_component_has_a_term.
COMPONENTS = ("harmonic", "bpm", "energy", "mixability")

__all__ = [
    "build_set",
    "transition_score",
    "bpm_score",
    "track_energy",
    "harmonic_relation",
    "parse_camelot",
    "MODEL_VERSION",
    "COMPONENTS",
    "PLANNER_MODES",
]


_ARTIST_SPLIT_RE = re.compile(
    r"\s*(?:,|&|/|\+|\band\b|\bfeat\.?\b|\bft\.?\b|\bfeaturing\b)\s*|\s+x\s+",
    re.IGNORECASE,
)
_TITLE_ARTIST_RE = re.compile(r"\s[-–—]\s")


def _normalize_artist_token(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_text = re.sub(r"\([^)]*\)", " ", ascii_text)
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", " ", ascii_text).strip().lower()
    return re.sub(r"\s+", " ", ascii_text)


# Ile utworów z jednej płyty wolno wziąć do setu. Dwa, bo jeden to zakaz
# grania składanek, których DJ-e używają normalnie, a trzy na ośmiu to już
# jest odtwarzanie cudzej kolejności zamiast układania własnej.
MAX_PER_RELEASE = 2

# Kształty planu tempa. "off" to zachowanie dotychczasowe: planer nie ma zdania
# o tempie w skali setu i tempo wychodzi z kolejności, a nie odwrotnie.
TEMPO_SHAPE_OFF = "off"
TEMPO_SHAPE_LINEAR = "linear"
TEMPO_SHAPE_STAIRCASE = "staircase"
TEMPO_SHAPES = (TEMPO_SHAPE_OFF, TEMPO_SHAPE_LINEAR, TEMPO_SHAPE_STAIRCASE)

# Zakres pitchu, w którym utwór wolno postawić na cudzym tempie. ±6% to
# domyślne ustawienie CDJ-a; przy większym zakresie zmienia się barwa i to
# przestaje być decyzja o tempie, a staje się decyzją o brzmieniu.
MAX_PITCH_PCT = 6.0

# Ile płyt stoi na jednym piętrze i ile podejść dzieli piętra. Wartości z
# rendererów, gdzie zostały wysłuchane; silnik nie twierdzi, że są jedyne
# słuszne — to punkt wyjścia, który DJ może zmienić.
STAIRCASE_LANDING = 4
STAIRCASE_FLIGHT = 3


def tempo_plan(
    bpms: Sequence[float],
    shape: str,
    *,
    slots: int,
    landing: int = STAIRCASE_LANDING,
    flight: int = STAIRCASE_FLIGHT,
) -> list[float] | None:
    """Zaplanowane tempo dla każdego miejsca w secie. None = brak planu.

    Do tej pory tempo setu było SKUTKIEM kolejności: planer układał utwory według
    harmonii i energii, a tempo szło tam, gdzie akurat wypadło — w jednym
    z renderów spadło ze 136 na 124 przez pierwszą trzecią i wróciło na końcu.
    Set tak się nie buduje. Wchodzi się schodami: kilka płyt na jednym tempie,
    potem podejście wyżej, i nigdy w dół.

    Kształt jest WEJŚCIEM, nie wynikiem — silnik nie ma zdania, który jest
    słuszny. „linear" to równomierne wznoszenie, „staircase" to piętra i podejścia,
    „off" zostawia dotychczasowe zachowanie. Zakres brany jest z tego, co pula
    naprawdę ma, żeby plan dało się zagrać bez rozciągania płyt poza pitch.
    """
    known = sorted(float(b) for b in bpms if b)
    if shape == TEMPO_SHAPE_OFF or slots <= 0 or len(known) < 2:
        return None
    # Zakres z DZIESIĄTEGO i DZIEWIĘĆDZIESIĄTEGO percentyla, nie ze skrajności.
    # Pierwsza wersja brała min i max, a w bibliotece Janka skrajnymi były 70
    # i 178 — czyli w większości oktawy tego samego tempa i pojedyncze dziwolągi.
    # Plan rozciągnięty na taki zakres kazał silnikowi szukać utworów w tempach,
    # których pula nie ma, i wychodził GORZEJ niż brak planu.
    lo = float(np.percentile(known, 10))
    hi = float(np.percentile(known, 90))
    if hi - lo < 0.5:                      # cała pula na jednym tempie
        return [lo] * slots

    # Plan idzie po KWANTYLACH puli, nie po rozciągnięciu od lo do hi. Różnica
    # jest zmierzona i kosztowała cały ogon dwugodzinnego setu Janka: pula
    # 130–140 jest dwugarbna (dużo płyt przy 132–136, garstka przy 140), więc
    # plan rozłożony równomiernie prosił o siedem utworów po 140, gdy istniały
    # cztery. Set wspinał się ładnie przez dwadzieścia pozycji, a potem musiał
    # zejść na 132, bo nie było czym rosnąć.
    #
    # Po kwantylach każde piętro dostaje z definicji tyle płyt, ile plan prosi:
    # jeśli 25% puli stoi przy 140, to plan spędza przy 140 ostatnią ćwiartkę
    # setu, a nie połowę. Silnik nadal nie ma zdania o kształcie — ma zdanie
    # o tym, co półka DJ-a jest w stanie obsadzić.
    def _at(frac: float) -> float:
        return float(np.quantile(known, min(max(frac, 0.0), 1.0)))

    if shape == TEMPO_SHAPE_LINEAR:
        return [_at(i / max(slots - 1, 1)) for i in range(slots)]
    if shape == TEMPO_SHAPE_STAIRCASE:
        cycle = max(1, landing + flight)
        rises, level = [], 0
        for i in range(slots):
            if i and i % cycle >= landing:
                level += 1
            rises.append(level)
        top = max(rises) or 1
        return [_at(r / top) for r in rises]
    return None


def _tempo_plan_candidates(
    candidates: list[str],
    *,
    index: int,
    plan: list[float] | None,
    bpm_of: dict[str, float | None],
    previous_bpm: float | None = None,
    max_pitch_pct: float = MAX_PITCH_PCT,
    descent_tolerance_bpm: float = 0.5,
) -> list[str]:
    """Zostaw tych, których da się zagrać na zaplanowanym tempie i NIE W DÓŁ.

    Miękko, jak reszta ograniczeń: jeśli nikt nie mieści się w pitchu, wracamy do
    pełnej listy, zamiast zwracać set krótszy niż zamówiony. Utwór bez znanego
    tempa nie jest karany — nie wiemy, czy pasuje, a niewiedza to nie jest powód
    do odrzucenia (ADR-005).
    """
    if not plan or index >= len(plan) or not candidates:
        return candidates
    target = plan[index]
    # Pasmo rozszerzane STOPNIOWO, nie od razu do granicy pitchu. Pierwsza
    # wersja brała wszystko w ±6% i to zepsuło cały set na dwie godziny: plan
    # zaczynał się na 130, a pierwszy utwór wszedł na 137, bo mieścił się
    # w paśmie. Set osiągnął 140 po sześciu płytach, wypalił wszystkie
    # sto czterdziestki i na kolejnych piętnaście miejsc nie miał już czym
    # rosnąć — więc zakaz schodzenia musiał ustąpić i tempo spadło na 133.
    # Pasmo pitchu mówi, co DA SIĘ zagrać obok siebie; nie jest pozwoleniem na
    # olanie planu. Więc najpierw blisko planu, a szerzej dopiero gdy pusto.
    for tol in (1.0, 2.0, 4.0, max_pitch_pct):
        fits = _within(candidates, target, bpm_of, tol, previous_bpm,
                       descent_tolerance_bpm)
        if fits:
            return fits
    return candidates


def _within(
    candidates: list[str],
    target: float,
    bpm_of: dict[str, float | None],
    tol_pct: float,
    previous_bpm: float | None,
    descent_tolerance_bpm: float,
) -> list[str]:
    """Kandydaci mieszczący się w danym procencie od planu i nie schodzący w dół."""
    band = target * tol_pct / 100.0
    fits: list[str] = []
    for track_id in candidates:
        bpm = bpm_of.get(track_id)
        if bpm is None:
            fits.append(track_id)
            continue
        # Porównanie z uwzględnieniem oktawy: płyta zmierzona na 70 stoi na tej
        # samej podłodze co plan 140 — grana jest tak samo, liczy się tylko, na
        # której oktawie DJ ją odtwarza.
        variant = nearest_bpm_variant(target, bpm)
        if variant is None or abs(variant - target) > band:
            continue
        # Zakaz schodzenia. Sama bliskość planu tego nie załatwia: zmierzone
        # na 20 płytach dawało 5 spadków, czyli tyle co bez planu.
        if previous_bpm is not None and variant < previous_bpm - descent_tolerance_bpm:
            continue
        fits.append(track_id)
    return fits


def _tempo_plan_warnings(
    order: Sequence[str],
    plan: list[float] | None,
    bpm_of: dict[str, float | None],
    max_pitch_pct: float = MAX_PITCH_PCT,
) -> list[str]:
    """Powiedz, ile miejsc planu nie udało się obsadzić — nie chowaj tego."""
    if not plan:
        return []
    missed = []
    for i, t in enumerate(order):
        if i >= len(plan) or bpm_of.get(t) is None:
            continue
        variant = nearest_bpm_variant(plan[i], bpm_of[t]) or bpm_of[t]
        if abs(variant - plan[i]) > plan[i] * max_pitch_pct / 100.0:
            missed.append((i + 1, variant, plan[i]))
    if not missed:
        return []
    worst = max(missed, key=lambda m: abs(m[1] - m[2]))
    return [
        f"plan tempa nietrafiony w {len(missed)} z {len(order)} miejsc "
        f"(najgorsze: pozycja {worst[0]}, {worst[1]:.1f} zamiast {worst[2]:.1f}) — "
        f"pula nie ma utworów w tym tempie"
    ]


def _release_token(analysis: AnalysisResult) -> str | None:
    """Z jakiego wydawnictwa jest ten utwór — po katalogu, w którym leży plik.

    Janek zobaczył to na pierwszym secie, który wypuściliśmy do jego Rekordboxa:
    siedem z ośmiu utworów pochodziło z tej samej ściągniętej składanki. Reguła
    różnorodności zadziałała poprawnie i nie miała z tym nic wspólnego — ona
    pilnuje ARTYSTY, a na tej składance każdy utwór jest innego artysty. Reguły
    o wspólnym wydawnictwie po prostu nie było.

    Metadanych albumu w analizie nie mamy, ale katalog jest wiarygodnym
    zastępnikiem: pobrane albumy i składanki lądują w swoim folderze. To
    heurystyka, nie fakt — dlatego jest miękka i wyłączalna (patrz niżej).
    """
    path = getattr(analysis.track, "source_path", None)
    if not path:
        return None
    token = _normalize_artist_token(Path(str(path)).parent.name)
    return token or None


def _release_tokens(by_id: dict[str, AnalysisResult]) -> dict[str, str | None]:
    """Tokeny wydawnictw — albo puste, gdy nie ma czego różnicować.

    Jeśli CAŁA pula siedzi w jednym katalogu, ten katalog nie jest wydawnictwem,
    tylko folderem z muzyką. Limit „dwa z płyty" obciąłby wtedy set do dwóch
    utworów. Więc w takim wypadku reguła sama się wyłącza — brak różnorodności
    do wymuszenia to nie jest powód, żeby odmówić ułożenia setu.
    """
    tokens = {tid: _release_token(a) for tid, a in by_id.items()}
    distinct = {t for t in tokens.values() if t}
    if len(distinct) <= 1:
        return {tid: None for tid in tokens}
    return tokens


def _release_diverse_candidates(
    candidates: list[str],
    *,
    order: Sequence[str],
    release_tokens: dict[str, str | None],
    max_per_release: int = MAX_PER_RELEASE,
) -> list[str]:
    """Odetnij kandydatów z płyty, z której wzięliśmy już dosyć.

    Miękko, tak samo jak przy artyście: jeśli po odcięciu nie zostaje nikt,
    wracamy do pełnej listy. Set niepełny byłby gorszy niż set z trzecim
    utworem z tej samej składanki, a decyzję „lepiej mniej" podejmuje DJ,
    nie silnik.
    """
    if not candidates:
        return candidates
    counts: dict[str, int] = {}
    for track_id in order:
        token = release_tokens.get(track_id)
        if token:
            counts[token] = counts.get(token, 0) + 1
    allowed = [
        track_id
        for track_id in candidates
        if not release_tokens.get(track_id)
        or counts.get(release_tokens[track_id], 0) < max_per_release
    ]
    return allowed or candidates


def _release_diversity_warnings(
    order: Sequence[str],
    release_tokens: dict[str, str | None],
    max_per_release: int = MAX_PER_RELEASE,
) -> list[str]:
    """Powiedz wprost, gdy set i tak przekroczył limit — nie chowaj tego."""
    counts: dict[str, int] = {}
    for track_id in order:
        token = release_tokens.get(track_id)
        if token:
            counts[token] = counts.get(token, 0) + 1
    return [
        f"{n} utworów z jednego wydawnictwa ({token}) — pula nie miała czego "
        f"zaproponować zamiast"
        for token, n in sorted(counts.items())
        if n > max_per_release
    ]


def _artist_tokens(analysis: AnalysisResult) -> set[str]:
    """Artist tokens used for playlist diversity.

    Metadata is preferred. When files only expose titles like
    "Artist - Track", infer the artist from the title prefix. Collaboration
    strings produce multiple tokens so a solo track and a collab still count as
    the same artist when they share a name.
    """
    track = analysis.track
    raw_artist = (track.artist or "").strip()
    if not raw_artist and track.title:
        parts = _TITLE_ARTIST_RE.split(track.title, maxsplit=1)
        if len(parts) == 2:
            raw_artist = parts[0].strip()
    if not raw_artist:
        return set()
    tokens = {
        _normalize_artist_token(part)
        for part in _ARTIST_SPLIT_RE.split(raw_artist)
        if part.strip()
    }
    return {token for token in tokens if token}


def _share_artist(track_id_a: str | None, track_id_b: str | None, artist_tokens: dict[str, set[str]]) -> bool:
    if not track_id_a or not track_id_b:
        return False
    artists_a = artist_tokens.get(track_id_a, set())
    artists_b = artist_tokens.get(track_id_b, set())
    return bool(artists_a and artists_b and artists_a & artists_b)


def _used_artist_tokens(order: Sequence[str], artist_tokens: dict[str, set[str]]) -> set[str]:
    used: set[str] = set()
    for track_id in order:
        used.update(artist_tokens.get(track_id, set()))
    return used


def _artist_diverse_candidates(
    candidates: list[str],
    *,
    order: Sequence[str],
    index: int,
    target_count: int,
    locked_slots: dict[int, str],
    artist_tokens: dict[str, set[str]],
) -> list[str]:
    """Prefer unseen artists; when impossible, at least avoid adjacency."""
    if not candidates:
        return candidates

    result = candidates
    used = _used_artist_tokens(order, artist_tokens)
    unseen = [
        track_id
        for track_id in result
        if not artist_tokens.get(track_id) or not (artist_tokens[track_id] & used)
    ]
    if unseen:
        result = unseen

    previous = order[-1] if order else None
    non_adjacent = [
        track_id
        for track_id in result
        if not _share_artist(previous, track_id, artist_tokens)
    ]
    if non_adjacent:
        result = non_adjacent
    else:
        fallback_non_adjacent = [
            track_id
            for track_id in candidates
            if not _share_artist(previous, track_id, artist_tokens)
        ]
        if fallback_non_adjacent:
            result = fallback_non_adjacent

    next_locked = locked_slots.get(index + 1) if index + 1 < target_count else None
    if next_locked:
        before_locked = [
            track_id
            for track_id in result
            if not _share_artist(track_id, next_locked, artist_tokens)
        ]
        if before_locked:
            result = before_locked
    return result


def _artist_diversity_warnings(
    order: Sequence[str],
    artist_tokens: dict[str, set[str]],
) -> list[str]:
    warnings: list[str] = []
    seen: set[str] = set()
    repeated: set[str] = set()
    for track_id in order:
        tokens = artist_tokens.get(track_id, set())
        repeated.update(tokens & seen)
        seen.update(tokens)
    if repeated:
        warnings.append(
            "artist diversity relaxed - repeated artist(s): "
            + ", ".join(sorted(repeated))
        )

    adjacent: list[str] = []
    for left, right in zip(order, order[1:], strict=False):
        overlap = artist_tokens.get(left, set()) & artist_tokens.get(right, set())
        adjacent.extend(sorted(overlap))
    if adjacent:
        warnings.append(
            "artist diversity warning - adjacent repeated artist(s): "
            + ", ".join(sorted(set(adjacent)))
        )
    return warnings


# How strongly the engine favours staying in the same tempo octave. The corpus
# (2026-07-17, n=6142 adjacent pairs) shows DJs keep the same octave in 99.1% of
# transitions — a same-octave match is what "belongs together". Calibrated on
# Janek's 35 blind ratings: sweeping this preference rose rho 0.272→0.344
# monotonically; set to 0.9 (strong, matching the corpus). Thin leverage (2/35
# pairs crossed octaves, both rated 1/5) — revisit with the 5-rater study.
# 0.0 restores the old octave-agnostic behaviour.
SAME_OCTAVE_PREFERENCE = 0.9


def _crosses_octave(bpm_a: float | None, bpm_b: float | None) -> bool:
    """True when the best BPM match needs a half/double-time fold (octave jump)."""
    if not bpm_a or not bpm_b:
        return False
    variant = nearest_bpm_variant(bpm_a, bpm_b)
    if variant is None or variant <= 0:
        return False
    return abs(round(math.log2(variant / bpm_b))) >= 1


def bpm_score(bpm_a: float | None, bpm_b: float | None, tolerance_pct: float = 0.06) -> float:
    """1.0 at equal BPM → 0 beyond 2×tolerance, half/double-time aware.

    Same-octave matches score full; octave-equivalent ones (e.g. 90↔180) keep
    only ``1 - SAME_OCTAVE_PREFERENCE`` of the score, because the corpus shows
    DJs overwhelmingly keep tracks in one tempo family.
    """
    base = tempo_proximity_score(bpm_a, bpm_b, tolerance_pct)
    if SAME_OCTAVE_PREFERENCE and _crosses_octave(bpm_a, bpm_b):
        base *= 1.0 - SAME_OCTAVE_PREFERENCE
    return base


def track_energy(analysis: AnalysisResult) -> float:
    """Mean RMS as a coarse energy proxy."""
    vals = [f.rms for f in analysis.features if f.rms is not None]
    return float(np.mean(vals)) if vals else 0.0


def _energy_score(delta: float, arc: str) -> float:
    """Reward energy change appropriate to the set arc."""
    if arc == "build":              # gentle rise preferred; punish big drops
        return float(np.clip(0.6 + 4.0 * delta, 0.0, 1.0)) if delta >= -0.02 else \
            float(np.clip(0.6 + 8.0 * delta, 0.0, 1.0))
    if arc == "peak":               # keep energy high/flat
        return float(np.clip(1.0 - 6.0 * abs(delta), 0.0, 1.0))
    return float(np.clip(1.0 - 5.0 * abs(delta), 0.0, 1.0))  # "flat": small changes


def _normalized_energy(value: float, e_min: float, e_range: float) -> float:
    return float(np.clip((value - e_min) / max(e_range, 1e-9), 0.0, 1.0))


def _set_arc_target_profile(
    energy: Mapping[str, float],
    *,
    target_count: int,
    arc: str,
    e_min: float,
    e_range: float,
    forced_opener_id: str | None,
) -> list[float]:
    """Return a bounded set-level target in normalized RMS space.

    Build is a single broad climb, peak stays in the upper energy region, and
    flat stays near the median. This is a ranking target, not a fabricated
    measurement and not a claim about crowd response.
    """
    count = max(int(target_count), 1)
    values = sorted(_normalized_energy(value, e_min, e_range) for value in energy.values())
    if not values:
        return [0.5] * count

    opener = (
        _normalized_energy(energy[forced_opener_id], e_min, e_range)
        if forced_opener_id in energy
        else None
    )
    p15, p50, p80, p85 = [float(value) for value in np.percentile(values, [15, 50, 80, 85])]
    if arc == "build":
        start = opener if opener is not None else (values[0] if count >= len(values) else p15)
        end = values[-1] if count >= len(values) else p85
        end = max(start, end)
        if count == 1:
            return [start]
        return [
            float(np.clip(start + (end - start) * ((index / (count - 1)) ** 1.15), 0.0, 1.0))
            for index in range(count)
        ]
    if arc == "peak":
        target = max(p80, opener if opener is not None else 0.0)
        return [float(np.clip(target, 0.0, 1.0))] * count

    target = opener if opener is not None else p50
    return [float(np.clip(target, 0.0, 1.0))] * count


def _arc_profile_candidates(
    candidates: list[str],
    *,
    current: str | None,
    index: int,
    arc: str,
    target_profile: Sequence[float],
    energy: Mapping[str, float],
    e_min: float,
    e_range: float,
) -> list[str]:
    """Keep energy-near choices, then let transition scoring break the tie."""
    if not candidates:
        return candidates
    shaped = list(candidates)

    if arc == "build" and current is not None:
        current_norm = _normalized_energy(energy[current], e_min, e_range)
        no_large_drop = [
            track_id
            for track_id in shaped
            if _normalized_energy(energy[track_id], e_min, e_range)
            >= current_norm - _BUILD_MAX_DROP_FRACTION
        ]
        if no_large_drop:
            shaped = no_large_drop

    target = target_profile[min(index, len(target_profile) - 1)]
    errors = {
        track_id: abs(_normalized_energy(energy[track_id], e_min, e_range) - target)
        for track_id in shaped
    }
    best_error = min(errors.values())
    return [
        track_id
        for track_id in shaped
        if errors[track_id] <= best_error + _ARC_PROFILE_SLACK
    ]


def compute_set_coherence(
    order: Sequence[str],
    *,
    arc: str,
    energy: Mapping[str, float],
    e_min: float,
    e_range: float,
    target_profile: Sequence[float],
    bpm_by_id: Mapping[str, float | None],
) -> SetCoherence | None:
    """Whole-set shape as one number: arc adherence + tempo continuity.

    A report, not a ranking input (measure first, like the octave preference).
    - arc_adherence: how closely the set's normalised energy curve follows the
      intended arc target — this is the "energy curve exists / follows intent"
      measure directly answering set-level complaints.
    - tempo_continuity: smoothness of the raw BPM progression; the corpus shows
      DJs keep adjacent tracks within ~2% (median 1.8%), so big raw jumps read
      as a less coherent whole (octave jumps count as jumps here, on purpose).
    """
    if len(order) < 2:
        return None

    actual = [_normalized_energy(energy[t], e_min, e_range) for t in order]
    target = list(target_profile)[: len(actual)]
    if len(target) == len(actual) and target:
        mae = float(np.mean([abs(a - t) for a, t in zip(actual, target)]))
        arc_adherence = float(np.clip(1.0 - 2.0 * mae, 0.0, 1.0))
    else:  # no usable target → reward monotonic rise for build, flatness else
        deltas = np.diff(actual)
        arc_adherence = (
            float(np.clip(0.5 + 2.0 * float(np.mean(deltas)), 0.0, 1.0))
            if arc == "build"
            else float(np.clip(1.0 - 2.0 * float(np.mean(np.abs(deltas))), 0.0, 1.0))
        )

    bpms = [bpm_by_id.get(t) for t in order]
    jumps = [
        abs(b - a) / a
        for a, b in zip(bpms, bpms[1:])
        if a and b and a > 0
    ]
    tempo_continuity = (
        float(np.clip(1.0 - float(np.mean(jumps)) / 0.10, 0.0, 1.0)) if jumps else 0.5
    )

    overall = round(0.5 * arc_adherence + 0.5 * tempo_continuity, 4)
    note = (
        f"{arc} arc adherence {arc_adherence:.2f}, tempo continuity "
        f"{tempo_continuity:.2f} — whole-set report, not a ranking input"
    )
    return SetCoherence(
        overall=overall,
        arc_adherence=round(arc_adherence, 4),
        tempo_continuity=round(tempo_continuity, 4),
        note=note,
    )


def _arc_shape_warnings(
    order: Sequence[str],
    *,
    arc: str,
    energy: Mapping[str, float],
    e_range: float,
) -> list[str]:
    if arc != "build" or len(order) < 2:
        return []
    large_drop_positions = [
        index + 2
        for index, (left, right) in enumerate(zip(order, order[1:], strict=False))
        if (energy[right] - energy[left]) / max(e_range, 1e-9)
        < -_BUILD_MAX_DROP_FRACTION
    ]
    if not large_drop_positions:
        return []
    return [
        "build arc relaxed - energy drop exceeded 8% before position(s): "
        + ", ".join(str(position) for position in large_drop_positions)
    ]


def _normalize_planner_mode(planner_mode: str | None) -> str:
    mode = (planner_mode or PLANNER_MODE_SMART).strip().lower()
    if mode in {"auto", "balanced", "smart_playlist"}:
        return PLANNER_MODE_SMART
    if mode in {"key", "camelot", "harmonic_match"}:
        return PLANNER_MODE_HARMONIC
    if mode in {"tempo", "bpm_match"}:
        return PLANNER_MODE_BPM
    if mode not in PLANNER_MODES:
        raise ValueError(
            "planner_mode must be one of: " + ", ".join(PLANNER_MODES)
        )
    return mode


def _planner_component_weights(
    weights: DescriptorWeights,
    planner_mode: str,
) -> dict[str, float]:
    """Score weights for user-facing playlist preferences.

    The components remain the same measured descriptors. Modes only rebalance
    their contribution: Smart = balanced, Harmonic = Camelot/key-first, BPM =
    tempo-continuity-first.
    """
    if planner_mode == PLANNER_MODE_HARMONIC:
        return {"harmonic": 0.55, "bpm": 0.15, "energy": 0.10, "mixability": 0.20}
    if planner_mode == PLANNER_MODE_BPM:
        return {"harmonic": 0.15, "bpm": 0.55, "energy": 0.10, "mixability": 0.20}
    return dict(weights.set_builder.weights)


def transition_score(
    a: AnalysisResult,
    b: AnalysisResult,
    weights: DescriptorWeights,
    arc: str,
    energy_a: float,
    energy_b: float,
    energy_range: float,
    planner_mode: str = PLANNER_MODE_SMART,
    context: ContextProfile | None = None,
    mixability_precomputation: MixabilityPrecomputation | None = None,
) -> tuple[float, str, list[str]]:
    """Combined A→B transition score in [0,1] + harmonic relation + reasoning."""
    planner_mode = _normalize_planner_mode(planner_mode)
    harm = harmonic_compatibility(
        a.track.key_estimate, b.track.key_estimate,
        a.track.key_confidence, b.track.key_confidence,
    )
    rel = harm.harmonic_relation
    h = harm.harmonic_compatibility_score
    bp = bpm_score(a.track.bpm_estimate, b.track.bpm_estimate)
    d_energy = (energy_b - energy_a) / (energy_range + 1e-9)
    en = _energy_score(d_energy, arc)
    mix = compute_mixability(
        MixabilityInput(track_a=a, track_b=b, context=context),
        weights.mixability,
        weights.mixability_conflict,
        precomputed=mixability_precomputation,
    ).mixability_score

    w = _planner_component_weights(weights, planner_mode)
    component_values = {"harmonic": h, "bpm": bp, "energy": en, "mixability": mix}
    score = sum(w[name] * component_values[name] for name in COMPONENTS)

    # Brzmienie wmieszane PO rdzeniu i tylko w trybie smart — czyste tryby
    # harmonic/bpm to jawna wola usera i zostają dokładnie tym, o co prosił.
    # Zmierzone na 45 miksach: dolna tercja DJ-ów +0,071 (patrz sound_affinity).
    sound_note = None
    if planner_mode == PLANNER_MODE_SMART:
        sound_w = getattr(weights, "sound_affinity_weight", 0.0) or 0.0
        if sound_w > 0:
            aff = cosine_affinity(a.track.sound_embedding, b.track.sound_embedding)
            score, sound_note = blend(score, aff, sound_w)
    reasoning = [
        f"planner mode {planner_mode}",
        f"harmonic {rel} ({a.track.key_estimate}->{b.track.key_estimate}) score {h:.2f}",
        f"bpm {a.track.bpm_estimate}->{b.track.bpm_estimate} score {bp:.2f}",
        f"energy Δ {d_energy:+.2f} ({arc}) score {en:.2f}",
        f"mixability {mix:.2f}",
    ]
    if sound_note:
        reasoning.append(sound_note)
    # corpus prior only in SMART mode: pure harmonic/bpm modes are the user's
    # explicit override and must stay exactly what they ask for
    prior_weight = getattr(weights, "corpus_priors_weight", 0.0) or 0.0
    if prior_weight > 0 and planner_mode == PLANNER_MODE_SMART:
        lift, prior_notes = transition_prior_lift(
            rel, a.track.bpm_estimate, b.track.bpm_estimate
        )
        if lift != 1.0:
            score = min(1.0, max(0.0, score * (lift ** prior_weight)))
        reasoning.extend(prior_notes)
    return float(score), rel, reasoning


def _normalize_locked_positions(
    locked_positions: Mapping[int | str, str] | None,
) -> dict[int, str]:
    normalized: dict[int, str] = {}
    for raw_position, raw_track_id in (locked_positions or {}).items():
        try:
            position = int(raw_position)
        except (TypeError, ValueError) as exc:
            raise ValueError("locked_positions keys must be 1-based integer positions") from exc
        track_id = str(raw_track_id).strip()
        if not track_id:
            raise ValueError("locked_positions values must be non-empty track IDs")
        normalized[position] = track_id
    return normalized


def _normalize_pinned_track_ids(pinned_track_ids: Sequence[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw_track_id in pinned_track_ids or []:
        track_id = str(raw_track_id).strip()
        if track_id and track_id not in seen:
            normalized.append(track_id)
            seen.add(track_id)
    return normalized


def _validate_build_constraints(
    by_id: dict[str, AnalysisResult],
    *,
    target_track_count: int | None,
    locked_positions: dict[int, str],
    pinned_track_ids: list[str],
    start_track_id: str | None,
) -> tuple[int, list[str]]:
    target_count = target_track_count or len(by_id)
    if target_count < 1:
        raise ValueError("target_track_count must be >= 1")
    if target_count > len(by_id):
        raise ValueError("target_track_count cannot exceed the number of available tracks")

    warnings: list[str] = []
    unknown_locked = sorted(set(locked_positions.values()) - set(by_id))
    if unknown_locked:
        raise ValueError(f"locked_positions reference unknown tracks: {', '.join(unknown_locked)}")
    unknown_pinned = sorted(set(pinned_track_ids) - set(by_id))
    if unknown_pinned:
        raise ValueError(f"pinned_track_ids reference unknown tracks: {', '.join(unknown_pinned)}")

    invalid_positions = sorted(position for position in locked_positions if position < 1 or position > target_count)
    if invalid_positions:
        raise ValueError(
            "locked_positions must be within the final 1-based set length: "
            + ", ".join(str(position) for position in invalid_positions)
        )

    locked_track_ids = list(locked_positions.values())
    duplicate_locked_ids = sorted({track_id for track_id in locked_track_ids if locked_track_ids.count(track_id) > 1})
    if duplicate_locked_ids:
        raise ValueError(
            "a track cannot be locked to multiple positions: " + ", ".join(duplicate_locked_ids)
        )

    required_ids = set(locked_track_ids) | set(pinned_track_ids)
    if len(required_ids) > target_count:
        raise ValueError("locked/pinned tracks exceed target_track_count")

    if start_track_id and start_track_id not in by_id:
        warnings.append(f"start_track_id `{start_track_id}` is unknown and was ignored")
    elif start_track_id and locked_positions.get(1) and locked_positions[1] != start_track_id:
        warnings.append("start_track_id ignored because locked position 1 defines the opener")
    elif start_track_id and start_track_id in locked_track_ids and locked_positions.get(1) != start_track_id:
        warnings.append("start_track_id is locked to a later position, so opener was chosen by constraints")

    return target_count, warnings


def _best_successor(
    current: str,
    candidates: list[str],
    *,
    by_id: dict[str, AnalysisResult],
    weights: DescriptorWeights,
    arc: str,
    energy: dict[str, float],
    energy_range: float,
    planner_mode: str,
    context: ContextProfile | None,
    mixability_precomputation: MixabilityPrecomputation,
    novelty: "NoveltyContext | None" = None,
    steering: "SoundSteering | None" = None,
    premia: "_premia.PremiaGatunku | None" = None,
    position: int = 0,
    bridge_to: str | None = None,
) -> str:
    scored: list[tuple[float, str]] = []
    for candidate in candidates:
        score, _, _ = transition_score(
            by_id[current],
            by_id[candidate],
            weights,
            arc,
            energy[current],
            energy[candidate],
            energy_range,
            planner_mode,
            context,
            mixability_precomputation,
        )
        if bridge_to is not None:
            # KRAWĘDŹ MOSTOWA (badanie tripletów, 09.08.2026): gdy następny
            # slot to FILAR, kandydat jest oceniany także za wejście W NIEGO —
            # suma obu krawędzi, wagi równe (zmierzone α=1,0). Na 636
            # segmentach realnych setów podnosi dokładne rekonstrukcje
            # 28,1%→36,2% (p<0,0001). Tylko ustalone C — spekulacyjny
            # lookahead bez celu zmierzony jako bezwartościowy i celowo
            # NIEobecny (p=0,88 na 152 setach).
            score_w_filar, _, _ = transition_score(
                by_id[candidate],
                by_id[bridge_to],
                weights,
                arc,
                energy[candidate],
                energy[bridge_to],
                energy_range,
                planner_mode,
                context,
                mixability_precomputation,
            )
            score += score_w_filar
        # Sterowanie (kotwica/kontur) to jawne wejście DJ-a — działa tylko gdy
        # o nie poprosił; ścieżka domyślna pozostaje bajt w bajt ta sama.
        if steering is not None and steering.active:
            score, _why = steering.adjust(
                score, by_id[current], by_id[candidate], position)
        if premia is not None and premia.aktywna:
            # dwie krawędzie, gdy następny slot to filar (reguła tripletów)
            score, _ = premia.dopasuj(
                score, by_id[candidate], 2 if bridge_to is not None else 1)
        if novelty is not None:
            # §14: soft penalties inside the gate-passing candidate set —
            # relevance ordering first, history discourages repeats
            score -= novelty.penalty(current, candidate)
        scored.append((score, candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score = scored[0][0]
    if novelty is not None and novelty.rng is not None and novelty.epsilon > 0:
        # seeded tie-break ONLY among candidates within the honest score
        # resolution — variation never sacrifices relevance
        ties = [cand for score, cand in scored if best_score - score <= novelty.epsilon]
        if len(ties) > 1:
            return novelty.rng.choice(ties)
    return scored[0][1]


def _build_transition(
    from_track_id: str,
    to_track_id: str,
    *,
    by_id: dict[str, AnalysisResult],
    weights: DescriptorWeights,
    arc: str,
    energy: dict[str, float],
    energy_range: float,
    planner_mode: str,
    context: ContextProfile | None,
    mixability_precomputation: MixabilityPrecomputation,
) -> SetTransition:
    a = by_id[from_track_id]
    b = by_id[to_track_id]
    score, rel, reason = transition_score(
        a,
        b,
        weights,
        arc,
        energy[from_track_id],
        energy[to_track_id],
        energy_range,
        planner_mode,
        context,
        mixability_precomputation,
    )
    d_bpm = None
    if a.track.bpm_estimate and b.track.bpm_estimate:
        d_bpm = round((b.track.bpm_estimate - a.track.bpm_estimate) / a.track.bpm_estimate * 100, 1)
    warnings = []
    if rel == "risky":
        warnings.append("risky key change — consider an echo-out / effect transition")
    return SetTransition(
        from_track_id=from_track_id,
        to_track_id=to_track_id,
        transition_score=round(score, 4),
        harmonic_relation=rel,
        key_from=a.track.key_estimate,
        key_to=b.track.key_estimate,
        bpm_from=a.track.bpm_estimate,
        bpm_to=b.track.bpm_estimate,
        bpm_delta_pct=d_bpm,
        energy_delta=round(energy[to_track_id] - energy[from_track_id], 4),
        reasoning=reason,
        warnings=warnings,
    )


def _constrained_order(
    by_id: dict[str, AnalysisResult],
    *,
    weights: DescriptorWeights,
    arc: str,
    start_track_id: str | None,
    target_count: int,
    locked_positions: dict[int, str],
    pinned_track_ids: list[str],
    energy: dict[str, float],
    e_min: float,
    energy_range: float,
    target_profile: Sequence[float],
    artist_tokens: dict[str, set[str]],
    release_tokens: dict[str, str | None],
    tempo_targets: list[float] | None,
    bpm_of: dict[str, float | None],
    planner_mode: str,
    context: ContextProfile | None,
    mixability_precomputation: MixabilityPrecomputation,
    novelty: "NoveltyContext | None" = None,
    steering: "SoundSteering | None" = None,
    premia: "_premia.PremiaGatunku | None" = None,
) -> list[str]:
    locked_slots = {position - 1: track_id for position, track_id in locked_positions.items()}
    locked_track_ids = set(locked_positions.values())
    remaining = set(by_id) - locked_track_ids
    order: list[str] = []
    current: str | None = None
    # Tempo POPRZEDNIEJ płyty tak, jak realnie zabrzmiała — czyli sprowadzone do
    # oktawy, na której DJ ją odtwarza. Bez tego zakaz schodzenia porównywałby
    # 70 ze 140 i wyrzucał utwór, który stoi dokładnie na miejscu.
    played_bpm: float | None = None

    for index in range(target_count):
        if index in locked_slots:
            chosen = locked_slots[index]
        else:
            open_slots = sum(1 for slot in range(index, target_count) if slot not in locked_slots)
            remaining_pinned = [track_id for track_id in pinned_track_ids if track_id in remaining]
            candidates = sorted(remaining_pinned if len(remaining_pinned) >= open_slots else remaining)
            # PLAN TEMPA IDZIE PIERWSZY. Kolejność sit nie jest kosmetyką:
            # gdy różnorodność wydawnictwa szła przed nim, na 22. pozycji
            # dwugodzinnego setu odcięła utwory z już użytych folderów — a to
            # właśnie tam siedziały ostatnie płyty przy 140. Plan dostawał listę
            # bez niczego szybkiego, ustępował i tempo spadało ze 140 na 132.
            # Plan tempa to jawne wejście DJ-a; różnorodność to udogodnienie,
            # które ma się układać wewnątrz jego ramy, a nie łamać ją.
            candidates = _tempo_plan_candidates(
                candidates,
                index=index,
                plan=tempo_targets,
                bpm_of=bpm_of,
                previous_bpm=played_bpm,
            )
            # Wydawnictwo przed artystą: jest grubszym sitem. Na składance każdy
            # utwór ma innego artystę, więc sito artysty przepuszcza ją w całości.
            candidates = _release_diverse_candidates(
                candidates,
                order=order,
                release_tokens=release_tokens,
            )
            candidates = _artist_diverse_candidates(
                candidates,
                order=order,
                index=index,
                target_count=target_count,
                locked_slots=locked_slots,
                artist_tokens=artist_tokens,
            )
            candidates = _arc_profile_candidates(
                candidates,
                current=current,
                index=index,
                arc=arc,
                target_profile=target_profile,
                energy=energy,
                e_min=e_min,
                e_range=energy_range,
            )
            if not candidates:
                raise ValueError("constraints left no candidate track for an unlocked position")
            if current is None:
                if start_track_id in candidates:
                    chosen = start_track_id
                else:
                    target = target_profile[min(index, len(target_profile) - 1)]
                    chosen = min(
                        candidates,
                        key=lambda tid: (
                            abs(_normalized_energy(energy[tid], e_min, energy_range) - target),
                            tid,
                        ),
                    )
            else:
                chosen = _best_successor(
                    current,
                    candidates,
                    by_id=by_id,
                    weights=weights,
                    arc=arc,
                    energy=energy,
                    energy_range=energy_range,
                    planner_mode=planner_mode,
                    context=context,
                    mixability_precomputation=mixability_precomputation,
                    novelty=novelty,
                    steering=steering,
                    premia=premia,
                    position=index,
                    # następny slot zajęty filarem → kandydat musi umieć
                    # w niego WEJŚĆ (krawędź mostowa; bez filarów None
                    # i ścieżka pozostaje bajt w bajt dawna)
                    bridge_to=locked_slots.get(index + 1),
                )
            remaining.remove(chosen)

        order.append(chosen)
        current = chosen
        chosen_bpm = bpm_of.get(chosen)
        if chosen_bpm:
            played_bpm = (
                nearest_bpm_variant(played_bpm, chosen_bpm) if played_bpm else chosen_bpm
            ) or chosen_bpm

    return order


def build_set(
    analyses: list[AnalysisResult],
    weights: DescriptorWeights,
    arc: str = "build",
    start_track_id: str | None = None,
    target_track_count: int | None = None,
    locked_positions: Mapping[int | str, str] | None = None,
    pinned_track_ids: Sequence[str] | None = None,
    planner_mode: str = PLANNER_MODE_SMART,
    context: ContextProfile | None = None,
    preferred_styles: Sequence[str] | None = None,
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    novelty_mode: str = "deterministic",
    history: Sequence["PlaylistFingerprint"] | None = None,
    seed: int | None = None,
    tempo_shape: str = TEMPO_SHAPE_OFF,
    sound_anchor: Sequence[float] | None = None,
    anchor_name: str | None = None,
    anchor_weight: float | None = None,
    jump_contour: Sequence[float] | None = None,
    contour_weight: float | None = None,
) -> SetPlan:
    """Greedy harmonic/energy set ordering with optional lock/pin constraints.

    `locked_positions` uses 1-based final playlist slots. Pinned tracks must
    appear somewhere in the final plan; `target_track_count` lets the planner
    choose a constrained subset from a larger candidate pool.

    §14 novelty: `novelty_mode` (deterministic/conservative/balanced/fresh/
    exploratory) applies soft history penalties and a seeded ε tie-break.
    Default "deterministic" = byte-stable, identical to pre-novelty behavior.
    Pinned tracks are exempt from overuse penalties (§15.10 — intentional
    carryover). Hard gates are never overridden by novelty pressure.
    """
    provenance = provenance_for("set_builder")
    planner_mode = _normalize_planner_mode(planner_mode)
    locked = _normalize_locked_positions(locked_positions)
    pinned = _normalize_pinned_track_ids(pinned_track_ids)
    # Collapse byte-identical audio to one entry so the same track can't appear
    # twice in a set under two filenames (see decision/dedup.py).
    analyses, dedup_warnings = dedupe_by_audio(analyses)
    by_id_all = {a.track.track_id: a for a in analyses}
    by_id = by_id_all
    if not by_id:
        if target_track_count or locked or pinned:
            raise ValueError("no tracks available for requested set constraints")
        return SetPlan(
            track_order=[],
            arc=arc,
            planner_mode=planner_mode,
            target_track_count=target_track_count,
            locked_positions=locked,
            pinned_track_ids=pinned,
            model_version=MODEL_VERSION,
            provenance=provenance,
            warnings=["need >=2 tracks to build a set"],
        )

    preference_warnings: list[str] = []
    target_count_for_preferences = target_track_count or len(by_id)
    required_ids = set(locked.values()) | set(pinned)
    if start_track_id:
        required_ids.add(start_track_id)

    premia_gatunku = None
    style_preferences = normalize_style_list(preferred_styles)
    if not style_preferences and context is not None:
        style_preferences = normalize_style_list(context.style_focus)
    if style_preferences:
        style_ids = {
            track_id
            for track_id, analysis in by_id_all.items()
            if style_matches(analysis.track.style_label, style_preferences)
        }
        preferred_pool = style_ids | required_ids
        if len(preferred_pool & set(by_id_all)) >= target_count_for_preferences:
            by_id = {track_id: by_id_all[track_id] for track_id in by_id_all if track_id in preferred_pool}
            dropped = len(by_id_all) - len(by_id)
            if dropped:
                preference_warnings.append(
                    f"style preference applied ({', '.join(style_preferences)}); "
                    f"{dropped} non-matching track(s) left out"
                )
        else:
            # Twarde sito nie przechodzi (za mało pasujących utworów na set),
            # ale preferencja NIE ZNIKA: schodzi do premii w ocenie, żeby set
            # trzymał się gatunku tak długo, jak pula pozwala (decyzja Janka
            # 09.08 — wcześniej jeden utwór poniżej progu kasował brief).
            premia_gatunku = _premia.zbuduj(style_preferences)
            preference_warnings.append(
                "style preference relaxed - not enough analyzed tracks match "
                + ", ".join(style_preferences)
            )

    resolved_bpm_min = bpm_min if bpm_min is not None else (context.bpm_min if context else None)
    resolved_bpm_max = bpm_max if bpm_max is not None else (context.bpm_max if context else None)
    if resolved_bpm_min is not None or resolved_bpm_max is not None:
        bpm_ids = {
            track_id
            for track_id, analysis in by_id.items()
            if bpm_in_range(analysis.track.bpm_estimate, resolved_bpm_min, resolved_bpm_max)
        }
        preferred_pool = bpm_ids | required_ids
        if len(preferred_pool & set(by_id)) >= target_count_for_preferences:
            before = len(by_id)
            by_id = {track_id: analysis for track_id, analysis in by_id.items() if track_id in preferred_pool}
            dropped = before - len(by_id)
            if dropped:
                preference_warnings.append(
                    f"BPM range applied ({resolved_bpm_min or '-∞'}-{resolved_bpm_max or '+∞'}); "
                    f"{dropped} out-of-range track(s) left out"
                )
        else:
            preference_warnings.append(
                "BPM range relaxed - not enough analyzed tracks match "
                f"{resolved_bpm_min or '-∞'}-{resolved_bpm_max or '+∞'}"
            )

    target_count, constraint_warnings = _validate_build_constraints(
        by_id,
        target_track_count=target_track_count,
        locked_positions=locked,
        pinned_track_ids=pinned,
        start_track_id=start_track_id,
    )
    mixability_precomputation = precompute_mixability_inputs(
        by_id.values(),
        context=context,
    )
    # A track the analysis produced no RMS for has UNKNOWN energy, not zero
    # energy. Substituting 0.0 made it the floor of the scale, rescaling every
    # other track and — under a build arc, which opens at the quietest point —
    # dragging it toward the opener on the strength of a measurement that was
    # never taken (ADR-005).
    measured: dict[str, float] = {}
    unmeasured: list[str] = []
    for track_id in by_id:
        mean_rms = mixability_precomputation.feature_means[track_id]["rms"]
        if mean_rms is None:
            unmeasured.append(track_id)
        else:
            measured[track_id] = float(mean_rms)

    if measured:
        e_min = min(measured.values())
        e_range = max(measured.values()) - e_min or 1.0
        # Unknown energy sits at the middle of the measured pool: neutral for
        # ranking, and it cannot stretch the scale or claim an extreme.
        placeholder = float(np.median(list(measured.values())))
    else:
        e_min, e_range, placeholder = 0.0, 1.0, 0.0

    energy: dict[str, float] = dict(measured)
    energy_warnings = [
        f"energy unavailable for {track_id} (no RMS frames) — "
        "treated as the pool median and excluded from the energy scale"
        for track_id in unmeasured
    ]
    for track_id in unmeasured:
        energy[track_id] = placeholder
    forced_opener_id = locked.get(1) or (start_track_id if start_track_id in by_id else None)
    target_profile = _set_arc_target_profile(
        energy,
        target_count=target_count,
        arc=arc,
        e_min=e_min,
        e_range=e_range,
        forced_opener_id=forced_opener_id,
    )
    artist_tokens = {tid: _artist_tokens(analysis) for tid, analysis in by_id.items()}
    release_tokens = _release_tokens(by_id)
    bpm_of = {tid: (a.track.bpm_estimate or None) for tid, a in by_id.items()}
    tempo_targets = tempo_plan(
        [b for b in bpm_of.values() if b], tempo_shape, slots=target_track_count
    )

    steering = None
    if sound_anchor is not None or jump_contour:
        import numpy as _np

        from dancelab.decision.steering import (
            DEFAULT_ANCHOR_WEIGHT,
            DEFAULT_CONTOUR_WEIGHT,
            SoundSteering,
        )
        steering = SoundSteering(
            anchor=_np.asarray(sound_anchor, dtype=float) if sound_anchor is not None else None,
            anchor_weight=DEFAULT_ANCHOR_WEIGHT if anchor_weight is None else float(anchor_weight),
            contour=list(jump_contour) if jump_contour else None,
            contour_weight=DEFAULT_CONTOUR_WEIGHT if contour_weight is None else float(contour_weight),
            anchor_name=anchor_name,
        )
        with_vec = sum(1 for a in by_id_all.values() if a.track.sound_embedding is not None)
        preference_warnings.append(
            f"sterowanie brzmieniem aktywne ({anchor_name or 'kontur'}): "
            f"wektory ma {with_vec}/{len(by_id_all)} utworów puli")
        if with_vec == 0:
            preference_warnings.append(
                "ŻADEN utwór puli nie ma wektora brzmienia — sterowanie nie "
                "zmieni doboru; uzupełnij data/reports/library_embeddings.json")

    novelty = NoveltyContext.build(
        mode=novelty_mode,
        history=list(history or []),
        seed=seed,
        exempt_ids=set(pinned),
    )

    def _run_order(active_novelty: NoveltyContext) -> list[str]:
        return _constrained_order(
            by_id,
            weights=weights,
            arc=arc,
            start_track_id=start_track_id,
            target_count=target_count,
            locked_positions=locked,
            pinned_track_ids=pinned,
            energy=energy,
            e_min=e_min,
            energy_range=e_range,
            target_profile=target_profile,
            artist_tokens=artist_tokens,
            release_tokens=release_tokens,
            tempo_targets=tempo_targets,
            bpm_of=bpm_of,
            planner_mode=planner_mode,
            context=context,
            mixability_precomputation=mixability_precomputation,
            novelty=active_novelty,
            steering=steering,
            premia=premia_gatunku,
        )

    order = _run_order(novelty)
    novelty_warnings: list[str] = []
    if novelty_mode != "deterministic" and history:
        last = history[-1]
        if list(order) == list(last.track_ids_ordered):
            # §14 same-sequence guard: one retry with next seed + doubled edge
            # penalty; if STILL identical the library is too small to vary —
            # keep the honest result, never fake-shuffle.
            retry = NoveltyContext.build(
                mode=novelty_mode,
                history=list(history),
                seed=(seed or 0) + 1,
                exempt_ids=set(pinned),
            )
            retry.edge_penalty *= 2
            retry_order = _run_order(retry)
            if list(retry_order) == list(order):
                novelty_warnings.append(
                    "library too small to vary — identical set returned"
                )
            else:
                order = retry_order
    transitions = [
        _build_transition(
            current,
            successor,
            by_id=by_id,
            weights=weights,
            arc=arc,
            energy=energy,
            energy_range=e_range,
            planner_mode=planner_mode,
            context=context,
            mixability_precomputation=mixability_precomputation,
        )
        for current, successor in zip(order, order[1:], strict=False)
    ]
    mean_score = round(float(np.mean([t.transition_score for t in transitions])), 4) if transitions else None
    coherence = compute_set_coherence(
        order,
        arc=arc,
        energy=energy,
        e_min=e_min,
        e_range=e_range,
        target_profile=target_profile,
        bpm_by_id={tid: by_id[tid].track.bpm_estimate for tid in order},
    )
    warnings = [
        *dedup_warnings,
        *preference_warnings,
        *(steering.coverage_warnings() if steering is not None else []),
        *([premia_gatunku.podsumowanie()]
          if premia_gatunku is not None and premia_gatunku.ocenione else []),
        *constraint_warnings,
        *energy_warnings,
        *_artist_diversity_warnings(order, artist_tokens),
        *_release_diversity_warnings(order, release_tokens),
        *_tempo_plan_warnings(order, tempo_targets, bpm_of),
        *_arc_shape_warnings(order, arc=arc, energy=energy, e_range=e_range),
        *novelty_warnings,
    ]
    if len(order) < 2:
        warnings.append("need >=2 tracks to build a set")

    return SetPlan(
        track_order=order, transitions=transitions, arc=arc, planner_mode=planner_mode,
        target_track_count=target_count,
        locked_positions=locked,
        pinned_track_ids=pinned,
        dropped_track_ids=sorted(set(by_id_all) - set(order)),
        mean_transition_score=mean_score, set_coherence=coherence,
        model_version=MODEL_VERSION,
        warnings=warnings,
        provenance=provenance,
    )
