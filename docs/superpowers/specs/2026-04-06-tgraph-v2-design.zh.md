# TGraph v2 设计

## 状态

这是 TRACE 下一代 TGraph 抽象的已确认设计草案。

## 背景

TRACE 目前主要把 TGraph 当作一种 JSON 形态的 schema 对象，用在阶段产物、校验、补丁和提示词契约里。这个格式适合做工件交换，但如果直接拿它承担运行时拓扑抽象，会显得过于单薄，无法很好支撑：

- 拓扑构建
- 拓扑查询
- 图结构分析
- checkpoint 编译
- 迭代修复

TGraph v2 的核心思路，是把交换格式和运行时图对象分离，同时保持与当前 logical / physical 流程兼容。

## 目标

TGraph v2 必须：

- 保持当前 logical 与 physical 阶段使用的 artifact 形状
- 通过受约束的运行时 API 支持安全构建和修改
- 借助 NetworkX 提供图算法支持，但不让 NetworkX 成为 source of truth
- 支持迭代式校验和修复
- 保留 benchmark 和 stage-specific 的语义约束

TGraph v2 不打算成为一个通用图类库。

## 非目标

TGraph v2 不追求：

- 向 Agent 直接暴露原始 NetworkX API
- 把 NetworkX 当作主存储格式
- 把所有校验规则揉成单层、无区分的 validator
- 在事务边界之外允许无约束的就地修改

## 核心模型

TGraph v2 分为两层。

### TGraphJSON

`TGraphJSON` 是交换格式和持久化格式。

职责：

- artifact 载荷格式
- LLM 输入输出契约
- JSON 序列化
- JSON 反序列化
- 与当前 prompts 和阶段 schema 保持兼容

规范顶层结构：

```python
{
    "profile": str,
    "nodes": list[NodeJSON],
    "links": list[LinkJSON],
}
```

`NodeJSON`：

```python
{
    "id": str,
    "type": "switch" | "router" | "computer",
    "label": str,
    "ports": list[PortJSON],
    "image": dict | None,
    "flavor": dict | None,
}
```

`PortJSON`：

```python
{
    "id": str,
    "ip": str,
    "cidr": str,
}
```

`LinkJSON`：

```python
{
    "id": str,
    "from_port": str,
    "to_port": str,
    "from_node": str | None,
    "to_node": str | None,
}
```

说明：

- `from_port` 和 `to_port` 出于兼容性保留在 schema 中，但 link 在语义上是无向的。
- `from_node` 和 `to_node` 是冗余导出字段，不是 source of truth。
- 规范化步骤可以对端点顺序做 canonical ordering，以得到稳定的 link id。

### TGraphRuntime

`TGraphRuntime` 是由 `TGraphJSON` 初始化得到的运行时语义图。

职责：

- 受控构建与修改
- 拓扑和语义查询
- 图结构分析
- 校验编排
- 基于事务的编辑
- 导出回 `TGraphJSON`

`TGraphRuntime` 是系统代码实际操作的图对象；`TGraphJSON` 仍然是跨阶段边界传递的对象。

## 图语义

拓扑在语义上是无向多重图。

这意味着：

- 同一对节点之间可以存在多条链路
- 链路方向没有语义意义
- 一个 port 最多参与一条 link
- NetworkX 只是算法后端，不是 source of truth

主算法投影：

- `nx.MultiGraph`

临时算法视图：

- 某些 NetworkX 算法如果不直接支持 `MultiGraph`，运行时可以按需派生一个临时视图供该算法使用
- 这些派生视图不是运行时状态，也不参与 source-of-truth 管理

## 运行时权威状态

运行时层只维护一份规范语义状态，并从中派生索引。

建议的运行时存储：

```python
nodes_by_id: dict[str, NodeRecord]
ports_by_id: dict[str, PortRecord]
links_by_id: dict[str, LinkRecord]
```

建议的派生索引：

```python
node_ports: dict[str, list[str]]
port_owner: dict[str, str]
port_link: dict[str, str | None]
```

建议的图缓存：

```python
_nx_multi: nx.MultiGraph
```

Record 约定：

