from artifacts.summarizer import build_repair_context
from tools.tgraph.ops.patch import patch
from validators.patching import apply_patch_ops


def test_patch_supports_expand_nodes_from_pattern() -> None:
    result = patch(
        {"profile": "logical.v1", "nodes": [], "links": []},
        [{"op": "expand_nodes_from_pattern", "pattern": "PLC[1..2]", "node_type": "computer"}],
    )

    assert result.ok is True
    assert result.graph is not None
    assert [node["id"] for node in result.graph["nodes"]] == ["PLC1", "PLC2"]


def test_patch_supports_batch_update_nodes() -> None:
    graph = {
        "profile": "taal.default.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
            {"id": "PLC2", "type": "computer", "label": "PLC2", "ports": [], "image": None, "flavor": None},
        ],
        "links": [],
    }

    result = patch(
        graph,
        [
            {
                "op": "batch_update_nodes",
                "node_ids": ["PLC1", "PLC2"],
                "changes": {
                    "image": {"id": "ubuntu-22", "name": "Ubuntu 22.04"},
                    "flavor": {"vcpu": 2, "ram": 2048, "disk": 20},
                },
            }
        ],
    )

    assert result.ok is True
    assert result.graph is not None
    assert result.graph["nodes"][0]["image"]["id"] == "ubuntu-22"
    assert result.graph["nodes"][1]["flavor"]["disk"] == 20


def test_patch_supports_update_node() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
        ],
        "links": [],
    }

    result = patch(
        graph,
        [
            {
                "op": "update_node",
                "node_id": "PLC1",
                "changes": {"type": "router", "label": "Core PLC1"},
            }
        ],
    )

    assert result.ok is True
    assert result.graph is not None
    assert result.graph["nodes"][0]["type"] == "router"
    assert result.graph["nodes"][0]["label"] == "Core PLC1"


def test_patch_normalizes_firewall_type_alias_to_computer() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "FW1", "type": "computer", "label": "FW1", "ports": [], "image": None, "flavor": None},
        ],
        "links": [],
    }

    result = patch(
        graph,
        [
            {
                "op": "update_node",
                "node_id": "FW1",
                "changes": {"type": "firewall"},
            }
        ],
    )

    assert result.ok is True
    assert result.graph is not None
    assert result.graph["nodes"][0]["type"] == "computer"


def test_patch_supports_add_port() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
        ],
        "links": [],
    }

    result = patch(
        graph,
        [
            {
                "op": "add_port",
                "node_id": "PLC1",
                "value": {"id": "PLC1:p1", "ip": "", "cidr": ""},
            }
        ],
    )

    assert result.ok is True
    assert result.graph is not None
    assert result.graph["nodes"][0]["ports"][0]["id"] == "PLC1:p1"


def test_patch_add_link_returns_updated_graph() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "R1", "type": "router", "label": "R1", "ports": [{"id": "R1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            {"id": "PC1", "type": "computer", "label": "PC1", "ports": [{"id": "PC1:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
        ],
        "links": [],
    }

    result = patch(
        graph,
        [{"op": "add_link", "value": {"id": "R1:p1--PC1:p1", "from_port": "R1:p1", "to_port": "PC1:p1", "from_node": "R1", "to_node": "PC1"}, "reason": "connect pc"}],
    )

    assert result.ok is True
    assert result.graph is not None
    assert result.graph["links"][0]["id"] == "R1:p1--PC1:p1"
    assert apply_patch_ops(graph, [{"op": "add_link", "value": {"id": "R1:p1--PC1:p1", "from_port": "R1:p1", "to_port": "PC1:p1", "from_node": "R1", "to_node": "PC1"}, "reason": "connect pc"}])["links"][0]["id"] == "R1:p1--PC1:p1"


