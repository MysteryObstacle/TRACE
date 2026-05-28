from trace.stages.repair_tools import StageRepairTools


def _seed():
    return {
        "stage": "logical",
        "nodes": [{"id": "A", "type": "computer", "label": "A", "ports": []}],
        "links": [],
    }


def test_default_mutation_index_seed_is_one(tmp_path):
    tools = StageRepairTools({"graph": _seed(), "constraint_files": {}, "checkpoint_files": {}}, support_file_root=str(tmp_path))
    result = tools.write_mutation_file(content="def mutate(tgraph):\n    pass\n")
    assert result["path"] == "logical/mutations/attempt_1.py"


def test_mutation_index_seed_advances_attempt_number(tmp_path):
    tools = StageRepairTools(
        {"graph": _seed(), "constraint_files": {}, "checkpoint_files": {}},
        support_file_root=str(tmp_path),
        mutation_index_seed=3,
    )
    result = tools.write_mutation_file(content="def mutate(tgraph):\n    pass\n")
    assert result["path"] == "logical/mutations/attempt_3.py"


def test_mutation_index_seed_zero_falls_back_to_one(tmp_path):
    tools = StageRepairTools(
        {"graph": _seed(), "constraint_files": {}, "checkpoint_files": {}},
        support_file_root=str(tmp_path),
        mutation_index_seed=0,
    )
    result = tools.write_mutation_file(content="def mutate(tgraph):\n    pass\n")
    assert result["path"] == "logical/mutations/attempt_1.py"


def test_repair_node_passes_seeded_index(monkeypatch):
    captured = {}

    real_cls = __import__("trace.stages.repair_tools", fromlist=["StageRepairTools"]).StageRepairTools

    class SpyStageRepairTools(real_cls):
        def __init__(self, *args, mutation_index_seed: int = 1, **kwargs):
            captured["mutation_index_seed"] = mutation_index_seed
            super().__init__(*args, mutation_index_seed=mutation_index_seed, **kwargs)

    monkeypatch.setattr("trace.stages.logical.nodes.repair.StageRepairTools", SpyStageRepairTools)

    from trace.stages.logical.nodes.repair import repair_node

    state = {
        "draft_artifact": {
            "graph": {"stage": "logical", "nodes": [{"id": "A", "type": "computer", "label": "A", "ports": []}], "links": []},
            "constraint_files": {},
            "checkpoint_files": {},
        },
        "support_files": {},
        "evaluation_report": {"ok": False, "issues": []},
        "attempt": 0,
        "repair_history": [{}, {}],
        "events": [],
    }

    class FakeClient:
        def invoke_agent(self, **_):
            return {"messages": []}

    repair_node(state, FakeClient())
    assert captured["mutation_index_seed"] == 3
