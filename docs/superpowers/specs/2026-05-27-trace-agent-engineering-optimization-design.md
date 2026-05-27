# TRACE Agent 工程化优化设计

Status: draft for discussion

## Context

`tgraph-standalone-ir-engine` worktree 已经具备 `ground -> logical -> physical -> finalize` 主流程，并以 `LangGraph` 编排、`LangChain` 调用模型、`LangSmith` 追踪、本地 `runs/<run_id>/` 落盘的形式落地。`runs/demo-007` 的实证跑通了一份较复杂工业网络拓扑，但 LangSmith 日志和落盘文件暴露出八类 Agent 工程问题：tool / prompt 冗余、与 LangGraph 适配度不足、文件读取与目录查询缺少精确检索、node 记忆建模不充分、mutation 反复整体写出、mutation 返回完整 graph 污染记忆、stage 间意图传递缺少回流通道，以及 physical author 既未查询 image / flavor 库也未使用 kind 对应的内置 check 函数。本设计统一规划这八处的整改，使运行链路更短、token 更省、产出更稳定。

## Agreed Direction

将整改分成八个并列模块，按"风险隔离 + 价值密度"排序分批落地，最终覆盖：

- prompt 与工具表面整顿
- mutation 增量化与 agent 产物指针记忆
- LangGraph 1.x 原生特性接入（reducer、Command、Checkpointer）
- escalation 反馈通道
- image / flavor 库的工具化与 kind 决策表

落地范围为最大档（用户已确认 scope=max），但实现分批 PR，避免 runtime 大动脉与表层整顿同批合入。

## 模块 A · Builder 输入裁剪与 mutation 工具返回值瘦身

### 现状

- 三处 node 函数 `context_sections` 中都注入 `graph_summary`，并各自带一个本地 `_graph_summary(...)` 私有函数：
  - `src/trace/stages/logical/nodes/builder.py` L29-34（建 logical builder context）
  - `src/trace/stages/physical/nodes/author.py` L33-37（建 physical author context）
  - `src/trace/stages/physical/nodes/builder.py` L31-35（建 physical builder context）
  与三处的 `inspect_graph` 工具能力重叠。
- `src/trace/stages/repair_tools.py` 的 `execute_mutation_file` 默认返回 `result.model_dump(mode="json", exclude_none=True)`，其中 `graph` 字段为完整 TGraph 序列化（demo-007 `physical/repair_history.json` 单次 ToolMessage 700+ 行）。
- 该 ToolMessage 留存在 agent 内部消息序列里，对后续 LLM 调用是长期上下文负担。

### 设计

- 删除 `graph_summary` 注入与三处 `_graph_summary` 私有函数：
  - `logical/nodes/builder.py`
  - `physical/nodes/author.py`
  - `physical/nodes/builder.py`
  `constraint_files` 与 `checkpoint_files` 保留（agent 需要知道有哪些 file 引用）。
- `StageRepairTools.execute_mutation_file` 的 `MutationExecutionResult` 序列化策略改为：
  - 默认 `include_graph=False`，返回 `{ ok, operations, summary: MutationSummary }`（详见 schema 定义）。
  - 当 `ok=False` 时，返回 `{ ok, operations, issues, summary }`，便于失败定位。
  - 暴露 `include_graph: bool = False` 参数给 tool；agent 显式置 true 时才会拿到完整 `graph`。
- `MutationExecutionResult` 模型新增 `summary: MutationSummary` 字段，独立于 `graph`。
- `MutationSummary` schema 定义（与 `editor.operations` 字段对齐）：

  ```python
  class MutationSummary(BaseModel):
      stage: str                           # "logical" | "physical"
      node_count: int                      # 当前 graph node 总数
      link_count: int                      # 当前 graph link 总数
      affected_node_ids: list[str]         # 排序去重；由 operations[i].node 与 operations[i].nodes[*] 聚合而来
      affected_link_ids: list[str]         # 排序去重；由 operations[i].link 与 operations[i].links_removed[*] 聚合
      op_counts: dict[str, int]            # 每种 op 出现次数；op 取值见 TGraphEditor.operations 字段
  ```

  `op` 取值枚举与 `TGraphEditor.operations` 一致：`ensure_node` / `ensure_direct_link` / `ensure_subnet` / `ensure_interface` / `set_image` / `set_flavor` / `remove_node` / `remove_links`。
  - 推导规则：
    - `affected_node_ids` 来源：每个 op 的 `node`（标量）、`nodes`（列表）字段。
    - `affected_link_ids` 来源：每个 op 的 `link`（标量）、`links_removed`（列表）字段。
    - `op_counts` 直接对 `operations` 中的 `op` 字段做 Counter。

