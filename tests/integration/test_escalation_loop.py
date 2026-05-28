from trace.config.settings import load_settings
from trace.runtime.engine import TraceRuntime


def _tool_name(tool):
    return getattr(tool, "name", getattr(tool, "__name__", type(tool).__name__))


def _call_tool(tool, payload=None):
    invoke = getattr(tool, "invoke", None)
    if callable(invoke):
        if payload is None:
            return invoke({})
        return invoke(payload)
    if payload is None:
        return tool()
    return tool(**payload)


class SequenceRoleClient:
    def __init__(self, responses):
        self.responses = {key: list(value) for key, value in responses.items()}
        self.calls = []

    def invoke_structured(self, *, role_name, messages, schema):
        del messages, schema
        self.calls.append(role_name)
        return self.responses[role_name].pop(0)

    def invoke_agent(self, *, role_name, messages, tools, max_react_steps=12):
        del messages, max_react_steps
        self.calls.append(role_name)
        response = self.responses[role_name].pop(0)
        bound = {_tool_name(tool): tool for tool in tools}
        transcript = []
        for index, action in enumerate(response.get("actions", [])):
            call_id = f"{role_name}-{index}"
            payload = action.get("payload") or {}
            transcript.append({"type": "ai", "tool_calls": [{"id": call_id, "name": action["tool"], "args": payload}]})
            result = _call_tool(bound[action["tool"]], payload)
            transcript.append({"type": "tool", "name": action["tool"], "tool_call_id": call_id, "content": result})
        transcript.extend(response.get("messages", []))
        return {"messages": transcript}


def test_full_escalation_loop_recovers(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)

    call_count = {"ground": 0, "logical": 0, "physical": 0}

    def fake_ground(**kwargs):
        call_count["ground"] += 1
        return {
            "status": "completed",
            "artifact": {
                "node_groups": [{"type": "router", "members": ["R1"]}],
                "constraint_files": {"logical": "ground/logical_constraints.json"},
            },
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [],
            "tool_journal": [],
            "retry_history": [],
            "events": [{"type": "ground.completed", "round": call_count["ground"]}],
            "support_files": {},
        }

    def fake_logical(**kwargs):
        call_count["logical"] += 1
        if call_count["logical"] == 1:
            return {
                "status": "escalated",
                "escalation_report": {
                    "source_stage": "logical",
                    "attempt_at_escalation": 1,
                    "issues": [{"details": {"issue_kind": "logical.escalation.constraint_conflict"}}],
                    "partial_artifact": {},
                },
                "partial_artifact": {"graph": {"nodes": [], "links": []}},
                "evaluation_summary": {"ok": False, "issues": []},
                "attempts_used": 1,
                "messages": [],
                "tool_journal": [],
                "repair_history": [],
                "events": [],
                "support_files": {},
            }
        return {
            "status": "completed",
            "artifact": {"graph": {"nodes": [{"id": "n1"}], "links": []}},
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [],
            "tool_journal": [],
            "repair_history": [],
            "events": [],
            "support_files": {},
        }

    def fake_physical(**kwargs):
        call_count["physical"] += 1
        return {
            "status": "completed",
            "artifact": {"graph": {"nodes": [], "links": []}, "constraint_files": {}, "checkpoint_files": {}},
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [],
            "tool_journal": [],
            "repair_history": [],
            "events": [],
            "support_files": {},
        }

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", fake_ground)
    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", fake_logical)
    monkeypatch.setattr("trace.runtime.engine.run_physical_stage", fake_physical)

    final = runtime.run(intent="x", run_id="escalation-loop")

    assert call_count["ground"] == 2
    assert call_count["logical"] == 2
    assert call_count["physical"] == 1
    assert final["status"] == "completed"
    assert len(final.get("escalation_history", [])) == 1
    assert final["escalation_history"][0]["stage"] == "logical"