- `NodeRecord` 表示节点级字段和 port 归属关系
- `PortRecord` 包含 owner 信息
- `LinkRecord` 只存 endpoint ports
- 冗余的 node endpoint 字段只在导出时补齐，不作为运行时真相维护

## 校验模型

校验仍然采用与你当前设计一致的四层流水线。

### F1：format

目的：

- 校验输入 payload 是否具备初始化所需的顶层 JSON 结构

示例：

- payload 不是对象
- 缺少顶层字段
- 顶层字段类型错误

### F2：schema

目的：

- 校验 `TGraphJSON` 能否初始化成 `TGraphRuntime`
- 校验对象级 schema 和 profile-aware 字段要求

示例：

- node / port / link 字段类型错误
- 不支持的 node type
- image / flavor 结构错误
- profile 取值错误

规则：

- logical 阶段不要求 `computer.image` 和 `computer.flavor`
- physical 阶段可以要求 `computer.image` 和 `computer.flavor`

### F3：consistency

目的：

- 校验初始化后或修改后的运行时语义一致性

示例：

- node id 重复
- port id 重复
- link id 重复
- endpoint 引用缺失
- owner 不一致
- 规范化后 link id 不匹配
- IP 或 CIDR 非法
- switch / router 语义违规
- 某个 port 参与多于一条 link

这一层是细化图不变量和结构一致性规则的主要位置。

### F4：intent

目的：

- 校验更高层的 benchmark、checkpoint 和编译意图

示例：

- checkpoint selector 无法解析
- 预期唯一的 selector 出现歧义
- 编辑后 checkpoint 仍引用过时 id
- 拓扑违反 benchmark 特定设计意图

## 不变量

除非某个阶段策略明确放宽，否则下列规则属于运行时语义正确性的一部分：

- node id 全局唯一
- port id 全局唯一
- link id 全局唯一
- 每个 port 的 owner 存在
- 每条 link 的 endpoint 必须引用现有 port
- 每个 port 恰好属于一个 node
- 每个 port 最多属于一条 link
- 内部索引与规范运行时状态一致
- link 在语义上是无向的
- 如果导出冗余的 `from_node` / `to_node`，则必须与 port owner 一致

诸如 `computer.image` / `computer.flavor` 这类 profile-specific 规则，不属于核心不变量集合。

## API 设计

这里需要明确区分三层概念：

- runtime 内部方法
- transaction 编辑原语
- Agent 实际可见的使用面

不是所有 runtime 方法都应该直接暴露给 Agent。

### 读取 API

```python
get_node(node_id) -> NodeRecord
get_port(port_id) -> PortRecord
get_link(link_id) -> LinkRecord

list_nodes() -> list[str]
list_ports(node_id: str | None = None) -> list[str]
list_links() -> list[str]

get_port_owner(port_id) -> str
list_node_ports(node_id) -> list[str]
get_link_ports(link_id) -> tuple[str, str]
get_peer_port(port_id) -> str | None
get_peer_node(port_id) -> str | None

neighbors(node_id) -> list[str]
incident_links(node_id) -> list[str]
adjacent(node_a, node_b) -> bool
degree(node_id) -> int
```

命名规则：

- 单对象读取统一用 `get_*`
- 列表读取统一用 `list_*`
- 谓词查询统一用 `select_*`
- 修改统一用 `add_*`、`update_*`、`remove_*`、`rename_*`、`rewire_*`

### 选择器 API

```python
select_nodes(**predicates) -> list[str]
select_ports(**predicates) -> list[str]
select_links(**predicates) -> list[str]

select_one_node(**predicates) -> str | None
select_one_port(**predicates) -> str | None
select_one_link(**predicates) -> str | None
```

说明：

- `count_*` 不再单列，因为它本质上等于 `len(select_*(...))`
- `select_one_*` 比 `select_unique_*` 更适合 Agent 使用，语义也更直观

### 图分析 API

```python
connected(node_a, node_b) -> bool
shortest_path(node_a, node_b) -> list[str]
all_simple_paths(node_a, node_b, cutoff=None) -> list[list[str]]

bridges() -> list[tuple[str, str]]
articulation_points() -> list[str]
cycle_basis() -> list[list[str]]
core_number() -> dict[str, int]
k_core(k=None) -> set[str]
betweenness(node_id: str | None = None) -> dict | float
```