### 验证

- 新建单元测试：mutation 成功 / 失败 / 显式 include_graph 三态返回结构稳定。
- LangSmith 抓取 demo-007 重跑时单条 ToolMessage 长度应下降到 KB 级以下。

## 模块 B · Prompt 单一来源与精度修复

### 现状

- 8 份 `src/trace/stages/*/prompts/*.md`（ground×2 + logical×3 + physical×3）与 `load_tgraph_contract_for(...)` 注入的 playbook 双源描述 TGraph API。
- playbook 源在 `src/tgraph/agent/playbooks/{capabilities,authoring,repair,validation,emission}.md`，由 `prompt_contracts.py` 按角色挑选拼装。
- `logical/prompts/author.md` 与 `playbooks/authoring.md`（实际描述 `check_interface` 的真正源头）都给人 segment 可选错觉；demo-007 `logical/repair_history.json` 第一轮失败正是 `check_interface(node)` 缺 segment。
- `logical/prompts/builder.md` 同时出现"不要发明 `segment` 等 IR 字段"与 `ensure_interface(..., segment=...)`，自我矛盾。
- 所有 prompt 都缺少"最后一条消息只输出动作摘要，不重述方案"约束。

### 设计

#### 改 prompts/*.md（角色级表层）

- `src/trace/stages/{ground,logical,physical}/prompts/*.md` 只保留：角色定位、任务模式、输出契约、关键禁忌、kind→tool 决策表（仅 physical author / repair 需要，详见模块 H）。
- 删除 prompts 中的所有 `## TGraph Check API` / `## Mutation Contract` API 清单条目。API 描述统一由 `load_tgraph_contract_for(audience)` 注入到独立 system 消息。
- `logical/prompts/builder.md` 删除 "Do not invent unsupported IR fields such as `segment`..." 一行；改为"不要发明 `zone` / `firewall_rules` / `software` / `packages` 等 IR 之外字段；`segment` 是 `ensure_interface` 的合法参数，请使用 ground 提供的节点 id 作为 segment"。
- 所有 prompts 末尾统一追加一句："Final message MUST be a one-sentence action summary; do not restate the artifact or repeat code."

#### 改 playbook（API 真正单一来源）

- `src/tgraph/agent/playbooks/authoring.md`（以及 `validation.md` 若也描述 check_interface）中 `tgraph.check_interface` 描述显式标注 `segment` 必填、`cidr` / `ip` / `link_key` 可选。
- `src/tgraph/agent/playbooks/capabilities.md` 中如有 `ensure_interface` / `check_interface` 描述同步修订。
- 若 `src/tgraph/agent/docs/tgraph_check_api.md` / `tgraph_editor_api.md` 也出现，再同步一次。
- 实现时先 grep `check_interface` 全仓所有出现处，逐个修订并以单元测试加固"`check_interface(node, segment=...)` 必填"的契约。

### 验证

- 测试 `load_tgraph_contract_for("logical_author")` 包含 `check_interface(node, segment=...)` 必填描述。
- 测试 prompts 不再包含独立 API 章节（grep `tgraph.check_` 在 `src/trace/stages/*/prompts/*.md` 命中 0 处）。
- demo-007 重跑：`logical/repair_history.json` 第一轮不再出现 `check_interface` 缺 segment 错误。

## 模块 C · LangGraph / LangChain 适配收敛

### 现状

- `RunState` / `GroundState` / `LogicalState` / `PhysicalState` 都是 `TypedDict(total=False)`，`events` / `repair_history` / `retry_history` 都在 node 内手写 `[*prev, *new]` 拼接。
- node 之间 `messages` 字段是覆盖式存储，跨 node 不可见。
- evaluator / validator 用 `state["next_action"]` 字段 + `add_conditional_edges` 二段式路由，路由表与状态更新分离。
- `LangChainRoleClient.invoke_agent` 把 `recursion_limit=max_tool_calls` 当作工具调用次数上限，但 react agent 每步至少消耗 2 次递归（model -> tool -> model），语义不一致。
- `LangChainRoleClient` 每次 `invoke_*` 都重新实例化 `ChatOpenAI(...)`，无缓存。
- README 已声明 LangGraph Checkpointer 暂未启用；`RunStorage` 自己承担了 resume 责任。

### 设计

整改分三档，按风险递增：

#### C1 reducer 与基础修正（低风险）