def test_escalation_limit_terminates(tmp_path, monkeypatch):
    runtime = TraceRuntime(output_root=tmp_path)

    def fake_ground(**kwargs):
        return {
            "status": "completed",
            "artifact": {
                "node_groups": [{"type": "router", "members": ["R1"]}],
                "constraint_files": {"logical": "ground/logical_constraints.json"},
            },
            "evaluation_summary": {"ok": True, "issues": []},
            "attempts_used": 1,
            "messages": [],
            "tool_journal": [],
            "retry_history": [],
            "events": [],
            "support_files": {},
        }

    def fake_logical(**kwargs):
        return {
            "status": "escalated",
            "escalation_report": {"source_stage": "logical", "issues": []},
            "partial_artifact": {},
            "evaluation_summary": {"ok": False, "issues": []},
            "attempts_used": 1,
            "messages": [],
            "tool_journal": [],
            "repair_history": [],
            "events": [],
            "support_files": {},
        }

    monkeypatch.setattr("trace.runtime.engine.run_ground_stage", fake_ground)
    monkeypatch.setattr("trace.runtime.engine.run_logical_stage", fake_logical)

    final = runtime.run(intent="x", run_id="escalation-cap")
    assert final["status"] == "failed"
    assert final.get("error", {}).get("type") == "EscalationLimitExceeded"


def test_logical_checkpoint_escalation_reenters_ground_and_recovers(tmp_path):
    client = SequenceRoleClient(
        {
            "ground_author": [
                {
                    "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                    "logical_constraints": [
                        {"id": "lc1", "kind": "logical.custom", "statement": "This constraint conflicts with intent."}
                    ],
                    "physical_constraints": [],
                },
                {
                    "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                    "logical_constraints": [],
                    "physical_constraints": [],
                },
            ],
            "ground_evaluator": [
                {"passed": True, "issues": [], "notes": []},
                {"passed": True, "issues": [], "notes": []},
            ],
            "logical_author": [
                {
                    "actions": [
                        {
                            "tool": "write_checkpoint_file",
                            "payload": {
                                "content": (
                                    "def check_lc1(tgraph):\n"
                                    "    return tgraph.escalate(\n"
                                    "        'logical.escalation.constraint_conflict',\n"
                                    "        'lc1 conflicts with the grounded topology facts',\n"
                                    "    )\n"
                                ),
                            },
                        },
                        {"tool": "validate_checkpoint_file", "payload": {}},
                    ],
                    "messages": [{"role": "assistant", "content": "logical escalation checkpoint authored"}],
                },
                {"actions": [], "messages": [{"role": "assistant", "content": "logical author complete"}]},
            ],
            "logical_builder": [
                {"actions": [], "messages": [{"role": "assistant", "content": "logical builder complete"}]},
                {"actions": [], "messages": [{"role": "assistant", "content": "logical builder complete"}]},
            ],
            "physical_author": [{"actions": [], "messages": [{"role": "assistant", "content": "physical author complete"}]}],
            "physical_builder": [{"actions": [], "messages": [{"role": "assistant", "content": "physical builder complete"}]}],
        }
    )
    runtime = TraceRuntime(settings=load_settings(), role_client=client, output_root=tmp_path / "runs")

    final = runtime.run("Build a one-node topology with a conflicting logical fact.", run_id="logical-real-escalation")

    assert final["status"] == "completed"
    assert len(final.get("escalation_history", [])) == 1
    assert final["escalation_history"][0]["stage"] == "logical"
    assert final["escalation_history"][0]["report"]["issues"][0]["details"]["issue_kind"] == "logical.escalation.constraint_conflict"
    assert client.calls.count("ground_author") == 2
    assert (tmp_path / "runs" / "logical-real-escalation" / "logical-escalation-001" / "artifact.json").exists()


