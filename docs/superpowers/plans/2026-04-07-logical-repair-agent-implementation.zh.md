# Logical Repair Agent 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `logical.repair` 从“结构化 LLM 直接返回完整 artifact”改造成“节点代码自动装载/写回 TGraphRuntime，Agent 通过低层工具执行事务式修图”。

**Architecture:** 外层 LangGraph stage 控制流保持 `builder -> validator -> repair -> validator` 不变。`repair` 节点内部不再手写循环，也不让 LLM 接触完整 `TGraphJSON`；节点代码自动创建当前 `TGraphRuntime`、绑定一组无 handle 的低层工具给 Agent、在 Agent 结束后自动将 `runtime.to_json()` 写回 `draft_artifact`。循环和停止条件下沉到 Agent executor 的 tool loop。

**Tech Stack:** Python 3.11, LangGraph, LangChain, Pydantic, pytest

---

## 文件映射

- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/runtime.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/transaction.py`
- Delete/Replace: `d:/Projects/Trace/src/trace/tools/tgraph/protocol.py`
- Modify: `d:/Projects/Trace/src/trace/runtime/role_client.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/nodes/repair.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prompts/repair.md`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/__init__.py`
- Test: `d:/Projects/Trace/tests/unit/tools/tgraph/test_graph_core.py`
- Test: `d:/Projects/Trace/tests/unit/runtime/test_role_client.py`
- Create: `d:/Projects/Trace/tests/unit/stages/logical/test_repair_agent.py`
- Modify: `d:/Projects/Trace/tests/integration/test_runtime_pipeline.py`

---

## Chunk 1: 绑定到当前图实例的低层工具

### Task 1: 用失败测试定义 repair agent 的最小工具面

**Files:**

- Modify: `d:/Projects/Trace/tests/unit/tools/tgraph/test_graph_core.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/runtime.py`
- Modify: `d:/Projects/Trace/src/trace/tools/tgraph/transaction.py`
- Delete/Replace: `d:/Projects/Trace/src/trace/tools/tgraph/protocol.py`

- [ ] **Step 1: 写失败测试，约束“无 handle、绑定当前图实例”的工具上下文**

```python
from trace.tools.tgraph.protocol import BoundTGraphTools


def test_bound_tgraph_tools_expose_topology_view_and_validate():
    tools = BoundTGraphTools.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "r1", "ports": [{"id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
                {"id": "r2", "type": "router", "label": "r2", "ports": [{"id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/24"}], "image": None, "flavor": None},
            ],
            "links": [{"id": "p1--p2", "from_port": "p1", "to_port": "p2"}],
        }
    )

    assert tools.topology_view() == {
        "nodes": ["r1", "r2"],
        "links": ["p1--p2"],
    }
    assert tools.validate()["ok"] is True
```

- [ ] **Step 2: 再写失败测试，约束单活事务模型**

```python
def test_bound_tgraph_tools_allow_only_one_active_transaction():
    tools = BoundTGraphTools.from_json({...})

    tools.begin_tx()

    with pytest.raises(RuntimeError):
        tools.begin_tx()
```

- [ ] **Step 3: 再写失败测试，约束第一批可用操作**

```python
def test_bound_tgraph_tools_commit_low_level_repairs():
    tools = BoundTGraphTools.from_json(
        {
            "profile": "logical.v1",
            "nodes": [
                {"id": "r1", "type": "router", "label": "r1", "ports": [], "image": None, "flavor": None},
                {"id": "r2", "type": "router", "label": "r2", "ports": [], "image": None, "flavor": None},
            ],
            "links": [],
        }
    )

    tools.begin_tx()
    tools.tx_apply("add_port", {"node_id": "r1", "port_id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"})
    tools.tx_apply("add_port", {"node_id": "r2", "port_id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"})
    tools.tx_apply("add_link", {"from_port": "p1", "to_port": "p2"})
    result = tools.tx_commit(["f1", "f2", "f3"])

    assert result["ok"] is True
    assert tools.topology_view()["links"] == ["p1--p2"]
```

