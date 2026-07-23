"""DanceLab Engine API (FastAPI). The first integration gateway (ADR-006).

Run: uvicorn dancelab.api.main:app --reload
Docs: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from dancelab import __version__
from dancelab.api import (
    routes_context,
    routes_pairs,
    routes_sets,
    routes_stems,
    routes_tracks,
)
from dancelab.api.schemas import HealthResponse, NotImplementedResponse
from dancelab.api.security import RequestBodyLimitMiddleware
from dancelab.core.config import load_config, load_weights
from dancelab.core.errors import (
    ConfigError,
    IngestionError,
    MissingDependencyError,
    NotImplementedFeature,
)
from dancelab.storage.repositories import InvalidTrackIdError, TrackNotFoundError

app = FastAPI(
    title="DanceLab Engine API",
    version=__version__,
    description="audio → features → descriptors → context conditioning → decision outputs",
)

_allowed_hosts = [
    host.strip()
    for host in os.environ.get(
        "DANCELAB_API_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver"
    ).split(",")
    if host.strip()
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts)
app.add_middleware(RequestBodyLimitMiddleware)

app.include_router(routes_tracks.router)
app.include_router(routes_pairs.router)
app.include_router(routes_context.router)
app.include_router(routes_sets.router)
app.include_router(routes_stems.router)


def get_config():
    return load_config(os.environ.get("DANCELAB_CONFIG", "configs/default.yaml"))


@app.exception_handler(NotImplementedFeature)
async def not_implemented_handler(request: Request, exc: NotImplementedFeature):
    """Specified-but-unimplemented computation → honest 501, never fake numbers."""
    body = NotImplementedResponse(
        feature=exc.feature, formula_status=exc.status, detail=exc.detail
    )
    return JSONResponse(status_code=501, content=body.model_dump())


@app.exception_handler(TrackNotFoundError)
async def track_not_found_handler(request: Request, exc: TrackNotFoundError):
    return JSONResponse(status_code=404, content={"error": "not_found", "detail": str(exc)})


@app.exception_handler(InvalidTrackIdError)
async def invalid_track_id_handler(request: Request, exc: InvalidTrackIdError):
    return JSONResponse(status_code=422, content={"error": "invalid_track_id", "detail": str(exc)})


@app.exception_handler(IngestionError)
async def ingestion_handler(request: Request, exc: IngestionError):
    return JSONResponse(status_code=422, content={"error": "ingestion", "detail": str(exc)})


@app.exception_handler(ConfigError)
async def config_handler(request: Request, exc: ConfigError):
    return JSONResponse(status_code=400, content={"error": "config", "detail": str(exc)})


@app.exception_handler(MissingDependencyError)
async def missing_dep_handler(request: Request, exc: MissingDependencyError):
    return JSONResponse(
        status_code=503, content={"error": "missing_dependency", "detail": str(exc)}
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    config = get_config()
    weights = load_weights(config.weights_file)
    return HealthResponse(
        status="ok", engine_version=__version__, weights_version=weights.version
    )


@app.get("/model-cards")
async def model_cards() -> dict:
    """Engine model cards (Sprint 3 traceability). Every decision output's
    provenance.model_card_id resolves to one of these."""
    from dancelab.core.provenance import load_model_cards

    cards = load_model_cards(get_config().model_cards_file)
    return {key: card.model_dump() for key, card in cards.items()}


@app.get("/formula-terms")
async def formula_terms() -> dict:
    """Per-component formula-term metadata (no anonymous variables — Sprint 3).
    Each weighted term in a decision score resolves to one of these."""
    from dancelab.core.provenance import load_formula_terms

    terms = load_formula_terms(get_config().formula_terms_file)
    return {key: term.model_dump() for key, term in terms.items()}