def test_patch_rejects_missing_endpoint() -> None:
    result = patch(
        {"profile": "logical.v1", "nodes": [], "links": []},
        [{"op": "add_link", "value": {"id": "A:p1--B:p1", "from_port": "A:p1", "to_port": "B:p1"}, "reason": "bad link"}],
    )

    assert result.ok is False
    assert result.issues[0].code == "patch_link_endpoint_not_found"


def test_patch_connect_nodes_creates_missing_ports_and_link() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
            {"id": "SW1", "type": "switch", "label": "SW1", "ports": [], "image": None, "flavor": None},
        ],
        "links": [],
    }

    result = patch(
        graph,
        [
            {
                "op": "connect_nodes",
                "from": {"node_id": "PLC1", "port": {"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}},
                "to": {"node_id": "SW1", "port": {"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}},
            }
        ],
    )

    assert result.ok is True
    assert result.graph is not None
    assert result.graph["nodes"][0]["ports"] == [{"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}]
    assert result.graph["nodes"][1]["ports"] == [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}]
    assert result.graph["links"] == [
        {
            "id": "PLC1:eth0--SW1:ge0/1",
            "from_port": "PLC1:eth0",
            "to_port": "SW1:ge0/1",
            "from_node": "PLC1",
            "to_node": "SW1",
        }
    ]


def test_patch_disconnect_nodes_removes_link_but_keeps_ports() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "PLC1",
                "type": "computer",
                "label": "PLC1",
                "ports": [{"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}],
                "image": None,
                "flavor": None,
            },
            {
                "id": "SW1",
                "type": "switch",
                "label": "SW1",
                "ports": [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}],
                "image": None,
                "flavor": None,
            },
        ],
        "links": [{"id": "PLC1:eth0--SW1:ge0/1", "from_port": "PLC1:eth0", "to_port": "SW1:ge0/1", "from_node": "PLC1", "to_node": "SW1"}],
    }

    result = patch(
        graph,
        [{"op": "disconnect_nodes", "from": {"node_id": "PLC1", "port_id": "PLC1:eth0"}, "to": {"node_id": "SW1", "port_id": "SW1:ge0/1"}}],
    )

    assert result.ok is True
    assert result.graph is not None
    assert result.graph["links"] == []
    assert result.graph["nodes"][0]["ports"] == [{"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}]
    assert result.graph["nodes"][1]["ports"] == [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}]


def test_patch_remove_nodes_cascades_owned_ports_and_links() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "PLC1",
                "type": "computer",
                "label": "PLC1",
                "ports": [{"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}],
                "image": None,
                "flavor": None,
            },
            {
                "id": "SW1",
                "type": "switch",
                "label": "SW1",
                "ports": [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}],
                "image": None,
                "flavor": None,
            },
        ],
        "links": [{"id": "PLC1:eth0--SW1:ge0/1", "from_port": "PLC1:eth0", "to_port": "SW1:ge0/1", "from_node": "PLC1", "to_node": "SW1"}],
    }

    result = patch(graph, [{"op": "remove_nodes", "node_ids": ["PLC1"]}])

    assert result.ok is True
    assert result.graph is not None
    assert [node["id"] for node in result.graph["nodes"]] == ["SW1"]
    assert result.graph["nodes"][0]["ports"] == [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}]
    assert result.graph["links"] == []


def test_patch_update_node_supports_port_upsert_and_remove() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "PLC1",
                "type": "computer",
                "label": "PLC1",
                "ports": [
                    {"id": "PLC1:eth0", "ip": "", "cidr": ""},
                    {"id": "PLC1:eth1", "ip": "", "cidr": ""},
                ],
                "image": None,
                "flavor": None,
            }
        ],
        "links": [],
    }

    result = patch(
        graph,
        [
            {
                "op": "update_node",
                "node_id": "PLC1",
                "changes": {
                    "label": "PLC-1",
                    "ports": [
                        {"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"},
                        {"id": "PLC1:eth2", "ip": "", "cidr": ""},
                    ],
                },
                "remove": {"ports": ["PLC1:eth1"]},
            }
        ],
    )

    assert result.ok is True
    assert result.graph is not None
    assert result.graph["nodes"][0]["label"] == "PLC-1"
    assert result.graph["nodes"][0]["ports"] == [
        {"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"},
        {"id": "PLC1:eth2", "ip": "", "cidr": ""},
    ]