def test_physical_checkpoint_escalation_reenters_ground_and_recovers(tmp_path):
    client = SequenceRoleClient(
        {
            "ground_author": [
                {
                    "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                    "logical_constraints": [],
                    "physical_constraints": [
                        {"id": "pc1", "kind": "physical.custom", "statement": "PLC1 requires an unavailable image."}
                    ],
                },
                {
                    "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                    "logical_constraints": [],
                    "physical_constraints": [],
                },
            ],
            "ground_evaluator": [
                {"passed": True, "issues": [], "notes": []},
                {"passed": True, "issues": [], "notes": []},
            ],
            "logical_author": [
                {"actions": [], "messages": [{"role": "assistant", "content": "logical author complete"}]},
                {"actions": [], "messages": [{"role": "assistant", "content": "logical author complete"}]},
            ],
            "logical_builder": [
                {"actions": [], "messages": [{"role": "assistant", "content": "logical builder complete"}]},
                {"actions": [], "messages": [{"role": "assistant", "content": "logical builder complete"}]},
            ],
            "physical_author": [
                {
                    "actions": [
                        {
                            "tool": "write_checkpoint_file",
                            "payload": {
                                "content": (
                                    "def check_pc1(tgraph):\n"
                                    "    return tgraph.escalate(\n"
                                    "        'physical.escalation.no_satisfying_image',\n"
                                    "        'no catalog image can satisfy pc1',\n"
                                    "    )\n"
                                ),
                            },
                        },
                        {"tool": "validate_checkpoint_file", "payload": {}},
                    ],
                    "messages": [{"role": "assistant", "content": "physical escalation checkpoint authored"}],
                },
                {"actions": [], "messages": [{"role": "assistant", "content": "physical author complete"}]},
            ],
            "physical_builder": [
                {"actions": [], "messages": [{"role": "assistant", "content": "physical builder complete"}]},
                {"actions": [], "messages": [{"role": "assistant", "content": "physical builder complete"}]},
            ],
        }
    )
    runtime = TraceRuntime(settings=load_settings(), role_client=client, output_root=tmp_path / "runs")

    final = runtime.run("Build a one-node topology with an unavailable image.", run_id="physical-real-escalation")

    assert final["status"] == "completed"
    assert len(final.get("escalation_history", [])) == 1
    assert final["escalation_history"][0]["stage"] == "physical"
    assert final["escalation_history"][0]["report"]["issues"][0]["details"]["issue_kind"] == "physical.escalation.no_satisfying_image"
    assert client.calls.count("ground_author") == 2
    assert (tmp_path / "runs" / "physical-real-escalation" / "physical-escalation-001" / "artifact.json").exists()


def test_ground_unsolvable_after_checkpoint_escalation_ends_run(tmp_path):
    client = SequenceRoleClient(
        {
            "ground_author": [
                {
                    "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                    "logical_constraints": [
                        {"id": "lc1", "kind": "logical.custom", "statement": "This constraint conflicts with intent."}
                    ],
                    "physical_constraints": [],
                },
                {
                    "node_groups": [],
                    "logical_constraints": [],
                    "physical_constraints": [],
                    "unsolvable": True,
                    "unsolvable_reason": "intent contains contradictory topology requirements",
                },
            ],
            "ground_evaluator": [{"passed": True, "issues": [], "notes": []}],
            "logical_author": [
                {
                    "actions": [
                        {
                            "tool": "write_checkpoint_file",
                            "payload": {
                                "content": (
                                    "def check_lc1(tgraph):\n"
                                    "    return tgraph.escalate(\n"
                                    "        'logical.escalation.constraint_conflict',\n"
                                    "        'lc1 conflicts with the grounded topology facts',\n"
                                    "    )\n"
                                ),
                            },
                        },
                        {"tool": "validate_checkpoint_file", "payload": {}},
                    ],
                    "messages": [{"role": "assistant", "content": "logical escalation checkpoint authored"}],
                }
            ],
            "logical_builder": [{"actions": [], "messages": [{"role": "assistant", "content": "logical builder complete"}]}],
        }
    )
    runtime = TraceRuntime(settings=load_settings(), role_client=client, output_root=tmp_path / "runs")

    final = runtime.run("Build an impossible topology.", run_id="logical-unsolvable")

    assert final["status"] == "unsolvable"
    assert final["unsolvable_notes"] == ["intent contains contradictory topology requirements"]
    assert len(final.get("escalation_history", [])) == 1
    assert client.calls.count("ground_author") == 2
