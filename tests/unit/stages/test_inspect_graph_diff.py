from trace.stages.repair_tools import StageRepairTools


def _physical(nodes=None, links=None):
    return {
        "stage": "physical",
        "nodes": nodes or [],
        "links": links or [],
    }


def _logical(nodes=None, links=None):
    return {
        "stage": "logical",
        "nodes": nodes or [],
        "links": links or [],
    }


def test_inspect_graph_diff_against_logical_reference():
    logical_ref = _logical([{"id": "FIREWALL", "type": "computer", "label": "FIREWALL", "ports": []}])
    physical_artifact = {
        "graph": _physical(
            [
                {
                    "id": "FIREWALL",
                    "type": "computer",
                    "label": "FIREWALL",
                    "ports": [],
                    "image": {"id": "img_pfsense", "name": "pfsense"},
                    "flavor": {"vcpu": 2, "ram": 2048, "disk": 10},
                }
            ]
        ),
        "constraint_files": {},
        "checkpoint_files": {},
    }
    tools = StageRepairTools(physical_artifact, logical_reference_graph=logical_ref)
    result = tools.inspect_graph(view="diff", against="logical_reference")
    assert result["changed_nodes"] == [{"id": "FIREWALL", "fields_changed": ["flavor", "image"]}]


def test_inspect_graph_diff_against_previous_attempt_uses_snapshot(tmp_path):
    artifact = {"graph": _logical([{"id": "A", "type": "computer", "label": "A", "ports": []}]), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    write = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_node('B', type='switch', label='B')\n",
        path="logical/mutations/attempt_1.py",
    )
    tools.execute_mutation_file(path=write["path"], validate=False)
    write2 = tools.write_mutation_file(
        content="def mutate(tgraph):\n    tgraph.ensure_node('C', type='computer', label='C')\n",
        path="logical/mutations/attempt_2.py",
    )
    tools.execute_mutation_file(path=write2["path"], validate=False)
    result = tools.inspect_graph(view="diff", against="previous_attempt", baseline_attempt_id=1)
    assert "C" in result["added_nodes"]


def test_inspect_graph_diff_previous_attempt_requires_existing_snapshot(tmp_path):
    artifact = {"graph": _logical([{"id": "A", "type": "computer", "label": "A", "ports": []}]), "constraint_files": {}, "checkpoint_files": {}}
    tools = StageRepairTools(artifact, support_file_root=str(tmp_path))
    result = tools.inspect_graph(view="diff", against="previous_attempt")
    assert result.get("ok") is False
    assert "no previous attempt snapshot" in result.get("error", {}).get("message", "").lower()
