import pytest

from trace.tools.tgraph.derive import (
    build_logical_skeleton,
    build_physical_graph,
    expand_node_groups,
)
from trace.tools.tgraph.model import normalize_tgraph_json
from trace.tools.tgraph.protocol import BoundTGraphTools
from trace.tools.tgraph.prompting import get_tgraph_tool_doc
from trace.tools.tgraph.runtime import TGraphRuntime
from trace.tools.tgraph.validate import run_default_validators
from trace.tools.tgraph.validate.intent_sdk import IntentTGraphView


def _logical_bound_tools(graph: dict, *, checkpoints=None, validator_script=None):
    return BoundTGraphTools.from_json(
        graph,
        graph_field="tgraph_logical",
        checkpoints_field="logical_checkpoints",
        validator_script_field="logical_validator_script",
        checkpoints=checkpoints,
        validator_script=validator_script,
    )


def test_build_logical_skeleton_and_physical_graph():
    logical = build_logical_skeleton(
        [
            {"id": "PLC1", "type": "computer", "label": "PLC1"},
            {"id": "SW1", "type": "switch", "label": "SW1"},
        ]
    )

    assert logical["profile"] == "logical.v1"
    assert logical["links"] == []
    assert logical["nodes"][0]["ports"] == []

    physical = build_physical_graph(logical)

    assert physical["profile"] == "taal.default.v1"
    assert [node["id"] for node in physical["nodes"]] == ["PLC1", "SW1"]
    assert physical["links"] == logical["links"]


def test_expand_node_groups_expands_ranges_into_nodes():
    expanded = expand_node_groups(
        [
            {"type": "computer", "members": ["PLC[1..2]", "HMI1"]},
            {"type": "switch", "members": ["SW1"]},
        ]
    )

    assert expanded == [
        {"id": "PLC1", "type": "computer", "label": "PLC1"},
        {"id": "PLC2", "type": "computer", "label": "PLC2"},
        {"id": "HMI1", "type": "computer", "label": "HMI1"},
        {"id": "SW1", "type": "switch", "label": "SW1"},
    ]


def test_default_validators_require_physical_metadata_for_computers():
    physical = {
        "profile": "taal.default.v1",
        "nodes": [
            {
                "id": "PLC1",
                "type": "computer",
                "label": "PLC1",
                "ports": [],
                "image": None,
                "flavor": None,
            }
        ],
        "links": [],
    }

    report = run_default_validators(physical)

    assert report.ok is False
    assert {issue.code for issue in report.issues} >= {
        "computer_image_required",
        "computer_flavor_required",
    }


def test_normalize_tgraph_canonicalizes_link_ids_and_infers_node_refs():
    logical = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "p_r1", "ip": "", "cidr": ""}]},
            {"id": "SW1", "type": "switch", "label": "SW1", "ports": [{"id": "p_sw1", "ip": "", "cidr": ""}]},
        ],
        "links": [
            {"id": "custom-link-name", "from_port": "p_r1", "to_port": "p_sw1"},
        ],
    }

    normalized = normalize_tgraph_json(logical).model_dump(mode="json")

    assert normalized["links"][0]["id"] == "p_r1--p_sw1"
    assert normalized["links"][0]["from_node"] == "R1"
    assert normalized["links"][0]["to_node"] == "SW1"


def test_runtime_from_json_normalizes_link_ids_and_infers_node_refs():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p2", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [{"id": "p2--p1", "from_port": "p2", "to_port": "p1"}],
    }

    runtime = TGraphRuntime.from_json(graph)

    assert runtime.to_json()["links"][0]["id"] == "p1--p2"
    assert runtime.to_json()["links"][0]["from_node"] == "r2"
    assert runtime.to_json()["links"][0]["to_node"] == "r1"


def test_transaction_add_link_commits_when_f1_to_f3_pass():
    runtime = TGraphRuntime.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
                {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            ],
            "links": [],
        }
    )

    tx = runtime.begin_transaction()
    tx.add_link("p1", "p2")
    result = tx.commit(levels=["f1", "f2", "f3"])

    assert result["ok"] is True
    assert runtime.to_json()["links"][0]["id"] == "p1--p2"


