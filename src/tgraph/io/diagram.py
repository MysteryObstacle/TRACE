from __future__ import annotations

import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tgraph.core.graph import Link, Node, TGraph

DiagramFormat = Literal["mermaid", "png"]


@dataclass(frozen=True)
class DiagramResult:
    format: DiagramFormat
    mermaid: str
    mermaid_path: Path | None = None
    png_path: Path | None = None


def _switch_subnet_cidr(node: Node) -> str | None:
    cidrs = [port.cidr for port in node.ports if port.cidr]
    if not cidrs:
        return None
    return Counter(cidrs).most_common(1)[0][0]


def _connected_switch_id(node_id: str, links: list[Link], nodes_by_id: dict[str, Node]) -> str | None:
    for link in links:
        if link.from_node == node_id:
            peer_id = link.to_node
        elif link.to_node == node_id:
            peer_id = link.from_node
        else:
            continue
        if not peer_id:
            continue
        peer = nodes_by_id.get(peer_id)
        if peer is not None and peer.type == "switch":
            return peer_id
    return None


def render_mermaid(graph: TGraph) -> str:
    """Render a TGraph as a Mermaid flowchart topology diagram."""
    nodes = graph.nodes
    links = graph.links
    nodes_by_id = {node.id: node for node in nodes}
    node_type = {node.id: node.type for node in nodes}

    switch_groups: dict[str, list[str]] = defaultdict(list)
    standalone: list[str] = []

    for node in nodes:
        node_id = node.id
        if node.type == "switch":
            switch_groups[node_id].append(node_id)
            continue
        if node.type == "computer":
            switch_id = _connected_switch_id(node_id, links, nodes_by_id)
            if switch_id is not None:
                switch_groups[switch_id].append(node_id)
            else:
                standalone.append(node_id)
            continue
        standalone.append(node_id)

    lines = [
        "flowchart TB",
        "  classDef router fill:#dbeafe,stroke:#2563eb,stroke-width:2px",
        "  classDef switch fill:#fef3c7,stroke:#d97706,stroke-width:1.5px",
        "  classDef computer fill:#dcfce7,stroke:#16a34a,stroke-width:1px",
        "",
    ]

    used: set[str] = set()
    for switch_id in sorted(switch_groups):
        members = switch_groups[switch_id]
        switch_node = nodes_by_id.get(switch_id)
        cidr = _switch_subnet_cidr(switch_node) if switch_node is not None else None
        group_id = f"subnet_{switch_id}"
        title = f"{switch_id} ({cidr})" if cidr else switch_id
        lines.append(f'  subgraph {group_id}["{title}"]')
        for member in sorted(set(members)):
            lines.append(f"    {member}[{member}]")
            used.add(member)
        lines.append("  end")
        lines.append("")

    for node_id in sorted(standalone):
        if node_id not in used:
            lines.append(f"  {node_id}[{node_id}]")
            used.add(node_id)

    lines.append("")
    seen_edges: set[tuple[str, str]] = set()
    for link in links:
        src = link.from_node
        dst = link.to_node
        if not src or not dst:
            continue
        edge = (src, dst)
        if edge in seen_edges:
            continue
        seen_edges.add(edge)
        lines.append(f"  {src} --- {dst}")

    lines.append("")
    for node in nodes:
        node_id = node.id
        kind = node_type.get(node_id, "node")
        if kind == "router":
            lines.append(f"  class {node_id} router")
        elif kind == "switch":
            lines.append(f"  class {node_id} switch")
        elif kind == "computer":
            lines.append(f"  class {node_id} computer")

    return "\n".join(lines) + "\n"


def _render_png(mermaid_path: Path, png_path: Path, *, width: int = 1800) -> None:
    subprocess.run(
        [
            "npx",
            "--yes",
            "@mermaid-js/mermaid-cli",
            "-i",
            str(mermaid_path),
            "-o",
            str(png_path),
            "-b",
            "white",
            "-w",
            str(width),
        ],
        check=True,
        capture_output=True,
        text=True,
        shell=sys.platform == "win32",
    )


def write_diagram(
    graph: TGraph,
    out: Path,
    *,
    format: DiagramFormat = "mermaid",
    width: int = 1800,
) -> DiagramResult:
    """Write a topology diagram for the given graph."""
    mermaid = render_mermaid(graph)
    out = out.resolve()

    if format == "mermaid":
        out.write_text(mermaid, encoding="utf-8")
        return DiagramResult(format="mermaid", mermaid=mermaid, mermaid_path=out)

    if out.suffix.lower() != ".png":
        out = out.with_suffix(".png")

    mermaid_path = out.with_suffix(".mmd")
    mermaid_path.write_text(mermaid, encoding="utf-8")
    _render_png(mermaid_path, out, width=width)
    return DiagramResult(
        format="png",
        mermaid=mermaid,
        mermaid_path=mermaid_path,
        png_path=out,
    )
