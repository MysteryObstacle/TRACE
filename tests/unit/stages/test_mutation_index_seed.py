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