def test_default_validators_accept_runtime_normalizable_links():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p2", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [{"id": "custom-link-name", "from_port": "p2", "to_port": "p1"}],
    }

    report = run_default_validators(graph)

    assert report.ok is True


def test_bound_tgraph_tools_expose_topology_view_and_validate():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
                {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            ],
            "links": [{"id": "p1--p2", "from_port": "p1", "to_port": "p2"}],
        }
    )

    assert tools.topology_view() == {
        "nodes": ["r1", "r2"],
        "links": ["p1--p2"],
    }
    assert tools.validate()["ok"] is True


def test_bound_tgraph_tools_can_bulk_read_nodes_and_links():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [{"id": "A_p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}], "image": None, "flavor": None},
                {"id": "B", "type": "router", "label": "B", "ports": [{"id": "B_p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}], "image": None, "flavor": None},
            ],
            "links": [{"id": "A_p1--B_p1", "from_port": "A_p1", "to_port": "B_p1"}],
        }
    )

    assert [node["id"] for node in tools.get_nodes(["B", "A"])] == ["B", "A"]
    assert [link["id"] for link in tools.get_links(["A_p1--B_p1"])] == ["A_p1--B_p1"]
    assert [link["id"] for link in tools.get_links(node_id="A")] == ["A_p1--B_p1"]


def test_bound_tgraph_tools_validate_includes_logical_f4_checkpoints():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [], "image": None, "flavor": None},
                {"id": "B", "type": "router", "label": "B", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        },
        checkpoints=[
            {
                "id": "cp1",
                "func": "connect_nodes",
                "description": "A connect B",
                "constraint_ids": ["lc1"],
                "args": {"node_a": "A", "node_b": "B"},
            }
        ],
    )

    report = tools.validate()

    assert report["ok"] is False
    assert {issue["code"] for issue in report["issues"]} >= {"missing_required_link"}


def test_bound_tgraph_tools_can_add_update_and_remove_checkpoint():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [], "image": None, "flavor": None},
                {"id": "B", "type": "router", "label": "B", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        }
    )

    add_result = tools.add_checkpoint(
        {
            "id": "cp1",
            "func": "connect_nodes",
            "description": "A connect B",
            "constraint_ids": ["lc1"],
            "args": {"node_a": "A", "node_b": "B"},
        }
    )
    assert add_result["ok"] is True
    assert tools.get_checkpoint("cp1")["description"] == "A connect B"

    update_result = tools.update_checkpoint(
        "cp1",
        description="patched",
        args={"node_a": "A", "node_b": "B"},
    )
    assert update_result["ok"] is True
    assert tools.get_checkpoint("cp1")["description"] == "patched"

    remove_result = tools.remove_checkpoint("cp1")
    assert remove_result["ok"] is True
    with pytest.raises(KeyError):
        tools.get_checkpoint("cp1")


def test_add_checkpoint_tool_requires_id():
    tools = _logical_bound_tools({"profile": "logical.v1", "nodes": [], "links": []})
    add_checkpoint_tool = next(tool for tool in tools.tools() if tool.name == "add_checkpoint")

    result = add_checkpoint_tool.invoke({"checkpoint": {}})

    assert result["ok"] is False
    assert {issue["code"] for issue in result["issues"]} >= {"checkpoint_id_required"}


def test_update_checkpoint_tool_accepts_args_field():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [], "image": None, "flavor": None},
                {"id": "B", "type": "router", "label": "B", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        }
    )
    tools.add_checkpoint(
        {
            "id": "cp1",
            "func": "connect_nodes",
            "description": "A connect B",
            "constraint_ids": ["lc1"],
            "args": {"node_a": "A", "node_b": "B"},
        }
    )

    update_checkpoint_tool = next(tool for tool in tools.tools() if tool.name == "update_checkpoint")
    result = update_checkpoint_tool.invoke(
        {
            "checkpoint_id": "cp1",
            "description": "patched via tool",
            "args": {"node_a": "B", "node_b": "A"},
        }
    )

    assert result["ok"] is True
    assert tools.get_checkpoint("cp1")["description"] == "patched via tool"
    assert tools.get_checkpoint("cp1")["args"] == {"node_a": "B", "node_b": "A"}