- [ ] **Step 4: 运行测试，确认当前实现失败**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py -k "bound_tgraph_tools or topology_view" -q`

Expected: FAIL，因为当前还是 handle-based `protocol.py`，而且 `tx_apply` 只支持 `add_link`。

- [ ] **Step 5: 最小实现 `BoundTGraphTools`**

实现要求：
- 不暴露 `load(handle)` 给 LLM
- 节点代码创建 `BoundTGraphTools(runtime)`
- 提供：
  - `topology_view()`
  - `get_node(node_id)`
  - `get_link(link_id)`
  - `validate()`
  - `begin_tx()`
  - `tx_apply(op, args)`
  - `tx_commit(levels)`
  - `tx_rollback()`
  - `to_json()`
  - `rollback_if_open()`

`topology_view()` 返回：

```python
{
    "nodes": [...],
    "links": [...],
}
```

其中：
- `nodes` 只返回 node id 列表
- `links` 只返回 link id 列表

- [ ] **Step 6: 为 runtime/transaction 补最小读写能力**

在 `TGraphRuntime` / `TGraphTransaction` 中补最小 API：

+ `topology_view()`

- `get_node(node_id)`
- `get_link(link_id)`
- `add_node(...)`
- `add_link(...)`
- `update_node(...)`
- `update_link(...)`
- `remove_node(...)`
- `remove_link(...)`

保持 YAGNI，不要实现第二批操作。

- [ ] **Step 7: 运行测试确认通过**

Run: `pytest tests/unit/tools/tgraph/test_graph_core.py -q`

Expected: PASS

---

## Chunk 2: 将 `RoleClient` 拆成 structured/agent 两条调用路径

### Task 2: 用失败测试定义 `invoke_agent()`，确保不破坏现有 structured 路径

**Files:**

- Modify: `d:/Projects/Trace/tests/unit/runtime/test_role_client.py`
- Modify: `d:/Projects/Trace/src/trace/runtime/role_client.py`

- [ ] **Step 1: 写失败测试，约束 `invoke_structured()` 保持现有行为**

```python
def test_role_client_invoke_structured_uses_schema_path(monkeypatch):
    ...
    result = client.invoke_structured(
        role_name="logical_author",
        messages=[...],
        schema=SomeSchema,
    )
    assert ...
```

- [ ] **Step 2: 写失败测试，约束 `invoke_agent()` 走 tools 路径**

```python
def test_role_client_invoke_agent_binds_tools(monkeypatch):
    captured = {}

    class FakeModel:
        def __init__(self, **kwargs):
            ...
        def bind_tools(self, tools):
            captured["tools"] = tools
            return self
        def invoke(self, messages):
            return {"content": "ok"}

    ...
    result = client.invoke_agent(
        role_name="logical_repair",
        messages=[...],
        tools=["tool-a"],
    )

    assert result["content"] == "ok"
    assert captured["tools"] == ["tool-a"]
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/unit/runtime/test_role_client.py -q`

Expected: FAIL，因为当前只有单一 `invoke()`。

- [ ] **Step 4: 最小实现 `invoke_structured()` 与 `invoke_agent()`**

建议收口：

```python
class RoleClient(Protocol):
    def invoke_structured(...): ...
    def invoke_agent(...): ...
```

`LangChainRoleClient` 中：

- `invoke_structured()`：走 `with_structured_output(schema)`
- `invoke_agent()`：走 `bind_tools(tools)`，不接 schema

保留一个兼容层：
- 旧 `invoke()` 可暂时转发到新接口
- 但新的 repair 节点不要再用旧 `invoke()`

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/unit/runtime/test_role_client.py -q`

Expected: PASS

---

## Chunk 3: 将 `logical.repair` 改造成“节点代码自动 load/writeback + 一次 agent run”

### Task 3: 用失败测试定义 repair node 的新职责边界

**Files:**
- Create: `d:/Projects/Trace/tests/unit/stages/logical/test_repair_agent.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/nodes/repair.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/prompts/repair.md`

- [ ] **Step 1: 写失败测试，约束 repair node 不再要求 LLM 返回完整 artifact**

```python
from trace.stages.logical.nodes.repair import repair_node


def test_repair_node_loads_runtime_and_writes_back_after_agent_run():
    state = {
        "draft_artifact": {
            "logical_checkpoints": [],
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [
                    {"id": "r1", "type": "router", "label": "r1", "ports": [], "image": None, "flavor": None},
                    {"id": "r2", "type": "router", "label": "r2", "ports": [], "image": None, "flavor": None},
                ],
                "links": [],
            },
        },
        "evaluation_report": {"ok": False, "issues": [...]},
        "shared_memory": {},
        "attempt": 1,
        "repair_history": [],
        "events": [],
    }

    class FakeRoleClient:
        def invoke_agent(self, **kwargs):
            tools = {tool.name: tool for tool in kwargs["tools"]}
            tools["begin_tx"].invoke({})
            tools["tx_apply"].invoke({"op": "add_port", "args": {"node_id": "r1", "port_id": "p1", "ip": "10.0.0.1", "cidr": "10.0.0.0/30"}})
            tools["tx_apply"].invoke({"op": "add_port", "args": {"node_id": "r2", "port_id": "p2", "ip": "10.0.0.2", "cidr": "10.0.0.0/30"}})
            tools["tx_apply"].invoke({"op": "add_link", "args": {"from_port": "p1", "to_port": "p2"}})
            tools["tx_commit"].invoke({"levels": ["f1", "f2", "f3"]})
            return {"messages": [{"role": "assistant", "content": "repaired"}]}

    new_state = repair_node(state, FakeRoleClient())

    assert new_state["draft_artifact"]["tgraph_logical"]["links"] == ["..."]  # 按实际结构断言
```

