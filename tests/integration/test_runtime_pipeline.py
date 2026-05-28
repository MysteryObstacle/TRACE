import json

import pytest

from trace.config.settings import load_settings
from trace.runtime.engine import TraceRuntime
from trace.stages.ground.schemas import LOGICAL_CONSTRAINTS_PATH, PHYSICAL_CONSTRAINTS_PATH


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
        self.message_log = []
        self.agent_tool_log = []

    def invoke_structured(self, *, role_name, messages, schema):
        self.calls.append(role_name)
        self.message_log.append({"role_name": role_name, "messages": messages})
        return self.responses[role_name].pop(0)

    def invoke_agent(self, *, role_name, messages, tools, max_react_steps=12):
        self.calls.append(role_name)
        self.message_log.append({"role_name": role_name, "messages": messages})
        response = self.responses[role_name].pop(0)
        bound = {_tool_name(tool): tool for tool in tools}
        actions = list(response.get("actions", []))
        self.agent_tool_log.append(
            {
                "role_name": role_name,
                "tool_names": list(bound),
                "actions": actions,
            }
        )

        transcript = []
        for index, action in enumerate(actions):
            call_id = f"{role_name}-{index}"
            payload = action.get("payload") or {}
            transcript.append({"type": "ai", "tool_calls": [{"id": call_id, "name": action["tool"], "args": payload}]})
            tool_result = _call_tool(bound[action["tool"]], payload)
            transcript.append({"type": "tool", "name": action["tool"], "tool_call_id": call_id, "content": json.dumps(tool_result)})
        transcript.extend(response.get("messages", []))
        return {"messages": transcript}

    def invoke(self, *, role_name, messages, schema=None, tools=None):
        if schema is not None:
            return self.invoke_structured(role_name=role_name, messages=messages, schema=schema)
        return self.invoke_agent(role_name=role_name, messages=messages, tools=tools or [])


