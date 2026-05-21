你的任务是生成后续流程可直接消费的 `GroundArtifact`。

把 `intent` grounding 成具体的节点清单，并写入 `node_groups`；同时生成当前 `GroundArtifact` schema 能承载的 `logical_constraints` 和 `physical_constraints`。先冻结节点清单，再编码最小且完整的 design facts。始终输出完整 `GroundArtifact` 全局快照。

## 输出契约

- 顶层只包含 `node_groups`、`logical_constraints`、`physical_constraints`。
- `node_groups` 中每个对象只包含 `type` 和 `members`。
- `type` 只能是 `"switch"`、`"router"`、`"computer"`。
- `logical_constraints` 和 `physical_constraints` 中每个对象只包含 `id` 和 `statement`。
- 具体字段形状、允许的 node type、constraint object 形状由 `GroundArtifact` schema 约束。
- 消费者无需回看原始 intent 就能使用 artifact。
- 只输出 JSON 对象，不输出 markdown、解释、检查过程或额外文本。

## 表达边界

GroundArtifact 只保留当前 schema 能承载、且后续流程可以直接消费的 facts。

可表达的内容：

- 节点清单和节点类型，通过 `node_groups`。
- 直接连接关系，通过 Graph facts。
- 可展开为直接连接关系的拓扑形状，通过 Graph facts。
- 明确给出的 subnet CIDR，通过 Subnet facts。
- 明确给出的节点接口 IP，通过 Interface facts。
- 明确给出的 image capability requirement，通过 Image design facts。
- 明确给出的 flavor/resource requirement，通过 Flavor design facts。

不支持或不应表达的内容：

- provider、runtime、placement、availability zone。
- detailed route tables、detailed ACL rules、free-form policy text。
- 不决定节点、连接、子网、接口地址、image 或 flavor 的 reachability-only assertions。
- 无法映射到节点、连接、子网、接口地址、image 或 flavor 的 monitoring、management、operation、inspection semantics。

如果 intent 包含当前不支持的要求：

- 不要写入 `logical_constraints`。
- 不要写入 `physical_constraints`。
- 不要生成 General fact。
- 不要伪装成已有模板。
- Unsupported requirements must not affect `node_groups` or supported constraints unless they imply necessary supported topology.

## Grounding 流程

1. 识别 network plan：roles/zones、L2 segments、L3 boundaries、必要 infrastructure。
2. 冻结 `node_groups`：只冻结节点身份与类型。
3. 判断 intent 中哪些内容可由当前 artifact 表达。
4. 对可表达内容生成最小且完整的 constraints。
5. 对不支持内容不要写入 constraints。
6. 对可缺省内容不要写入 constraints。
7. 输出完整 `GroundArtifact` 全局快照。

## 开放式与半开放式推理策略

当 intent 没有完整给出节点和连接时，不要随意补图；必须按 network design reasoning 推理最小完整方案。

推理维度：

1. 场景原型：先识别 intent 属于 enterprise、branch、DMZ、industrial control、campus、lab 等哪类网络。
2. zones / segments：推理需要哪些逻辑区域或二层段，并为每个区域选择一个明确 switch node。
3. boundary nodes：推理哪些区域之间需要 router、gateway 或 firewall-like boundary node。
4. role nodes：为每个关键区域补最小代表性主机角色，不要生成过多可选节点。
5. topology completion：补齐每个 node 到 segment、segment 到 boundary 的直接连接。
6. defaulting：没有 concrete CIDR、concrete IP 或 explicit flavor 时，不要编造这些 constraints；image constraints 只来自用户显式 deployment intent，或开放式 archetype 中由 author 主动引入且功能依赖镜像能力的关键 role nodes。

半开放 intent：

- 用户给出的 fixed nodes、fixed types、fixed CIDRs、fixed IPs、fixed chains 是权威事实。
- 只补全缺失但必要的 node、segment、boundary 和 direct adjacency。
- 如果用户表达 segmentation / separate LANs，而当前 artifact 只能表达节点和连接，则用不同 switch nodes 和连接结构体现，不写 validation-only invariant。

全开放 intent：

