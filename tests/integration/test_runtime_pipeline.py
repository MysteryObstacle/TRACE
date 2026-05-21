from trace.config.settings import load_settings
from trace.runtime.engine import TraceRuntime


class SequenceRoleClient:
    def __init__(self, responses):
        self.responses = {key: list(value) for key, value in responses.items()}
        self.calls = []
        self.message_log = []

    def invoke_structured(self, *, role_name, messages, schema):
        self.calls.append(role_name)
        self.message_log.append({"role_name": role_name, "messages": messages})
        return self.responses[role_name].pop(0)

    def invoke_agent(self, *, role_name, messages, tools, max_tool_calls=12):
        self.calls.append(role_name)
        self.message_log.append({"role_name": role_name, "messages": messages})
        response = self.responses[role_name].pop(0)
        bound = {_tool_name(tool): tool for tool in tools}
        for action in response.get("actions", []):
            _call_tool(bound[action["tool"]], action.get("payload"))
        return {"messages": response.get("messages", [])}

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
                    "logical_constraints": [{"id": "l1", "statement": "PLC1 must connect to R1"}],
                    "physical_constraints": [{"id": "p1", "statement": "PLC1 must have deployable metadata"}],
                }
            ],
            "ground_evaluator": [
                {"passed": True, "issues": [], "optimizer_brief": {}}
            ],
            "logical_author": [
                {
                    "logical_checkpoints": [
                        {"id": "lc1", "func": "connect_nodes", "description": "PLC1 connect R1", "constraint_ids": ["l1"], "args": {"node_a": "PLC1", "node_b": "R1"}}
                    ],
                    "logical_validator_script": None,
                }
            ],
            "logical_builder": [
                {
                    "tgraph_logical": {
                        "profile": "logical.v1",
                        "nodes": [
                            {"id": "PLC1", "type": "computer", "label": "PLC1", "ports": [], "image": None, "flavor": None},
                            {"id": "R1", "type": "router", "label": "R1", "ports": [], "image": None, "flavor": None},
                        ],
                        "links": [
                            {
                                "id": "PLC1:p1--R1:p1",
                                "from_port": "PLC1:p1",
                                "to_port": "R1:p1",
                                "from_node": "PLC1",
                                "to_node": "R1",
                            }
                        ],
                    }
                }
            ],
            "logical_repair": [
                {
                    "actions": [
                        {
                            "tool": "add_link",
                            "payload": {
                                "from_port": "PLC1:p1",
                                "to_port": "R1:p1",
                                "from_node": "PLC1",
                                "to_node": "R1",
                                "from_ip": "10.0.0.2",
                                "from_cidr": "10.0.0.0/30",
                                "to_ip": "10.0.0.1",
                                "to_cidr": "10.0.0.0/30",
                            },
                        },
                    ],
                    "messages": [{"role": "assistant", "content": "logical repair complete"}],
                }
            ],
            "physical_author": [
                {
                    "physical_checkpoints": [
                        {
                            "id": "pc1",
                            "func": "check_node_deployable",
                            "description": "PLC1 has deployable metadata",
                            "constraint_ids": ["p1"],
                            "args": {"node_id": "PLC1"},
                        }
                    ],
                    "physical_validator_script": (
                        "def check_node_deployable(tgraph, **kwargs):\n"
                        "    node = tgraph.get_node(kwargs['node_id'])\n"
                        "    if node and node.get('image') and node.get('flavor'):\n"
                        "        return []\n"
                        "    return [issue('deployable_metadata_missing', 'node requires image and flavor', targets=[kwargs['node_id']])]\n"
                    ),
                }
            ],
            "physical_builder": [
                {
                    "tgraph_physical": {
                        "profile": "taal.default.v1",
                        "nodes": [
                            {
                                "id": "PLC1",
                                "type": "computer",
                                "label": "PLC1",
                                "ports": [{"id": "PLC1:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}],
                                "image": None,
                                "flavor": None,
                            },
                            {
                                "id": "R1",
                                "type": "router",
                                "label": "R1",
                                "ports": [{"id": "R1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}],
                                "image": None,
                                "flavor": None,
                            },
                        ],
                        "links": [
                            {
                                "id": "PLC1:p1--R1:p1",
                                "from_port": "PLC1:p1",
                                "to_port": "R1:p1",
                                "from_node": "PLC1",
                                "to_node": "R1",
                            }
                        ],
                    }
                }
            ],
            "physical_repair": [
                {
                    "actions": [
                        {
                            "tool": "update_node",
                            "payload": {
                                "node_id": "PLC1",
                                "image": {"id": "plc-image", "name": "OpenPLC"},
                                "flavor": {"vcpu": 1, "ram": 512, "disk": 4},
                            },
                        }
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
    assert result["artifacts"]["logical"]["tgraph_logical"]["profile"] == "logical.v1"
    assert result["artifacts"]["physical"]["tgraph_physical"]["profile"] == "taal.default.v1"
    assert result["artifacts"]["physical"]["tgraph_physical"]["links"] == result["artifacts"]["logical"]["tgraph_logical"]["links"]
    assert all("[shared_memory]" not in message["content"] for entry in client.message_log for message in entry["messages"])
    assert (tmp_path / "runs" / "run-001" / "ground" / "artifact.json").exists()
    assert (tmp_path / "runs" / "run-001" / "logical" / "messages.json").exists()
    assert (tmp_path / "runs" / "run-001" / "physical" / "evaluation.json").exists()


def test_trace_runtime_accepts_semantically_identical_physical_links_even_when_order_differs(tmp_path):
    client = SequenceRoleClient(
        {
            "ground_author": [
                {
                    "node_groups": [
                        {"type": "router", "members": ["R1", "R2", "R3"]},
                    ],
                    "logical_constraints": [
                        {"id": "g1", "statement": "R1 must connect to R2 and R3 must connect to R2."}
                    ],
                    "physical_constraints": [],
                }
            ],
            "ground_evaluator": [
                {"passed": True, "issues": [], "optimizer_brief": {}}
            ],
            "logical_author": [
                {
                    "logical_checkpoints": [
                        {"id": "lc1", "func": "connect_nodes", "description": "R1 connect R2", "constraint_ids": ["g1"], "args": {"node_a": "R1", "node_b": "R2"}},
                        {"id": "lc2", "func": "connect_nodes", "description": "R3 connect R2", "constraint_ids": ["g1"], "args": {"node_a": "R3", "node_b": "R2"}},
                    ],
                    "logical_validator_script": None,
                }
            ],
            "logical_builder": [
                {
                    "tgraph_logical": {
                        "profile": "logical.v1",
                        "nodes": [
                            {
                                "id": "R1",
                                "type": "router",
                                "label": "R1",
                                "ports": [{"id": "R1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}],
                                "image": None,
                                "flavor": None,
                            },
                            {
                                "id": "R2",
                                "type": "router",
                                "label": "R2",
                                "ports": [
                                    {"id": "R2:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"},
                                    {"id": "R2:p2", "ip": "10.0.0.5", "cidr": "10.0.0.4/30"},
                                ],
                                "image": None,
                                "flavor": None,
                            },
                            {
                                "id": "R3",
                                "type": "router",
                                "label": "R3",
                                "ports": [{"id": "R3:p1", "ip": "10.0.0.6", "cidr": "10.0.0.4/30"}],
                                "image": None,
                                "flavor": None,
                            },
                        ],
                        "links": [
                            {
                                "id": "R1:p1--R2:p1",
                                "from_port": "R1:p1",
                                "to_port": "R2:p1",
                                "from_node": "R1",
                                "to_node": "R2",
                            },
                            {
                                "id": "R2:p2--R3:p1",
                                "from_port": "R2:p2",
                                "to_port": "R3:p1",
                                "from_node": "R2",
                                "to_node": "R3",
                            },
                        ],
                    }
                }
            ],
            "physical_author": [
                {
                    "physical_checkpoints": [],
                    "physical_validator_script": None,
                }
            ],
            "physical_builder": [
                {
                    "tgraph_physical": {
                        "profile": "taal.default.v1",
                        "nodes": [
                                {
                                    "id": "R1",
                                    "type": "router",
                                    "label": "R1",
                                    "ports": [{"id": "R1:p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}],
                                    "image": None,
                                    "flavor": None,
                                },
                                {
                                    "id": "R2",
                                    "type": "router",
                                    "label": "R2",
                                    "ports": [
                                        {"id": "R2:p1", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"},
                                        {"id": "R2:p2", "ip": "10.0.0.5", "cidr": "10.0.0.4/30"},
                                    ],
                                    "image": None,
                                    "flavor": None,
                                },
                                {
                                    "id": "R3",
                                    "type": "router",
                                    "label": "R3",
                                    "ports": [{"id": "R3:p1", "ip": "10.0.0.6", "cidr": "10.0.0.4/30"}],
                                    "image": None,
                                    "flavor": None,
                                },
                            ],
                            "links": [
                                {
                                    "id": "R2:p2--R3:p1",
                                    "from_port": "R3:p1",
                                    "to_port": "R2:p2",
                                    "from_node": "R3",
                                    "to_node": "R2",
                                },
                                {
                                    "id": "R1:p1--R2:p1",
                                    "from_port": "R2:p1",
                                    "to_port": "R1:p1",
                                    "from_node": "R2",
                                    "to_node": "R1",
                                },
                            ],
                        }
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
    assert "physical_repair" not in client.calls


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
