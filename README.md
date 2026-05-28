# TRACE

TRACE 是一个面向网络拓扑意图建模的核心运行时重写版。当前版本聚焦最小但完整的主流程：

- `ground -> logical -> physical -> finalize`
- 外层 `LangGraph` 负责任务与阶段流转
- 内层阶段子图负责各阶段自己的 author / builder / validator / repair 回路
- `LangChain` 负责角色节点、模型调用、结构化输出和 agent tool 调用
- `LangSmith` 负责 `run + stage + role + tool` 粒度 tracing
- 本地 `runs/<run_id>/` 目录保存完整调试快照

当前实现是 greenfield 骨架，重点是运行时结构、阶段边界、状态传递、TGraph IR 和调试可见性，而不是复刻旧项目的全部实验能力。

## 当前能力

已经实现：

- `trace run <intent-or-md>` 运行完整主流程
- `trace resume <run_id> --from <stage>` 从 stage artifact checkpoint 恢复调试
- 仓库根目录 `.env` 自动加载
- `ground` 阶段的 `prepare -> author -> evaluator -> finalize`
- `logical` 阶段的 `prepare -> author(agent) -> builder -> validator -> repair -> finalize`
- `physical` 阶段的 `prepare -> author -> builder -> validator -> repair -> finalize`
- standalone `tgraph` 包：模型、JSON IO、inspect、mutate、validate、target emit
- stage artifact 使用 `graph + constraint_files + checkpoint_files`
- ground 会落盘 `ground/logical_constraints.json` 和 `ground/physical_constraints.json`
- logical / physical author 会分别生成 `logical/checkpoints.py` 和 `physical/checkpoints.py`
- `runs/<run_id>/` 完整快照落盘
- LangSmith tracing 接线
- LangGraph SqliteSaver checkpointer（`runs/<run_id>/state.sqlite`）与 RunStorage 双轨 resume
- logical / physical escalation 回流 ground（`*.escalation.*` issue kinds）

暂未实现或仍在收敛：

- `translate` 阶段
- 跨 run 长期记忆
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

## 从阶段恢复

每个 stage 完成后都会写入 `runs/<run_id>/<stage>/artifact.json`。调试后续阶段时，可以从已有 artifact 恢复，避免从头重跑：

```powershell
trace resume demo-001 --from physical --output-root runs
```

支持的入口：

- `--from ground`：复用原 run 的 intent，完整重跑
- `--from logical`：复用 `ground` artifact，重跑 `logical -> physical -> finalize`
- `--from physical`：复用 `ground` 和 `logical` artifact，重跑 `physical -> finalize`
- `--from finalize`：复用 `ground`、`logical` 和 `physical` artifact，只重新 finalize

默认会写入新 run，例如 `demo-001-resume-physical`；如果同名目录已存在，会自动追加 `-001`、`-002`。也可以显式指定：

```powershell
trace resume demo-001 --from physical --new-run-id demo-001-phys-debug --output-root runs
```

本地临时调试时也可以原地覆盖：

```powershell
trace resume demo-001 --from physical --in-place --output-root runs
```

恢复到新 run 时，被复用 stage 的 snapshot 目录也会复制过去，方便在一个 run 目录里查看完整链路。

### 状态持久化与恢复策略

每次 `trace run` 会在 `runs/<run_id>/state.sqlite` 落地一份 LangGraph 状态 (Checkpointer)；
`runs/<run_id>/run.json` 与 `<stage>/` 子目录仍作为人类可读快照保留。

恢复时：

- `--in-place` 模式下，优先使用 `runs/<run_id>/<stage>/state.sqlite` 从该 stage 子图的最近 checkpoint 继续；如果 stage sqlite 不可用，则回退到外层 `runs/<run_id>/state.sqlite` / RunStorage 路径；
- `--new-run-id <id>` 模式（默认）下，始终走 `RunStorage` 路径：把上一 run 的 stage 快照拷贝进新 `runs/<new_id>/` 目录后重新跑，并在新目录里建立自己的 sqlite。

