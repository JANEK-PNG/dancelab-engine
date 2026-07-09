from fastapi.testclient import TestClient

from dancelab.api.main import app
from dancelab.contracts.node_host import get_node_host_registry


def test_node_host_registry_has_pinned_engine_anchor():
    registry = get_node_host_registry()
    by_id = {node.node_id: node for node in registry.nodes}

    engine = by_id["engine"]
    assert engine.category == "system"
    assert engine.default_visible is True
    assert engine.pinned is True
    assert engine.deletable is False


def test_node_host_registry_maps_real_engine_capabilities():
    registry = get_node_host_registry()
    by_id = {node.node_id: node for node in registry.nodes}
    port_types = {port.key for port in registry.port_types}

    for node_id in (
        "load_corpus",
        "analyze_tracks",
        "transition_windows",
        "mixability",
        "edge_decision",
        "recommend_next",
        "recommend_sequence",
        "build_set",
        "decision_report",
        "validation_pack",
    ):
        assert node_id in by_id
        assert by_id[node_id].status == "implemented"

    assert by_id["extract_stems"].status == "adapter_needed"
    assert by_id["telemetry_screen"].category == "screens"
    assert by_id["listen_screen"].status == "adapter_needed"
    assert "telemetry_manifest" in port_types
    assert "stem_window_feature_set" in port_types


def test_node_host_contract_endpoint():
    client = TestClient(app)
    response = client.get("/contracts/node-host")
    assert response.status_code == 200

    body = response.json()
    assert body["version"] == "node_host_v0.1"
    assert body["dictionary_doc"] == "docs/NODE_DICTIONARY.md"
    assert any(node["node_id"] == "engine" for node in body["nodes"])


def test_node_host_shell_route():
    client = TestClient(app)
    response = client.get("/host/node-shell")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/contracts/node-host" in response.text
    assert "SIGNAL GRAPH" in response.text
