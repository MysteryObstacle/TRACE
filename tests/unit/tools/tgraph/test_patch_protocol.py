from __future__ import annotations

from trace.tools.tgraph.patch import apply_artifact_patch, infer_artifact_stage


def _logical_artifact(graph: dict | None = None, **extra):
    return {
        "tgraph_logical": graph or {"profile": "logical.v1", "nodes": [], "links": []},
        "logical_checkpoints": extra.pop("logical_checkpoints", []),
        "logical_validator_script": extra.pop("logical_validator_script", None),
        **extra,
    }


def test_infer_artifact_stage_logical():
    assert infer_artifact_stage({"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}}) == "logical"


def test_infer_artifact_stage_ambiguous_fails():
    result = apply_artifact_patch(
        {
            "tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []},
            "tgraph_physical": {"profile": "taal.default.v1", "nodes": [], "links": []},
        },
        {"graph_patch": []},
    )

    assert result["ok"] is False
    assert result["committed"] is False
    assert result["error"]["code"] == "artifact_shape_error"


def test_empty_patch_validates_and_does_not_include_artifact_by_default():
    result = apply_artifact_patch(
        _logical_artifact(),
        {"graph_patch": [], "options": {"stage": "logical", "validate": ["f1", "f2", "f3"]}},
    )

    assert result["ok"] is True
    assert result["committed"] is True
    assert result["artifact"] is None
    assert result["validation"]["ok"] is True


def test_ensure_node_creates_and_merges_existing_node():
    artifact = _logical_artifact(
        {
            "profile": "logical.v1",
            "nodes": [{"id": "R1", "type": "router", "label": "old", "ports": []}],
            "links": [],
        }
    )

    result = apply_artifact_patch(
        artifact,
        {
            "graph_patch": [
                {"op": "ensure_node", "id": "R1", "label": "Core Router"},
                {"op": "ensure_node", "id": "SW1", "type": "switch", "label": "Access Switch"},
            ],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"], "include_artifact": True},
        },
    )

    nodes = {node["id"]: node for node in result["artifact"]["tgraph_logical"]["nodes"]}
    assert result["ok"] is True
    assert nodes["R1"]["type"] == "router"
    assert nodes["R1"]["label"] == "Core Router"
    assert nodes["SW1"]["type"] == "switch"
    assert result["diff"]["nodes_added"] == ["SW1"]
    assert result["diff"]["nodes_updated"] == ["R1"]


def test_ensure_link_creates_missing_ports_and_link():
    artifact = _logical_artifact(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1", "ports": []},
                {"id": "SW1", "type": "switch", "label": "SW1", "ports": []},
            ],
            "links": [],
        }
    )

    result = apply_artifact_patch(
        artifact,
        {
            "graph_patch": [
                    {
                        "op": "ensure_link",
                        "a": {"node": "R1", "port": "R1_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"},
                    "b": {"node": "SW1", "port": "SW1_p1", "cidr": "10.0.0.0/30"},
                }
            ],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"], "include_artifact": True},
        },
    )

    graph = result["artifact"]["tgraph_logical"]
    assert result["ok"] is True
    assert graph["links"] == [
        {"id": "R1_p1--SW1_p1", "from_port": "R1_p1", "to_port": "SW1_p1", "from_node": "R1", "to_node": "SW1"}
    ]
    assert result["diff"]["ports_added"] == ["R1.R1_p1", "SW1.SW1_p1"]
    assert result["diff"]["links_added"] == ["R1_p1--SW1_p1"]