- `RunState` / `GroundState` / `LogicalState` / `PhysicalState` 的 `events`、`repair_history`、`retry_history` 等 list 字段改为 `Annotated[list[dict], operator.add]`。
- 删除所有 node 函数里 `state["events"] = [*state.get("events", []), ...]` 与 `state["repair_history"] = [*prior_ledger, entry]` 之类的手工拼接，改为返回部分更新让 reducer 自动合并；node 内只 `return {"events": [new_event]}` 即可。
- **`TraceRuntime._merge_stage_result` / `_merge_stage_exception` 同步改造**：当前实现里 outer run graph 节点在拿到 stage 返回后会再次 `merge_run_state(state, {"events": result["events"]})`；reducer 启用后必须避免双写：
  - 选项 a（推荐）：outer run state 的 `events` 字段也启用 reducer，`_merge_stage_result` 只 `return {"events": result["events"]}` 让 reducer 自动 append。
  - 选项 b：保留 `merge_run_state` 自己的语义不变，但 outer `RunState.events` 不启用 reducer，仅 stage 内部启用 reducer。
  实现时选 a，统一语义。
- `LangChainRoleClient` 内部按 `(role_name, model, temperature, base_url)` 元组缓存 `ChatOpenAI` 实例。
- `invoke_agent` 用 `create_react_agent(...)` 的内置 `max_steps`（如不存在则改用自定义 `should_continue`）控制工具步数；`max_tool_calls` 字段语义改名为 `max_react_steps`，并在 `MAX_TOOL_CALLS` 常量旁加注释明确含义。
- 为模块 G 做前置预留：本 PR 在 `RunState` 同时增加 `Annotated[list[dict], operator.add] escalation_history` 字段（默认空），避免后续 PR4 再动 RunState 形状。

#### C2 Command 化路由（中风险）

- evaluator / validator 节点的返回类型改为 `langgraph.types.Command[...]`：
  - `Command(goto="finalize", update={...})` 替代 `state["next_action"] = "finalize"` + 条件边。
  - `Command(goto="repair", update={...})` / `Command(goto=END, update={"error": ...})` 同理。
- stage `__init__.py` 中相应删除 `add_conditional_edges("validator", lambda state: state["next_action"], ...)`，因为路由信息回到节点函数内部。
- `next_action` 字段从 `GroundState`、`LogicalState`、`PhysicalState` 三处 TypedDict 中移除；所有引用该字段的测试与 reducer 调用一并修订。

#### C3 LangGraph Checkpointer 接入（高风险）

- 引入 `langgraph.checkpoint.sqlite.SqliteSaver`，存储路径 `runs/<run_id>/state.sqlite`。
- `TraceRuntime._build_run_graph()` 编译时传入 `checkpointer=SqliteSaver(...)`；`graph.invoke(initial, config={"configurable": {"thread_id": run_id}})`。
- `runs/<run_id>/state.sqlite` 加入 `.gitignore`。

**双轨语义（权威性 / 优先级 / 冲突解决）：**

| 关注点 | LangGraph Checkpointer | RunStorage |
|---|---|---|
| 角色 | runtime 恢复源（authority for `state.sqlite` 存在的 run） | 调试快照与跨工具契约 |
| 写入时机 | 由 langgraph 自动写（每个 node 边界）| `_merge_stage_result` 显式 flush |
| 包含内容 | 完整 LangGraph state（含未完成 stage 的中间态） | `run.json` + `<stage>/artifact.json` + `messages.json` + `tool_journal.json` + `events.jsonl` + `<stage>/mutations/*` |
| resume 时优先级 | 优先；只有当 sqlite 缺失或损坏才回退 | fallback |
| 冲突解决 | sqlite 的 stage state 与 RunStorage 的 artifact 不一致时，以 sqlite 为准；resume 后第一次写 stage snapshot 时用 sqlite 数据覆盖 RunStorage |

**`TraceRuntime.resume(...)` 改造：**

1. 检查 `runs/<run_id>/state.sqlite` 是否存在且可被 SqliteSaver 打开。
2. 若可用：
   - 用 `thread_id=run_id`、`checkpoint_ns=""`、`config={"configurable": {"thread_id": run_id}}` 让 langgraph 从最近 checkpoint 继续；`--from <stage>` 改为定位最近 `state["current_stage"] == <stage>` 的 checkpoint，调用 `get_state_history(...)` 找到目标 checkpoint id 后 invoke。
   - resume 路径下 RunStorage 仍然写入新的 stage snapshot，但起始 artifact 从 sqlite 恢复。
