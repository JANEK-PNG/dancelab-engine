"""Host-shell routes for external control surfaces."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from dancelab.host import load_node_host_shell_html

router = APIRouter(prefix="/host", tags=["host"])


@router.get("/node-shell", response_class=HTMLResponse, include_in_schema=False)
async def node_shell() -> HTMLResponse:
    """Serve the first registry-backed node host shell."""
    return HTMLResponse(load_node_host_shell_html())