def test_bound_tgraph_tools_can_replace_validator_script_and_validate_against_it():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        },
        checkpoints=[
            {
                "id": "cp1",
                "func": "broken_check",
                "description": "broken custom check",
                "constraint_ids": ["lc1"],
                "args": {},
            }
        ],
        validator_script="def broken_check(tgraph, **kwargs):\n    raise KeyError('boom')\n",
    )

    before = tools.validate()
    assert before["ok"] is False

    replace_result = tools.replace_validator_script("def broken_check(tgraph, **kwargs):\n    return []\n")
    assert replace_result["ok"] is True
    after = tools.validate()
    assert after["ok"] is True


def test_bound_tgraph_tools_expose_strong_tool_surface_without_tx_controls():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "r1", "ports": [], "image": None, "flavor": None},
                {"id": "r2", "type": "router", "label": "r2", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        }
    )

    tool_names = {tool.name for tool in tools.tools()}
    assert {"topology_view", "get_node", "get_link", "validate", "add_node", "update_node", "add_link", "update_link", "remove_link", "remove_node"} <= tool_names
    assert "begin_tx" not in tool_names
    assert "tx_apply" not in tool_names
    assert "tx_commit" not in tool_names
    assert "tx_rollback" not in tool_names


def test_bound_tgraph_tools_descriptions_come_from_shared_contract():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [],
            "links": [],
        }
    )

    by_name = {tool.name: tool for tool in tools.tools()}

    assert get_tgraph_tool_doc("topology_view") in by_name["topology_view"].description
    assert get_tgraph_tool_doc("add_link") in by_name["add_link"].description
    assert get_tgraph_tool_doc("update_node") in by_name["update_node"].description


def test_update_node_tool_description_warns_against_json_string_ports():
    description = get_tgraph_tool_doc("update_node")

    assert "ports must be an actual JSON array of objects" in description
    assert "not a JSON-encoded string" in description


def test_bound_tgraph_tools_can_be_configured_for_physical_artifact_shape():
    tools = BoundTGraphTools.from_json(
        {
            "profile": "taal.default.v1",
            "nodes": [
                {"id": "A", "type": "router", "label": "A", "ports": [], "image": None, "flavor": None},
                {"id": "B", "type": "router", "label": "B", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        },
        graph_field="tgraph_physical",
        checkpoints_field="physical_checkpoints",
        validator_script_field="physical_validator_script",
        checkpoints=[
            {
                "id": "cp1",
                "func": "connect_nodes",
                "description": "A connect B",
                "constraint_ids": ["lc1"],
                "args": {"node_a": "A", "node_b": "B"},
            }
        ],
    )

    report = tools.validate()
    artifact = tools.artifact_state()

    assert report["ok"] is False
    assert {issue["code"] for issue in report["issues"]} >= {"missing_required_link"}
    assert artifact["tgraph_physical"]["profile"] == "taal.default.v1"
    assert artifact["physical_checkpoints"][0]["id"] == "cp1"
    assert artifact["physical_validator_script"] is None
    assert "tgraph_logical" not in artifact
    assert "logical_checkpoints" not in artifact


def test_bound_tgraph_tools_from_json_requires_explicit_field_names():
    with pytest.raises(TypeError):
        BoundTGraphTools.from_json({"profile": "logical.v1", "nodes": [], "links": []})

    with pytest.raises(TypeError):
        BoundTGraphTools.from_json(
            {"profile": "logical.v1", "nodes": [], "links": []},
            graph_field="tgraph_logical",
            logical_checkpoints=[],
            logical_validator_script=None,
        )


def test_bound_tgraph_tools_commit_low_level_repairs():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "r1", "ports": [], "image": None, "flavor": None},
                {"id": "r2", "type": "router", "label": "r2", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        }
    )

    result = tools.add_link(
        from_port="p1",
        to_port="p2",
        from_node="r1",
        to_node="r2",
        from_ip="10.0.0.1",
        from_cidr="10.0.0.0/30",
        to_ip="10.0.0.2",
        to_cidr="10.0.0.0/30",
    )

    assert result["ok"] is True
    assert tools.topology_view()["links"] == ["p1--p2"]


