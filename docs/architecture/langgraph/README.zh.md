# LangGraph 架构说明

本文描述 TRACE 当前基于 LangGraph 的运行结构，以及 stage artifact、support files、TGraph 校验和修复工具之间的边界。

## 1. 运行分层

- 顶层运行图：`ground -> logical -> physical -> finalize`
- 每个 stage 是独立子图，由 `src/trace/stages/<stage>/__init__.py` 组装。
- 每个 stage 完成后写入 `runs/<run_id>/<stage>/artifact.json`，用于 `trace resume <run_id> --from <stage>`。
- 支撑文件跟随 run snapshot 落盘，例如 `ground/logical_constraints.json`、`logical/checkpoints.py`。

## 2. 节点类型约定

- 脚本节点：纯 Python 逻辑，不调模型。
- 结构化 LLM 节点：通过 Pydantic schema 约束完整对象输出。
- Agent 节点：通过 tools 做局部读写、校验和修复。

## 3. 顶层流程

```mermaid
flowchart TD
    run["TraceRuntime.run / resume"] --> graph["Run Graph"]
    graph --> ground["ground subgraph"]
    ground --> logical["logical subgraph"]
    logical --> physical["physical subgraph"]
    physical --> finalize["finalize"]
```

## 4. Stage 职责

- `ground`：把用户意图整理成 `node_groups`、`logical_constraints`、`physical_constraints`，并写出 constraint files。
- `logical`：生成 logical `graph`，生成 `logical/checkpoints.py`，运行 TGraph F1-F4 校验和修复。
- `physical`：在 logical graph 基础上补 `image` / `flavor`，生成 `physical/checkpoints.py`，并保持 logical topology identity。

Stage artifact 统一使用：

- `graph`
- `constraint_files`
- `checkpoint_files`

最终 artifact 不再包含旧的内联校验结构。

## 5. Author / Builder / Validator / Repair

### Logical

- `logical.prepare` 根据 `ground_artifact.node_groups` 初始化只含节点的 logical skeleton，并挂载 `ground/logical_constraints.json`。
- `logical.author` 是 Agent 节点，读取 constraint file，写入 `logical/checkpoints.py`。
- `logical.builder` 生成或补全 logical graph，但不改 checkpoint 文件。
- `logical.validator` 调用 TGraph 校验，并读取 `constraint_files` / `checkpoint_files`。
- `logical.repair` 通过 mutation file 修 graph，通过文件工具修 checkpoint。

### Physical

- `physical.prepare` 从 logical graph 派生 physical graph，先填默认 `image` / `flavor`，并挂载 `ground/physical_constraints.json`。
- `physical.author` 是 Agent 节点，读取 physical constraints 和静态知识文档，写入 `physical/checkpoints.py`。
- `physical.builder` 只补部署字段，不破坏 logical topology。
- `physical.validator` 检查 schema、topology preservation、required fields 和 authored checkpoints。
- `physical.repair` 通过 mutation file 修 graph / image / flavor，通过文件工具修 checkpoint。

## 6. TGraph Agent 文档

Agent 可查询的短文档放在 `src/tgraph/agent/docs/`：

- `artifact-files.md`
- `fact-kinds.md`
- `checkpoint-files.md`
- `mutation-files.md`
- `naming.md`
- `catalogs.md`

Prompts 和架构说明应链接这些短文档，不在提示词里重复长 API 清单。