- [ ] **Step 2: 写失败测试，约束 repair node 会清理未提交事务**

```python
def test_repair_node_rolls_back_open_transaction_after_agent_run():
    ...
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest tests/unit/stages/logical/test_repair_agent.py -q`

Expected: FAIL，因为当前 repair node 仍然要求结构化 `LogicalArtifact` 返回。

- [ ] **Step 4: 最小重写 `logical/nodes/repair.py`**

实现要求：
- 节点代码自行 `runtime = TGraphRuntime.from_json(...)`
- 创建 `BoundTGraphTools(runtime)`
- 调 `role_client.invoke_agent(...)`
- Agent 结束后执行：

```python
tools.rollback_if_open()
state["draft_artifact"] = {
    **state["draft_artifact"],
    "tgraph_logical": tools.to_json(),
}
```

- [ ] **Step 5: 更新 repair prompt**

将 [repair.md](d:/Projects/Trace/src/trace/stages/logical/prompts/repair.md) 调整为 Agent 语义：
- 不再要求“返回完整 LogicalArtifact”
- 明确要求：
  - 先用 `validate()` 和 `topology_view()`
  - 通过工具修图
  - 每次修改前先 `begin_tx()`
  - 最终必须 `tx_commit()` 或 `tx_rollback()`

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/unit/stages/logical/test_repair_agent.py -q`

Expected: PASS

---

## Chunk 4: 将 agent repair 接入现有 logical stage，并保持外层 validator-repair-validator 循环

### Task 4: 用集成测试验证“外层循环不变，内层改为 Agent”

**Files:**
- Modify: `d:/Projects/Trace/tests/integration/test_runtime_pipeline.py`
- Modify: `d:/Projects/Trace/src/trace/stages/logical/__init__.py`

- [ ] **Step 1: 写失败测试，约束 logical stage 可以通过 agent repair 修好图**

```python
def test_runtime_pipeline_logical_repair_agent_can_fix_topology(...):
    ...
```

测试重点：
- builder 先产出一个会触发 validator 报错的 logical graph
- `logical_repair` 通过 tools 路径修复
- 外层仍然走 `validator -> repair -> validator`
- 最终 logical stage 成功完成

- [ ] **Step 2: 运行聚焦集成测试，确认失败**

Run: `pytest tests/integration/test_runtime_pipeline.py -k logical_repair_agent -q`

Expected: FAIL

- [ ] **Step 3: 最小接线**

确认：
- [logical `__init__.py`](d:/Projects/Trace/src/trace/stages/logical/__init__.py) 不需要改变 stage-level 边
- 只要 repair node 已切到 `invoke_agent()`，外层控制流应原样工作

- [ ] **Step 4: 运行聚焦集成测试，确认通过**

Run: `pytest tests/integration/test_runtime_pipeline.py -k logical_repair_agent -q`

Expected: PASS

---

## Chunk 5: 全量验证与清理

### Task 5: 验证逻辑修图 agent 化不会破坏现有阶段行为

**Files:**

- Verify only

- [ ] **Step 1: 运行工具层与 role client 测试**

Run:

```powershell
pytest tests/unit/tools/tgraph/test_graph_core.py tests/unit/runtime/test_role_client.py tests/unit/stages/logical/test_repair_agent.py -q
```

Expected: PASS

- [ ] **Step 2: 运行 stage/integration 测试**

Run:

```powershell
pytest tests/integration/test_ground_stage.py tests/integration/test_runtime_pipeline.py -q
```

Expected: PASS

- [ ] **Step 3: 运行全量测试**

Run:

```powershell
pytest -q
```

Expected: PASS

- [ ] **Step 4: 如全绿，再考虑是否复制到 `physical.repair`**

这一步不实现，只记录结论：
- 如果 `logical.repair` agent 化稳定，再将同样模式复制到 `physical.repair`
- 当前计划不包含 `physical.repair` 改造