### Escalation 反馈通道

logical / physical stage 在遇到 `*.escalation.*` 类 issue 时不会进入 repair，而是把
`escalation_report` 回流给 ground，由 ground 重新评估 constraints。计数器
`attempt_counters.escalation` 上限为 2 次；超出则整体失败。
若 ground 判断 `unsolvable=true`，run 直接以 `status="unsolvable"` 终止并提示用户检查 intent。

## 输出目录

每次运行都会写入：

```text
runs/<run_id>/
  run.json
  events.jsonl
  ground/
    state.sqlite
    artifact.json
    logical_constraints.json
    physical_constraints.json
    evaluation.json
    summary.json
    messages.json
    tool_journal.json
    retry_history.json
    events.jsonl
  logical/
    state.sqlite
    artifact.json
    checkpoints.py
    evaluation.json
    summary.json
    messages.json
    tool_journal.json
    repair_history.json
    events.jsonl
  physical/
    state.sqlite
    artifact.json
    checkpoints.py
    evaluation.json
    summary.json
    messages.json
    tool_journal.json
    repair_history.json
    events.jsonl
```

`ground/artifact.json` 只包含 `node_groups` 和 `constraint_files`；约束正文落在 `ground/logical_constraints.json`、`ground/physical_constraints.json`，并通过 `artifact.constraint_files` 引用。

`logical/artifact.json` 只包含：

- `graph`
- `constraint_files`
- `checkpoint_files`

`physical/artifact.json` 包含：

- `graph`
- `constraint_files`
- `checkpoint_files`

这是“调试友好型快照”：除了最终 artifact，也会保留阶段消息、validator 结果、repair 历史和事件流。

## 架构概览

### 外层运行图

外层 run graph 负责：

- `ground`
- `logical`
- `physical`
- `finalize`

`RunState` 保留跨阶段共享的核心字段：

- `run_id`
- `intent`
- `status`
- `current_stage`
- `artifacts`
- `stage_reports`
- `attempt_counters`
- `events`
- `error`
- `config_snapshot`
- `resume`

### 阶段子图

`ground`：

- `prepare`
- `author`
- `evaluator`
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

- `logical.prepare` 会根据 `ground_artifact` 确定性初始化 logical seed graph
- `logical.author` 是 agent 节点，通过文件工具写入 `logical/checkpoints.py`
- `physical.prepare` 会从 `logical_artifact.graph` 派生 physical working graph
- `physical` 只能补充 `image` / `flavor` 等物理字段，不能破坏 logical 拓扑

### TGraph 工具层

`TGraph` 相关逻辑统一放在 standalone 包 `src/tgraph/`：

- `core/`：`TGraph`、node、port、link、stage、normalize
- `io/`：JSON document parse / dump
- `operations/inspect/`：summary、nodes、ports、links、paths、CIDR 视图
- `operations/mutate/`：sandboxed mutation file 执行和 `TGraphEditor`
- `operations/validate/`：F1/F2/F3/F4 校验、constraint file / checkpoint file 执行
- `agent/docs/`：给 Agent 查询的 artifact、fact kind、checkpoint、mutation、naming 短文档
- `targets/`：target emitter registry
- `cli/`：`tgraph inspect|validate|normalize|export|emit`

## 项目结构

```text
src/
  tgraph/
    agent/
    cli/
    core/
    io/
    operations/
    targets/
  trace/
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
      images/
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
- run storage 和 stage resume
- TGraph core / IO / inspect / mutate / validate / targets / CLI
- `ground` evaluator retry 回路
- logical author agent、builder、validator、repair
- physical author、builder、validator、repair
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
- 后续阶段有问题时，优先用 `trace resume <run_id> --from logical|physical|finalize` 缩短调试循环