def test_bound_tgraph_tools_add_link_idempotent_and_updates_addressing():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p0", "ip": "", "cidr": ""}], "image": None, "flavor": None},
                {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p1", "ip": "", "cidr": ""}], "image": None, "flavor": None},
            ],
            "links": [{"id": "p0--p1", "from_port": "p0", "to_port": "p1"}],
        }
    )
    result = tools.add_link(
        from_port="p0",
        to_port="p1",
        from_node="r1",
        to_node="r2",
        from_ip="10.0.0.1",
        from_cidr="10.0.0.0/30",
        to_ip="10.0.0.2",
        to_cidr="10.0.0.0/30",
    )
    assert result["ok"] is True
    assert len(tools.to_json()["links"]) == 1
    assert tools.get_node("r1")["ports"][0]["ip"] == "10.0.0.1"

    result = tools.add_link(
        from_port="p0",
        to_port="p1",
        from_node="r1",
        to_node="r2",
        to_cidr="10.0.0.0/24",
    )
    assert result["ok"] is True
    assert tools.get_node("r2")["ports"][0]["cidr"] == "10.0.0.0/24"


def test_transaction_add_node_and_update_node_ports():
    runtime = TGraphRuntime.from_json({"profile": "logical.v1", "nodes": [], "links": []})
    tx = runtime.begin_transaction()
    tx.add_node("r1", "router", "R1")
    tx.add_node("r2", "router", "R2")
    tx.add_link(
        "r1:p1",
        "r2:p1",
        from_node="r1",
        to_node="r2",
        from_ip="10.0.0.1",
        from_cidr="10.0.0.0/30",
        to_ip="10.0.0.2",
        to_cidr="10.0.0.0/30",
    )
    tx.commit()

    tx = runtime.begin_transaction()
    tx.update_node("r1", ports=[{"id": "r1:p1", "ip": "10.0.0.3"}])
    result = tx.commit()

    assert result["ok"] is True
    assert runtime.get_node("r1")["ports"][0]["ip"] == "10.0.0.3"


def test_update_node_rejects_unknown_port_id():
    runtime = TGraphRuntime.from_json(
        {"profile": "logical.v1", "nodes": [{"id": "r1", "type": "router", "label": "R1", "ports": []}], "links": []}
    )
    tx = runtime.begin_transaction()
    with pytest.raises(KeyError):
        tx.update_node("r1", ports=[{"id": "r1:p9", "ip": "10.0.0.9"}])


def test_add_link_can_create_ports_with_node_ids():
    runtime = TGraphRuntime.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "R1", "ports": []},
                {"id": "r2", "type": "router", "label": "R2", "ports": []},
            ],
            "links": [],
        }
    )
    tx = runtime.begin_transaction()
    tx.add_link(
        "r1:p1",
        "r2:p1",
        from_node="r1",
        to_node="r2",
        from_ip="10.0.0.1",
        from_cidr="10.0.0.0/30",
        to_ip="10.0.0.2",
        to_cidr="10.0.0.0/30",
    )
    result = tx.commit(levels=["f1", "f2", "f3"])
    assert result["ok"] is True


