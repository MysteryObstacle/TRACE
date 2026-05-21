from __future__ import annotations

import json
from typing import Any

from langchain.tools import tool
from pydantic import BaseModel

from trace.tools.tgraph.prompting import get_tgraph_tool_doc
from trace.tools.tgraph.runtime import TGraphRuntime
from trace.tools.tgraph.validate.issues import issue
from trace.tools.tgraph.validate import run_default_validators


class _UpdateCheckpointToolInput(BaseModel):
    checkpoint_id: str
    func: str | None = None
    description: str | None = None
    constraint_ids: list[str] | None = None
    args: dict[str, Any] | None = None


class _UpdateNodeToolInput(BaseModel):
    node_id: str
    ports: Any = None
    type: str | None = None
    label: str | None = None
    image: Any = None
    flavor: Any = None


class BoundTGraphTools:
    _MUTATION_LEVELS = ["f1", "f2"]

    def __init__(
        self,
        runtime: TGraphRuntime,
        *,
        graph_field: str,
        checkpoints_field: str,
        validator_script_field: str,
        checkpoints: list[dict[str, Any]] | None = None,
        validator_script: str | None = None,
        constraints: list[dict[str, Any]] | None = None,
    ) -> None:
        self._runtime = runtime
        self._checkpoints = [dict(item) for item in (checkpoints or []) if isinstance(item, dict)]
        self._constraints = [dict(item) for item in (constraints or []) if isinstance(item, dict)]
        self._graph_field = str(graph_field).strip()
        self._checkpoints_field = str(checkpoints_field).strip()
        self._validator_script_field = str(validator_script_field).strip()
        self._validator_script = validator_script

    @classmethod
    def from_json(
        cls,
        graph_json: dict[str, Any],
        *,
        graph_field: str,
        checkpoints_field: str,
        validator_script_field: str,
        checkpoints: list[dict[str, Any]] | None = None,
        validator_script: str | None = None,
        constraints: list[dict[str, Any]] | None = None,
    ) -> "BoundTGraphTools":
        return cls(
            TGraphRuntime.from_json(graph_json),
            graph_field=graph_field,
            checkpoints_field=checkpoints_field,
            validator_script_field=validator_script_field,
            checkpoints=checkpoints,
            validator_script=validator_script,
            constraints=constraints,
        )

    def topology_view(self) -> dict[str, list[str]]:
        return self._runtime.topology_view()

    def find_checkpoints(
        self,
        *,
        node_ids: list[str] | None = None,
        constraint_ids: list[str] | None = None,
        cidrs: list[str] | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        requested_nodes = {str(item).strip() for item in (node_ids or []) if str(item).strip()}
        requested_constraints = {str(item).strip() for item in (constraint_ids or []) if str(item).strip()}
        requested_cidrs = {str(item).strip() for item in (cidrs or []) if str(item).strip()}
        query_text = str(query or "").strip().lower()
        query_terms = [item for item in query_text.split() if item]
        normalized_limit = max(1, min(int(limit), 50))

        scored: list[tuple[int, dict[str, Any]]] = []
        for checkpoint in self._checkpoints:
            score = _checkpoint_match_score(
                checkpoint,
                node_ids=requested_nodes,
                constraint_ids=requested_constraints,
                cidrs=requested_cidrs,
                query_terms=query_terms,
            )
            if score <= 0 and (requested_nodes or requested_constraints or requested_cidrs or query_terms):
                continue
            scored.append((score, checkpoint))

        scored.sort(key=lambda item: (-item[0], str(item[1].get("id") or "")))
        return [dict(item) for _, item in scored[:normalized_limit]]

    def get_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        for checkpoint in self._checkpoints:
            if str(checkpoint.get("id") or "") == checkpoint_id:
                return dict(checkpoint)
        raise KeyError(f"unknown checkpoint id: {checkpoint_id}")

    def add_checkpoint(self, checkpoint: dict[str, Any]) -> dict[str, Any]:
        checkpoint_id = str(checkpoint.get("id") or "").strip()
        if not checkpoint_id:
            return {
                "ok": False,
                "issues": [issue("checkpoint_id_required", "checkpoint id is required")],
                "change_map": {},
            }
        if any(str(item.get("id") or "") == checkpoint_id for item in self._checkpoints):
            return {
                "ok": False,
                "issues": [issue("checkpoint_id_exists", f"checkpoint id already exists: {checkpoint_id}")],
                "change_map": {},
            }
        self._checkpoints.append(dict(checkpoint))
        return {"ok": True, "issues": [], "change_map": {}}

    def update_checkpoint(
        self,
        checkpoint_id: str,
        *,
        func: str | None = None,
        description: str | None = None,
        constraint_ids: list[str] | None = None,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for checkpoint in self._checkpoints:
            if str(checkpoint.get("id") or "") != checkpoint_id:
                continue
            if func is not None:
                checkpoint["func"] = func
            if description is not None:
                checkpoint["description"] = description
            if constraint_ids is not None:
                checkpoint["constraint_ids"] = list(constraint_ids)
            if args is not None:
                checkpoint["args"] = dict(args)
            return {"ok": True, "issues": [], "change_map": {}}
        return {
            "ok": False,
            "issues": [issue("checkpoint_id_unknown", f"unknown checkpoint id: {checkpoint_id}")],
            "change_map": {},
        }

    def remove_checkpoint(self, checkpoint_id: str) -> dict[str, Any]:
        for index, checkpoint in enumerate(list(self._checkpoints)):
            if str(checkpoint.get("id") or "") != checkpoint_id:
                continue
            del self._checkpoints[index]
            return {"ok": True, "issues": [], "change_map": {}}
        return {
            "ok": False,
            "issues": [issue("checkpoint_id_unknown", f"unknown checkpoint id: {checkpoint_id}")],
            "change_map": {},
        }

    def get_validator_script(self) -> dict[str, Any]:
        return {"script": self._validator_script}

    def replace_validator_script(self, script: str | None) -> dict[str, Any]:
        self._validator_script = script
        return {"ok": True, "issues": [], "change_map": {}}

    def get_node(self, node_id: str) -> dict[str, Any]:
        return self._runtime.get_node(node_id)

    def get_nodes(self, node_ids: list[str] | None = None) -> list[dict[str, Any]]:
        return self._runtime.get_nodes(node_ids)

    def get_link(self, link_id: str) -> dict[str, Any]:
        return self._runtime.get_link(link_id)

    def get_links(
        self,
        link_ids: list[str] | None = None,
        *,
        node_id: str | None = None,
        port_id: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._runtime.get_links(link_ids, node_id=node_id, port_id=port_id)

    def validate(self) -> dict[str, Any]:
        validate_kwargs: dict[str, Any] = {self._checkpoints_field: [dict(item) for item in self._checkpoints]}
        if self._constraints:
            constraints_field = "logical_constraints" if self._checkpoints_field == "logical_checkpoints" else "physical_constraints"
            validate_kwargs[constraints_field] = [dict(item) for item in self._constraints]
        if self._validator_script is not None:
            validate_kwargs[self._validator_script_field] = self._validator_script
        return run_default_validators(self._runtime.to_json(), **validate_kwargs).model_dump(mode="json")

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        image: dict[str, Any] | None = None,
        flavor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._runtime.add_node(
            node_id=node_id,
            node_type=node_type,
            label=label,
            image=image,
            flavor=flavor,
            levels=self._MUTATION_LEVELS,
        )

    def update_node(
        self,
        node_id: str,
        ports: list[dict[str, Any]] | None = None,
        node_type: str | None = None,
        label: str | None = None,
        image: dict[str, Any] | None = None,
        flavor: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if ports is not None:
            attrs["ports"] = _coerce_json_structure(ports)
        if node_type is not None:
            attrs["type"] = node_type
        if label is not None:
            attrs["label"] = label
        if image is not None:
            attrs["image"] = _coerce_json_structure(image)
        if flavor is not None:
            attrs["flavor"] = _coerce_json_structure(flavor)
        return self._runtime.update_node(node_id=node_id, levels=self._MUTATION_LEVELS, **attrs)

    def add_link(
        self,
        from_port: str,
        to_port: str,
        from_node: str | None = None,
        to_node: str | None = None,
        from_ip: str = "",
        from_cidr: str = "",
        to_ip: str = "",
        to_cidr: str = "",
    ) -> dict[str, Any]:
        return self._runtime.add_link(
            from_port=from_port,
            to_port=to_port,
            from_node=from_node,
            to_node=to_node,
            from_ip=from_ip,
            from_cidr=from_cidr,
            to_ip=to_ip,
            to_cidr=to_cidr,
            levels=self._MUTATION_LEVELS,
        )

    def update_link(
        self,
        link_id: str,
        *,
        from_port: str,
        to_port: str,
        from_node: str | None = None,
        to_node: str | None = None,
        from_ip: str = "",
        from_cidr: str = "",
        to_ip: str = "",
        to_cidr: str = "",
    ) -> dict[str, Any]:
        return self._runtime.update_link(
            link_id=link_id,
            from_port=from_port,
            to_port=to_port,
            from_node=from_node,
            to_node=to_node,
            from_ip=from_ip,
            from_cidr=from_cidr,
            to_ip=to_ip,
            to_cidr=to_cidr,
            levels=self._MUTATION_LEVELS,
        )

    def remove_link(self, link_id: str) -> dict[str, Any]:
        return self._runtime.remove_link(link_id=link_id, levels=self._MUTATION_LEVELS)

    def remove_node(self, node_id: str, cascade: bool = True) -> dict[str, Any]:
        return self._runtime.remove_node(node_id=node_id, cascade=cascade, levels=self._MUTATION_LEVELS)

    def tools(self):
        def topology_view_tool() -> dict[str, list[str]]:
            return self.topology_view()

        def find_checkpoints_tool(
            node_ids: list[str] | None = None,
            constraint_ids: list[str] | None = None,
            cidrs: list[str] | None = None,
            query: str | None = None,
            limit: int = 10,
        ) -> list[dict[str, Any]]:
            return self.find_checkpoints(
                node_ids=node_ids,
                constraint_ids=constraint_ids,
                cidrs=cidrs,
                query=query,
                limit=limit,
            )

        def get_checkpoint_tool(checkpoint_id: str) -> dict[str, Any]:
            return self.get_checkpoint(checkpoint_id)

        def add_checkpoint_tool(checkpoint: dict[str, Any]) -> dict[str, Any]:
            return self.add_checkpoint(checkpoint)

        def update_checkpoint_tool(
            checkpoint_id: str,
            func: str | None = None,
            description: str | None = None,
            constraint_ids: list[str] | None = None,
            args: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return self.update_checkpoint(
                checkpoint_id,
                func=func,
                description=description,
                constraint_ids=constraint_ids,
                args=args,
            )

        def remove_checkpoint_tool(checkpoint_id: str) -> dict[str, Any]:
            return self.remove_checkpoint(checkpoint_id)

        def get_validator_script_tool() -> dict[str, Any]:
            return self.get_validator_script()

        def replace_validator_script_tool(script: str | None) -> dict[str, Any]:
            return self.replace_validator_script(script)

        def get_node_tool(node_id: str) -> dict[str, Any]:
            return self.get_node(node_id)

        def get_nodes_tool(node_ids: list[str] | None = None) -> list[dict[str, Any]]:
            return self.get_nodes(node_ids)

        def get_link_tool(link_id: str) -> dict[str, Any]:
            return self.get_link(link_id)

        def get_links_tool(
            link_ids: list[str] | None = None,
            node_id: str | None = None,
            port_id: str | None = None,
        ) -> list[dict[str, Any]]:
            return self.get_links(link_ids, node_id=node_id, port_id=port_id)

        def validate_tool() -> dict[str, Any]:
            return self.validate()

        def add_node_tool(
            node_id: str,
            type: str,
            label: str,
            image: dict[str, Any] | None = None,
            flavor: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            return self.add_node(node_id=node_id, node_type=type, label=label, image=image, flavor=flavor)

        def update_node_tool(
            node_id: str,
            ports: Any = None,
            type: str | None = None,
            label: str | None = None,
            image: Any = None,
            flavor: Any = None,
        ) -> dict[str, Any]:
            return self.update_node(
                node_id=node_id,
                ports=ports,
                node_type=type,
                label=label,
                image=image,
                flavor=flavor,
            )

        def add_link_tool(
            from_port: str,
            to_port: str,
            from_node: str | None = None,
            to_node: str | None = None,
            from_ip: str = "",
            from_cidr: str = "",
            to_ip: str = "",
            to_cidr: str = "",
        ) -> dict[str, Any]:
            return self.add_link(
                from_port=from_port,
                to_port=to_port,
                from_node=from_node,
                to_node=to_node,
                from_ip=from_ip,
                from_cidr=from_cidr,
                to_ip=to_ip,
                to_cidr=to_cidr,
            )

        def update_link_tool(
            link_id: str,
            from_port: str,
            to_port: str,
            from_node: str | None = None,
            to_node: str | None = None,
            from_ip: str = "",
            from_cidr: str = "",
            to_ip: str = "",
            to_cidr: str = "",
        ) -> dict[str, Any]:
            return self.update_link(
                link_id=link_id,
                from_port=from_port,
                to_port=to_port,
                from_node=from_node,
                to_node=to_node,
                from_ip=from_ip,
                from_cidr=from_cidr,
                to_ip=to_ip,
                to_cidr=to_cidr,
            )

        def remove_link_tool(link_id: str) -> dict[str, Any]:
            return self.remove_link(link_id=link_id)

        def remove_node_tool(node_id: str, cascade: bool = True) -> dict[str, Any]:
            return self.remove_node(node_id=node_id, cascade=cascade)

        return [
            _decorate_tool("topology_view", topology_view_tool),
            _decorate_tool("find_checkpoints", find_checkpoints_tool),
            _decorate_tool("get_checkpoint", get_checkpoint_tool),
            _decorate_tool("add_checkpoint", add_checkpoint_tool),
            _decorate_tool("update_checkpoint", update_checkpoint_tool, args_schema=_UpdateCheckpointToolInput),
            _decorate_tool("remove_checkpoint", remove_checkpoint_tool),
            _decorate_tool("get_validator_script", get_validator_script_tool),
            _decorate_tool("replace_validator_script", replace_validator_script_tool),
            _decorate_tool("get_node", get_node_tool),
            _decorate_tool("get_nodes", get_nodes_tool),
            _decorate_tool("get_link", get_link_tool),
            _decorate_tool("get_links", get_links_tool),
            _decorate_tool("validate", validate_tool),
            _decorate_tool("add_node", add_node_tool),
            _decorate_tool("update_node", update_node_tool, args_schema=_UpdateNodeToolInput),
            _decorate_tool("add_link", add_link_tool),
            _decorate_tool("update_link", update_link_tool),
            _decorate_tool("remove_link", remove_link_tool),
            _decorate_tool("remove_node", remove_node_tool),
        ]

    def to_json(self) -> dict[str, Any]:
        return self._runtime.to_json()

    def artifact_state(self) -> dict[str, Any]:
        return {
            self._graph_field: self._runtime.to_json(),
            self._checkpoints_field: [dict(item) for item in self._checkpoints],
            self._validator_script_field: self._validator_script,
        }


def _decorate_tool(name: str, func, *, args_schema: type[BaseModel] | None = None):
    func.__doc__ = get_tgraph_tool_doc(name)
    if args_schema is None:
        return tool(name)(func)
    return tool(name, args_schema=args_schema)(func)


def _checkpoint_match_score(
    checkpoint: dict[str, Any],
    *,
    node_ids: set[str],
    constraint_ids: set[str],
    cidrs: set[str],
    query_terms: list[str],
) -> int:
    haystack = _checkpoint_haystack(checkpoint)
    score = 0

    for node_id in node_ids:
        if node_id in haystack:
            score += 5
    for constraint_id in constraint_ids:
        if constraint_id in haystack:
            score += 4
    for cidr in cidrs:
        if cidr in haystack:
            score += 5
    for term in query_terms:
        if term in haystack.lower():
            score += 1

    if not (node_ids or constraint_ids or cidrs or query_terms):
        return 1
    return score


def _checkpoint_haystack(checkpoint: dict[str, Any]) -> str:
    parts = [
        str(checkpoint.get("id") or ""),
        str(checkpoint.get("func") or ""),
        str(checkpoint.get("description") or ""),
        " ".join(str(item) for item in checkpoint.get("constraint_ids") or []),
        _flatten_checkpoint_args(checkpoint.get("args") or {}),
    ]
    return " ".join(part for part in parts if part).strip()


def _flatten_checkpoint_args(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_checkpoint_args(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_checkpoint_args(item) for item in value)
    return str(value)


def _coerce_json_structure(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value