def test_ensure_link_is_idempotent_and_updates_addressing():
    artifact = _logical_artifact(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
                {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "SW1_p1", "ip": "", "cidr": ""}]},
            ],
            "links": [{"id": "R1_p1--SW1_p1", "from_port": "R1_p1", "to_port": "SW1_p1"}],
        }
    )

    result = apply_artifact_patch(
        artifact,
        {
            "graph_patch": [
                {
                    "op": "ensure_link",
                    "a": {"node": "R1", "port": "R1_p1", "ip": "10.0.0.1"},
                    "b": {"node": "SW1", "port": "SW1_p1", "cidr": "10.0.0.0/30"},
                }
            ],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"], "include_artifact": True},
        },
    )

    graph = result["artifact"]["tgraph_logical"]
    node_map = {node["id"]: node for node in graph["nodes"]}
    assert result["ok"] is True
    assert len(graph["links"]) == 1
    assert node_map["R1"]["ports"][0]["ip"] == "10.0.0.1"
    assert node_map["SW1"]["ports"][0]["cidr"] == "10.0.0.0/30"
    assert result["diff"]["ports_updated"] == ["SW1.SW1_p1"]


def test_ensure_link_conflicts_when_port_already_connected():
    artifact = _logical_artifact(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
                {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "SW1_p1", "ip": "", "cidr": ""}]},
                {"id": "SW2", "type": "switch", "label": "SW2", "ports": [{"id": "SW2_p1", "ip": "", "cidr": "10.0.0.0/30"}]},
            ],
            "links": [{"id": "R1_p1--SW1_p1", "from_port": "R1_p1", "to_port": "SW1_p1"}],
        }
    )

    result = apply_artifact_patch(
        artifact,
        {
            "graph_patch": [
                {"op": "ensure_link", "a": {"node": "R1", "port": "R1_p1"}, "b": {"node": "SW2", "port": "SW2_p1"}}
            ],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"]},
        },
    )

    assert result["ok"] is False
    assert result["committed"] is False
    assert result["error"]["code"] == "op_conflict"
    assert result["rejected_ops"][0]["error"]["code"] == "op_conflict"


def test_ensure_link_reconnect_removes_old_incident_link():
    artifact = _logical_artifact(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
                {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "SW1_p1", "ip": "", "cidr": "10.0.0.0/30"}]},
                {"id": "SW2", "type": "switch", "label": "SW2", "ports": [{"id": "SW2_p1", "ip": "", "cidr": "10.0.0.0/30"}]},
            ],
            "links": [{"id": "R1_p1--SW1_p1", "from_port": "R1_p1", "to_port": "SW1_p1"}],
        }
    )

    result = apply_artifact_patch(
        artifact,
        {
            "graph_patch": [
                {
                    "op": "ensure_link",
                    "a": {"node": "R1", "port": "R1_p1"},
                    "b": {"node": "SW2", "port": "SW2_p1"},
                    "reconnect": True,
                }
            ],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"], "include_artifact": True},
        },
    )

    assert result["ok"] is True
    assert result["artifact"]["tgraph_logical"]["links"] == [
        {"id": "R1_p1--SW2_p1", "from_port": "R1_p1", "to_port": "SW2_p1", "from_node": "R1", "to_node": "SW2"}
    ]
    assert result["diff"]["links_removed"] == ["R1_p1--SW1_p1"]
    assert result["diff"]["links_added"] == ["R1_p1--SW2_p1"]


def test_remove_link_keeps_ports():
    artifact = _logical_artifact(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
                {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "SW1_p1", "ip": "", "cidr": "10.0.0.0/30"}]},
            ],
            "links": [{"id": "R1_p1--SW1_p1", "from_port": "R1_p1", "to_port": "SW1_p1"}],
        }
    )

    result = apply_artifact_patch(
        artifact,
        {
            "graph_patch": [{"op": "remove_link", "id": "R1_p1--SW1_p1"}],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"], "include_artifact": True},
        },
    )

    assert result["ok"] is True
    assert result["artifact"]["tgraph_logical"]["links"] == []
    assert result["artifact"]["tgraph_logical"]["nodes"][0]["ports"] == [{"id": "R1_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]


def test_remove_node_cascade_removes_incident_links():
    artifact = _logical_artifact(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
                {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "SW1_p1", "ip": "", "cidr": "10.0.0.0/30"}]},
            ],
            "links": [{"id": "R1_p1--SW1_p1", "from_port": "R1_p1", "to_port": "SW1_p1"}],
        }
    )

    result = apply_artifact_patch(
        artifact,
        {
            "graph_patch": [{"op": "remove_node", "id": "R1", "cascade": True}],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"], "include_artifact": True},
        },
    )

    assert result["ok"] is True
    assert [node["id"] for node in result["artifact"]["tgraph_logical"]["nodes"]] == ["SW1"]
    assert result["artifact"]["tgraph_logical"]["links"] == []


