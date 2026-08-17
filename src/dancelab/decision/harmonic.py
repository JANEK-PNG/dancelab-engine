"""Harmonic Compatibility layer v0.1 (Sprint 5.1 hotfix — first-class engine layer).

Camelot-key harmonic scoring, used by mixability (S_harmonic) and transition
windows (R_harmonic). Relation taxonomy per R&D Harmonic Compatibility Model v0.1:

    exact                same number + mode        strong compatibility
    relative_major_minor same number, opposite mode compatibility
    adjacent_same_mode   ±1 number, same mode       compatibility
    cautious             +2 same mode (energy lift) to-validate
    risky                large jump / clash         risk candidate
    unknown              missing / low-conf key     confidence penalty

Key principle (Transition Windows hotfix): a risky key relationship matters
MORE when harmonic material (vocals / melodic "other") is exposed in the overlap
window, LESS in percussion-only windows.

STATUS: candidate. C011: Camelot compatibility supports a transition decision but
does NOT validate the mix. Source basis: Mixed In Key (S049), Serato (S050).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

_RELATION_SCORE = {
    "exact": 1.0,
    "relative_major_minor": 0.85,
    "adjacent_same_mode": 0.85,
    "cautious": 0.6,
    "risky": 0.15,
    "unknown": 0.5,
}
_RELATION_RISK = {  # base risk before exposure modulation
    "exact": 0.05,
    "relative_major_minor": 0.15,
    "adjacent_same_mode": 0.15,
    "cautious": 0.4,
    "risky": 0.8,
    "unknown": 0.5,
}


def parse_camelot(code: str | None) -> tuple[int, str] | None:
    if not code or len(code) < 2 or code[-1] not in ("A", "B"):
        return None
    try:
        num = int(code[:-1])
    except ValueError:
        return None
    return (num, code[-1]) if 1 <= num <= 12 else None


def camelot_distance(cam_a: str | None, cam_b: str | None) -> int | None:
    """Cyclic distance between Camelot numbers (0-6). None if unparseable."""
    a, b = parse_camelot(cam_a), parse_camelot(cam_b)
    if a is None or b is None:
        return None
    d = abs(a[0] - b[0])
    return min(d, 12 - d)


def harmonic_relation(cam_a: str | None, cam_b: str | None) -> str:
    a, b = parse_camelot(cam_a), parse_camelot(cam_b)
    if a is None or b is None:
        return "unknown"
    (na, la), (nb, lb) = a, b
    if na == nb and la == lb:
        return "exact"
    if na == nb and la != lb:
        return "relative_major_minor"
    if la == lb and min(abs(na - nb), 12 - abs(na - nb)) == 1:
        return "adjacent_same_mode"
    # AUD-H1: distance-2 same-mode moves are symmetric — +2 (energy lift) and
    # −2 (energy drop) are both plausible-but-secondary Camelot moves, not the
    # "large jump / clash" the risky bucket documents. The old `(nb-na)%12==2`
    # tagged only the upward direction, scoring 8A→6A as a near-clash (0.15)
    # while 6A→8A scored 0.60 — an undocumented asymmetry in the single
    # highest-weighted set-builder term.
    if la == lb and min(abs(na - nb), 12 - abs(na - nb)) == 2:
        return "cautious"
    return "risky"


class HarmonicResult(BaseModel):
    """Pairwise harmonic outputs (R&D Engine Extension outputs)."""

    harmonic_relation: str
    camelot_distance: int | None = None
    key_a: str | None = None
    key_b: str | None = None
    harmonic_compatibility_score: float = Field(ge=0, le=1)   # S_harmonic
    harmonic_risk: float = Field(ge=0, le=1)                  # R_harmonic
    key_confidence_min: float = Field(ge=0, le=1)
    harmonic_reasoning: list[str] = Field(default_factory=list)
    harmonic_warning: str = ""


def harmonic_compatibility(
    cam_a: str | None,
    cam_b: str | None,
    conf_a: float | None = None,
    conf_b: float | None = None,
    exposure: float | None = None,
) -> HarmonicResult:
    """Compute S_harmonic + R_harmonic for a track/window pair.

    conf_a/conf_b: key-detection confidences (low → damp score, raise risk).
    exposure ∈ [0,1]: harmonic material exposed in the overlap (vocals/melodic).
      Higher exposure amplifies the risk of a risky relation; percussion-only
      (low exposure) masks it. None → neutral 0.5.
    """
    # Brak pewności to NIE jest pewność. Do 17.08 `None` zamieniało się tu
    # po cichu na 1.0 — czyli „nikt nie zmierzył" znaczyło „jestem absolutnie
    # pewien", i to w członie o najwyższej wadze w całym silniku. Domyślną
    # wartością jest teraz 0.5: ani nie ufamy, ani nie odrzucamy.
    # Skutek zmierzony na samej funkcji: rozpiętość ocen między najlepszą
    # a najgorszą relacją spada z 0,850 na 0,425, czyli człon harmoniczny
    # przestaje rozstrzygać, a zaczyna doradzać. Kierunek zgodny z korpusem:
    # prawdziwi DJ-e rozciągają oś Camelota na 1,50×, silnik rozciągał ją
    # na 6,7× i po tej zmianie schodzi do 2,3×.
    NIEZMIERZONA = 0.5
    conf_min = min(conf_a if conf_a is not None else NIEZMIERZONA,
                   conf_b if conf_b is not None else NIEZMIERZONA)
    exp = 0.5 if exposure is None else max(0.0, min(1.0, exposure))

    rel = harmonic_relation(cam_a, cam_b)
    # R&D confidence rule: a very low-confidence key is unreliable, so don't
    # confidently declare a "risky" (or any) relation — mark it unknown.
    low_conf = conf_min < 0.15
    if low_conf and rel != "unknown":
        rel = "unknown"

    base_score = _RELATION_SCORE[rel]
    # low key confidence pulls the score toward neutral (can't trust the relation)
    score = base_score * conf_min + 0.5 * (1.0 - conf_min)

    base_risk = _RELATION_RISK[rel]
    # exposure modulation: risky relation matters ×(0.5..1.5) with exposure;
    # low key confidence adds risk (unknown territory)
    risk = base_risk * (0.5 + exp) + 0.2 * (1.0 - conf_min)
    risk = max(0.0, min(1.0, risk))

    reasoning = [
        f"camelot {cam_a}->{cam_b}: {rel} (distance {camelot_distance(cam_a, cam_b)})",
        f"key confidence min {conf_min:.2f}",
        f"harmonic exposure in window {exp:.2f}",
    ]
    warning = ""
    if rel == "risky" and exp > 0.4:
        warning = "risky key clash with exposed harmonic/vocal content — echo-out or effect transition"
    elif rel == "risky":
        warning = "risky key relation, but low harmonic exposure may mask it"
    elif conf_min < 0.3:
        warning = "low key confidence — verify key before trusting harmonic result"

    return HarmonicResult(
        harmonic_relation=rel,
        camelot_distance=camelot_distance(cam_a, cam_b),
        key_a=cam_a, key_b=cam_b,
        harmonic_compatibility_score=round(score, 4),
        harmonic_risk=round(risk, 4),
        key_confidence_min=round(conf_min, 4),
        harmonic_reasoning=reasoning,
        harmonic_warning=warning,
    )
