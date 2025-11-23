from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent
from typing import Dict, Iterable, List, Mapping, Optional


@dataclass
class Tool:
    name: str
    description: str

    def run(self, query: str) -> str:
        raise NotImplementedError


@dataclass
class StaticTool(Tool):
    responses: Mapping[str, str] = field(default_factory=dict)

    def run(self, query: str) -> str:  # pragma: no cover - placeholder behavior
        return self.responses.get(query, f"No cached answer for: {query}")


class Toolset:
    """Collection of predefined tools described in the requirements."""

    def __init__(self) -> None:
        self.plan_context_query = StaticTool(
            name="Plan Context Query",
            description="查询当前PLAN上下文的历史记录，以便跨步骤复用信息",
            responses={"default": "(无PLAN上下文，可在各步骤结束后写入)"},
        )
        self.topo_source = StaticTool(
            name="Topo Source JSON",
            description="查询/初始化旧拓扑JSON对象（当前状态）",
            responses={"default": DEMO_TOPO_JSON},
        )
        self.topo_target = StaticTool(
            name="Topo Target JSON",
            description="查询/初始化目标拓扑JSON对象（期望状态）",
            responses={"default": DEMO_TOPO_JSON},
        )
        self.topo_diff = StaticTool(
            name="Topo Diff Planner",
            description="对比新旧拓扑JSON并生成最小改动计划(diff)，包括新增/删除节点、分组、链路",
            responses={"default": "当目标拓扑与当前拓扑一致时，最小改动集为空；否则请列出新增/删除/更新的节点、组、链路。"},
        )
        self.scenegraph_sdk = StaticTool(
            name="SceneGraph SDK",
            description="SceneGraph支持的方法及用法摘要",
            responses={"default": SCENEGRAPH_SDK_GUIDE},
        )
        self.image_catalog = StaticTool(
            name="Image Catalog",
            description="典型网络/工控相关镜像列表及描述",
            responses={"default": IMAGE_CATALOG},
        )
        self.domain_knowledge = StaticTool(
            name="Domain Knowledge",
            description="行业网络拓扑知识，如工控普渡模型分区示例",
            responses={"default": ICS_DOMAIN_KNOWLEDGE},
        )
        self.topo_spec = StaticTool(
            name="Topo Spec",
            description="基于示例总结的Topo JSON规范",
            responses={"default": TOPO_SPEC},
        )
        self.code_spec = StaticTool(
            name="SceneGraph Code Spec",
            description="基于示例总结的SceneGraph脚本/代码规范",
            responses={"default": CODE_SPEC},
        )

    @property
    def all_tools(self) -> Iterable[Tool]:
        return (
            self.plan_context_query,
            self.topo_source,
            self.topo_target,
            self.topo_diff,
            self.scenegraph_sdk,
            self.image_catalog,
            self.domain_knowledge,
            self.topo_spec,
            self.code_spec,
        )

    def tool_names(self) -> List[str]:
        return [tool.name for tool in self.all_tools]

    def describe(self) -> str:
        return "\n".join(f"{tool.name}: {tool.description}" for tool in self.all_tools)

    def prime_topology(
        self,
        source_json: Optional[str] = None,
        target_json: Optional[str] = None,
        diff_plan: Optional[str] = None,
    ) -> None:
        if source_json:
            self.topo_source.responses["default"] = source_json
        if target_json:
            self.topo_target.responses["default"] = target_json
        if diff_plan:
            self.topo_diff.responses["default"] = diff_plan

    def prime_scenegraph_sdk(self, sdk_text: str) -> None:
        self.scenegraph_sdk.responses["default"] = sdk_text

    def prime_images(self, catalog: List[str]) -> None:
        self.image_catalog.responses["default"] = ", ".join(catalog)


