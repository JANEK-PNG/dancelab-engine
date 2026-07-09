"""Contract endpoints for external hosts and diagnostics."""

from __future__ import annotations

from fastapi import APIRouter

from dancelab.contracts.node_host import NodeHostRegistry, get_node_host_registry

router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.get("/node-host", response_model=NodeHostRegistry)
async def node_host_contract() -> NodeHostRegistry:
    """Return the node-host registry used by external graph shells."""
    return get_node_host_registry()