def test_trace_runtime_runs_all_stages_and_persists_outputs(tmp_path):
    client = SequenceRoleClient(
        {
            "ground_author": [
                {
                    "node_groups": [
                        {"type": "computer", "members": ["PLC1"]},
                        {"type": "router", "members": ["R1"]},
                    ],
                    "logical_constraints": [
                        {"id": "l1", "kind": "logical.topology.direct", "statement": "PLC1 directly connects to R1."}
                    ],
                    "physical_constraints": [
                        {"id": "p1", "kind": "physical.image.exact", "statement": "PLC1 uses image img_openplc."}
                    ],
                }
            ],
            "ground_evaluator": [
                {"passed": True, "issues": [], "notes": []}
            ],
            "logical_author": [
                {
                    "actions": [
                        {
                            "tool": "write_checkpoint_file",
                            "payload": {
                                "content": (
                                    "def check_l1(tgraph):\n"
                                    "    return tgraph.check_direct_link('PLC1', 'R1')\n"
                                ),
                            },
                        },
                        {"tool": "validate_checkpoint_file", "payload": {}},
                    ],
                    "messages": [{"role": "assistant", "content": "logical author complete"}],
                }
            ],
            "logical_builder": [
                {
                    "actions": [],
                    "messages": [{"role": "assistant", "content": "logical builder complete"}],
                }
            ],
            "logical_repair": [
                {
                    "actions": [
                        {
                            "tool": "write_mutation_file",
                            "payload": {
                                "path": "logical/mutations/attempt_1.py",
                                "content": (
                                    "def mutate(tgraph):\n"
                                    "    tgraph.ensure_direct_link('PLC1', 'R1')\n"
                                    "    tgraph.ensure_interface('PLC1', segment='R1', ip='10.0.0.2', cidr='10.0.0.0/30')\n"
                                ),
                            },
                        },
                        {"tool": "execute_mutation_file", "payload": {"path": "logical/mutations/attempt_1.py", "validate": True}},
                    ],
                    "messages": [{"role": "assistant", "content": "logical repair complete"}],
                }
            ],
            "physical_author": [
                {
                    "actions": [
                        {
                            "tool": "write_checkpoint_file",
                            "payload": {
                                "content": (
                                    "def check_p1(tgraph):\n"
                                    "    return tgraph.check_image_exact('PLC1', 'openplc')\n"
                                ),
                            },
                        },
                        {"tool": "validate_checkpoint_file", "payload": {}},
                    ],
                    "messages": [{"role": "assistant", "content": "physical author complete"}],
                }
            ],
            "physical_builder": [
                {
                    "actions": [],
                    "messages": [{"role": "assistant", "content": "physical builder complete"}],
                }
            ],
            "physical_repair": [
                    {
                        "actions": [
                            {
                                "tool": "write_mutation_file",
                                "payload": {
                                    "path": "physical/mutations/attempt_1.py",
                                    "content": (
                                        "def mutate(tgraph):\n"
                                        "    tgraph.set_image('PLC1', 'img_openplc', name='OpenPLC')\n"
                                        "    tgraph.set_flavor('PLC1', vcpu=1, ram=512, disk=4)\n"
                                    ),
                                },
                            },
                            {"tool": "execute_mutation_file", "payload": {"path": "physical/mutations/attempt_1.py", "validate": True}},
                        ],
                        "messages": [{"role": "assistant", "content": "physical repair complete"}],
                    }
            ],
        }
    )
    runtime = TraceRuntime(
        settings=load_settings(),
        role_client=client,
        output_root=tmp_path / "runs",
    )

    result = runtime.run("Build a tiny industrial control network.", run_id="run-001")

    assert result["status"] == "completed"
    assert result["attempt_counters"]["ground"] == 1
    assert result["attempt_counters"]["logical"] == 2
    assert result["attempt_counters"]["physical"] == 2
    assert "shared_memory" not in result
    assert set(result["artifacts"]["ground"]) == {"node_groups", "constraint_files"}
    assert result["artifacts"]["ground"]["constraint_files"]["logical"] == "ground/logical_constraints.json"
    assert result["artifacts"]["ground"]["constraint_files"]["physical"] == "ground/physical_constraints.json"
    assert set(result["artifacts"]["logical"]) == {"graph", "constraint_files", "checkpoint_files"}
    assert set(result["artifacts"]["physical"]) == {"graph", "constraint_files", "checkpoint_files"}
    assert result["artifacts"]["logical"]["graph"]["stage"] == "logical"
    assert result["artifacts"]["physical"]["graph"]["stage"] == "physical"
    assert result["artifacts"]["physical"]["graph"]["links"] == result["artifacts"]["logical"]["graph"]["links"]
    assert all("[shared_memory]" not in message["content"] for entry in client.message_log for message in entry["messages"])
    assert (tmp_path / "runs" / "run-001" / "ground" / "artifact.json").exists()
    assert (tmp_path / "runs" / "run-001" / "ground" / "state.sqlite").exists()
    assert (tmp_path / "runs" / "run-001" / "ground" / "logical_constraints.json").exists()
    assert (tmp_path / "runs" / "run-001" / "ground" / "physical_constraints.json").exists()
    assert (tmp_path / "runs" / "run-001" / "logical" / "messages.json").exists()
    assert (tmp_path / "runs" / "run-001" / "logical" / "state.sqlite").exists()
    assert (tmp_path / "runs" / "run-001" / "logical" / "checkpoints.py").exists()
    assert not (tmp_path / "runs" / "run-001" / "logical" / "constraints.json").exists()
    assert (tmp_path / "runs" / "run-001" / "physical" / "evaluation.json").exists()
    assert (tmp_path / "runs" / "run-001" / "physical" / "state.sqlite").exists()
    assert (tmp_path / "runs" / "run-001" / "physical" / "checkpoints.py").exists()
    assert not (tmp_path / "runs" / "run-001" / "physical" / "constraints.json").exists()

    repair_calls = [item for item in client.agent_tool_log if item["role_name"] in {"logical_repair", "physical_repair"}]
    assert repair_calls[0]["actions"][0]["tool"] == "write_mutation_file"
    assert repair_calls[0]["actions"][1]["tool"] == "execute_mutation_file"
    assert repair_calls[1]["actions"][0]["tool"] == "write_mutation_file"
    assert repair_calls[1]["actions"][1]["tool"] == "execute_mutation_file"
    assert "apply_graph_patch" not in repair_calls[0]["tool_names"]
    assert "apply_graph_patch" not in repair_calls[1]["tool_names"]


