"""Source-grounding / no-overclaiming layer (Sprint 3).

Loads engine model cards from configs/model_cards.yaml and turns them into the
OutputProvenance block that every decision output must carry (R&D Guardrails —
No Overclaiming Output Contract). Also provides the standard guardrail warnings.

Core stays framework-free (ADR-003); this is pure data + Pydantic.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from dancelab.core.errors import ConfigError
from dancelab.core.models import (
    ComponentMetadata,
    EvidenceGrade,
    ModelCard,
    OutputProvenance,
    SourceStatus,
    StemAwareScore,
    ValidationStatus,
    WarningLevel,
)

# Sprint 3 honesty cap: nothing may claim more than validation-ready without a
# real pilot (Evidence Grading Standard). Enforced when cards are loaded.
_MAX_EVIDENCE_GRADE = EvidenceGrade.E4


@lru_cache(maxsize=8)
def load_model_cards(path: str = "configs/model_cards.yaml") -> dict[str, ModelCard]:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Model cards file not found: {p}")
    data = yaml.safe_load(p.read_text())
    cards = {key: ModelCard.model_validate(card) for key, card in data.get("cards", {}).items()}
    for key, card in cards.items():
        if card.evidence_grade in (EvidenceGrade.E5, EvidenceGrade.E6):
            raise ConfigError(
                f"model card '{key}' claims {card.evidence_grade.value} without a pilot — "
                "forbidden by the Evidence Grading Standard (Sprint 3 cap = E4)"
            )
        if card.validation_status != ValidationStatus.to_validate:
            raise ConfigError(
                f"model card '{key}' is not to_validate — no engine output is validated yet"
            )
    return cards


def get_model_card(engine_key: str, path: str = "configs/model_cards.yaml") -> ModelCard:
    cards = load_model_cards(path)
    if engine_key not in cards:
        raise ConfigError(f"No model card for engine '{engine_key}'. Have: {sorted(cards)}")
    return cards[engine_key]


def provenance_for(engine_key: str, path: str = "configs/model_cards.yaml") -> OutputProvenance:
    """Build the OutputProvenance block for an engine, traceable to its card."""
    c = get_model_card(engine_key, path)
    return OutputProvenance(
        model_card_id=c.model_card_id,
        scientific_status=c.scientific_status,
        evidence_grade=c.evidence_grade,
        validation_status=c.validation_status,
        source_basis=c.source_basis,
        dance_lab_inference=c.dance_lab_inference,
        cannot_claim=c.cannot_claim,
        required_validation=c.required_validation,
        limitations=c.limitations,
        allowed_ui_wording=c.allowed_ui_wording,
    )


@lru_cache(maxsize=8)
def load_formula_terms(path: str = "configs/formula_terms.yaml") -> dict[str, ComponentMetadata]:
    """Load per-component formula-term metadata (no anonymous variables)."""
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Formula terms file not found: {p}")
    data = yaml.safe_load(p.read_text())
    return {
        key: ComponentMetadata(component_key=key, **term)
        for key, term in data.get("terms", {}).items()
    }


def guardrail_warnings(
    *,
    has_beatgrid: bool = True,
    has_context: bool = True,
    dj_validated: bool = False,
    source_grounding: float = 1.0,
    conflicting: bool = False,
    risk_score: float | None = None,
    annotator_agreement: float | None = None,
    high_risk_threshold: float = 0.6,
    low_agreement_threshold: float = 0.6,
) -> list[str]:
    """Standard guardrail warnings (No-Overclaiming Contract — Required warnings).

    dj_validated defaults False: nothing is DJ-validated yet, so the
    'not DJ-validated' warning is emitted unless a caller proves otherwise.
    """
    w: list[str] = []
    if not has_beatgrid:
        w.append("no beatgrid — phrase alignment unavailable, confidence reduced")
    if not has_context:
        w.append("no context profile — role/fit is context-free")
    if not dj_validated:
        w.append("not DJ-validated — output is a candidate estimate, not ground truth")
    if source_grounding < 0.5:
        w.append(f"low source grounding ({source_grounding:.2f}) — treat as hypothesis")
    if conflicting:
        w.append("conflicting descriptors — interpretation is unstable")
    if risk_score is not None and risk_score >= high_risk_threshold:
        w.append(f"high risk score ({risk_score:.2f}) — review before use")
    if annotator_agreement is not None and annotator_agreement < low_agreement_threshold:
        w.append(f"low annotator agreement ({annotator_agreement:.2f})")
    return w


def stem_cannot_claim_note() -> str:
    return (
        "Stem-aware outputs are candidate estimates derived from source separation and "
        "require DJ annotation pilots before any strong recommendation claim."
    )


def stem_score(
    *,
    score: float | None,
    source_status: SourceStatus,
    provenance_pointer: str | None,
    warnings: list[str] | None = None,
    reasoning: list[str] | None = None,
    warning_level: WarningLevel = WarningLevel.info,
    validation_status: ValidationStatus = ValidationStatus.to_validate,
) -> StemAwareScore:
    """Standard guardrailed container for Sprint 4 stem-aware outputs."""
    return StemAwareScore(
        score=score,
        warning_level=warning_level,
        source_status=source_status,
        validation_status=validation_status,
        cannot_claim=stem_cannot_claim_note(),
        provenance_pointer=provenance_pointer,
        warnings=warnings or [],
        reasoning=reasoning or [],
    )