DEMO_TOPO_JSON = dedent(
    """
    {
        "nodes": [
            {"id": "cloud-internet", "type": "Cloud", "label": "Internet", "loc": "0 0"},
            {"id": "fw-edge", "type": "Firewall", "label": "Edge FW", "loc": "100 0"},
            {"id": "r-core", "type": "Router", "label": "Core Router", "loc": "200 0"},
            {"id": "srv-core", "type": "Server", "label": "Core Server", "loc": "300 0"},
            {"id": "sw-core", "type": "Switch", "label": "Core Switch", "loc": "200 100"},
            {"id": "fw-branch", "type": "Firewall", "label": "Branch FW", "loc": "25 100"},
            {"id": "r-branch", "type": "Router", "label": "Branch Router", "loc": "25 200"},
            {"id": "sw-dmz", "type": "Switch", "label": "DMZ Switch", "loc": "400 100"},
            {"id": "pc-a1", "type": "PC", "label": "Client A1", "loc": "150 220"},
            {"id": "pc-a2", "type": "PC", "label": "Client A2", "loc": "250 220"},
            {"id": "pc-a3", "type": "PC", "label": "Client A3", "loc": "150 300"},
            {"id": "pc-a4", "type": "PC", "label": "Client A4", "loc": "250 300"},
            {"id": "pc-b1", "type": "PC", "label": "Client B1", "loc": "350 220"},
            {"id": "pc-b2", "type": "PC", "label": "Client B2", "loc": "450 220"},
            {"id": "pc-b3", "type": "PC", "label": "Client B3", "loc": "350 300"},
            {"id": "pc-b4", "type": "PC", "label": "Client B4", "loc": "450 300"},
            {"id": "srv-app", "type": "Server", "label": "App Server", "loc": "-100 172"},
            {"id": "srv-db", "type": "Server", "label": "DB Server", "loc": "-100 242.5"}
        ],
        "groups": [
            {"id": "intra-1", "label": "Intranet 1", "connectTo": "sw-core", "members": ["pc-a1", "pc-a2", "pc-a3", "pc-a4"]},
            {"id": "intra-2", "label": "Intranet 2", "connectTo": "sw-dmz", "members": ["pc-b1", "pc-b2", "pc-b3", "pc-b4"]},
            {"id": "intra-3", "label": "Intranet 3", "connectTo": "r-branch", "members": ["srv-app", "srv-db"]}
        ],
        "links": [
            {"id": "cloud-internet--fw-edge", "from": "cloud-internet", "to": "fw-edge", "directed": false},
            {"id": "fw-edge--r-core", "from": "fw-edge", "to": "r-core", "directed": false},
            {"id": "r-core--srv-core", "from": "r-core", "to": "srv-core", "directed": false},
            {"id": "r-core--sw-core", "from": "r-core", "to": "sw-core", "directed": false},
            {"id": "fw-branch--sw-core", "from": "fw-branch", "to": "sw-core", "directed": false},
            {"id": "fw-branch--r-branch", "from": "fw-branch", "to": "r-branch", "directed": false},
            {"id": "sw-core--sw-dmz", "from": "sw-core", "to": "sw-dmz", "directed": false},
            {"id": "sw-dmz--srv-core", "from": "sw-dmz", "to": "srv-core", "directed": false},
            {"id": "pc-a1--sw-core::u", "from": "pc-a1", "to": "sw-core", "directed": false},
            {"id": "pc-a2--sw-core::u", "from": "pc-a2", "to": "sw-core", "directed": false},
            {"id": "pc-a3--sw-core::u", "from": "pc-a3", "to": "sw-core", "directed": false},
            {"id": "pc-a4--sw-core::u", "from": "pc-a4", "to": "sw-core", "directed": false},
            {"id": "pc-b1--sw-dmz::u", "from": "pc-b1", "to": "sw-dmz", "directed": false},
            {"id": "pc-b2--sw-dmz::u", "from": "pc-b2", "to": "sw-dmz", "directed": false},
            {"id": "pc-b3--sw-dmz::u", "from": "pc-b3", "to": "sw-dmz", "directed": false},
            {"id": "pc-b4--sw-dmz::u", "from": "pc-b4", "to": "sw-dmz", "directed": false},
            {"id": "srv-app--r-branch::u", "from": "srv-app", "to": "r-branch", "directed": false},
            {"id": "srv-db--r-branch::u", "from": "srv-db", "to": "r-branch", "directed": false}
        ]
    }
    """
)

