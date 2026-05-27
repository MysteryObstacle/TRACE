from unittest.mock import MagicMock

from trace.stages.logical.nodes.repair import repair_node


def test_logical_repair_includes_constraints_from_support_files(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_invoke_agent(*, role_name, messages, tools, max_react_steps):
        del role_name, tools, max_react_steps
        for message in messages:
            if message.get("role") != "human":
                continue
            content = str(message.get("content", ""))
            if content.startswith("[logical_constraints]"):
                captured["logical_constraints"] = content
        return {"messages": []}

    monkeypatch.setattr(
        "trace.stages.logical.nodes.repair.StageRepairTools",
        lambda artifact, **kwargs: MagicMock(
            inspect_graph=lambda **_: {"nodes": 0},
            validate_graph=lambda: {"ok": True, "issues": []},
            artifact_state=lambda: artifact,
            support_files=lambda: kwargs.get("support_files", {}),
            as_agent_tools=lambda: [],
        ),
    )
    monkeypatch.setattr(
        "trace.stages.logical.nodes.repair.load_tgraph_contract_for",
        lambda _: "contract",
    )

    state = {
        "draft_artifact": {
            "graph": {"stage": "logical", "nodes": [], "links": []},
            "constraint_files": {"logical": "ground/logical_constraints.json"},
            "checkpoint_files": {"logical": "logical/checkpoints.py"},
        },
        "ground_artifact": {
            "node_groups": [],
            "constraint_files": {"logical": "ground/logical_constraints.json"},
        },
        "support_files": {
            "ground/logical_constraints.json": (
                '{"lc1": {"kind": "logical.topology.direct", "statement": "WEB adjacent SW_DMZ"}}'
            )
        },
        "support_file_root": None,
        "evaluation_report": {"ok": False, "issues": []},
        "attempt": 1,
        "repair_history": [],
    }

    repair_node(state, MagicMock(invoke_agent=fake_invoke_agent))

    assert "lc1" in str(captured.get("logical_constraints", ""))
