# Physical Stage 架构说明

Physical stage 在 logical graph 基础上补充部署字段，例如 `image` 和 `flavor`，同时保持 logical topology identity。

## 1. Artifact 合约

`PhysicalArtifact` 只包含：

- `graph`
- `constraint_files`
- `checkpoint_files`

典型文件引用：

```json
{
  "constraint_files": {"physical": "ground/physical_constraints.json"},
  "checkpoint_files": {"physical": "physical/checkpoints.py"}
}
```

## 2. Prepare 策略

`physical.prepare` 从 `logical_artifact.graph` 派生 physical graph：

- 不新增 logical node。
- 不删除 logical node。
- 不改 logical link identity。
- 按 node type 填默认 `image` / `flavor`。
- 挂载 `ground/physical_constraints.json`。

特殊 image / flavor 意图由 physical author / repair 后续调整。

## 3. Checkpoint 文件

`ground/physical_constraints.json` 是 JSON object，key 是 constraint id：

```json
{
  "pc1": {
    "kind": "physical.image.capability",
    "statement": "FIREWALL must use an image compatible with firewall appliance capability."
  }
}
```

`physical/checkpoints.py` 每条 constraint 对应一个函数：

```python
def check_pc1(tgraph):
    return tgraph.check_image_exact("FIREWALL", image_id="img_firewall")
```

第一版的 image / flavor capability 知识来自 Agent 可读的静态文档。TGraph 不查询 provider catalog，也不自行推断 capability。

## 4. 节点职责

| 节点 | 类型 | 主要职责 |
| --- | --- | --- |
| `prepare` | 脚本 | 从 logical graph 派生 physical graph，填默认部署字段 |
| `author` | Agent | 读取 physical constraints 和静态知识，写入 `physical/checkpoints.py` |
| `builder` | LLM | 补全部署字段，保持 topology |
| `validator` | 脚本 | 检查 F1-F4、topology preservation、required fields 和 authored checkpoints |
| `repair` | Agent | 用 mutation file 修 graph / image / flavor，用文件工具修 checkpoint |
| `finalize` | 脚本 | 校验 artifact 合约并封装 stage 结果 |

## 5. Repair 工具边界

Physical repair 工具面：

- `inspect_graph`
- `read_support_file`
- `write_checkpoint_file`
- `write_mutation_file`
- `execute_mutation_file`
- `validate_graph`

Graph、image、flavor 修改必须通过 mutation file 执行。Checkpoint 修改直接重写 `physical/checkpoints.py`。

## 6. 参考文档

- `src/tgraph/agent/docs/fact-kinds.md`
- `src/tgraph/agent/docs/checkpoint-files.md`
- `src/tgraph/agent/docs/mutation-files.md`
- `src/tgraph/agent/docs/catalogs.md`