说明：

- `path_exists` 被省略，因为在无向拓扑图里它和 `connected` 语义重复
- 某些分析方法可按需创建临时的 NetworkX 算法视图
- 这些临时视图不属于运行时状态

### 转换 API

```python
from_json(obj: dict) -> TGraphRuntime
to_json() -> dict
to_networkx() -> nx.MultiGraph
```

`to_networkx()` 的目的是暴露算法支持，不是把运行时状态所有权交给外部。

## 事务模型

所有运行时修改都应该经过显式事务。

事务模型不是专门为 LangGraph 节点设计的，它是统一的编辑基元，适用于：

- 图补全
- 图修复
- 将来的交互式编辑

示例：

```python
tx = graph.begin_transaction()
tx.add_node(...)
tx.add_port(...)
tx.add_link(...)
tx.update_node(...)
tx.update_port(...)
tx.update_link(...)
tx.remove_link(...)
tx.rewire_link(...)

preview = tx.validate(levels=["f1", "f2", "f3"])
result = tx.commit(levels=["f1", "f2", "f3"])
```

事务职责：

- 在可变工作副本上执行修改
- 允许中间态暂时不一致
- 在编辑过程中维护临时索引
- 提交前统一校验
- 产出 `change_map`
- 原子提交或回滚

### 提交策略

事务默认不要求通过全部 `f4`。

建议规则：

- build 和 iterative repair 的提交只要求通过 `f1`、`f2`、`f3`
- `f4` 可以在迭代过程中部分未解决
- 只有阶段 finalize 或显式 strict validation，才要求通过 `f1` 到 `f4`

这样 Agent 就可以一次只修复一部分问题，只要这次修改在结构上是健康的，就应允许提交，然后继续迭代。

建议事务结果结构：

```python
{
    "ok": bool,
    "issues": list[Issue],
    "change_map": dict,
}
```

建议 `change_map` 结构：

```python
{
    "node_ids": {"old": "new"},
    "port_ids": {"old": "new"},
    "link_ids": {"old": "new"},
    "updated_targets": list[str],
}
```

## 修复模型

`repair` 更适合作为“基于事务的工作流概念”，而不是 runtime 核心对象必须提供的方法。

也就是说：

- runtime core 必须支持 transaction-based editing
- 系统上层可以选择性提供 `repair(...)` 这类便利封装
- 如果 Agent 已经通过 Python 代码直接操作事务模型，那么不一定还需要单独暴露 `repair()`

可选的高层封装：

```python
repair(issue: Issue, strategy: str | None = None) -> RepairResult
repair_all(issues: list[Issue]) -> list[RepairResult]
```

修复流程：

1. 接收一个 issue 或 issue 子集
2. 选择若干 transaction primitive
3. 在事务中执行
4. 按当前提交策略做校验
5. 如果上层需要，再返回结构化的 `RepairResult`

建议保留的编辑原语：

- `add_node`
- `add_port`
- `add_link`
- `remove_link`
- `rewire_link`
- `rename_port`
- `rename_link`
- `normalize_link_endpoints`
- `fix_invalid_ip`
- `fix_invalid_cidr`

## Agent 使用面

Agent 不应该在 prompt 里背负完整 runtime API。

更推荐的模式是：

- 给 Agent 少量读取 helper
- 让 Agent 通过 Python 代码拿事务对象编辑图
- 把 repair 作为 workflow 概念，而不是对象级强制方法

建议最小 Agent 可见操作：

- `get_node`
- `get_port`
- `get_link`
- `list_nodes`
- `neighbors`
- `select_nodes`
- `select_ports`
- `select_links`
- `validate`
- `begin_transaction`

在事务中，Agent 只需要掌握一套很小、很规则的动词集合：

- `add_*`
- `update_*`
- `remove_*`
- `rename_*`
- `rewire_*`
- `commit()`
- `rollback()`

Agent 不应直接接触原始 NetworkX 方法或内部索引。

## 一次性迁移策略