def test_remove_link_does_not_delete_ports():
    runtime = TGraphRuntime.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "R1", "ports": [{"id": "r1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
                {"id": "r2", "type": "router", "label": "R2", "ports": [{"id": "r2:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
            ],
            "links": [{"id": "r1:p1--r2:p1", "from_port": "r1:p1", "to_port": "r2:p1"}],
        }
    )
    tx = runtime.begin_transaction()
    tx.remove_link("r1:p1--r2:p1")
    result = tx.commit(levels=["f1", "f2", "f3"])
    assert result["ok"] is True
    assert runtime.to_json()["links"] == []
    assert len(runtime.to_json()["nodes"][0]["ports"]) == 1


def test_transaction_update_link_rewires_existing_link_and_normalizes_id():
    runtime = TGraphRuntime.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {
                    "id": "r1",
                    "type": "router",
                    "label": "R1",
                    "ports": [
                        {"id": "r1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"},
                        {"id": "r1:p2", "ip": "", "cidr": ""},
                    ],
                },
                {
                    "id": "r2",
                    "type": "router",
                    "label": "R2",
                    "ports": [
                        {"id": "r2:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"},
                        {"id": "r2:p3", "ip": "", "cidr": ""},
                    ],
                },
            ],
            "links": [{"id": "r1:p1--r2:p1", "from_port": "r1:p1", "to_port": "r2:p1"}],
        }
    )
    tx = runtime.begin_transaction()
    tx.update_link(
        "r1:p1--r2:p1",
        from_port="r1:p2",
        to_port="r2:p3",
        from_node="r1",
        to_node="r2",
        from_ip="10.0.0.5",
        from_cidr="10.0.0.4/30",
        to_ip="10.0.0.6",
        to_cidr="10.0.0.4/30",
    )
    result = tx.commit(levels=["f1", "f2", "f3"])

    assert result["ok"] is True
    assert runtime.to_json()["links"] == [
        {
            "id": "r1:p2--r2:p3",
            "from_port": "r1:p2",
            "to_port": "r2:p3",
            "from_node": "r1",
            "to_node": "r2",
        }
    ]
    node_map = {node["id"]: node for node in runtime.to_json()["nodes"]}
    assert next(port for port in node_map["r1"]["ports"] if port["id"] == "r1:p2")["ip"] == "10.0.0.5"
    assert next(port for port in node_map["r2"]["ports"] if port["id"] == "r2:p3")["cidr"] == "10.0.0.4/30"


def test_remove_node_cascade_removes_links_and_ports():
    runtime = TGraphRuntime.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "R1", "ports": [{"id": "r1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
                {"id": "r2", "type": "router", "label": "R2", "ports": [{"id": "r2:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
            ],
            "links": [{"id": "r1:p1--r2:p1", "from_port": "r1:p1", "to_port": "r2:p1"}],
        }
    )
    tx = runtime.begin_transaction()
    tx.remove_node("r1", cascade=True)
    result = tx.commit(levels=["f1", "f2", "f3"])
    assert result["ok"] is True
    assert [n["id"] for n in runtime.to_json()["nodes"]] == ["r2"]
    assert runtime.to_json()["links"] == []


def test_bound_tgraph_tools_supports_add_node_and_remove_node():
    tools = _logical_bound_tools({"profile": "logical.v1", "nodes": [], "links": []})
    result = tools.add_node("r1", "router", "R1")
    assert result["ok"] is True
    assert tools.topology_view()["nodes"] == ["r1"]


def test_update_node_tool_coerces_json_string_image_flavor_and_ports():
    tools = _logical_bound_tools(
        {
            "profile": "taal.default.v1",
            "nodes": [
                {
                    "id": "FIREWALL",
                    "type": "computer",
                    "label": "FIREWALL",
                    "ports": [{"id": "FIREWALL_p1", "ip": "", "cidr": ""}],
                    "image": None,
                    "flavor": None,
                }
            ],
            "links": [],
        }
    )
    update_node_tool = next(tool for tool in tools.tools() if tool.name == "update_node")

    result = update_node_tool.invoke(
        {
            "node_id": "FIREWALL",
            "image": "{\"id\": \"img_pfsense\", \"name\": \"pfsense\"}",
            "flavor": "{\"vcpu\": 2, \"ram\": 2048, \"disk\": 10}",
            "ports": "[{\"id\": \"FIREWALL_p1\", \"ip\": \"10.0.0.2\", \"cidr\": \"10.0.0.0/30\"}]",
        }
    )

    node = tools.get_node("FIREWALL")
    assert result["ok"] is True
    assert node["image"] == {"id": "img_pfsense", "name": "pfsense"}
    assert node["flavor"] == {"vcpu": 2, "ram": 2048, "disk": 10}
    assert node["ports"][0]["ip"] == "10.0.0.2"


def test_runtime_update_node_returns_error_report_on_invalid_port():
    runtime = TGraphRuntime.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "R1", "ports": [{"id": "r1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
            ],
            "links": [],
        }
    )
    result = runtime.update_node("r1", ports=[{"id": "r1:p9", "ip": "10.0.0.9"}])
    assert result["ok"] is False
    assert result["issues"][0]["code"] == "runtime_error"


def test_bound_tools_allow_incremental_repair_across_multiple_mutations():
    tools = _logical_bound_tools(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [{"id": "PLC1_p0", "ip": "", "cidr": ""}], "image": None, "flavor": None},
                {
                    "id": "SW1",
                    "type": "switch",
                    "label": "SW1",
                    "ports": [
                        {"id": "SW1_p0", "ip": "", "cidr": ""},
                        {"id": "SW1_p1", "ip": "", "cidr": ""},
                    ],
                    "image": None,
                    "flavor": None,
                },
                {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1_p0", "ip": "", "cidr": ""}], "image": None, "flavor": None},
            ],
            "links": [
                {"id": "PLC1_p0--SW1_p0", "from_port": "PLC1_p0", "to_port": "SW1_p0"},
                {"id": "R1_p0--SW1_p1", "from_port": "R1_p0", "to_port": "SW1_p1"},
            ],
        }
    )

    # First partial fix: switch CIDRs.
    first = tools.update_node(
        "SW1",
        ports=[
            {"id": "SW1_p0", "cidr": "192.168.1.0/24"},
            {"id": "SW1_p1", "cidr": "192.168.1.0/24"},
        ],
    )
    assert first["ok"] is True

    # Second partial fix: router IP.
    second = tools.update_node(
        "R1",
        ports=[{"id": "R1_p0", "ip": "192.168.1.1"}],
    )
    assert second["ok"] is True

    report = tools.validate()
    assert report["ok"] is True


