# TRACE

TRACE 是一个面向网络拓扑意图建模的核心运行时重写版。当前版本聚焦最小但完整的主流程：

- `ground -> logical -> physical`
- 外层 `LangGraph` 负责任务与阶段流转
- 内层阶段子图负责 `author / evaluator / builder / optimizer / repair`
- `LangChain` 负责角色节点、模型调用和结构化输出
- `LangSmith` 负责 `run + stage + role + tool` 粒度 tracing
- 本地 `runs/<run_id>/` 目录保存完整调试快照

当前实现是 greenfield 骨架，重点是运行时结构、阶段边界、状态传递和调试可见性，而不是复刻旧项目的全部实验能力。

## 当前能力

已经实现：

- `trace run <intent-or-md>` 单一 CLI 入口
- 仓库根目录 `.env` 自动加载
- `ground` 阶段的 `author -> evaluator -> optimizer`
- `logical` 阶段的 `prepare -> author -> builder -> validator -> repair`
- `physical` 阶段的 `prepare -> author -> builder -> validator -> repair`
- `TGraph` 最小模型、derive、patch、query、validate 工具
- `runs/<run_id>/` 完整快照落盘
- LangSmith tracing 接线

暂未实现：

- `resume`
- `translate` 阶段
- 跨 run 长期记忆
- agent 生成并执行 Python validator 脚本
- 前端可视化
- 旧项目 `experiments/` 迁移

## 安装

### 1. 激活环境

```powershell
conda activate Trace
```

### 2. 安装项目

日常运行：

```powershell
pip install -e .
```

如果需要运行测试：

```powershell
pip install -e ".[dev]"
```

### 3. 已验证依赖族

当前仓库按下面这组 1.x 依赖族做了兼容性验证：

- `langchain>=1.2,<1.3`
- `langgraph>=1.1.1,<1.2`
- `langchain-openai>=1.1,<1.2`
- `langsmith>=0.7,<0.8`
- Python `3.10`

之所以这样收窄，是因为 `langchain 1.2.x` 依赖 `langgraph 1.1.x`，如果把 `langgraph` 锁在 `<1.0`，`pip install -e .` 会直接触发 `ResolutionImpossible`。

如果你不想安装脚本入口，也可以直接用模块方式运行：

```powershell
$env:PYTHONPATH = "src"
python -m trace.main --help
```

## 环境变量

项目会自动读取仓库根目录的 `.env`。

常用配置示例：

```env
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=trace-iac

OPENAI_API_KEY=...
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
TRACE_MODEL_NAME=qwen-plus-2025-07-28
```

其中 `OPENAI_*` / `LANGSMITH_*` 是提供商原生配置；`TRACE_*` 只用于 TRACE 自己的运行时和角色配置。

默认情况下，`TRACE_MODEL_NAME` 会作为所有角色节点的默认模型。你也可以覆盖具体角色：

- `TRACE_ROLE_GROUND_AUTHOR_MODEL`
- `TRACE_ROLE_GROUND_EVALUATOR_MODEL`
- `TRACE_ROLE_LOGICAL_AUTHOR_MODEL`
- `TRACE_ROLE_LOGICAL_BUILDER_MODEL`
- `TRACE_ROLE_LOGICAL_REPAIR_MODEL`
- `TRACE_ROLE_PHYSICAL_AUTHOR_MODEL`
- `TRACE_ROLE_PHYSICAL_BUILDER_MODEL`
- `TRACE_ROLE_PHYSICAL_REPAIR_MODEL`

同理也支持对应的 `*_TEMPERATURE` 和 `*_MAX_ATTEMPTS`。

## 快速运行

直接传自然语言：

```powershell
trace run "Construct a typical industrial control network with 2 PLCs, 1 switch, and 1 router."
```

或者传一个 `.md` 文件：

```powershell
trace run tests/demo/demo.md --run-id demo-001
```

也可以指定输出目录：

```powershell
trace run tests/demo/demo.md --output-root runs --run-id demo-001
```

成功时 CLI 会输出：

```text
completed:<run_id>
status:completed
```

## 输出目录

每次运行都会写入：

```text
runs/<run_id>/
  run.json
  shared_memory.json
  events.jsonl
  ground/
    artifact.json
    evaluation.json
    summary.json
    messages.json
    tool_journal.json
    retry_history.json
    events.jsonl
  logical/
    artifact.json
    evaluation.json
    summary.json
    messages.json
    tool_journal.json
    repair_history.json
    events.jsonl
  physical/
    artifact.json
    evaluation.json
    summary.json
    messages.json
    tool_journal.json
    repair_history.json
    events.jsonl
```

这是“调试友好型快照”：除了最终 artifact，也会保留阶段消息、validator 结果、repair 历史和事件流。

## 架构概览

### 外层运行图

外层 run graph 负责：

- `ground`
- `logical`
- `physical`
- `finalize`

`RunState` 只保留跨阶段共享的核心字段：

- `run_id`
- `intent`
- `status`
- `current_stage`
- `artifacts`
- `shared_memory`
- `stage_reports`
- `attempt_counters`
- `events`
- `error`
- `config_snapshot`

### 阶段子图

`ground`：

- `prepare`
- `author`
- `evaluator`
- `optimizer`
- `finalize`

`logical`：

- `prepare`
- `author`
- `builder`
- `validator`
- `repair`
- `finalize`

`physical`：

- `prepare`
- `author`
- `builder`
- `validator`
- `repair`
- `finalize`

关键约束：

- `logical.prepare` 会确定性初始化 logical skeleton
- `physical.prepare` 会从 `logical.tgraph_logical` 派生 physical working graph
- `physical` 只能补充物理字段，不能破坏 logical 拓扑

### TGraph 工具层

`TGraph` 相关逻辑统一放在 `src/trace/tools/tgraph/`：

- `model.py`
- `derive.py`
- `patch.py`
- `query.py`
- `validate/`

当前 validator 包含格式检查、schema 检查、基础一致性检查，以及一个占位版 `intent` validator。

## 项目结构

```text
src/trace/
  main.py
  config/
  observability/
  runtime/
  stages/
    ground/
    logical/
    physical/
  storage/
  tools/
    tgraph/
tests/
  demo/
  e2e/
  fixtures/
  integration/
  unit/
frontend/
```

## 测试

运行全部测试：

```powershell
conda activate Trace
python -m pytest -q
```

当前自动化覆盖：

- 配置读取
- packaging 依赖范围
- state reducer
- run storage
- TGraph derive / patch / query / validate
- `ground` evaluator-optimizer 回路
- 三阶段运行图集成
- CLI smoke

## Troubleshooting

### `pip install -e .` 提示 `ResolutionImpossible`

优先检查 `langchain` 和 `langgraph` 是否处在兼容的 1.x 版本族。当前仓库已经把依赖范围收窄到经过验证的组合；如果你的环境里手动装过更老的 `langgraph 0.x`，建议先清理后重装。

### `conda-libmamba-solver` 噪音警告

`conda run` 在某些环境里会打印 `libmambapy` 或 PowerShell profile 的噪音信息。这和本项目的依赖解析冲突不是同一个问题。只要安装命令本身成功、测试和 CLI 能跑通，就不影响 TRACE 本身。

## 开发建议

- 真实端到端 smoke 建议从 `tests/demo/demo.md` 开始
- 如果阶段结果不理想，优先检查 `runs/<run_id>/.../messages.json`
- `ground` 阶段结合 `evaluation.json`、`retry_history.json` 和 LangSmith traces 排查
- `logical` / `physical` 阶段结合 `evaluation.json`、`repair_history.json` 和 LangSmith traces 排查
