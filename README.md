# TRACE

Topology-Reasoning Agent for Controllable Environments.

This repository contains a LangChain-based orchestration layer that follows the two-phase PLAN + ReAct loop described in the requirements. The agent is designed for Python 3.10 and integrates with Qwen3 served by vLLM via the OpenAI-compatible API surface.

## Features

- Fixed PLAN outline aligned with the required seven steps (intent → node types → 分区 → 属性 → JSON → SceneGraph → 校验).
- ReAct-style step execution that records Think/Action/Observe for every phase.
- Conversation memory that tracks总体目标、Topo JSON对象、Plan Context和当前步骤。
- Tool registry matching the required topology, SceneGraph、镜像查询接口（可通过缓存数据预热）。
- Minimal vLLM + Qwen3 builder using LangChain's `ChatOpenAI` client for OpenAI-compatible endpoints.
- Offline demo showing the orchestration loop without external connectivity.

## Installation

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

### Create a Qwen3 chat client (vLLM backend)

```python
from trace_agent import TraceAgent, build_qwen_vllm_chat_model

llm = build_qwen_vllm_chat_model(
    base_url="http://localhost:8000/v1",
    api_key="EMPTY",
    model="Qwen3-1.5B-Instruct",
)
agent = TraceAgent(llm)
plan = agent.run_plan("在VPC中创建三层应用拓扑", topo_state={"summary": "空白集群"})
for step, results in plan.steps.items():
    for idx, result in enumerate(results, start=1):
        print(step.label, result.think, result.action, result.observe)
```

### Offline deterministic demo

Run the canned-response example to see the PLAN + ReAct trace without hitting an LLM endpoint:

```bash
python examples/offline_demo.py
```

## Architecture

- `trace_agent.agent.TraceAgent` orchestrates initialization, PLAN step execution, and context tracking.
- `trace_agent.memory` stores plan metadata, ConversationState, and handles JSON persistence for Step 5.
- `trace_agent.prompting` contains the system primer plus prompts for goal extraction、任务分类、每步ReAct提示。
- `trace_agent.tools.Toolset` exposes the required查询工具（拓扑摘要/详情、SceneGraph API与类型、镜像信息），支持以缓存形式预热。
- `trace_agent.model_provider.build_qwen_vllm_chat_model` builds a ChatOpenAI-compatible client pointing to vLLM + Qwen3。
- `examples/offline_demo.py` demonstrates the full loop with a deterministic chat model for testing.

## Development notes

- Python 3.10+ is required.
- The agent keeps persistent prompts and topo JSON in memory during the session. External persistence can be added by serializing `ConversationState` as needed.
- Try/catch wrappers around imports are intentionally avoided to keep module loading straightforward.