def test_f4_intent_runs_builtin_connect_nodes_from_authored_checkpoints():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "A", "type": "router", "label": "A", "ports": [{"id": "A_p0", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
            {"id": "B", "type": "router", "label": "B", "ports": [{"id": "B_p0", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
        ],
        "links": [{"id": "A_p0--B_p0", "from_port": "A_p0", "to_port": "B_p0"}],
    }

    report = run_default_validators(
        graph,
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "connect_nodes",
                "description": "A connect B",
                "constraint_ids": ["lc1"],
                "args": {"node_a": "A", "node_b": "B"},
            }
        ],
        logical_validator_script=None,
    )

    assert report.ok is True


def test_f4_intent_runs_builtin_switch_has_subnet_for_subnet_facts():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "R1",
                "type": "router",
                "label": "R1",
                "ports": [{"id": "R1__to__SW_LAN", "ip": "192.168.10.1", "cidr": "192.168.10.0/24"}],
            },
            {
                "id": "SW_LAN",
                "type": "switch",
                "label": "SW_LAN",
                "ports": [{"id": "SW_LAN__to__R1", "ip": "", "cidr": "192.168.10.0/24"}],
            },
        ],
        "links": [
            {
                "id": "R1__to__SW_LAN--SW_LAN__to__R1",
                "from_port": "R1__to__SW_LAN",
                "to_port": "SW_LAN__to__R1",
            }
        ],
    }

    report = run_default_validators(
        graph,
        logical_checkpoints=[
            {
                "id": "cp_subnet_lan",
                "func": "switch_has_subnet",
                "description": "SW_LAN represents subnet 192.168.10.0/24",
                "constraint_ids": ["lc1"],
                "args": {"switch_id": "SW_LAN", "expected_cidr": "192.168.10.0/24"},
            }
        ],
        logical_validator_script=None,
    )

    assert report.ok is True


