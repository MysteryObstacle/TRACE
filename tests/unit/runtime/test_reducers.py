from trace.runtime.reducers import merge_run_state


def test_merge_run_state_appends_events_without_shared_memory():
    current = {
        "artifacts": {"ground": {"node_groups": []}},
        "events": [{"type": "run.started"}],
        "attempt_counters": {"ground": 1},
        "stage_reports": {"ground": {"attempts_used": 1}},
    }
    update = {
        "artifacts": {
            "logical": {
                "graph": {"stage": "logical", "nodes": [], "links": []},
                "constraint_files": {"logical": "logical/constraints.json"},
                "checkpoint_files": {"logical": "logical/checkpoints.py"},
            }
        },
        "events": [{"type": "stage.completed", "stage": "logical"}],
        "attempt_counters": {"logical": 2},
        "stage_reports": {"logical": {"attempts_used": 2}},
    }

    merged = merge_run_state(current, update)

    assert merged["artifacts"].keys() == {"ground", "logical"}
    assert "shared_memory" not in merged
    assert merged["events"][-1]["type"] == "stage.completed"
    assert merged["attempt_counters"]["logical"] == 2
    assert merged["stage_reports"]["logical"]["attempts_used"] == 2
    assert "tgraph_logical" not in merged["artifacts"]["logical"]
    assert "checkpoints" not in merged["artifacts"]["logical"]