3. 若不可用：回退到现有 `RunStorage` 路径（基于 `<stage>/artifact.json`）。

**fork resume（new_run_id）行为：**

- `new_run_id` 模式下需要把源 `state.sqlite` 内容复制到目标路径并改写 `thread_id`。
- 简化方案：fork 时不复制 sqlite，强制回退到 RunStorage 路径，并在新 run 的 sqlite 里以源 RunStorage 快照为种子初始化；这意味着 fork resume 一律走 RunStorage 路径，不依赖源 sqlite。在 spec 落地时优先实现该简化方案。
- `--in-place` 模式直接复用源 sqlite，无需复制。

**存量 runs 迁移：**

- 既有 `runs/<run_id>/` 目录没有 `state.sqlite`。`resume` 自动走"不可用回退"分支，行为与改造前一致；不强制迁移。
- 文档 `README.md` 在 "从阶段恢复" 章节加一段说明：新 run 自带 sqlite；旧 run resume 走 RunStorage fallback，能力与之前等价但失去"中间态恢复"。

### 验证

- 现有测试 `tests/integration/test_runtime_pipeline.py` 与 `tests/unit/runtime/*` 必须仍然全绿。
- 新增测试：
  - reducer 行为：连续两个 node 各 append 一个 event，最终 events 长度 == 2。
  - Command 化：validator 返回 Command 时 state 与 goto 同步更新。
  - Checkpointer：模拟在 logical 中断后从 sqlite 恢复，验证 thread_id 复用 + RunStorage 快照独立可用。

## 模块 D · 文件读取与目录查询工具

### 现状

- `read_constraint_file`（在 `logical/nodes/author.py` 与 `physical/nodes/author.py` 内作为 agent tool 闭包定义）与 `read_support_file`（在 `repair_tools.py:StageRepairTools` 中定义）都直接返回整文件；demo-007 logical/repair_history.json 第 60-69 行可见 agent 读 17 条约束 JSON 只为查 lc17。
- `src/trace/tools/images/catalog.py` 已实现 `list_images()` / `get_image(image_id)` / `find_images(query, roles, node_type, limit)`，但仅通过 `image_catalog_prompt()` 整段 dump 进 system prompt，未暴露为 agent tool。

### 设计

- 抽取公共查询助手 `support_files.filtered_view(content, *, match=None, keys=None, head_lines=None) -> str`：
  - `match: str | None`：返回包含该子串的行（含上下 1 行）。
  - `keys: list[str] | None`：当文件为 JSON 对象时，仅返回这些顶层 key 对应子文档。
  - `head_lines: int | None`：仅返回前 N 行。
  - 多参数互斥（同时指定多个时按 `match > keys > head_lines` 优先级取最严格，并在 result 中携带 `warning`）；同时为空时回退整文件返回。
- 该助手在三处接入（参数 schema 通过同一个 pydantic 模型 `_FilteredReadInput` 复用，避免漂移）：
  - `StageRepairTools.read_support_file`（`repair_tools.py`）→ 既是底层方法，也通过 `read_support_file` agent tool 暴露。
  - `LogicalAuthorTools` 的 `read_constraint_file` agent tool 闭包（`logical/nodes/author.py`）。
  - `PhysicalAuthorTools` 的 `read_constraint_file` agent tool 闭包（`physical/nodes/author.py`）。
- 在 `StageRepairTools` 暴露 `list_support_files() -> { paths: list[str] }`，便于 agent 知道当前可访问的 support 文件清单。
- physical author / builder / repair tool 列表加入：
  - `find_images(query: str | None, roles: list[str] | None, node_type: str | None, limit: int = 10)`。
  - `get_image(image_id: str)`。
- system context 中删除 `image_catalog` 大段注入（即模块 H 配套），仅在 contract 中保留一句"使用 `find_images` / `get_image` 查询；不要凭记忆写 image_id"。

### 验证

- 单元测试 `read_support_file(path, match="lc17")` 返回包含 lc17 的命中片段，不含 lc1-lc16。
- 单元测试 `find_images(roles=["firewall"])` 返回 `img_pfsense`。
- demo-007 重跑：LangSmith trace 中 `find_images` 出现在 physical author 工具调用列表里。

## 模块 E · Node 记忆：产物指针 ledger

### 现状