def test_patch_update_node_rejects_removing_connected_port() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "PLC1",
                "type": "computer",
                "label": "PLC1",
                "ports": [{"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}],
                "image": None,
                "flavor": None,
            },
            {
                "id": "SW1",
                "type": "switch",
                "label": "SW1",
                "ports": [{"id": "SW1:ge0/1", "ip": "", "cidr": "10.0.0.0/24"}],
                "image": None,
                "flavor": None,
            },
        ],
        "links": [{"id": "PLC1:eth0--SW1:ge0/1", "from_port": "PLC1:eth0", "to_port": "SW1:ge0/1", "from_node": "PLC1", "to_node": "SW1"}],
    }

    result = patch(
        graph,
        [{"op": "update_node", "node_id": "PLC1", "remove": {"ports": ["PLC1:eth0"]}}],
    )

    assert result.ok is False
    assert result.issues[0].code == "patch_remove_connected_port_forbidden"


def test_patch_batch_update_nodes_accepts_changes_and_remove_for_single_target() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {
                "id": "PLC1",
                "type": "computer",
                "label": "PLC1",
                "ports": [{"id": "PLC1:eth0", "ip": "", "cidr": ""}],
                "image": None,
                "flavor": None,
            }
        ],
        "links": [],
    }

    result = patch(
        graph,
        [
            {
                "op": "batch_update_nodes",
                "node_ids": ["PLC1"],
                "changes": {
                    "image": {"id": "ubuntu-22", "name": "Ubuntu 22.04"},
                    "ports": [
                        {"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"},
                        {"id": "PLC1:eth1", "ip": "", "cidr": ""},
                    ],
                },
                "remove": {"ports": []},
            }
        ],
    )

    assert result.ok is True
    assert result.graph is not None
    assert result.graph["nodes"][0]["image"]["id"] == "ubuntu-22"
    assert result.graph["nodes"][0]["ports"] == [
        {"id": "PLC1:eth0", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"},
        {"id": "PLC1:eth1", "ip": "", "cidr": ""},
    ]


def test_patch_batch_update_nodes_rejects_port_id_owned_by_other_node() -> None:
    graph = {
        "profile": "logical.v1",
        "nodes": [
            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [{"id": "PLC1:eth0", "ip": "", "cidr": ""}], "image": None, "flavor": None},
            {"id": "PLC2", "type": "computer", "label": "PLC2", "ports": [], "image": None, "flavor": None},
        ],
        "links": [],
    }

    result = patch(
        graph,
        [
            {
                "op": "batch_update_nodes",
                "node_ids": ["PLC2"],
                "changes": {"ports": [{"id": "PLC1:eth0", "ip": "10.0.0.3", "cidr": "10.0.0.0/24"}]},
            }
        ],
    )

    assert result.ok is False
    assert result.issues[0].code in {"patch_port_owner_mismatch", "patch_duplicate_port_id"}


def test_build_repair_context_extracts_open_issues() -> None:
    graph = {"profile": "logical.v1", "nodes": [{"id": "PLC1"}], "links": []}
    report = {
        "ok": False,
        "issues": [
            {
                "code": "missing_link",
                "message": "Link missing",
                "severity": "error",
                "scope": "topology",
                "targets": ["PLC1"],
                "json_paths": ["$.links"],
            }
        ],
    }

    context = build_repair_context(graph, report)

    assert context["open_issues"] == ["missing_link: Link missing"]
    assert context["related_nodes"] == ["PLC1"]
    assert context["affected_scopes"] == ["topology"]
    assert context["latest_patch_summary"] == {"op_count": 0, "ops": []}