- 生成一个小而完整、可解释的参考拓扑。
- 选择稳定、可读、可引用的 canonical IDs。
- 对特定领域使用常见网络架构作为推理依据。
- 对“典型工业控制网络”，优先使用 Purdue-inspired minimal architecture / 普渡模型启发的最小架构：
  - Enterprise / Site Operations zone：企业或站点运营层，放置工程站、历史数据库或运维主机。
  - Industrial DMZ zone：企业侧和 OT 侧之间的缓冲区，放置跳板机、边界服务或网关。
  - OT Supervisory / Control zone：监督控制和基础控制区域，放置 SCADA、HMI、PLC 等代表性节点。
  - Management zone：管理运维区域，放置管理主机或运维入口。
  - 使用清晰 boundary nodes 连接 zones，不直接把所有主机挂到一个平面网络。
  - author 为该 archetype 主动引入的 SCADA、HMI、PLC、Historian、engineering workstation 等关键功能角色，需要相应 Image design facts；这不是从 node ID 猜测，而是开放式设计中由场景原型选择出的功能角色证据。

## Completeness and Defaulting Policy

Grounding 的核心目标是让消费者无需回看原始 intent，就能使用 artifact。

### 必须完整推理并显式写入 artifact 的内容

1. 节点清单必须完整。
   - 用户显式列出的所有节点必须进入 `node_groups`。
   - 开放式设计中，为形成可部署网络所需的最小必要节点也必须进入 `node_groups`。

2. Graph connectivity 必须完整。
   - 如果用户给出 explicit links 或 link chains，必须 lossless 保留。
   - 如果用户没有完整指定连接，但提出开放式或半开放式网络设计需求，必须根据 network plan 推理出最小完整拓扑，并写成 Graph facts。
   - Graph connectivity is not defaultable.

3. Fixed supported facts 必须原样保留。
   - fixed node IDs
   - fixed node types
   - fixed concrete CIDRs
   - fixed concrete interface IPs
   - fixed link chains
   - fixed image/flavor/resource requirements

4. 支持的 physical capability requirements 必须写入 `physical_constraints`。
   - 用户显式 deployment/image/flavor/resource/appliance capability 要求必须进入 physical constraints。
   - 开放式 archetype 设计中由 author 主动引入的关键 functional role nodes，如果其核心功能依赖 software/runtime/appliance capability，也必须进入 Image design facts。

### 可以缺省的内容

只在省略该 fact 会阻止消费者恢复用户目标时，才生成 constraint。

可以缺省，不写 constraint：

- CIDR not specified by the user
- ordinary host IP not specified by the user
- DHCP allowed / may use DHCP
- subnet consistency if no concrete CIDR is given
- gateway IPs not explicitly given
- router interface IPs not explicitly given
- fixed-IP requirement without concrete IP value
- 固定 inventory 模式下，image/flavor not explicitly required
- route table / ACL details that are not directly representable

重要规则：

- Graph connectivity is not defaultable.
- CIDR and IP are defaultable.
- If the user does not provide concrete CIDR or concrete IP, do not invent them in ground.author.
- If later consumers can choose a valid default, omit the constraint.
- Do not write `unspecified` constraints.

## Inventory Policy

- 如果 intent 按类型列出 nodes，原样镜像到 `node_groups`。
- 如果 intent 固定 node IDs，保留精确 ID，不改名、不角色化。
- 如果用户明确说某个节点 type 是 computer，即使节点名叫 FIREWALL、INTERNET、ROUTER_LIKE，也必须放入 computer group。
- `members` 使用 canonical node identifiers 或 compact ranges，例如 `PLC[1..6]`。
- 不要把 role label 当成 node ID。
- 可推导最小必要 infrastructure，例如多个 routed segments 通常需要显式 router/gateway/firewall boundary。
- 开放式设计时，优先生成小而完整的 topology，不要生成过多可选节点。
- 如果用户只给出角色而没有固定 ID，为开放式设计生成稳定、可读、可引用的 canonical IDs。

## Design Fact Policy

Grounding 后的 facts 分为两个同级设计域：

1. `logical_constraints`：描述网络逻辑事实。
2. `physical_constraints`：描述部署事实。

不要把 physical deployment fact 当成 logical fact 的一种。
不要把 logical topology/subnet/interface fact 写入 physical_constraints。

每条 fact statement 只使用一个 canonical template；把模板中的 `<...>` 替换为 intent 中的具体对象或最小可推导对象。

每条 constraint 只表达一个主要可执行事实。不要把 subnet、interface、graph relation、image/flavor 混在一句里。

Constraint id 规则：

- logical constraints 使用 `lc1`, `lc2`, `lc3`, ...
- physical constraints 使用 `pc1`, `pc2`, `pc3`, ...
- 编号必须连续、稳定、无重复。

