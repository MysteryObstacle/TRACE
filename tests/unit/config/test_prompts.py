from pathlib import Path

from trace.stages.logical.schemas import LogicalArtifact
from trace.stages.physical.schemas import PhysicalArtifact
from trace.tools.tgraph.model import TGraphJSON
from trace.tools.tgraph.prompting import load_tgraph_contract_for


ROOT = Path(__file__).resolve().parents[3]


def _prompt(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_stage_artifacts_use_tgraph_json_schema():
    assert LogicalArtifact.model_fields["tgraph_logical"].annotation is TGraphJSON
    assert PhysicalArtifact.model_fields["tgraph_physical"].annotation is TGraphJSON


def test_all_stage_prompts_are_chinese_first():
    prompt_paths = [
        "src/trace/stages/ground/prompts/author.md",
        "src/trace/stages/ground/prompts/evaluator.md",
        "src/trace/stages/logical/prompts/author.md",
        "src/trace/stages/logical/prompts/builder.md",
        "src/trace/stages/logical/prompts/repair.md",
        "src/trace/stages/physical/prompts/author.md",
        "src/trace/stages/physical/prompts/builder.md",
        "src/trace/stages/physical/prompts/repair.md",
    ]

    for path in prompt_paths:
        prompt = _prompt(path)
        assert prompt.startswith(("你是 TRACE", "你的任务"))
        assert "你的任务" in prompt


def test_ground_author_prompt_preserves_schema_and_no_inference_rules():
    prompt = _prompt("src/trace/stages/ground/prompts/author.md")

    assert "GroundArtifact" in prompt
    assert "## 输出契约" in prompt
    assert "node_groups" in prompt
    assert "logical_constraints" in prompt
    assert "physical_constraints" in prompt
    assert "完整 `GroundArtifact` 全局快照" in prompt
    assert "节点清单" in prompt
    assert "写入 `node_groups`" in prompt
    assert "只输出 JSON 对象" in prompt
    assert "## 表达边界" in prompt
    assert "GroundArtifact 只保留当前 schema 能承载、且后续流程可以直接消费的 facts" in prompt
    assert "不决定节点、连接、子网、接口地址、image 或 flavor 的 reachability-only assertions" in prompt
    assert "不要生成 General fact" in prompt
    assert "不要伪装成已有模板" in prompt
    assert "## Completeness and Defaulting Policy" in prompt
    assert "Graph connectivity is not defaultable." in prompt
    assert "CIDR and IP are defaultable." in prompt
    assert "If the user does not provide concrete CIDR or concrete IP, do not invent them in ground.author." in prompt
    assert "冻结 `node_groups`：显式命名的 node IDs、typed inventories、subnets、link chains" not in prompt
    assert "node inventory" not in prompt
    assert "node_inventory" not in prompt
    assert "## Design Fact Policy" in prompt
    assert "logical_constraints`：描述网络逻辑事实" in prompt
    assert "physical_constraints`：描述部署事实" in prompt
    assert "不要把 physical deployment fact 当成 logical fact 的一种" in prompt
    assert "不要把 logical topology/subnet/interface fact 写入 physical_constraints" in prompt
    assert "## Logical Design Facts" in prompt
    assert "TGraph" not in prompt
    assert "logical 阶段" not in prompt
    assert "physical 阶段" not in prompt
    assert "logical stage" not in prompt
    assert "physical stage" not in prompt
    assert "port IDs" not in prompt
    assert "link IDs" not in prompt
    assert "node.id" not in prompt
    assert "ports[]" not in prompt
    assert "links[]" not in prompt
    assert "每条 fact statement 只使用一个 canonical template" in prompt
    assert "Subnet fact: <SWITCH_ID> represents subnet <CIDR>." in prompt
    assert "SEGMENT_ID_OR_NAME" not in prompt
    assert "CIDR_OR_UNSPECIFIED" not in prompt
    assert "represents segment LAN with subnet" not in prompt
    assert "Interface fact: <NODE_ID> uses IP <IP>/<PREFIX> on segment <SWITCH_ID>." in prompt
    assert "The segment must be a switch ID, not a CIDR or zone name." in prompt
    assert "Interface fact: <NODE_OR_GROUP> uses <ADDRESS_POLICY>" not in prompt
    assert "Interface fact: <NODE_OR_GROUP> may use DHCP" not in prompt
    assert "Graph facts describe links to construct, not reachability to validate." in prompt
    assert "Graph fact: <NODE_A> directly connects to <NODE_B>." in prompt
    assert "普通 direct adjacency 必须一条边一条 constraint" in prompt
    assert "required adjacencies are <PAIR_LIST>" not in prompt
    assert "Graph fact: explicit chain <NODE_CHAIN>." in prompt
    assert "Graph fact: ring <NODE_RING>." in prompt
    assert "Graph fact: <CENTER_NODE> is the star center for leaves <LEAF_LIST>." in prompt
    assert "Graph fact: <NODE_ID> is dual-homed to <UPLINK_A> and <UPLINK_B>." in prompt
    assert "Graph fact: nodes <NODE_LIST> form a full mesh." in prompt
    assert "Graph fact: <HUB_NODE> is the hub for spokes <SPOKE_LIST>." in prompt
    assert "Graph fact: hierarchy <HIERARCHY_DESCRIPTION>." in prompt
    assert "Topology-shape Graph facts are authoritative shape descriptions" in prompt
    assert "must be realized as adjacent pairs <PAIR_LIST>" not in prompt
    assert "cycle pairs <PAIR_LIST>" not in prompt
    assert "<PAIR_LIST>" not in prompt
    assert "Graph fact: <SOURCE> must reach <TARGET>." not in prompt
    assert "Graph fact: traffic from <SOURCE> to <TARGET> must pass through <VIA_NODE>." not in prompt
    assert "Graph fact: <NODE_A> must not be adjacent to <NODE_B>." not in prompt
    assert "Graph fact: <NODE_ID> must have exactly neighbors <NEIGHBOR_LIST>." not in prompt
    assert "Graph fact: segments <SEGMENT_LIST> must remain distinct." not in prompt
    assert "Graph fact: <SUBJECT> must remain reachable if <FAILURE_DOMAIN> fails." not in prompt
    assert "General logical fact:" not in prompt
    assert "Segment design:" not in prompt
    assert "Topology design:" not in prompt
    assert "Addressing design:" not in prompt
    assert "Routing design:" not in prompt
    assert "Security design:" not in prompt
    assert "Service design:" not in prompt
    assert "Resilience design:" not in prompt
    assert "## Physical Design Facts" in prompt
    assert "Image design: <NODE_ID> must use an image compatible with <CAPABILITY> capability." in prompt
    assert "Flavor design: <NODE_ID_OR_GROUP> must use a flavor with at least <VCPU> vCPU, <RAM_MB> MB RAM, and <DISK_GB> GB disk." in prompt
    assert "Runtime design:" not in prompt
    assert "Placement design:" not in prompt
    assert "General physical design:" not in prompt
    assert "Unsupported requirements must not affect `node_groups` or supported constraints unless they imply necessary supported topology." in prompt
    assert "## 开放式与半开放式推理策略" in prompt
    assert "场景原型" in prompt
    assert "zones / segments" in prompt
    assert "boundary nodes" in prompt
    assert "role nodes" in prompt
    assert "topology completion" in prompt
    assert "defaulting" in prompt
    assert "Purdue-inspired minimal architecture" in prompt
    assert "Enterprise / Site Operations zone" in prompt
    assert "Industrial DMZ zone" in prompt
    assert "OT Supervisory / Control zone" in prompt
    assert "Management zone" in prompt
    assert "Use:" not in prompt
    assert "## Fact Selection" not in prompt
    assert "physical deployment fact`: image" not in prompt
    assert "## Logical Policy" not in prompt
    assert "## Addressing Policy" not in prompt
    assert "## Physical Policy" not in prompt
    assert "physical 证据分两类" in prompt
    assert "用户显式 deployment/image/flavor/resource/appliance capability 要求" in prompt
    assert "开放式 archetype 设计中由 author 主动引入的 functional role nodes" in prompt
    assert "固定 inventory 模式下，node ID 不是 deployment 证据" in prompt
    assert "开放式 archetype 模式下" in prompt
    assert "SCADA、HMI、PLC、Historian" in prompt
    assert "explicit deployment phrase 只作用于所在句子、bullet 或括号子句中命名的 nodes" in prompt
    assert "## Few-Shot" in prompt
    assert "示例 1" in prompt
    assert "示例 2" in prompt
    assert "示例 3" in prompt
    assert "示例 4" not in prompt
    assert prompt.count("### 示例 ") == 3
    assert "用户意图完整" in prompt
    assert "半开放" in prompt
    assert "全开放" in prompt
    assert "普渡模型启发" in prompt
    assert "statement\": \"Subnet fact:" in prompt
    assert "statement\": \"Graph fact:" in prompt
    assert "statement\": \"Interface fact:" in prompt
    assert "statement\": \"Image design:" in prompt
    assert "Image design: SCADA1 must use an image compatible with SCADA capability." in prompt
    assert "Image design: HMI1 must use an image compatible with HMI capability." in prompt
    assert "Image design: PLC1 must use an image compatible with PLC runtime capability." in prompt
    assert "Image design: PLC2 must use an image compatible with PLC runtime capability." in prompt
    assert "Image design: PLC3 must use an image compatible with PLC runtime capability." in prompt
    assert "Image design: HISTORIAN1 must use an image compatible with industrial historian capability." in prompt
    assert "静默检查" in prompt
    assert "只输出 GroundArtifact，不输出检查过程" in prompt
    assert "## 输出 Schema" not in prompt
    assert "错误示例" not in prompt
    assert '"logical_constraints": ["PLC1 must connect to SWITCH1."]' not in prompt
    assert "不要输出 delta patch" not in prompt
    assert "<thought>" not in prompt
    assert "当提供了 `evaluation_feedback`" not in prompt


def test_ground_evaluator_prompt_constrains_review_to_ground_schema():
    prompt = _prompt("src/trace/stages/ground/prompts/evaluator.md")

    assert "只评估这些 GroundArtifact 字段" in prompt
    assert "不要要求该 schema 之外的字段" in prompt
    assert "`issues` 中每项只能使用 `code`、`message`，以及 optional `location`" in prompt
    assert "不要输出 `id`、`severity`、`type`、`description` 等 issue fields" in prompt
    assert "optimizer_brief" in prompt
    assert "## Evaluation Flow" in prompt
    assert "按 author 静默检查的顺序评估" in prompt
    assert "named nodes 是否全部进入 `node_groups`" in prompt
    assert "explicit chains 是否 lossless" in prompt
    assert "logical facts 是否只进入 `logical_constraints`" in prompt
    assert "physical facts 是否只进入 `physical_constraints`" in prompt
    assert "fixed IP/interface 是否都有 Interface fact" in prompt
    assert "physical constraints 是否只来自 explicit deployment intent 或开放式 archetype functional role evidence" in prompt
    assert "## Logical Fact Checks" in prompt
    assert "Allowed logical fact families" in prompt
    assert "Subnet fact" in prompt
    assert "Interface fact" in prompt
    assert "Graph fact" in prompt
    assert "Graph fact: <NODE_A> directly connects to <NODE_B>." in prompt
    assert "普通 direct adjacency 应一条边一条 constraint" in prompt
    assert "Interface fact 不替代 Graph fact" in prompt
    assert "不要输出或接受 General logical facts" in prompt
    assert "reachability-only" in prompt
    assert "path-through" in prompt
    assert "forbidden adjacency" in prompt
    assert "exact neighbors" in prompt
    assert "distinct segments" in prompt
    assert "failure reachability" in prompt
    assert "## Physical Fact Checks" in prompt
    assert "physical 证据分两类" in prompt
    assert "固定 inventory 模式下" in prompt
    assert "开放式 archetype 模式下" in prompt
    assert "SCADA、HMI、PLC、Historian" in prompt
    assert "missing_fixed_interface_address" in prompt
    assert "missing_functional_image_constraint" in prompt
    assert "不要仅因为 node name 看起来像 functional role 就判失败" in prompt
    assert "Constraint Selection Priority" not in prompt
    assert "path / policy fact" not in prompt
    assert "only-connects" not in prompt
    assert "redundant_default_routing_role" not in prompt
    assert "generic router L3 summaries" not in prompt
    assert "runtime、CPU、RAM、disk 等 node metadata" not in prompt


def test_logical_author_prompt_defines_checkpoint_execution_contract():
    prompt = _prompt("src/trace/stages/logical/prompts/author.md")
    contract = _prompt("src/trace/tools/tgraph/contract.md")

    assert "logical_checkpoints" in prompt
    assert "logical_validator_script" in prompt
    assert "每个 checkpoint 都必须包含 `id`、`func`、`description`、`constraint_ids`、`args`" in prompt
    assert "`logical_validator_script` 中的 custom function 只有被某个 checkpoint 的 `func` 命名时才会执行" in prompt
    assert "不要依赖一个独立的 `logical_validator` 函数被自动执行" in prompt
    assert "不要为了“覆盖率”把 constraint id 挂到语义不匹配的最近 checkpoint 上" in prompt
    assert "不要把 subnet 或 interface constraint id 作为主要覆盖挂到 `connect_nodes` checkpoint 上" in prompt
    assert "Subnet fact" in prompt
    assert "Interface fact" in prompt
    assert "Graph fact" in prompt
    assert "Graph fact 映射为 direct adjacency 的 `connect_nodes` checkpoints" in prompt
    assert "Graph fact: <NODE_A> directly connects to <NODE_B>." in prompt
    assert "Graph fact 的 topology-shape deterministic expansion 映射为 `connect_nodes` checkpoints" in prompt
    assert "不要求 ground 提供 `adjacent pairs` 或 `cycle pairs`" in prompt
    assert "Subnet fact 映射为内置 `switch_has_subnet` checkpoint" in prompt
    assert '"func": "switch_has_subnet"' in prompt
    assert '{"switch_id": "<SWITCH_ID>", "expected_cidr": "<CIDR>"}' in prompt
    assert "Subnet fact: <SWITCH_ID> represents subnet <CIDR>." in prompt
    assert "SEGMENT_ID_OR_NAME" not in prompt
    assert "Interface fact 映射为内置 `node_interface_on_segment` checkpoint" in prompt
    assert '"func": "node_interface_on_segment"' in prompt
    assert '{"node_id": "<NODE_ID>", "segment_id": "<SWITCH_ID>", "expected_ip": "<IP>", "expected_cidr": "<CIDR>"}' in prompt
    assert "Interface fact: <NODE_ID> uses IP <IP>/<PREFIX> on segment <SWITCH_ID>." in prompt
    assert "不要为 Subnet fact 或 Interface fact 编写 custom validator script" in prompt
    assert "logical_validator_script` 必须为 `null`" in prompt
    assert "expected_cidr" in prompt
    assert "reachability-only" not in prompt
    assert "Graph fact 的 reachability 映射为 `path_exists`" not in prompt
    assert "Graph fact 的 pass-through 映射为 `path_must_include`" not in prompt
    assert "Graph fact 的 negative/exact/distinct/failure invariants 使用 custom validator script" not in prompt
    assert "General logical fact" not in prompt
    assert "CIDR_OR_UNSPECIFIED" not in prompt
    assert "R_CORE" not in prompt
    assert "SW_DMZ" not in prompt
    assert "10.10.10.1/24" not in prompt
    assert "connect_nodes" in contract
    assert "switch_has_subnet" in contract
    assert "node_interface_on_segment" in contract
    assert "path_exists" in contract
    assert "path_must_include" in contract
    assert "node_port_has_cidr" not in contract


def test_logical_builder_prompt_requires_tgraph_shape_and_ground_translation():
    prompt = _prompt("src/trace/stages/logical/prompts/builder.md")

    assert "顶层输出必须是 `LogicalArtifact` object" in prompt
    assert '{"tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []}}' in prompt
    assert "不要直接输出裸 TGraphJSON object" in prompt
    assert "本阶段不要输出 checkpoints 或 validator scripts" in prompt
    assert "只使用 `tgraph_contract` 中与 TGraphJSON schema、logical validator expectations、port/link 规则有关的内容" in prompt
    assert "不要模仿 contract 中的 mutation tool 或 checkpoint authoring 内容" in prompt
    assert "## 构图算法" in prompt
    assert "1. 复制 `working_graph` 中所有 frozen nodes" in prompt
    assert "2. 解析 `logical_constraints` 为中间设计集合" in prompt
    assert "3. 展开所有 Graph fact 为 node-pair edges" in prompt
    assert "4. 合并 edges" in prompt
    assert "5. 为每条 edge 的两个 endpoint 分配全局唯一 port" in prompt
    assert "6. 按 Subnet / Interface / defaulting 写入 port `ip` 和 `cidr`" in prompt
    assert "7. 构造 links" in prompt
    assert "同一 unordered node pair 默认只创建一条 link" in prompt
    assert "## Fact Implementation Rules" in prompt
    assert "Subnet fact 的实现效果" in prompt
    assert "该 switch 下由 Graph/Interface fact 创建出来的 linked ports 都必须使用该 CIDR" in prompt
    assert "不要仅因为 Subnet fact 创建没有 link 的 carrier port" in prompt
    assert "Fact: `Subnet fact: SW_LAN represents subnet 192.168.10.0/24.`" in prompt
    assert "Effect: every linked port on `SW_LAN` uses `cidr=\"192.168.10.0/24\"` and `ip=\"\"`." in prompt
    assert "Fact: `Subnet fact: SW_CORE_FW represents subnet 10.0.0.0/30.`" in prompt
    assert "SW_CORE_FW__to__R_CORE" in prompt
    assert "Subnet fact 映射为 switch ports" in prompt
    assert "Interface fact 的实现效果" in prompt
    assert "确保 `<NODE_ID>` 和 `<SWITCH_ID>` 之间存在一条 link" in prompt
    assert "Fact: `Interface fact: R1 uses IP 192.168.10.1/24 on segment SW_LAN.`" in prompt
    assert "R1__to__SW_LAN" in prompt
    assert "Fact: `Interface fact: FIREWALL uses IP 10.0.0.2/30 on segment SW_CORE_FW.`" in prompt
    assert "FIREWALL__to__SW_CORE_FW" in prompt
    assert "Interface fact 映射为 endpoint ports 的 `ip`/`cidr`" in prompt
    assert "Interface fact 和 Graph fact 命名同一 node-segment attachment 时，必须合并为同一条 link" in prompt
    assert "不要为同一 attachment 创建重复 links" in prompt
    assert "把 Interface fact 的 IP/CIDR 写到该 link 对应 endpoint port 上" in prompt
    assert "Graph fact 的实现效果" in prompt
    assert "Fact: `Graph fact: PC1 directly connects to SW_LAN.`" in prompt
    assert "PC1__to__SW_LAN--SW_LAN__to__PC1" in prompt
    assert "Fact: `Graph fact: explicit chain WEB -> SW_DMZ -> R_CORE.`" in prompt
    assert "SW_DMZ__to__WEB--WEB__to__SW_DMZ" in prompt
    assert "R_CORE__to__SW_DMZ--SW_DMZ__to__R_CORE" in prompt
    assert "Graph fact 映射为 topology-shape links" in prompt
    assert "deterministic expansion" in prompt
    assert "不要求 ground 提供 `adjacent pairs` 或 `cycle pairs`" in prompt
    assert "directly connects" in prompt
    assert "required adjacencies" not in prompt
    assert "explicit chain" in prompt
    assert "ring" in prompt
    assert "star center" in prompt
    assert "dual-homed" in prompt
    assert "full mesh" in prompt
    assert "hub for spokes" in prompt
    assert "hierarchy" in prompt
    assert "reachability-only" not in prompt
    assert "negative/exact/distinct/failure invariants" not in prompt
    assert "## Defaulting for valid TGraph" in prompt
    assert "缺省 CIDR/IP 不是 ground intent constraint" in prompt
    assert "按 switch id 排序生成稳定、非重叠 RFC1918 `/24`" in prompt
    assert "普通 computer host 没有 Interface fact 时，`ip` 保持空字符串" in prompt
    assert "router/gateway/internet-facing endpoint" in prompt
    assert "## Port Naming Convention" in prompt
    assert "`<NODE_ID>__to__<PEER_NODE_ID>`" in prompt
    assert "`<NODE_ID>__to__<PEER_NODE_ID>__l<N>`" in prompt
    assert "## Link Naming Convention" in prompt
    assert "`link.id = {from_port}--{to_port}`" in prompt
    assert "按 port id 字典序排列" in prompt
    assert "Port `ip` 不能包含 CIDR suffix" in prompt
    assert '"ip": "<IP>", "cidr": "<CIDR>"' in prompt
    assert "仍创建一个 switch port 承载该 subnet CIDR" not in prompt


def test_repair_prompts_preserve_tool_contracts_and_structured_arguments():
    logical_prompt = _prompt("src/trace/stages/logical/prompts/repair.md")
    physical_prompt = _prompt("src/trace/stages/physical/prompts/repair.md")

    for prompt in (logical_prompt, physical_prompt):
        assert "Tool calls 必须使用 structured JSON arguments" in prompt
        assert "不要把嵌套 list 或 object JSON-encode 成 string" in prompt
        assert "`ports` 必须是真正的 JSON array of objects" in prompt
        assert "candidate_checkpoints" in prompt
        assert "recent_repair_ledger" in prompt
        assert "不要重新生成整个" in prompt
        assert "get_nodes" in prompt
        assert "get_links" in prompt
        assert '"ports": "[{' not in prompt


def test_physical_author_and_builder_prompts_use_catalog_and_custom_checks():
    author_prompt = _prompt("src/trace/stages/physical/prompts/author.md")
    builder_prompt = _prompt("src/trace/stages/physical/prompts/builder.md")

    assert "image_catalog" in author_prompt
    assert "physical_checkpoints" in author_prompt
    assert "physical_validator_script" in author_prompt
    assert "Deployment-property checks 要放进 `physical_validator_script`" in author_prompt
    assert "`physical_validator_script` 中的 custom functions 只有被某个 checkpoint 的 `func` 命名时才会执行" in author_prompt
    assert '"func": "node_has_image_flavor"' in author_prompt
    assert '{"node_id": "<NODE_ID>", "expected_image_id": "<IMAGE_ID>"}' in author_prompt
    assert "FIREWALL" not in author_prompt
    assert "img_pfsense" not in author_prompt
    assert "保留 logical topology" in builder_prompt
    assert "只使用 `image_catalog` 中的 images" in builder_prompt
    assert "不要发明 image ids 或 image names" in builder_prompt
    assert "输出 `image` 时必须使用 object" in builder_prompt
    assert "输出 `flavor` 时必须使用 object" in builder_prompt
    assert "Image/Flavor issues 优先使用 `update_node` 修改 deployment metadata" in _prompt(
        "src/trace/stages/physical/prompts/repair.md"
    )


def test_tgraph_contract_defines_f4_checkpoint_execution_model_and_helpers():
    contract = _prompt("src/trace/tools/tgraph/contract.md")

    assert "### F4 checkpoint execution model" in contract
    assert "F3 checks implementation-complete graph validity, not whether an address was explicitly requested by intent." in contract
    assert "Implementation defaults are graph-validity choices, not intent facts." in contract
    assert "F4 executes authored checkpoints, not validator scripts directly." in contract
    assert "A custom validator function runs only when a checkpoint `func` names that function." in contract
    assert "A standalone function such as `logical_validator` or `physical_validator` is not an automatic entry point." in contract
    assert "`constraint_ids` are provenance and coverage metadata; they do not change what a checkpoint function checks." in contract
    assert "Attach a constraint id to the checkpoint whose function actually validates that constraint's semantics." in contract
    assert "tgraph.get_nodes(node_ids=None)" in contract
    assert "tgraph.get_links" in contract


def test_tgraph_contract_loader_returns_audience_specific_slices():
    logical_builder = load_tgraph_contract_for("logical_builder")
    logical_author = load_tgraph_contract_for("logical_author")
    logical_repair = load_tgraph_contract_for("logical_repair")
    physical_builder = load_tgraph_contract_for("physical_builder")
    physical_author = load_tgraph_contract_for("physical_author")

    assert "Canonical TGraphJSON shape" in logical_builder
    assert "Key logical-stage validator expectations" in logical_builder
    assert "Implementation defaults are graph-validity choices, not intent facts" in logical_builder
    assert "F4 checkpoint execution model" not in logical_builder
    assert "Low-level mutation tool semantics" not in logical_builder

    assert "F4 checkpoint execution model" in logical_author
    assert "Custom validator script surface" in logical_author
    assert "Low-level mutation tool semantics" not in logical_author

    assert "Low-level mutation tool semantics" in logical_repair
    assert "Structured tool-call argument rules" in logical_repair
    assert "F4 checkpoint execution model" in logical_repair

    assert "Physical metadata rules" in physical_builder
    assert "image` must be an object with `id` and `name`" in physical_builder
    assert "F4 checkpoint execution model" not in physical_builder
    assert "Low-level mutation tool semantics" not in physical_builder

    assert "Physical metadata rules" in physical_author
    assert "F4 checkpoint execution model" in physical_author