def test_f4_intent_runs_builtin_node_interface_on_segment_for_interface_facts():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "R1",
                "type": "router",
                "label": "R1",
                "ports": [{"id": "R1__to__SW_LAN", "ip": "192.168.10.1", "cidr": "192.168.10.0/24"}],
            },
            {
                "id": "SW_LAN",
                "type": "switch",
                "label": "SW_LAN",
                "ports": [{"id": "SW_LAN__to__R1", "ip": "", "cidr": "192.168.10.0/24"}],
            },
        ],
        "links": [
            {
                "id": "R1__to__SW_LAN--SW_LAN__to__R1",
                "from_port": "R1__to__SW_LAN",
                "to_port": "SW_LAN__to__R1",
            }
        ],
    }

    report = run_default_validators(
        graph,
        logical_checkpoints=[
            {
                "id": "cp_r1_lan_ip",
                "func": "node_interface_on_segment",
                "description": "R1 uses 192.168.10.1/24 on SW_LAN",
                "constraint_ids": ["lc2"],
                "args": {
                    "node_id": "R1",
                    "segment_id": "SW_LAN",
                    "expected_ip": "192.168.10.1",
                    "expected_cidr": "192.168.10.0/24",
                },
            }
        ],
        logical_validator_script=None,
    )

    assert report.ok is True


def test_f4_intent_reports_interface_mismatch_for_wrong_ip_or_cidr():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "R1",
                "type": "router",
                "label": "R1",
                "ports": [{"id": "R1__to__SW_LAN", "ip": "192.168.10.254", "cidr": "192.168.10.0/24"}],
            },
            {
                "id": "SW_LAN",
                "type": "switch",
                "label": "SW_LAN",
                "ports": [{"id": "SW_LAN__to__R1", "ip": "", "cidr": "192.168.10.0/24"}],
            },
        ],
        "links": [
            {
                "id": "R1__to__SW_LAN--SW_LAN__to__R1",
                "from_port": "R1__to__SW_LAN",
                "to_port": "SW_LAN__to__R1",
            }
        ],
    }

    report = run_default_validators(
        graph,
        logical_checkpoints=[
            {
                "id": "cp_r1_lan_ip",
                "func": "node_interface_on_segment",
                "description": "R1 uses 192.168.10.1/24 on SW_LAN",
                "constraint_ids": ["lc2"],
                "args": {
                    "node_id": "R1",
                    "segment_id": "SW_LAN",
                    "expected_ip": "192.168.10.1",
                    "expected_cidr": "192.168.10.0/24",
                },
            }
        ],
        logical_validator_script=None,
    )

    assert report.ok is False
    assert {item.code for item in report.issues} >= {"interface_ip_or_cidr_mismatch"}


def test_f4_intent_rejects_removed_address_helper_builtins():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "HOST1", "type": "computer", "label": "HOST1", "ports": [{"id": "HOST1_p0", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
        ],
        "links": [],
    }

    report = run_default_validators(
        graph,
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "node_port_has_cidr",
                "description": "legacy address helper should not exist",
                "constraint_ids": ["lc1"],
                "args": {"node_id": "HOST1", "required_cidr": "10.0.0.0/30", "mode": "any"},
            }
        ],
        logical_validator_script=None,
    )

    assert report.ok is False
    assert {item.code for item in report.issues} >= {"checkpoint_function_missing"}


def test_f4_intent_runs_custom_python_validator_script():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "A", "type": "router", "label": "A", "ports": [{"id": "A_p0", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
            {"id": "B", "type": "router", "label": "B", "ports": [{"id": "B_p0", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
        ],
        "links": [{"id": "A_p0--B_p0", "from_port": "A_p0", "to_port": "B_p0"}],
    }
    script = (
        "def check_no_direct_link(tgraph, **kwargs):\n"
        "    src = kwargs['source_id']\n"
        "    dst = kwargs['target_id']\n"
        "    if dst in tgraph.neighbors(src):\n"
        "        return [{'code':'custom_blocked_link','message':'direct link is forbidden','severity':'error','targets':[src,dst],'json_paths':[]}]\n"
        "    return []\n"
    )

    report = run_default_validators(
        graph,
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "check_no_direct_link",
                "description": "custom check",
                "constraint_ids": ["lc1"],
                "args": {"source_id": "A", "target_id": "B"},
            }
        ],
        logical_validator_script=script,
    )

    assert report.ok is False
    assert {item.code for item in report.issues} >= {"custom_blocked_link"}


def test_f4_intent_custom_script_can_validate_addressing_with_get_node():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "HOST1", "type": "computer", "label": "HOST1", "ports": [{"id": "HOST1_p0", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
        ],
        "links": [],
    }
    script = (
        "def check_host_ip_and_cidr(tgraph, **kwargs):\n"
        "    node = tgraph.get_node(kwargs['node_id'])\n"
        "    required_cidr = ipaddress.ip_network(kwargs['required_cidr'], strict=False)\n"
        "    if node is None:\n"
        "        return [issue('node_missing', 'node not found', targets=[kwargs['node_id']])]\n"
        "    problems = []\n"
        "    for port in node.get('ports', []):\n"
        "        cidr = str(port.get('cidr') or '').strip()\n"
        "        ip_value = str(port.get('ip') or '').strip()\n"
        "        if cidr != kwargs['required_cidr']:\n"
        "            problems.append(str(port.get('id') or 'unknown'))\n"
        "            continue\n"
        "        if ip_value and ipaddress.ip_address(ip_value) not in required_cidr:\n"
        "            problems.append(str(port.get('id') or 'unknown'))\n"
        "    if problems:\n"
        "        return [issue('address_mismatch', f\"ports failed address check: {problems}\", targets=problems)]\n"
        "    return []\n"
    )

    report = run_default_validators(
        graph,
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "check_host_ip_and_cidr",
                "description": "address check via custom script",
                "constraint_ids": ["lc1"],
                "args": {"node_id": "HOST1", "required_cidr": "10.0.0.0/30"},
            }
        ],
        logical_validator_script=script,
    )

    assert report.ok is True