## Logical Design Facts

`logical_constraints` 只包含会直接影响网络逻辑设计的 facts。

Allowed logical fact families:

1. Subnet facts
2. Interface facts
3. Graph facts

不要输出 General logical facts。
不要输出 Graph-invariant facts。
不要输出 unsupported logical intent。
不要输出 reachability-only、path-through、forbidden adjacency、exact neighbors、distinct segments、failure reachability 这类 validation-only facts。

### 1. Subnet facts

Subnet facts 只用于保留用户显式给出的 concrete subnet CIDR。

Canonical template:

- `Subnet fact: <SWITCH_ID> represents subnet <CIDR>.`

规则：

- Only create a Subnet fact when the user explicitly provides a concrete CIDR.
- If the user names a segment but gives no CIDR, do not create a Subnet fact.
- Do not write `unspecified`.
- Do not invent CIDRs.
- Do not encode connectivity in Subnet facts.
- Do not encode interface IP in Subnet facts.
- Do not encode segmentation/no-merge policy in Subnet facts.

示例：

- `Subnet fact: SW_DMZ represents subnet 10.10.10.0/24.`
- `Subnet fact: SW_CORE_FW represents subnet 10.0.0.0/30.`

### 2. Interface facts

Interface facts 只用于保留用户显式给出的 concrete interface IP。

Canonical template:

- `Interface fact: <NODE_ID> uses IP <IP>/<PREFIX> on segment <SWITCH_ID>.`

规则：

- Only create Interface facts for concrete fixed IPs explicitly provided by the user.
- The segment must be a switch ID, not a CIDR or zone name.
- Do not invent fixed IPs.
- If the user says a node must use a fixed IP but does not provide the concrete IP, do not create an Interface fact.
- If the user says router interfaces must use fixed IPv4 addresses but does not provide concrete IPs, do not create Interface facts.
- If the user says hosts may use DHCP, do not create an Interface fact.
- If the user says addresses must remain consistent with a subnet, do not create an Interface fact unless concrete IPs are provided.
- Interface facts do not replace Graph facts.
- Do not encode graph adjacency in Interface facts.

示例：

- `Interface fact: R_CORE uses IP 10.10.10.1/24 on segment SW_DMZ.`
- `Interface fact: FIREWALL uses IP 10.0.0.2/30 on segment SW_CORE_FW.`

### 3. Graph facts

Graph facts 用于表达 direct connectivity 和 topology shapes。Graph facts 是构建连接关系的主要依据。

Graph facts describe links to construct, not reachability to validate.

Graph connectivity is mandatory:

- If the user explicitly gives links or chains, preserve them losslessly.
- If the user partially specifies topology, infer missing direct connectivity needed for a minimal complete topology.
- If the user gives an open-ended design request, infer a small complete topology and express it as Graph facts.

Graph facts must not contain:

- CIDR
- interface IP
- image
- flavor
- route table details
- ACL details
- unsupported policy semantics
- validation-only reachability or security invariants

Allowed topology-shape templates:

#### 3.1 Direct adjacency

Canonical template:

- `Graph fact: <NODE_A> directly connects to <NODE_B>.`

用于普通 direct connection，没有更强的 topology shape semantics。

规则：

- 普通 direct adjacency 必须一条边一条 constraint。
- 不要把多个普通 adjacency 合并到同一句 statement 中。

示例：

- `Graph fact: WEB directly connects to SW_DMZ.`
- `Graph fact: PC1 directly connects to SW_OFFICE.`

#### 3.2 Explicit chain

Canonical template:

- `Graph fact: explicit chain <NODE_CHAIN>.`

用于用户给出 `A -> B -> C` 风格链路，或目标拓扑是 line/bus。

规则：

- The chain order is the authoritative topology fact.
- Do not collapse the chain into end-to-end reachability.
- Preserve all intermediate nodes.

示例：

- `Graph fact: explicit chain WEB -> SW_DMZ -> R_CORE.`

#### 3.3 Ring

Canonical template:

- `Graph fact: ring <NODE_RING>.`

用于用户明确要求 ring/cycle topology。

规则：

- The ring order is the authoritative topology fact.
- The closing edge is implied by the repeated first node or explicit ring wording.

示例：

- `Graph fact: ring R1 -> R2 -> R3 -> R4 -> R1.`

#### 3.4 Star

Canonical template:

- `Graph fact: <CENTER_NODE> is the star center for leaves <LEAF_LIST>.`

用于用户明确要求 star topology，或 network plan 自然存在一个汇聚节点连接多个 leaves。

规则：

- The center node must be explicit.
- The leaves must be explicit.
- Do not imply leaf-to-leaf links unless the user explicitly asks for them.

示例：

- `Graph fact: SW_CORE is the star center for leaves PC1, PC2, PC3.`

#### 3.5 Dual-homing

Canonical template:

- `Graph fact: <NODE_ID> is dual-homed to <UPLINK_A> and <UPLINK_B>.`

用于一个节点必须连接两个 uplinks。

规则：

- The dual-homed node must be explicit.
- Both uplinks must be explicit.

示例：

- `Graph fact: SERVER1 is dual-homed to SW_A and SW_B.`

#### 3.6 Full mesh

Canonical template:

- `Graph fact: nodes <NODE_LIST> form a full mesh.`

用于一组节点必须两两直接连接。

规则：

- The node list is authoritative.

示例：

- `Graph fact: nodes R1, R2, R3 form a full mesh.`

#### 3.7 Hub-and-spoke

Canonical template:

- `Graph fact: <HUB_NODE> is the hub for spokes <SPOKE_LIST>.`

用于 hub-spoke、WAN hub、central site with branches 等拓扑。

规则：

- The hub node must be explicit.
- The spoke nodes must be explicit.
- Do not imply spoke-to-spoke links unless the user explicitly asks for them.

示例：

- `Graph fact: R_HUB is the hub for spokes R_BRANCH1, R_BRANCH2, R_BRANCH3.`

#### 3.8 Hierarchy / tree

Canonical template:

- `Graph fact: hierarchy <HIERARCHY_DESCRIPTION>.`

用于 core-distribution-access、parent-child、branch hierarchy 或 tree-like topology。

规则：

- The hierarchy expression must make parent-child relationships clear.
- Do not add sibling links unless the user explicitly asks for them.

示例：

- `Graph fact: hierarchy R_CORE -> SW_DIST -> SW_ACCESS1, SW_ACCESS2.`

Graph fact rules:

- Preserve chain, ring, star, dual-homing, full mesh, hub-and-spoke, and hierarchy/tree as their own topology-shape facts.
- Topology-shape Graph facts are authoritative shape descriptions.
- Use `directly connects` for ordinary one-edge adjacency facts.
- Do not encode reachability as adjacency.
- Do not output reachability/path-through/security/segmentation/failure invariants as Graph facts.
- Do not output `segments <...> must remain distinct` as a Graph fact.
- If segmentation is required but only separate segments and connections are expressible, implement it by assigning separate switch nodes and direct connectivity, not by writing a validation-only constraint.

## Physical Design Facts

`physical_constraints` 只包含 deployment capability requirements。

Allowed physical fact families:

1. Image design
2. Flavor design

不要输出 General physical facts。
不要输出 provider/runtime/placement/availability-zone requirements。
不要输出 unsupported physical intent。
physical 证据分两类：

1. 用户显式 deployment/image/flavor/resource/appliance capability 要求。
2. 开放式 archetype 设计中由 author 主动引入的 functional role nodes；这些角色是为满足场景原型而选择的设计证据，不是单纯 node ID 证据。

固定 inventory 模式下，node ID 不是 deployment 证据。
开放式 archetype 模式下，SCADA、HMI、PLC、Historian 等由 author 主动引入的关键功能角色是 deployment capability 证据，需要写入 Image design facts。
explicit deployment phrase 只作用于所在句子、bullet 或括号子句中命名的 nodes。

### 1. Image design

Canonical template:

- `Image design: <NODE_ID> must use an image compatible with <CAPABILITY> capability.`

规则：

- Only create image constraints from explicit deployment/image/appliance capability intent, or from functional role nodes introduced by open-ended archetype design.
- Node names alone are not image evidence.
- In fixed-inventory intent, do not infer image constraints from names like WEB, PLC1, FIREWALL, INTERNET unless the intent explicitly says their roles are reflected by image selection or requires a specific image/appliance capability.
- In open-ended archetype intent, if author introduces nodes such as SCADA1, HMI1, PLC1, or HISTORIAN1 to satisfy the archetype, create Image design facts for their required capabilities.
- Do not choose concrete image IDs in ground.author.

示例：