def test_ensure_checkpoint_creates_and_merges_existing_checkpoint():
    artifact = _logical_artifact(
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "connect_nodes",
                "description": "old",
                "constraint_ids": ["lc1"],
                "args": {"node_a": "A", "node_b": "B"},
            }
        ]
    )

    result = apply_artifact_patch(
        artifact,
        {
            "checkpoint_patch": [
                {"op": "ensure_checkpoint", "id": "cp1", "func": "connect_nodes", "description": "new"},
                {
                    "op": "ensure_checkpoint",
                    "id": "cp2",
                    "func": "connect_nodes",
                    "description": "second",
                    "constraint_ids": ["lc2"],
                    "args": {"node_a": "B", "node_b": "C"},
                },
            ],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"], "include_artifact": True},
        },
    )

    checkpoints = {item["id"]: item for item in result["artifact"]["logical_checkpoints"]}
    assert result["ok"] is True
    assert checkpoints["cp1"]["description"] == "new"
    assert checkpoints["cp1"]["args"] == {"node_a": "A", "node_b": "B"}
    assert checkpoints["cp2"]["func"] == "connect_nodes"
    assert result["diff"]["checkpoints_added"] == ["cp2"]
    assert result["diff"]["checkpoints_updated"] == ["cp1"]


def test_ensure_checkpoint_requires_id_and_func_for_new_checkpoint():
    result = apply_artifact_patch(
        _logical_artifact(),
        {
            "checkpoint_patch": [{"op": "ensure_checkpoint", "id": "cp1"}],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"]},
        },
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "patch_schema_error"


def test_remove_checkpoint_removes_by_id():
    artifact = _logical_artifact(
        logical_checkpoints=[
            {"id": "cp1", "func": "connect_nodes", "description": "old", "constraint_ids": [], "args": {}}
        ]
    )

    result = apply_artifact_patch(
        artifact,
        {
            "checkpoint_patch": [{"op": "remove_checkpoint", "id": "cp1"}],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"], "include_artifact": True},
        },
    )

    assert result["ok"] is True
    assert result["artifact"]["logical_checkpoints"] == []
    assert result["diff"]["checkpoints_removed"] == ["cp1"]


def test_replace_script_updates_validator_script():
    result = apply_artifact_patch(
        _logical_artifact(),
        {
            "validator_patch": {"op": "replace_script", "script": "def check_x(tgraph, **kwargs):\n    return []\n"},
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"], "include_artifact": True},
        },
    )

    assert result["ok"] is True
    assert result["artifact"]["logical_validator_script"].startswith("def check_x")
    assert result["diff"]["validator_script_replaced"] is True


def test_validation_failure_returns_diff_but_committed_false():
    result = apply_artifact_patch(
        _logical_artifact(
            logical_checkpoints=[
                {
                    "id": "cp1",
                    "func": "connect_nodes",
                    "description": "A must connect B",
                    "constraint_ids": ["lc1"],
                    "args": {"node_a": "A", "node_b": "B"},
                }
            ]
        ),
        {
            "graph_patch": [{"op": "ensure_node", "id": "A", "type": "router", "label": "A"}],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3", "f4"]},
        },
    )

    assert result["ok"] is False
    assert result["committed"] is False
    assert result["accepted_ops"] == [{"section": "graph_patch", "index": 0, "op": "ensure_node"}]
    assert result["diff"]["nodes_added"] == ["A"]
    assert result["error"]["code"] == "validation_failed"
