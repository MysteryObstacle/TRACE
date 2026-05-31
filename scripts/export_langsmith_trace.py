#!/usr/bin/env python3
"""Export a LangSmith public/shared Agent trace to local Markdown + JSON."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langsmith import Client
from tgraph import TGraph
from tgraph.io.diagram import render_mermaid, write_diagram

BATCH_SIZE = 100


def fetch_all_runs(client: Client, share_url: str):
    root = client.read_shared_run(share_url)
    runs: dict[str, Any] = {str(root.id): root}
    queue = deque([root])

    while queue:
        run = queue.popleft()
        child_ids = [
            str(rid)
            for rid in (run.child_run_ids or [])
            if str(rid) not in runs
        ]
        for i in range(0, len(child_ids), BATCH_SIZE):
            batch = child_ids[i : i + BATCH_SIZE]
            for child in client.list_shared_runs(share_url, run_ids=batch):
                runs[str(child.id)] = child
                queue.append(child)

    return root, runs


def duration_ms(run) -> float | None:
    if run.start_time and run.end_time:
        return (run.end_time - run.start_time).total_seconds() * 1000
    return None


def fmt_json(value: Any, limit: int = 8000) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n... [truncated, total {len(text)} chars]"


def extract_messages(payload: Any) -> list[dict] | None:
    if not isinstance(payload, dict):
        return None
    for key in ("messages", "input", "prompt"):
        val = payload.get(key)
        if isinstance(val, list) and val and isinstance(val[0], dict):
            if "role" in val[0] or "content" in val[0]:
                return val
    return None


def render_messages(messages: list[dict]) -> str:
    lines = []
    for i, msg in enumerate(messages, 1):
        role = msg.get("role", msg.get("type", "unknown"))
        content = msg.get("content", msg.get("text", ""))
        if isinstance(content, list):
            content = json.dumps(content, ensure_ascii=False, indent=2)
        lines.append(f"**Message {i} ({role})**\n\n```\n{content}\n```")
    return "\n\n".join(lines)


def build_tree_lines(runs: dict[str, Any], root_id: str) -> list[str]:
    children: dict[str | None, list[str]] = defaultdict(list)
    for run in runs.values():
        parent = str(run.parent_run_id) if run.parent_run_id else None
        children[parent].append(str(run.id))

    for ids in children.values():
        ids.sort(
            key=lambda rid: runs[rid].dotted_order
            if runs[rid].dotted_order
            else runs[rid].start_time.isoformat()
        )

    lines: list[str] = []

    def walk(run_id: str, depth: int = 0) -> None:
        run = runs[run_id]
        ms = duration_ms(run)
        latency = f", {ms:.0f}ms" if ms is not None else ""
        tokens = f", {run.total_tokens or 0} tok" if run.total_tokens else ""
        err = " ⚠️ ERROR" if run.error else ""
        lines.append(
            f"{'  ' * depth}- `{run.name}` ({run.run_type}{latency}{tokens}){err}"
        )
        for child_id in children.get(run_id, []):
            walk(child_id, depth + 1)

    walk(root_id)
    return lines


def render_run_section(run) -> str:
    ms = duration_ms(run)
    header = [
        f"## {run.name}",
        "",
        f"- **Type**: `{run.run_type}`",
        f"- **Status**: `{run.status}`",
        f"- **Run ID**: `{run.id}`",
    ]
    if ms is not None:
        header.append(f"- **Latency**: {ms:.0f} ms")
    if run.total_tokens:
        header.append(f"- **Tokens**: {run.total_tokens}")
    if run.error:
        header.append(f"- **Error**: `{run.error}`")
    header.append("")

    body: list[str] = []

    for label, payload in (("Inputs", run.inputs), ("Outputs", run.outputs)):
        if not payload:
            continue
        messages = extract_messages(payload)
        body.append(f"### {label}")
        if messages:
            body.append(render_messages(messages))
        else:
            body.append(f"```json\n{fmt_json(payload)}\n```")
        body.append("")

    return "\n".join(header + body)


def _graph_from_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    if "nodes" in payload and "links" in payload:
        return payload
    graph = payload.get("graph")
    if isinstance(graph, dict) and "nodes" in graph and "links" in graph:
        return graph
    artifact = payload.get("artifact")
    if isinstance(artifact, dict):
        return _graph_from_payload(artifact)
    return None


def extract_final_topology(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the final physical-stage topology graph from serialized runs."""
    for run in reversed(runs):
        outputs = run.get("outputs") or {}
        if not isinstance(outputs, dict):
            continue
        if run.get("name") == "finalize":
            result = outputs.get("result") or {}
            if result.get("stage_id") == "physical":
                graph = _graph_from_payload(result.get("artifact") or {})
                if graph and graph.get("stage") == "physical":
                    return graph
        for value in outputs.values():
            graph = _graph_from_payload(value)
            if graph and graph.get("stage") == "physical":
                return graph
    return None


