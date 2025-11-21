from __future__ import annotations

from dataclasses import dataclass, field
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
        self.topo_summary = StaticTool(
            name="Topo Summary",
            description="仅包含拓扑摘要，隐去繁杂节点信息",
            responses={},
        )
        self.topo_detail = StaticTool(
            name="Topo Detail",
            description="查询某个具体节点或边的详细信息",
            responses={},
        )
        self.scenegraph_ops = StaticTool(
            name="SceneGraph Ops",
            description="SceneGraph API支持的操作方法列表",
            responses={},
        )
        self.scenegraph_op_detail = StaticTool(
            name="SceneGraph Op Detail",
            description="查询某个操作方法的详细参数和类型",
            responses={},
        )
        self.scenegraph_types = StaticTool(
            name="SceneGraph Types",
            description="SceneGraph支持的类型摘要",
            responses={},
        )
        self.scenegraph_type_detail = StaticTool(
            name="SceneGraph Type Detail",
            description="SceneGraph类型的详细信息",
            responses={},
        )
        self.image_catalog = StaticTool(
            name="Image Catalog",
            description="镜像名称摘要",
            responses={},
        )
        self.image_detail = StaticTool(
            name="Image Detail",
            description="镜像的详细信息",
            responses={},
        )

    @property
    def all_tools(self) -> Iterable[Tool]:
        return (
            self.topo_summary,
            self.topo_detail,
            self.scenegraph_ops,
            self.scenegraph_op_detail,
            self.scenegraph_types,
            self.scenegraph_type_detail,
            self.image_catalog,
            self.image_detail,
        )

    def tool_names(self) -> List[str]:
        return [tool.name for tool in self.all_tools]

    def describe(self) -> str:
        return "\n".join(f"{tool.name}: {tool.description}" for tool in self.all_tools)

    def prime_topology(self, summary: str, details: Optional[Dict[str, str]] = None) -> None:
        self.topo_summary.responses["default"] = summary
        if details:
            self.topo_detail.responses.update(details)

    def prime_scenegraph(self, ops: Dict[str, str], types: Dict[str, str]) -> None:
        self.scenegraph_ops.responses.update(ops)
        self.scenegraph_types.responses.update(types)

    def prime_images(self, catalog: List[str], details: Optional[Dict[str, str]] = None) -> None:
        self.image_catalog.responses["default"] = ", ".join(catalog)
        if details:
            self.image_detail.responses.update(details)