def test_trace_runtime_accepts_semantically_identical_physical_links_even_when_order_differs(tmp_path):
    client = SequenceRoleClient(
        {
            "ground_author": [
                {
                    "node_groups": [
                        {"type": "router", "members": ["R1", "R2", "R3"]},
                    ],
                    "logical_constraints": [
                            {
                                "id": "g1",
                                "kind": "logical.custom",
                                "statement": "R1 directly connects to R2 and R3 directly connects to R2.",
                            }
                    ],
                    "physical_constraints": [],
                }
            ],
            "ground_evaluator": [
                {"passed": True, "issues": [], "notes": []}
            ],
            "logical_author": [
                {
                    "actions": [
                        {
                            "tool": "write_checkpoint_file",
                            "payload": {
                                "content": (
                                    "def check_g1(tgraph):\n"
                                    "    issues = []\n"
                                    "    issues.extend(tgraph.check_direct_link('R1', 'R2'))\n"
                                    "    issues.extend(tgraph.check_direct_link('R3', 'R2'))\n"
                                    "    return issues\n"
                                ),
                            },
                        },
                        {"tool": "validate_checkpoint_file", "payload": {}},
                    ],
                    "messages": [{"role": "assistant", "content": "logical author complete"}],
                }
            ],
            "logical_builder": [
                {
                    "actions": [
                        {
                            "tool": "write_mutation_file",
                            "payload": {
                                "path": "logical/mutations/attempt_1.py",
                                "content": (
                                    "def mutate(tgraph):\n"
                                    "    tgraph.ensure_direct_link('R1', 'R2')\n"
                                    "    tgraph.ensure_direct_link('R3', 'R2')\n"
                                ),
                            },
                        },
                        {"tool": "execute_mutation_file", "payload": {"path": "logical/mutations/attempt_1.py", "validate": True}},
                    ],
                    "messages": [{"role": "assistant", "content": "logical builder complete"}],
                }
            ],
            "physical_author": [
                {
                    "actions": [],
                    "messages": [{"role": "assistant", "content": "physical author complete"}],
                }
            ],
            "physical_builder": [
                {
                    "actions": [],
                    "messages": [{"role": "assistant", "content": "physical builder complete"}],
                }
            ],
        }
    )
    runtime = TraceRuntime(
        settings=load_settings(),
        role_client=client,
        output_root=tmp_path / "runs",
    )

    result = runtime.run("Build a small routed topology.", run_id="run-002")

    assert result["status"] == "completed"
    assert result["attempt_counters"]["logical"] == 1
    assert result["attempt_counters"]["physical"] == 1
    assert sorted(link["id"] for link in result["artifacts"]["physical"]["graph"]["links"]) == sorted(
        link["id"] for link in result["artifacts"]["logical"]["graph"]["links"]
    )
    assert "physical_repair" not in client.calls