- 每个 node 重新 `build_messages(...)`，把 evaluation_report、current_topology、constraints、ledger 全部当作"新对话"重塑。
- `repair_history` ledger 只摘要 `issue_kinds` / `attempted_actions`，不含上一轮写过的 mutation file 路径或 checkpoint file diff 摘要。
- agent 跨轮"忘记自己写过什么"，倾向于整体重写。

### 设计

- `_build_repair_ledger_entry(...)` 输出加入新字段 `produced_files`：

  ```python
  class ProducedFile(BaseModel):
      path: str                       # support file 相对路径，如 "logical/mutations/attempt_3.py"
      file_kind: Literal["mutation", "checkpoint"]
      node_targets: list[str]         # 排序去重；mutation 类来自 operations 聚合，checkpoint 类暂为空
      op_counts: dict[str, int]       # 仅 mutation 类填充；与 MutationSummary.op_counts 同源同 schema
      summary_one_line: str           # 见下方生成规则
      snapshot_path: str | None       # 仅 mutation 类填充；指向模块 F 落盘的 "<stage>/mutations/snapshots/attempt_N.json"
  ```

- `produced_files` 推断规则（系统侧确定性算法，不依赖 LLM）：
  - 扫描当轮 `_extract_tool_attempts(agent_result)` 输出，按 `tool` 字段筛选：
    - `write_mutation_file`：file_kind="mutation"。`path` 取 args.path；`node_targets` / `op_counts` 取**该 mutation 在同轮被** `execute_mutation_file` **成功执行后的 MutationSummary**（通过相邻 tool 调用配对识别；若 mutation 写完未执行则 node_targets=[]、op_counts={}）。
    - `write_checkpoint_file`：file_kind="checkpoint"。`node_targets=[]`；`op_counts={}`；`path` 取 args.path。
  - `summary_one_line` 生成规则：
    - mutation 类：按 `op_counts` 字段排序后拼接 `"set_image x3, set_flavor x3 on [SW_DMZ, SW_OFFICE, SW_OT]"`（节点列表超过 5 个时截断显示前 5 + `... +N more`）。
    - checkpoint 类：取 args.content 第一行注释或第一个 `def check_*` 函数名，形如 `"checkpoint defines: check_lc17, check_pc1"`（最多列前 5 个）。
  - `snapshot_path` 由模块 F 的 `execute_mutation_file` 后落盘动作填回；ledger 与 snapshot 一一对应。
- 下一轮 repair prompt 的 `recent_repair_ledger` section 在已有字段基础上展示 `produced_files`，提示 agent 如有需要可 `read_support_file(path=...)` 查看历史 mutation 文件。
- ledger 在 LangGraph reducer 模式下（模块 C1）作为 `Annotated[list[dict], operator.add]` 字段；PR 顺序上：**PR2（本模块）暂时保留 `[*prior_ledger, entry]` 的手工拼接**，待 PR3（C1 reducer）合并后再切换为返回部分更新；spec 落地时在 PR2 的代码注释中标记 TODO 链接到 PR3。

### 验证

- 单元测试：`_build_repair_ledger_entry` 给定一组 tool_calls 能产出正确 `produced_files`。
- demo-007 重跑：第 2 轮 repair prompt 内 `recent_repair_ledger` 含上一轮 mutation 文件 path 与 node_targets。

## 模块 F · Mutation 增量化与 inspect_graph diff 视图

### 现状

- `logical/prompts/builder.md` 明文 "Write one complete mutation file, normally `logical/mutations/build.py`"，鼓励整体写。
- demo-007 `physical/mutations/build.py` 只写了 2 个节点 image/flavor，遗漏 8 个 switch；attempt_1.py 才补全。
- `TGraphEditor.ensure_*` 全部幂等，技术层面早已支持增量。

### 设计

- 新增 `inspect_graph(view="diff", against="logical_reference" | "previous_attempt")` 子视图：
  - `against="logical_reference"`：物理 stage 专用，对比当前 physical graph 与传入的 logical 参考 graph 在 image/flavor 等 physical 字段上的差异。logical_reference 来自 `StageRepairTools.__init__` 的 `logical_reference_graph` 参数（physical stage 三个 node 已经传入）。
  - `against="previous_attempt"`：将最近一次成功 `execute_mutation_file` 后的 graph 快照作为基准，与当前 graph 比较。
  - 输出格式 `{ added_nodes: [...], removed_nodes: [...], changed_nodes: [{id, fields_changed: ["image", "flavor", ...]}], unchanged_count: N }`。

**snapshot 落盘与跨 node 接入：**

