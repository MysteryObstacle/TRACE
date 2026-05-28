from trace.stages.repair_tools import _derive_produced_files


def _attempt(tool_name, args, ok=True, result=None):
    entry = {"tool": tool_name, "args": args, "ok": ok}
    if result is not None:
        entry["result"] = result
    return entry


def test_mutation_paired_with_execute_by_exact_path():
    attempts = [
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_1.py", "content": "def mutate(tgraph): pass\n"}),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_1.py"}, ok=True, result={
            "ok": True,
            "operations": [{"op": "set_image", "node": "A"}, {"op": "set_image", "node": "B"}],
            "summary": {
                "op_counts": {"set_image": 2},
                "affected_node_ids": ["A", "B"],
                "snapshot_path": "logical/mutations/snapshots/attempt_1.json",
            },
        }),
    ]
    produced = _derive_produced_files(attempts)
    assert len(produced) == 1
    assert produced[0]["path"] == "logical/mutations/attempt_1.py"
    assert produced[0]["file_kind"] == "mutation"
    assert produced[0]["node_targets"] == ["A", "B"]
    assert produced[0]["op_counts"] == {"set_image": 2}
    assert produced[0]["snapshot_path"] == "logical/mutations/snapshots/attempt_1.json"
    assert "set_image x2 on [A, B]" in produced[0]["summary_one_line"]


def test_pairing_uses_exact_path_match_not_adjacency():
    attempts = [
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_1.py", "content": "x"}),
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_2.py", "content": "y"}),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_2.py"}, ok=True, result={
            "ok": True,
            "operations": [{"op": "ensure_subnet", "node": "SW"}],
            "summary": {"op_counts": {"ensure_subnet": 1}, "affected_node_ids": ["SW"], "snapshot_path": "logical/mutations/snapshots/attempt_2.json"},
        }),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_1.py"}, ok=True, result={
            "ok": True,
            "operations": [{"op": "ensure_node", "node": "A"}],
            "summary": {"op_counts": {"ensure_node": 1}, "affected_node_ids": ["A"], "snapshot_path": "logical/mutations/snapshots/attempt_1.json"},
        }),
    ]
    produced = _derive_produced_files(attempts)
    by_path = {item["path"]: item for item in produced}
    assert by_path["logical/mutations/attempt_1.py"]["node_targets"] == ["A"]
    assert by_path["logical/mutations/attempt_2.py"]["node_targets"] == ["SW"]


def test_mutation_written_but_not_executed_has_empty_op_counts():
    attempts = [
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_1.py", "content": "x"}),
    ]
    produced = _derive_produced_files(attempts)
    assert produced[0]["op_counts"] == {}
    assert produced[0]["node_targets"] == []
    assert produced[0]["snapshot_path"] is None


def test_checkpoint_file_derived_with_function_summary():
    attempts = [
        _attempt(
            "write_checkpoint_file",
            {
                "path": "logical/checkpoints.py",
                "content": "def check_lc1(tgraph):\n    return []\n\ndef check_lc17(tgraph):\n    return []\n",
            },
        ),
    ]
    produced = _derive_produced_files(attempts)
    assert len(produced) == 1
    assert produced[0]["file_kind"] == "checkpoint"
    assert produced[0]["node_targets"] == []
    assert "checkpoint defines: check_lc1, check_lc17" in produced[0]["summary_one_line"]


def test_pairing_picks_latest_successful_execute_for_same_path():
    attempts = [
        _attempt("write_mutation_file", {"path": "logical/mutations/attempt_1.py", "content": "x"}),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_1.py"}, ok=False, result={
            "ok": False,
            "operations": [],
            "summary": {"op_counts": {}, "affected_node_ids": [], "snapshot_path": None},
        }),
        _attempt("execute_mutation_file", {"path": "logical/mutations/attempt_1.py"}, ok=True, result={
            "ok": True,
            "operations": [{"op": "ensure_node", "node": "A"}],
            "summary": {"op_counts": {"ensure_node": 1}, "affected_node_ids": ["A"], "snapshot_path": "logical/mutations/snapshots/attempt_1.json"},
        }),
    ]
    produced = _derive_produced_files(attempts)
    assert produced[0]["node_targets"] == ["A"]