def test_f4_intent_custom_script_can_bulk_read_nodes_with_get_nodes():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "A", "type": "router", "label": "A", "ports": [{"id": "A_p0", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
            {"id": "B", "type": "router", "label": "B", "ports": [{"id": "B_p0", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
        ],
        "links": [{"id": "A_p0--B_p0", "from_port": "A_p0", "to_port": "B_p0"}],
    }
    script = (
        "def check_nodes_present(tgraph, **kwargs):\n"
        "    nodes = tgraph.get_nodes(kwargs['node_ids'])\n"
        "    if [node['id'] for node in nodes] == kwargs['node_ids']:\n"
        "        return []\n"
        "    return [issue('nodes_missing', 'node order mismatch', targets=kwargs['node_ids'])]\n"
    )

    report = run_default_validators(
        graph,
        logical_checkpoints=[
            {
                "id": "cp1",
                "func": "check_nodes_present",
                "description": "bulk node lookup via custom script",
                "constraint_ids": ["lc1"],
                "args": {"node_ids": ["B", "A"]},
            }
        ],
        logical_validator_script=script,
    )

    assert report.ok is True


def test_intent_tgraph_view_exposes_only_canonical_link_fields_and_relative_peer_fields():
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "A", "type": "router", "label": "A", "ports": [{"id": "A_p0", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}]},
            {"id": "B", "type": "router", "label": "B", "ports": [{"id": "B_p0", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}]},
        ],
        "links": [{"id": "A_p0--B_p0", "from_port": "A_p0", "to_port": "B_p0"}],
    }

    view = IntentTGraphView.from_json(graph)

    direct = view.get_link("A_p0--B_p0")
    assert direct is not None
    assert direct["id"] == "A_p0--B_p0"
    assert direct["from_port"] == "A_p0"
    assert direct["to_port"] == "B_p0"
    assert direct["from_node"] == "A"
    assert direct["to_node"] == "B"
    assert "source" not in direct
    assert "target" not in direct
    assert "ends" not in direct
    assert "ports" not in direct

    relative = view.list_links(node_id="A")
    assert len(relative) == 1
    assert relative[0]["id"] == "A_p0--B_p0"
    assert relative[0]["peer_node"] == "B"
    assert relative[0]["peer_port"] == "B_p0"
    assert relative[0]["from_node"] == "A"
    assert relative[0]["to_node"] == "B"
    assert "source" not in relative[0]
    assert "target" not in relative[0]
    assert "ends" not in relative[0]
    assert "ports" not in relative[0]

    port_relative = view.list_links(port_id="A_p0")
    assert len(port_relative) == 1
    assert port_relative[0]["peer_node"] == "B"
    assert port_relative[0]["peer_port"] == "B_p0"
    assert "source" not in port_relative[0]
    assert "target" not in port_relative[0]