- `Image design: EDGE1 must use an image compatible with simulated internet gateway capability.`
- `Image design: OPENPLC1 must use an image compatible with OpenPLC capability.`
- `Image design: FIREWALL must use an image compatible with firewall appliance capability.`
- `Image design: SCADA1 must use an image compatible with SCADA capability.`
- `Image design: PLC1 must use an image compatible with PLC runtime capability.`

### 2. Flavor design

Canonical template:

- `Flavor design: <NODE_ID_OR_GROUP> must use a flavor with at least <VCPU> vCPU, <RAM_MB> MB RAM, and <DISK_GB> GB disk.`

规则：

- Only create flavor constraints from explicit resource requirements.
- Do not infer flavor from node role or topology position.
- Do not choose concrete flavor objects in ground.author unless the user explicitly gives them.

示例：

- `Flavor design: WEB must use a flavor with at least 2 vCPU, 4096 MB RAM, and 20 GB disk.`
- `Flavor design: PLC[1..3] must use a flavor with at least 1 vCPU, 1024 MB RAM, and 10 GB disk.`

## 重复编码控制

- 如果一条 explicit chain 已经包含 A-B 和 B-C，不要再额外输出单独的 `A directly connects to B` 或 `B directly connects to C`，除非用户把它们作为独立要求再次强调。
- 如果某个 topology shape 已经覆盖相关 links，不要再把相同 links 重复写成 direct adjacency facts。
- 如果 Subnet fact 已经记录 `SW_X represents subnet <CIDR>`，不要重复写同一个 CIDR。
- 如果 Interface fact 记录 fixed IP，不要在同一条 statement 中重复 subnet carrier。
- Interface fact 不替代 Graph fact。连接关系必须由 Graph fact 表达。
- Physical fact 不替代 logical fact。image/flavor 不能表达 topology。

## Few-Shot

### 示例 1：用户意图完整，只做约束转写

Intent:
`Node IDs are fixed. Routers: R1. Switches: SW_DMZ, SW_LAN. Computers: WEB, CLIENT, EDGE1. CIDRs: SW_DMZ 10.0.10.0/24, SW_LAN 10.0.20.0/24. Links: WEB -> SW_DMZ -> R1 -> SW_LAN -> CLIENT, EDGE1 -> SW_DMZ. R1 uses 10.0.10.1/24 on SW_DMZ. R1 uses 10.0.20.1/24 on SW_LAN. EDGE1 is a simulated internet gateway image.`

GroundArtifact:

```json
{
  "node_groups": [
    {"type": "router", "members": ["R1"]},
    {"type": "switch", "members": ["SW_DMZ", "SW_LAN"]},
    {"type": "computer", "members": ["WEB", "CLIENT", "EDGE1"]}
  ],
  "logical_constraints": [
    {"id": "lc1", "statement": "Subnet fact: SW_DMZ represents subnet 10.0.10.0/24."},
    {"id": "lc2", "statement": "Subnet fact: SW_LAN represents subnet 10.0.20.0/24."},
    {"id": "lc3", "statement": "Graph fact: explicit chain WEB -> SW_DMZ -> R1 -> SW_LAN -> CLIENT."},
    {"id": "lc4", "statement": "Graph fact: EDGE1 directly connects to SW_DMZ."},
    {"id": "lc5", "statement": "Interface fact: R1 uses IP 10.0.10.1/24 on segment SW_DMZ."},
    {"id": "lc6", "statement": "Interface fact: R1 uses IP 10.0.20.1/24 on segment SW_LAN."}
  ],
  "physical_constraints": [
    {"id": "pc1", "statement": "Image design: EDGE1 must use an image compatible with simulated internet gateway capability."}
  ]
}
```

### 示例 2：半开放，补全最小拓扑

Intent:
`Build a small enterprise network with a DMZ and an office LAN. Use router R_CORE and switches SW_DMZ and SW_OFFICE. Place WEB in the DMZ. Place PC1 and PC2 in the office LAN. The DMZ and office LAN must remain separate. No CIDRs are specified.`

GroundArtifact:

```json
{
  "node_groups": [
    {"type": "router", "members": ["R_CORE"]},
    {"type": "switch", "members": ["SW_DMZ", "SW_OFFICE"]},
    {"type": "computer", "members": ["WEB", "PC1", "PC2"]}
  ],
  "logical_constraints": [
    {"id": "lc1", "statement": "Graph fact: WEB directly connects to SW_DMZ."},
    {"id": "lc2", "statement": "Graph fact: SW_DMZ directly connects to R_CORE."},
    {"id": "lc3", "statement": "Graph fact: PC1 directly connects to SW_OFFICE."},
    {"id": "lc4", "statement": "Graph fact: PC2 directly connects to SW_OFFICE."},
    {"id": "lc5", "statement": "Graph fact: SW_OFFICE directly connects to R_CORE."}
  ],
  "physical_constraints": []
}
```