def test_trace_runtime_resumes_from_physical_without_replaying_prior_stages(tmp_path):
    client = SequenceRoleClient(
        {
            "physical_author": [
                {
                    "actions": [
                        {
                            "tool": "write_checkpoint_file",
                            "payload": {
                                "content": (
                                    "def check_l1(tgraph):\n"
                                    "    return tgraph.check_direct_link('PLC1', 'R1')\n"
                                ),
                            },
                        },
                        {"tool": "validate_checkpoint_file", "payload": {}},
                    ],
                    "messages": [{"role": "assistant", "content": "physical author complete"}],
                }
            ],
            "physical_builder": [{"actions": [], "messages": [{"role": "assistant", "content": "physical builder complete"}]}],
        }
    )
    runtime = TraceRuntime(
        settings=load_settings(),
        role_client=client,
        output_root=tmp_path / "runs",
    )
    ground_artifact = _ground_artifact()
    logical_artifact = _logical_artifact()
    runtime.storage.initialize_run(
        run_id="run-003",
        run_payload={
            "run_id": "run-003",
            "intent": "Build a tiny industrial control network.",
            "status": "completed",
            "artifacts": {"ground": ground_artifact, "logical": logical_artifact},
            "stage_reports": {},
            "attempt_counters": {},
            "events": [],
            "error": None,
            "config_snapshot": {},
        },
    )
    runtime.storage.write_stage_snapshot(
        run_id="run-003",
        stage_id="ground",
        artifact=ground_artifact,
        evaluation={"passed": True, "issues": []},
        summary={"attempts_used": 1},
        messages=[],
        tool_journal=[],
        history_name="retry_history",
        history_entries=[],
        events=[],
        support_files=_ground_support_files(),
    )
    runtime.storage.write_stage_snapshot(
        run_id="run-003",
        stage_id="logical",
        artifact=logical_artifact,
        evaluation={"ok": True, "issues": []},
        summary={"attempts_used": 1},
        messages=[],
        tool_journal=[],
        history_name="repair_history",
        history_entries=[],
        events=[],
        support_files=_logical_support_files(),
    )

    result = runtime.resume(
        run_id="run-003",
        from_stage="physical",
        new_run_id="run-003-resume-physical",
    )

    assert result["run_id"] == "run-003-resume-physical"
    assert result["status"] == "completed"
    assert result["resume"] == {
        "source_run_id": "run-003",
        "from_stage": "physical",
        "reused_stages": ["ground", "logical"],
    }
    assert result["artifacts"]["ground"] == ground_artifact
    assert result["artifacts"]["logical"] == logical_artifact
    assert result["artifacts"]["physical"]["graph"]["stage"] == "physical"
    assert result["attempt_counters"] == {"physical": 1}
    assert client.calls == ["physical_author", "physical_builder"]
    assert (tmp_path / "runs" / "run-003-resume-physical" / "ground" / "artifact.json").exists()
    assert (tmp_path / "runs" / "run-003-resume-physical" / "logical" / "artifact.json").exists()
    assert (tmp_path / "runs" / "run-003-resume-physical" / "physical" / "artifact.json").exists()


def test_trace_runtime_resume_requires_prior_stage_artifacts(tmp_path):
    runtime = TraceRuntime(
        settings=load_settings(),
        role_client=SequenceRoleClient({}),
        output_root=tmp_path / "runs",
    )
    runtime.storage.initialize_run(
        run_id="run-004",
        run_payload={"run_id": "run-004", "intent": "Build a tiny topology.", "status": "failed"},
    )
    runtime.storage.write_stage_snapshot(
        run_id="run-004",
        stage_id="ground",
        artifact=_ground_artifact(),
        evaluation={"passed": True, "issues": []},
        summary={"attempts_used": 1},
        messages=[],
        tool_journal=[],
        history_name="retry_history",
        history_entries=[],
        events=[],
    )

    with pytest.raises(ValueError, match="logical"):
        runtime.resume(
            run_id="run-004",
            from_stage="physical",
            new_run_id="run-004-resume-physical",
        )