- `StageRepairTools.execute_mutation_file` 成功后落盘 `<stage>/mutations/snapshots/attempt_N.json`：
  - `N` 来源是 `StageRepairTools._mutation_index - 1`（写入后 `_mutation_index` 已自增）；与 `<stage>/mutations/attempt_N.py` 一一对应。
  - 由于 `_mutation_index` 是 StageRepairTools 实例字段，**跨 node 重新构造 StageRepairTools 时索引会重置**。修正方式：`StageRepairTools.__init__` 接收 `mutation_index_seed: int = 1` 参数；调用方（builder / repair node）在构造 StageRepairTools 时，从 state 的 `repair_history`（或新增的 `mutation_index` 字段）推断当前应使用的起始索引，确保 attempt 编号严格递增不冲突。
  - mutation file 写入路径由 `_next_mutation_path` 决定；snapshot 路径直接复用 attempt 号生成，避免分别推断。
- ledger（模块 E 的 `ProducedFile.snapshot_path`）记录 snapshot 路径。`inspect_graph(view="diff", against="previous_attempt")` 实现时按以下顺序定位 baseline：
  1. 从 `state["repair_history"][-1]["produced_files"]` 找到 `file_kind == "mutation"` 且 `snapshot_path` 非空的最新条目。
  2. 没有 ledger 时（如 builder 首轮后立即 diff），按 `<stage>/mutations/snapshots/` 目录下 attempt 号最大的 json。
- **与 E 的字段去重**：`ProducedFile.op_counts` 与 `MutationSummary.op_counts` 同源同 schema，复用同一推导函数 `_derive_op_counts(operations)`，避免维护两份。

**Prompt 调整：**

- 删除 builder / repair prompt 中 "Write one complete mutation file" 类表述。
- 改为 "First inspect current graph (use `inspect_graph(view='diff', against='previous_attempt')` if not the first attempt), then write only the `ensure_*` / `set_*` calls that change something. Skip operations whose target state already matches."。
- builder prompt 强调"对照 prepare 已 seed 的节点 inventory"，禁止重写节点列表。

### 验证

- 单元测试：`inspect_graph(view="diff", against="logical_reference")` 在 physical artifact 仅 image/flavor 不同 logical 时返回正确 changed_nodes。
- demo-007 重跑：`physical/mutations/build.py` 应一次性覆盖全部 10 个节点的 image/flavor，attempt_1.py 不再出现"补漏"用途。

## 模块 G · Escalation 反馈通道

### 现状

- `_next_unless_failed` 路由仅在 `status=="failed"` 时跳 END，没有反向通道。
- logical / physical 检出 constraint 冲突或 unsolvable 类问题时，要么 max_attempts 耗尽后失败，要么硬性 raise，无法回到 ground 调整 constraints。

### 设计

- 新增 issue kind 白名单常量 `ESCALATION_TO_GROUND_KINDS`，初始集合：
  - `logical.escalation.constraint_conflict`
  - `logical.escalation.no_satisfying_topology`
  - `physical.escalation.no_satisfying_image`
  - `physical.escalation.no_satisfying_flavor`
- validator 节点在生成 evaluation_report 后检查 issues：若任一 issue 的 `details.issue_kind` 命中白名单，则在 Command 化后的返回里 `goto="escalate"`，并附 `update={"escalation_report": {...}}`。
- stage 子图新增 `escalate` 出口（与 `finalize` / `failed` 并列），到达后让 stage 返回 `{ status: "escalated", escalation_report, partial_artifact }`。
- `TraceRuntime._run_logical` / `_run_physical` 中检测到 stage 返回 `escalated`，触发：
  - `RunState` 写入 `escalation_history`（含 stage_id, escalation_report, timestamp, source_run_id 等）。
  - 路由层不进 next stage，而是回到 `ground` 节点。
  - `_run_ground` 在新一轮调用时给 `run_ground_stage` 传入 `escalation_report`（新增可选参数）。
- `ground.author` 在收到 `escalation_report` 时：
  - 进入 `feedback_revision` 模式（与现有 evaluator feedback 复用）。
  - prompt context 多一段 `escalation_feedback`，说明"下游 stage 检测到这些 issue，请重新评估 constraints；如确认 unsolvable 请在 notes 中明确标记"。
  - ground evaluator 在 next attempt 中如果 author 标记 unsolvable，则置 `RunState.status="unsolvable"` 并直接走 END，附友好错误消息提醒用户检查 intent。
**escalation 计数器与 stage max_attempts 的关系（避免死循环）：**