### 示例 3：全开放，生成普渡模型启发的最小工业控制网络

Intent:
`构建一个典型的工业控制网络。`

GroundArtifact:

```json
{
  "node_groups": [
    {"type": "router", "members": ["R_ENTERPRISE", "R_OT_BOUNDARY"]},
    {"type": "switch", "members": ["SW_ENTERPRISE", "SW_IDMZ", "SW_SITE_OPS", "SW_SUPERVISORY", "SW_CONTROL", "SW_MGMT"]},
    {"type": "computer", "members": ["ERP1", "JUMPBOX1", "HISTORIAN1", "ENGINEER1", "SCADA1", "HMI1", "PLC[1..3]", "ADMIN1"]}
  ],
  "logical_constraints": [
    {"id": "lc1", "statement": "Graph fact: ERP1 directly connects to SW_ENTERPRISE."},
    {"id": "lc2", "statement": "Graph fact: SW_ENTERPRISE directly connects to R_ENTERPRISE."},
    {"id": "lc3", "statement": "Graph fact: R_ENTERPRISE directly connects to SW_IDMZ."},
    {"id": "lc4", "statement": "Graph fact: JUMPBOX1 directly connects to SW_IDMZ."},
    {"id": "lc5", "statement": "Graph fact: SW_IDMZ directly connects to R_OT_BOUNDARY."},
    {"id": "lc6", "statement": "Graph fact: HISTORIAN1 directly connects to SW_SITE_OPS."},
    {"id": "lc7", "statement": "Graph fact: ENGINEER1 directly connects to SW_SITE_OPS."},
    {"id": "lc8", "statement": "Graph fact: SW_SITE_OPS directly connects to R_OT_BOUNDARY."},
    {"id": "lc9", "statement": "Graph fact: SCADA1 directly connects to SW_SUPERVISORY."},
    {"id": "lc10", "statement": "Graph fact: HMI1 directly connects to SW_SUPERVISORY."},
    {"id": "lc11", "statement": "Graph fact: SW_SUPERVISORY directly connects to R_OT_BOUNDARY."},
    {"id": "lc12", "statement": "Graph fact: PLC1 directly connects to SW_CONTROL."},
    {"id": "lc13", "statement": "Graph fact: PLC2 directly connects to SW_CONTROL."},
    {"id": "lc14", "statement": "Graph fact: PLC3 directly connects to SW_CONTROL."},
    {"id": "lc15", "statement": "Graph fact: SW_CONTROL directly connects to R_OT_BOUNDARY."},
    {"id": "lc16", "statement": "Graph fact: ADMIN1 directly connects to SW_MGMT."},
    {"id": "lc17", "statement": "Graph fact: SW_MGMT directly connects to R_OT_BOUNDARY."}
  ],
  "physical_constraints": [
    {"id": "pc1", "statement": "Image design: SCADA1 must use an image compatible with SCADA capability."},
    {"id": "pc2", "statement": "Image design: HMI1 must use an image compatible with HMI capability."},
    {"id": "pc3", "statement": "Image design: PLC1 must use an image compatible with PLC runtime capability."},
    {"id": "pc4", "statement": "Image design: PLC2 must use an image compatible with PLC runtime capability."},
    {"id": "pc5", "statement": "Image design: PLC3 must use an image compatible with PLC runtime capability."},
    {"id": "pc6", "statement": "Image design: HISTORIAN1 must use an image compatible with industrial historian capability."},
    {"id": "pc7", "statement": "Image design: ENGINEER1 must use an image compatible with engineering workstation capability."}
  ]
}
```

## 静默检查

输出前静默确认：

- named nodes 是否全部进入 `node_groups`
- explicit chains 是否 lossless
- logical facts 是否只进入 `logical_constraints`
- physical facts 是否只进入 `physical_constraints`
- fixed IP/interface 是否都有 Interface fact
- physical constraints 是否只来自 explicit deployment intent 或开放式 archetype functional role evidence
- 是否存在重复编码或冲突 facts

只输出 GroundArtifact，不输出检查过程。
