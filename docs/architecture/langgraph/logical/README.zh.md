# Logical Stage 架构说明

Logical stage 基于 `ground_artifact` 生成 logical TGraph，并通过 `validator -> repair` 循环修复，直到满足逻辑层约束。

## 1. Artifact 合约

`LogicalArtifact` 只包含：

- `graph`
- `constraint_files`
- `checkpoint_files`

典型文件引用：

```json
{
  "constraint_files": {"logical": "ground/logical_constraints.json"},
  "checkpoint_files": {"logical": "logical/checkpoints.py"}
}
```

## 2. Constraint / Checkpoint 文件

`ground/logical_constraints.json` 是 JSON object，key 是 constraint id：

```json
{
  "lc9": {
    "kind": "logical.topology.chain",
    "statement": "explicit chain WEB -> SW_DMZ -> R_CORE."
  }
}
```

`logical/checkpoints.py` 每条 constraint 对应一个函数：

```python
def check_lc9(tgraph):
    return tgraph.check_chain(["WEB", "SW_DMZ", "R_CORE"])
```

validator 不解析 `statement` 执行语义，只用它做错误 provenance。真正的检查逻辑来自 checkpoint 函数。

## 3. 节点职责

| 节点 | 类型 | 主要职责 |
| --- | --- | --- |
| `prepare` | 脚本 | 根据 `node_groups` 初始化 logical skeleton，只生成节点，写入 constraint file 引用 |
| `author` | Agent | 读取 `ground/logical_constraints.json`，写入并校验 `logical/checkpoints.py` |
| `builder` | LLM | 基于 skeleton 和 grounded facts 生成 logical graph |
| `validator` | 脚本 | 运行 F1-F4 校验，执行 file-backed checkpoints |
| `repair` | Agent | 用 mutation file 修 graph，用文件工具修 checkpoint |
| `finalize` | 脚本 | 校验 artifact 合约并封装 stage 结果 |

## 4. Repair 工具边界

Logical repair 工具面：

- `inspect_graph`
- `read_support_file`
- `write_checkpoint_file`
- `write_mutation_file`
- `execute_mutation_file`
- `validate_graph`

Graph 修改必须通过 mutation file 执行。Checkpoint 修改直接重写 `logical/checkpoints.py`。最终 artifact 只保留文件引用。

## 5. 参考文档

- `src/tgraph/agent/docs/fact-kinds.md`
- `src/tgraph/agent/docs/checkpoint-files.md`
- `src/tgraph/agent/docs/mutation-files.md`
- `src/tgraph/agent/docs/naming.md`