- `RunState.attempt_counters["escalation"]` 是全局计数器，默认上限 2；每次任一 stage 触发 escalate 时 +1，达到上限即不再回流 ground，stage 直接走 `failed` 出口。
- 每次 escalation 后回到 ground 重新走 logical / physical 时，**logical / physical stage 内部的 `attempt` 重置为 1**（即一次 escalation 后给 stage 一个全新预算）。这是因为 escalation 的语义是"上一轮的 constraints 本身有问题，新一轮基于新 constraints 应该被公平对待"。
- 与 stage `max_attempts` 的优先级关系：在 validator 节点中，**先**检查 `attempt >= max_attempts`（即耗尽 repair 预算），**再**检查 issue 是否命中 escalation 白名单。这意味着：
  - 若 repair 预算耗尽且 issue 不含 escalation kind → `failed`。
  - 若 repair 预算耗尽且 issue 含 escalation kind → `escalate`（escalation 计数 +1，仍走回流）。
  - 若 repair 预算未耗尽且 issue 含 escalation kind → 直接 `escalate`，不再尝试 repair（这些 issue 不是 agent 能修复的）。
- 一次 stage 子图调用内 escalation 只触发一次（同一轮 validator 即使有多个白名单 issue，只生成一份 escalation_report 汇总）。

### 验证

- 单元测试：mock validator 注入 `logical.escalation.constraint_conflict` 的 issue，stage 返回 `escalated`，runtime 回到 ground 并触发 feedback_revision。
- escalation 上限测试：第 3 次 escalation 应 fail。
- 集成测试：构造一组明显冲突的 logical constraints（两条 chain 间矛盾），验证整条 escalation 链路。

## 模块 H · Physical Author：image/flavor 工具化与 kind 决策表

### 现状

- demo-007 `physical/checkpoints.py` 仅含 `check_pc1` / `check_pc2`，都是手写 capability 风格（pc1/pc2 的 kind 都是 `physical.image.capability`，缺少内置 check 是合理的）。
- 若 ground 产出 `physical.image.exact` / `physical.flavor.exact` / `physical.flavor.minimum` 类约束，prompt 没有引导 author 使用 `tgraph.check_image_exact` / `tgraph.check_flavor_exact` / `tgraph.check_flavor_minimum`。
- physical author / builder / repair 都没暴露 `find_images` / `get_image` 工具。

### 设计

- physical 三个 agent node（author / builder / repair）暴露 `find_images` / `get_image`（与模块 D 同一组实现）。
- `physical/prompts/author.md` 增加 "Kind→Tool Decision Table"（也写入 contract），简明列出：

```
physical.image.exact      -> tgraph.check_image_exact(node, image_id)
physical.image.capability -> custom check; must call find_images(...) to get candidate image_ids; use expected_image_ids in details
physical.flavor.exact     -> tgraph.check_flavor_exact(node, vcpu=..., ram=..., disk=...)
physical.flavor.minimum   -> tgraph.check_flavor_minimum(node, vcpu=..., ram=..., disk=...)
physical.custom           -> custom check
```

- prompt 顶部明确：非 `physical.custom` 与 `physical.image.capability` 的 kind 一律走对应 `tgraph.check_*`，不要包装 if-else 自定义实现。
- 不引入硬性 validator（用户已选 prompt_table 档），但保留扩展位：未来在 `validate_checkpoint_file` 内可以加 soft warning 检测，作为 follow-up。
- **删除 `image_catalog` 大段注入，三处接入点形式各不相同，需分别处理：**
  - `physical/nodes/author.py`：通过 `build_messages(..., system_context_sections={"image_catalog": image_catalog_prompt(), ...})` 注入 → 从 `system_context_sections` dict 删除 `image_catalog` 键。
  - `physical/nodes/builder.py`：同上 `system_context_sections` 形式 → 同样处理。
  - `physical/nodes/repair.py`：通过 `_build_repair_messages(..., image_catalog=image_catalog_prompt())` 函数参数传入，并在函数体内手动拼成 `{"role": "system", "content": "Image catalog for this repair round:\n\n" + image_catalog}` 这条独立 system message（`physical/nodes/repair.py:78`）→ 此处需删除该 system message 拼装，并相应删除函数 `image_catalog` 参数与调用方的 `image_catalog_prompt()` 调用。
  - image_catalog 仅留作 `find_images` / `get_image` 的内部数据源（仍 `from trace.tools.images.catalog import ...`）。
- physical builder prompt 增加一条："Use `find_images(node_type='switch')` to retrieve switch image and default_flavor; do not skip any switch node when authoring set_image / set_flavor calls." 直接定位 demo-007 漏写 switch image 的根因。

