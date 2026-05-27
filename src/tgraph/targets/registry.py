from __future__ import annotations

from tgraph.core.graph import TGraph
from tgraph.targets import pulumi, terraform, tosca
from tgraph.targets.base import EmitOptions, TargetEmitter
from tgraph.targets.result import EmitResult

_EMITTERS: dict[str, TargetEmitter] = {
    "pulumi": pulumi.emitter,
    "terraform": terraform.emitter,
    "tosca": tosca.emitter,
}


def list_targets() -> list[str]:
    return sorted(_EMITTERS)


def get_target(name: str) -> TargetEmitter | None:
    return _EMITTERS.get(name)


def emit_target(name: str, graph: TGraph | dict, options: EmitOptions | None = None) -> EmitResult:
    emitter = get_target(name)
    if emitter is None:
        return EmitResult(
            ok=False,
            target=name,
            error={"code": "target_error", "message": f"unknown target: {name}"},
        )
    current = graph if isinstance(graph, TGraph) else TGraph.model_validate(graph)
    return emitter.emit(current, options)