def test_trace_runtime_persists_failed_stage_when_logical_builder_raises(tmp_path):
    class FailingBuilderClient(SequenceRoleClient):
        def invoke_agent(self, *, role_name, messages, tools, max_react_steps=12):
            if role_name == "logical_builder":
                raise RuntimeError("builder model failed")
            return super().invoke_agent(role_name=role_name, messages=messages, tools=tools, max_react_steps=max_react_steps)

    client = FailingBuilderClient(
        {
            "ground_author": [
                {
                    "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                    "logical_constraints": [
                        {"id": "l1", "kind": "logical.custom", "statement": "PLC1 must satisfy a custom logical fact."}
                    ],
                    "physical_constraints": [],
                }
            ],
            "ground_evaluator": [{"passed": True, "issues": [], "notes": []}],
            "logical_author": [
                {
                    "actions": [
                        {
                            "tool": "write_checkpoint_file",
                            "payload": {"content": "def check_l1(tgraph):\n    return []\n"},
                        },
                        {"tool": "validate_checkpoint_file", "payload": {}},
                    ],
                    "messages": [{"role": "assistant", "content": "logical author complete"}],
                }
            ],
        }
    )
    runtime = TraceRuntime(settings=load_settings(), role_client=client, output_root=tmp_path / "runs")

    result = runtime.run("Build a tiny topology.", run_id="run-failed")

    assert result["status"] == "failed"
    assert result["current_stage"] == "logical"
    assert result["error"]["stage_id"] == "logical"
    assert result["error"]["type"] == "RuntimeError"
    assert "builder model failed" in result["error"]["message"]
    assert (tmp_path / "runs" / "run-failed" / "run.json").exists()
    persisted = json.loads((tmp_path / "runs" / "run-failed" / "run.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "failed"
    assert persisted["current_stage"] == "logical"


def test_in_place_resume_uses_nested_logical_checkpoint_without_replaying_author(tmp_path):
    class FailingOnceLogicalBuilderClient(SequenceRoleClient):
        def __init__(self, responses):
            super().__init__(responses)
            self.fail_builder = True

        def invoke_agent(self, *, role_name, messages, tools, max_react_steps=12):
            if role_name == "logical_builder" and self.fail_builder:
                self.fail_builder = False
                self.calls.append(role_name)
                self.message_log.append({"role_name": role_name, "messages": messages})
                raise RuntimeError("logical builder failed once")
            return super().invoke_agent(role_name=role_name, messages=messages, tools=tools, max_react_steps=max_react_steps)

    client = FailingOnceLogicalBuilderClient(
        {
            "ground_author": [
                {
                    "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                    "logical_constraints": [],
                    "physical_constraints": [],
                }
            ],
            "ground_evaluator": [{"passed": True, "issues": [], "notes": []}],
            "logical_author": [{"actions": [], "messages": [{"role": "assistant", "content": "logical author complete"}]}],
            "logical_builder": [{"actions": [], "messages": [{"role": "assistant", "content": "logical builder complete"}]}],
            "physical_author": [{"actions": [], "messages": [{"role": "assistant", "content": "physical author complete"}]}],
            "physical_builder": [{"actions": [], "messages": [{"role": "assistant", "content": "physical builder complete"}]}],
        }
    )
    runtime = TraceRuntime(settings=load_settings(), role_client=client, output_root=tmp_path / "runs")

    failed = runtime.run("Build a one-node topology.", run_id="nested-logical")
    assert failed["status"] == "failed"
    assert failed["current_stage"] == "logical"
    assert (tmp_path / "runs" / "nested-logical" / "logical" / "state.sqlite").exists()

    resumed = runtime.resume("nested-logical", from_stage="logical", in_place=True)

    assert resumed["status"] == "completed"
    assert client.calls.count("ground_author") == 1
    assert client.calls.count("logical_author") == 1
    assert client.calls.count("logical_builder") == 2
    assert client.calls.count("physical_author") == 1


def test_in_place_resume_uses_nested_physical_checkpoint_without_replaying_author(tmp_path):
    class FailingOncePhysicalBuilderClient(SequenceRoleClient):
        def __init__(self, responses):
            super().__init__(responses)
            self.fail_builder = True

        def invoke_agent(self, *, role_name, messages, tools, max_react_steps=12):
            if role_name == "physical_builder" and self.fail_builder:
                self.fail_builder = False
                self.calls.append(role_name)
                self.message_log.append({"role_name": role_name, "messages": messages})
                raise RuntimeError("physical builder failed once")
            return super().invoke_agent(role_name=role_name, messages=messages, tools=tools, max_react_steps=max_react_steps)

    client = FailingOncePhysicalBuilderClient(
        {
            "ground_author": [
                {
                    "node_groups": [{"type": "computer", "members": ["PLC1"]}],
                    "logical_constraints": [],
                    "physical_constraints": [],
                }
            ],
            "ground_evaluator": [{"passed": True, "issues": [], "notes": []}],
            "logical_author": [{"actions": [], "messages": [{"role": "assistant", "content": "logical author complete"}]}],
            "logical_builder": [{"actions": [], "messages": [{"role": "assistant", "content": "logical builder complete"}]}],
            "physical_author": [{"actions": [], "messages": [{"role": "assistant", "content": "physical author complete"}]}],
            "physical_builder": [{"actions": [], "messages": [{"role": "assistant", "content": "physical builder complete"}]}],
        }
    )
    runtime = TraceRuntime(settings=load_settings(), role_client=client, output_root=tmp_path / "runs")

    failed = runtime.run("Build a one-node topology.", run_id="nested-physical")
    assert failed["status"] == "failed"
    assert failed["current_stage"] == "physical"
    assert (tmp_path / "runs" / "nested-physical" / "physical" / "state.sqlite").exists()

    resumed = runtime.resume("nested-physical", from_stage="physical", in_place=True)

    assert resumed["status"] == "completed"
    assert client.calls.count("ground_author") == 1
    assert client.calls.count("logical_author") == 1
    assert client.calls.count("physical_author") == 1
    assert client.calls.count("physical_builder") == 2


def _ground_artifact():
    return {
        "node_groups": [
            {"type": "computer", "members": ["PLC1"]},
            {"type": "router", "members": ["R1"]},
        ],
        "constraint_files": {"logical": LOGICAL_CONSTRAINTS_PATH},
    }


def _ground_support_files() -> dict[str, str]:
    return {
        LOGICAL_CONSTRAINTS_PATH: json.dumps(
            {
                "l1": {
                    "kind": "logical.topology.direct",
                    "statement": "PLC1 directly connects to R1.",
                }
            },
            ensure_ascii=True,
        ),
    }


def _logical_artifact():
    return {
        "graph": {
            "stage": "logical",
            "nodes": [
                {
                    "id": "PLC1",
                    "type": "computer",
                    "label": "PLC1",
                    "ports": [{"id": "_R1-1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}],
                },
                {
                    "id": "R1",
                    "type": "router",
                    "label": "R1",
                    "ports": [{"id": "_PLC1-1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}],
                },
            ],
            "links": [
                {
                    "id": "PLC1-R1-1",
                    "from_port": "_R1-1",
                    "to_port": "_PLC1-1",
                    "from_node": "PLC1",
                    "to_node": "R1",
                }
            ],
        },
        "constraint_files": {"logical": LOGICAL_CONSTRAINTS_PATH},
        "checkpoint_files": {"logical": "logical/checkpoints.py"},
    }


def _logical_support_files() -> dict[str, str]:
    return {
        **_ground_support_files(),
        "logical/checkpoints.py": (
            "def check_l1(tgraph):\n"
            "    return tgraph.check_direct_link('PLC1', 'R1')\n"
        ),
    }


def _physical_graph():
    graph = json.loads(json.dumps(_logical_artifact()["graph"]))
    graph["stage"] = "physical"
    for node in graph["nodes"]:
        node["image"] = {"id": f"img-{node['id'].lower()}", "name": f"{node['id']} Image"}
        node["flavor"] = {"vcpu": 1, "ram": 512, "disk": 4}
    return graph
