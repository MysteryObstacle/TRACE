from trace.stages.logical.nodes.repair import _build_repair_ledger_entry, _summarize_recent_repair_ledger


def test_ledger_entry_includes_produced_files():
    attempted = [
        {
            "tool": "write_mutation_file",
            "args": {"path": "logical/mutations/attempt_1.py", "content": "def mutate(t): pass\n"},
            "ok": True,
        },
        {
            "tool": "execute_mutation_file",
            "args": {"path": "logical/mutations/attempt_1.py"},
            "ok": True,
            "result": {
                "ok": True,
                "operations": [{"op": "ensure_node", "node": "A"}],
                "summary": {
                    "op_counts": {"ensure_node": 1},
                    "affected_node_ids": ["A"],
                    "snapshot_path": "logical/mutations/snapshots/attempt_1.json",
                },
            },
        },
    ]
    entry = _build_repair_ledger_entry(
        round_index=1,
        issues_before={"issues": [{"details": {"issue_kind": "missing_link"}}]},
        issues_after={"issues": []},
        attempted_actions=attempted,
    )
    assert entry["produced_files"] == [
        {
            "path": "logical/mutations/attempt_1.py",
            "file_kind": "mutation",
            "node_targets": ["A"],
            "op_counts": {"ensure_node": 1},
            "summary_one_line": "ensure_node x1 on [A]",
            "snapshot_path": "logical/mutations/snapshots/attempt_1.json",
        }
    ]


def test_recent_repair_ledger_summary_includes_produced_files():
    prior = [
        {
            "round": 1,
            "issue_kinds_before": ["missing_link"],
            "resolved_issue_kinds": ["missing_link"],
            "remaining_issue_kinds": [],
            "new_issue_kinds": [],
            "attempted_actions": [],
            "failed_actions": [],
            "produced_files": [
                {
                    "path": "logical/mutations/attempt_1.py",
                    "file_kind": "mutation",
                    "node_targets": ["A"],
                    "op_counts": {"ensure_node": 1},
                    "summary_one_line": "ensure_node x1 on [A]",
                    "snapshot_path": "logical/mutations/snapshots/attempt_1.json",
                }
            ],
        }
    ]
    summary = _summarize_recent_repair_ledger(prior)
    assert summary[0]["produced_files"][0]["path"] == "logical/mutations/attempt_1.py"