SCENEGRAPH_SDK_GUIDE = dedent(
    """
    核心方法（TypeScript）：
    - sceneGraph.clear(scope) 清空指定来源的数据（如'script'）。
    - sceneGraph.addNode({id,type,label,loc}, scope) 添加节点。
    - sceneGraph.addEdge({id,source,target,directed?,label?}, scope) 添加链路，id 推荐 `${source}--${target}`。
    - sceneGraph.addGroup({id,label}, scope) 创建分组；attachToGroup(nodeId, groupId, scope) 关联成员。
    - sceneGraph.setGroupConnectTo(groupId, nodeId, scope) 指定组统一连接节点；applyGroupLinks(groupId, options, scope) 批量生成边。
    - 支持 loc 传入 "x y" 字符串便于布局；scope 使用 'script' 保持幂等。
    - 习惯：先 clear，再批量 addNode → addGroup/attach → addEdge → setGroupConnectTo/applyGroupLinks。
    """
)

IMAGE_CATALOG = dedent(
    """
    - ubuntu:22.04 通用基础镜像，适合服务器/跳板机。
    - alpine:3.19 轻量级系统，便于网络功能测试。
    - kali:rolling 安全测试与渗透工具集。
    - centos:7 传统企业/工控遗留环境。
    - node:20-alpine Web/业务前端或API。
    - openjdk:17-jdk 后端Java服务。
    - emqx/emqx:latest MQTT/IIoT 消息枢纽。
    - eclipse-mosquitto:2 MQTT 轻量代理。
    - influxdb:2.7 工控/时序数据采集存储。
    - grafana/grafana:10.2 可视化与监控。
    - modbus4j-simulator 或自定义modbus-sim：Modbus 设备仿真。
    - s7-plcsim 或开源 s7-comm-simulator：西门子S7协议仿真。
    """
)

ICS_DOMAIN_KNOWLEDGE = dedent(
    """
    工控普渡模型分区：
    - Level 4/5 企业IT区（办公网、DMZ、防火墙、边界路由）。
    - Level 3 生产管控区（核心交换、工程师站、AD/历史数据库）。
    - Level 2 过程控制区（PLC/RTU、HMI、工业交换机）。
    - Level 1 现场控制层（I/O模块、传感器/执行器）。
    - Level 0 物理过程。分区之间通常通过防火墙/工业交换机做纵深防护。

    典型区划：IT网 → DMZ → 控制中心(Level 3) → 车间/控制单元(Level 2) → 现场设备(Level 1)。
    安全要点：最小暴露、严格ACL、双网隔离、监控日志、远程维护跳板机、协议白名单（如 Modbus/TCP、S7、OPC UA）。
    """
)

TOPO_SPEC = dedent(
    """
    Topo JSON规范（基于示例）：
    - nodes: 数组，每个节点包含 id(唯一)、type(如 Cloud/Firewall/Router/Switch/Server/PC)、label、loc("x y").
    - groups: 数组，每个组含 id、label、members(节点ID列表)、connectTo(可选，组汇聚到的节点)。
    - links: 数组，每个链路含 id、from、to、directed(boolean，可省略视为false)。id 推荐 `${from}--${to}`，若需要区分无向/多路可追加后缀如 ::u。
    - 坐标 loc 使用字符串，方便 SceneGraph 直接复用；保持语义化 id 与 label 对应。
    - 建议：先定义节点，再分组及成员，再定义链路，组连接点可在生成 SceneGraph 时应用。
    """
)

CODE_SPEC = dedent(
    """
    SceneGraph脚本规范：
    1) 先 sceneGraph.clear('script') 确保幂等。
    2) 批量 addNode，使用语义化 id/label/type/loc。
    3) addGroup + attachToGroup 分配组成员。
    4) addEdge 创建链路，链路数组可用 [source,target,label?] 三元组生成；id 形如 `${a}--${b}`。
    5) setGroupConnectTo + applyGroupLinks 让组统一汇聚到目标节点。
    6) 大规模节点可用循环生成 loc 网格（示例：100 台 PC 按平方根分布）。
    7) scope 一律传 'script'，便于后续 diff/重放。
    """
)
