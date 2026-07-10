from fastapi.testclient import TestClient

from dancelab.api.main import app
from dancelab.contracts.node_host import get_node_host_registry
from dancelab.host.runtime import DesktopHostRuntime, RuntimeNodeState


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
        "extract_stems",
        "stem_export",
    ):
        assert node_id in by_id
        assert by_id[node_id].status == "implemented"

    assert by_id["telemetry_screen"].category == "screens"
    assert by_id["listen_screen"].status == "adapter_needed"
    assert "telemetry_manifest" in port_types
    assert "stem_window_feature_set" in port_types


def test_node_host_registry_declares_desktop_execution_truth():
    registry = get_node_host_registry()
    by_id = {node.node_id: node for node in registry.nodes}
    runnable_ids = {
        node.node_id for node in registry.nodes if node.host_execution_status == "runnable"
    }

    assert runnable_ids == DesktopHostRuntime.SUPPORTED_NODE_IDS
    assert by_id["telemetry_screen"].host_execution_status == "runnable"
    assert by_id["extract_stems"].host_execution_status == "runnable"
    assert by_id["stem_export"].host_execution_status == "runnable"
    assert by_id["transition_windows"].host_execution_status == "engine_only"
    assert by_id["mixability"].host_execution_status == "engine_only"
    assert by_id["recommend_sequence"].host_execution_status == "engine_only"
    assert by_id["bpm_sensor"].host_execution_status == "adapter_needed"
    assert by_id["listen_screen"].host_execution_status == "adapter_needed"
    assert by_id["filter"].host_execution_status == "planned"


def test_every_supported_node_has_a_real_dispatch_branch():
    # AUD-C1/NEW-M3: SUPPORTED_NODE_IDS must not claim a node the runtime cannot
    # actually execute. Drive each supported node through the runtime on its own;
    # any error is fine (missing upstream deps / config) EXCEPT the
    # "does not execute node" fall-through — that means the dispatch branch is
    # missing and the declared capability is a lie.
    for node_id in sorted(DesktopHostRuntime.SUPPORTED_NODE_IDS):
        runtime = DesktopHostRuntime()
        state = RuntimeNodeState(instance_id=f"probe_{node_id}", node_id=node_id)
        try:
            runtime.run([state], [], state.instance_id)
        except Exception as exc:  # noqa: BLE001 - only the fall-through is a failure
            assert "does not execute node" not in str(exc), (
                f"{node_id} is in SUPPORTED_NODE_IDS but has no run() dispatch branch"
            )


def test_node_host_contract_endpoint():
    client = TestClient(app)
    response = client.get("/contracts/node-host")
    assert response.status_code == 200

    body = response.json()
    assert body["version"] == "node_host_v0.1"
    assert body["dictionary_doc"] == "docs/NODE_DICTIONARY.md"
    engine = next(node for node in body["nodes"] if node["node_id"] == "engine")
    assert engine["host_execution_status"] == "runnable"


def test_node_host_shell_route():
    client = TestClient(app)
    response = client.get("/host/node-shell")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/contracts/node-host" in response.text
    assert "SIGNAL GRAPH" in response.text