TGraph v2 不再建议长期保留旧的函数式工具层与新的 runtime 层并行存在，而是建议一次性迁移完成后直接移除旧层。

迁移目标：

- 用 `TGraphJSON + TGraphRuntime + Transaction` 替换当前 `model.py + patch.py + query.py`
- 用 runtime-aware validator 替换仅围绕 JSON 结构工作的校验逻辑
- 让 logical / physical 的 build、validate、repair 统一围绕 runtime 和 transaction 工作
- 迁移完成后删除旧的函数式 patch/query 接口，避免双轨维护

建议的一次性迁移范围：

- `src/trace/tools/tgraph/`
- `src/trace/stages/logical/prepare.py`
- `src/trace/stages/logical/subgraph.py`
- `src/trace/stages/logical/schemas.py`
- `src/trace/stages/logical/validator.py`
- `src/trace/stages/physical/prepare.py`
- `src/trace/stages/physical/subgraph.py`
- `src/trace/stages/physical/schemas.py`
- `src/trace/stages/physical/validator.py`
- 对应的 `tests/unit/tools/tgraph/`、`tests/unit/config/test_prompts.py`、`tests/integration/test_runtime_pipeline.py`

迁移完成后的目标状态：

- 所有 stage artifact 仍然传递 `TGraphJSON`
- 所有规范化、验证和编辑行为都围绕 `TGraphRuntime`
- build 和 repair 使用同一套 transaction primitive
- 不再存在旧版 `apply_patch_ops()` 和独立 `query.py` 之类的旁路入口

## Agent / TGraph 工具协议

如果希望 Agent 通过 Python 代码操作 TGraph，不建议一开始就给它一个任意 Python 执行沙箱；更稳妥的做法是提供一层很薄的工具协议，再由工具内部调用 `TGraphRuntime` 和 `Transaction`。

推荐协议：

### 图对象加载

```python
tgraph_load(graph_json: dict) -> graph_handle
```

职责：

- 从 `TGraphJSON` 构建 `TGraphRuntime`
- 返回一个当前对话或当前节点生命周期内可用的句柄

### 只读操作

```python
tgraph_read(handle, op: str, args: dict | None = None) -> Any
```

示例 `op`：

- `get_node`
- `get_port`
- `get_link`
- `list_nodes`
- `neighbors`
- `select_nodes`
- `validate`

### 事务开启

```python
tgraph_begin_tx(handle) -> tx_handle
```

### 事务操作

```python
tgraph_tx_apply(tx_handle, op: str, args: dict | None = None) -> Any
```

示例 `op`：

- `add_node`
- `add_port`
- `add_link`
- `update_node`
- `update_port`
- `remove_link`
- `rename_port`
- `rewire_link`

### 提交与回滚

```python
tgraph_tx_commit(tx_handle, levels: list[str] | None = None) -> dict
tgraph_tx_rollback(tx_handle) -> None
```

这个协议的关键点是：

- Agent 感知到的是“我在通过 Python 语义操作图”
- 实际上它不是在拿一个任意 Python 解释器，而是在调用一层受控 API
- build 阶段和 repair 阶段都使用同一套接口
- LangGraph 节点侧只需要负责注入当前 graph handle / tx handle，不需要重新发明一套 patch 语言

## 已确认的设计约束

- logical 阶段不要求 `computer.image` 或 `computer.flavor`
- physical 阶段校验可以要求这些字段
- 拓扑在语义上是无向多重图
- NetworkX 的角色是提供图算法
- 一个 port 最多参与一条 link
- transaction commit 默认不要求完全通过 `f4`
- repair 基于事务，但可以只作为工作流概念存在，而不是 runtime 必备方法
- 推荐一次性迁移并移除旧的函数式 TGraph 工具层
- 推荐 Agent 通过一层薄工具协议驱动 runtime / transaction，而不是直接执行任意 Python

## 总结

TGraph v2 在保留现有 JSON artifact 契约的前提下，引入真正的运行时语义图，用于受控修改、校验、分析和迭代修复。它的核心设计选择不是“把当前 schema 做厚”，而是“把交换格式和运行时行为拆开”，同时保持 TRACE 各阶段对外看到的拓扑形状不变。