def write_topology_assets(out_dir: Path, graph: dict[str, Any]) -> tuple[Path, Path, Path | None]:
    json_path = out_dir / "topology.json"
    mmd_path = out_dir / "topology.mmd"
    png_path = out_dir / "topology.png"

    json_path.write_text(
        json.dumps(graph, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    tgraph = TGraph.model_validate(graph)
    rendered: Path | None = None
    try:
        result = write_diagram(tgraph, png_path, format="png")
        rendered = result.png_path
        if result.mermaid_path is not None:
            mmd_path = result.mermaid_path
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"Warning: could not render topology.png ({exc})")
        mmd_path.write_text(render_mermaid(tgraph), encoding="utf-8")

    return json_path, mmd_path, rendered


def write_readme(out_dir: Path, share_url: str, *, has_topology: bool) -> Path:
    readme = out_dir / "README.md"
    topology_lines = [
        "- `topology.png` — Final network topology produced by the agent (physical stage)",
        "- `topology.mmd` — Mermaid source for the topology diagram",
        "- `topology.json` — Structured graph export (nodes, links, ports)",
    ] if has_topology else []

    readme.write_text(
        "\n".join(
            [
                "# Review Package",
                "",
                "Static export of a LangSmith Agent execution trace for offline peer review.",
                "",
                "## Contents",
                "",
                *topology_lines,
                "- `trace.md` — Human-readable trace export (recommended starting point)",
                "- `trace.json` — Complete raw trace archive for programmatic inspection",
                f"- **Online trace (optional):** {share_url}",
                "",
                "## Suggested reading order",
                "",
                "1. Open `topology.png` to see the final network layout the agent produced.",
                "2. Read the **Execution Tree** at the top of `trace.md` to understand the pipeline.",
                "3. Drill into stage spans (`ground`, `logical`, `physical`) and inspect LLM/tool I/O.",
                "4. Use `trace.json` when you need the full unabridged payload for verification.",
                "",
                "## Notes for reviewers",
                "",
                "- This package is a point-in-time snapshot suitable for archival review.",
                "- The online LangSmith link is provided only as a convenience; the files above are the primary record.",
                "- Prompts, tool calls, and intermediate artifacts are preserved in `trace.md` / `trace.json`.",
            ]
        ),
        encoding="utf-8",
    )
    return readme


def run_to_dict(run) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "trace_id": str(run.trace_id),
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "name": run.name,
        "run_type": run.run_type,
        "status": run.status,
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "dotted_order": run.dotted_order,
        "inputs": run.inputs,
        "outputs": run.outputs,
        "error": run.error,
        "total_tokens": run.total_tokens,
        "tags": run.tags,
        "extra": run.extra,
    }