### 验证

- 单元测试：mock ground 产出含 `physical.image.exact` 的 constraint；author 产出的 checkpoints.py 包含 `tgraph.check_image_exact(...)` 调用而不是手写 if-else。
- demo-007 重跑：physical builder 第一轮 build.py 覆盖所有受 physical constraint 约束的节点（demo-007 中为 10 个 image/flavor 目标节点），不再出现"补漏"用途的 attempt_1.py。

## 落地分批

按风险隔离把模块拆为 4 批 PR：

1. PR1（表层整顿）：模块 A + B + D + H —— 不动 runtime / 状态机；预期能立即在 demo-007 重跑中体现 token 与轮数下降。
2. PR2（记忆与增量）：模块 E + F —— 改动 ledger 与 inspect_graph，依赖 PR1。
3. PR3（langgraph 收敛）：模块 C1 + C2 —— reducer / Command / role_client 缓存；中风险。
4. PR4（runtime 大改）：模块 C3 + G —— Checkpointer 接入与 escalation；高风险，单独评审。

每批 PR 单独跑 `python -m pytest -q` + `trace run tests/demo/demo.md --run-id smoke-...` 双重验证。

## 兼容性与回归风险

- 模块 A 改变 `execute_mutation_file` 默认返回结构 → 现有依赖完整 `graph` 字段的测试需要显式 `include_graph=True`；扫描 `tests/` 列出受影响测试一并修正。
- 模块 C1 的 reducer 改造对手写 `state["events"] = [*..]` 模式是破坏性变更 → 一次性整改所有 stage node。
- 模块 C2 Command 化删除 `next_action` 字段；任何读取该字段的测试需要改读 Command.goto 或仅断言图终态。
- 模块 C3 引入 sqlite 依赖 `langgraph-checkpoint-sqlite`，pyproject 收窄到 langgraph 1.1 兼容版本族。
- 模块 G escalation 链路允许 ground 被重新进入；需要确保 `RunStorage.write_stage_snapshot` 在二次进入时不覆盖旧 ground snapshot，而是写入 `ground-escalation-001/` 子目录（待 PR4 二次细化）。

## 待 follow-up（不在本次范围）

- 跨 run 长期记忆（user-level memory）。
- frontend 可视化对接 escalation 报告。
- target emit / translate stage 接入新工具表。
- physical checkpoint soft warning（kind 决策表的硬校验版本）。

## 实施期注意点（writing-plans 落地时点到）

- **NI-1（模块 A）**：`MutationSummary.affected_node_ids` 推导规则需补全 `ensure_interface.segment`（segment 也是节点 id，应纳入 affected_node_ids）与 `remove_links.ports_removed`（格式为 `"<node>.<port>"`，需提取 node 部分）两类边缘情况。
- **NI-2（模块 E）**：`ProducedFile` 与 mutation 执行结果配对应按 `args.path` **精确匹配**对应的 `execute_mutation_file` 调用（同一 path 的最近一次成功执行），而不是"相邻 tool 调用"启发式；否则 agent 在同一轮里 write A → write B → execute B → execute A 这类乱序场景会错配。
- **NI-3（模块 B）**：playbook 修订时需在 `tgraph.check_interface` / `tgraph.ensure_interface` 描述里**显式区分** `segment` 作为函数参数（指代邻接的 switch / 网段载体节点 id）vs 作为 IR 字段（不存在）的同名不同物语义；建议在描述里加一句"`segment` is the neighboring switch node id, not a top-level node IR field"。

## 决策摘要

| 决策项 | 选择 | 落地模块 |
|---|---|---|
| 改造范围 | 最大档：A+B+C(1/2/3)+D+E+F+G+H | 全部 |
| execute_mutation_file 默认返回 | summary 模式，include_graph 显式 | A |
| TGraph API 单一来源 | `tgraph_contract`（playbook + agent/docs），prompt.md 不再列 API | B |
| Agent 记忆模型 | ledger 产物指针 | E |
| image / flavor 访问 | find_images / get_image agent tool；删除 system prompt 大段注入 | D + H |
| kind→check 函数 | physical author prompt 决策表（轻量软引导） | H |
| escalation 触发 | issue kind 白名单 | G |
| escalation 入口 | ground.author（feedback_revision 模式） | G |
| Checkpointer backend | SqliteSaver，与 RunStorage 双轨 | C3 |
| 增量化辅助 | 新增 inspect_graph(view="diff") 子视图 + prompt 配合 | F |
