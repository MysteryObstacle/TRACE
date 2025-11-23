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

### Streaming + manual approvals demo (`main.py`)

Use the interactive demo to see streaming outputs and per-step confirmation. Disable auto execute with `--manual` to edit `Think` content before continuing:

```bash
python main.py "我想要构建一个工业控制网络的靶场场景" \
  --base-url http://10.10.5.8:9000/v1 \
  --api-key EMPTY \
  --model Qwen3-8B \
  --topo-summary "当前拓扑：空白" \
  --manual
```

> 提示：如果你的服务地址提供的是 `.../v1/chat/completions`，`build_qwen_vllm_chat_model` 会自动去掉尾部的 `/chat/completions`，因此 `--base-url` 保持到 `/v1` 即可。

Flags:

- `--manual` sets `auto_execute=False` and prompts for confirmation after each ReAct回合，可修改 Think 后继续。
- `--no-stream` turns off streaming; by default tokens are printed as they arrive.

### Offline deterministic demo

Run the canned-response example to see the PLAN + ReAct trace without hitting an LLM endpoint:

```bash
python examples/offline_demo.py
```

### Pushing this code to GitHub

If you want to see the latest code on GitHub, add your remote and push the current branch (default is `work`):

```bash
git remote add origin https://github.com/<your_org_or_user>/TRACE.git
git push -u origin work
```

If a remote already exists, simply run `git push` to publish updates.

## Architecture

- `trace_agent.agent.TraceAgent` orchestrates initialization, PLAN step execution, and context tracking.
- `trace_agent.memory` stores plan metadata, ConversationState, and handles JSON persistence for Step 5.
- `trace_agent.prompting` contains the system primer plus prompts for goal extraction、任务分类、每步ReAct提示。
- `trace_agent.tools.Toolset` 提供内置“静态工具”而非 `langchain.tools`：PLAN上下文查询、旧/目标Topo JSON与diff规划、SceneGraph SDK摘录、镜像清单、行业知识（普渡模型等）、Topo规范、SceneGraph代码规范。
- `trace_agent.model_provider.build_qwen_vllm_chat_model` builds a ChatOpenAI-compatible client pointing to vLLM + Qwen3。
- `examples/offline_demo.py` demonstrates the full loop with a deterministic chat model for testing.

## Development notes

- Python 3.10+ is required.
- The agent keeps persistent prompts and topo JSON in memory during the session. External persistence can be added by serializing `ConversationState` as needed.
- Try/catch wrappers around imports are intentionally avoided to keep module loading straightforward.