def build_trace_header(
    *,
    share_url: str,
    root_name: str,
    root_status: str,
    run_count: int,
    total_tokens: int,
    exported_at: str,
    include_topology: bool,
) -> list[str]:
    lines = [
        "# LangSmith Agent Trace Export",
        "",
        f"- **Source**: {share_url}",
        f"- **Root run**: `{root_name}`",
        f"- **Status**: `{root_status}`",
        f"- **Total spans**: {run_count}",
        f"- **Total tokens**: {total_tokens}",
        f"- **Exported at**: {exported_at}",
        "",
    ]
    if include_topology:
        lines.extend(
            [
                "## Network Topology",
                "",
                "Final physical-stage topology produced by the agent:",
                "",
                "![Network topology](topology.png)",
                "",
            ]
        )
    return lines


def patch_trace_markdown(md_path: Path, header_lines: list[str]) -> None:
    existing = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    marker = "## Execution Tree"
    if marker in existing:
        body = existing.split(marker, 1)[1]
        content = "\n".join(header_lines) + "\n\n" + marker + body
    else:
        content = "\n".join(header_lines)
    md_path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export a LangSmith public/shared trace to Markdown + JSON."
    )
    parser.add_argument("--url", help="LangSmith public share URL")
    parser.add_argument("--from-json", help="Regenerate docs from an existing trace.json")
    parser.add_argument("--out", default="./review-package", help="Output directory")
    args = parser.parse_args()

    if not args.url and not args.from_json:
        parser.error("Provide --url or --from-json")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.from_json:
        archive = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        share_url = archive.get("share_url") or args.url or ""
        serialized_runs = archive["runs"]
        root_meta = next(
            (run for run in serialized_runs if run.get("id") == archive.get("root_run_id")),
            serialized_runs[0],
        )
        root_name = root_meta.get("name", "trace.run")
        root_status = root_meta.get("status", "unknown")
        run_count = archive.get("run_count", len(serialized_runs))
        exported_at = archive.get("exported_at", datetime.now(timezone.utc).isoformat())
    else:
        client = Client()
        print("Fetching trace tree ...")
        root, runs = fetch_all_runs(client, args.url)
        print(f"Fetched {len(runs)} runs")

        ordered = sorted(
            runs.values(),
            key=lambda r: r.dotted_order or (r.start_time.isoformat() if r.start_time else ""),
        )

        share_url = args.url
        root_name = root.name
        root_status = root.status
        run_count = len(runs)
        exported_at = datetime.now(timezone.utc).isoformat()
        serialized_runs = [run_to_dict(r) for r in ordered]
        archive = {
            "share_url": share_url,
            "exported_at": exported_at,
            "root_run_id": str(root.id),
            "run_count": run_count,
            "runs": serialized_runs,
        }
    json_path = out_dir / "trace.json"
    json_path.write_text(
        json.dumps(archive, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    total_tokens = sum(run.get("total_tokens") or 0 for run in serialized_runs)
    topology = extract_final_topology(serialized_runs)
    header_lines = build_trace_header(
        share_url=share_url,
        root_name=root_name,
        root_status=root_status,
        run_count=run_count,
        total_tokens=total_tokens,
        exported_at=exported_at,
        include_topology=topology is not None,
    )

    md_path = out_dir / "trace.md"
    if args.from_json:
        patch_trace_markdown(md_path, header_lines)
    else:
        md_lines = [
            *header_lines,
            "## Execution Tree",
            "",
            *build_tree_lines(runs, archive["root_run_id"]),
            "",
            "---",
            "",
        ]
        for run_obj in ordered:
            md_lines.append(render_run_section(run_obj))
            md_lines.append("\n---\n")
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

    topology_paths: list[Path] = []
    if topology:
        json_topo, mmd_topo, png_topo = write_topology_assets(out_dir, topology)
        topology_paths.extend([json_topo, mmd_topo])
        if png_topo:
            topology_paths.append(png_topo)

    readme = write_readme(out_dir, share_url, has_topology=topology is not None)

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    for path in topology_paths:
        print(f"Wrote {path}")
    print(f"Wrote {readme}")


if __name__ == "__main__":
    main()
