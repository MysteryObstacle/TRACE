from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from agent.langchain.tracing import TraceRecorder
from agent.ports import ReasonerPort
from agent.types import AgentRequest
from app.contracts import ArtifactRef, ValidationReport
from app.errors import StageRuntimeError
from artifacts.selectors import resolve_inputs
from artifacts.store import ArtifactStore
from stages.ground.guard import assert_valid as assert_ground_valid
from stages.ground.normalize import expand_node_patterns
from stages.ground.output_schema import GroundOutput
from stages.logical.guard import assert_valid as assert_logical_valid
from stages.logical.output_schema import LogicalOutput
from stages.physical.guard import assert_valid as assert_physical_valid
from stages.physical.output_schema import PhysicalOutput
from validators.patching import apply_patch_ops


CheckpointRunner = Callable[[dict[str, Any], list[dict[str, Any]], str], ValidationReport]


class StageRunResult(BaseModel):
    stage_id: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    output_refs: list[ArtifactRef] = Field(default_factory=list)
    attempts: int = 1
    validation_report: ValidationReport | None = None


class StageRuntime:
    def __init__(
        self,
        artifact_store: ArtifactStore,
        agent_facade: ReasonerPort,
        stage_specs: dict[str, Any],
        checkpoint_runner: CheckpointRunner | None = None,
        tracer: TraceRecorder | None = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.agent_facade = agent_facade
        self.stage_specs = stage_specs
        self.checkpoint_runner = checkpoint_runner
        self.tracer = tracer or TraceRecorder(enabled=False)

    def run_stage(self, stage_id: str) -> StageRunResult:
        spec = self.stage_specs[stage_id]
        attempt = 1

        with self.tracer.stage_run(stage_id=stage_id):
            while attempt <= spec.max_rounds:
                inputs = resolve_inputs(self.artifact_store, spec.inputs)
                request = AgentRequest(stage_id=stage_id, prompt=spec.prompt_path, inputs=inputs)
                response = self.agent_facade.invoke(request)
                output_refs = self._persist_stage_output(stage_id, response.output)
                validation_report = self._validate_stage_output(stage_id, response.output)

                if validation_report is None or validation_report.ok or spec.repair_mode == 'none':
                    return StageRunResult(
                        stage_id=stage_id,
                        inputs=inputs,
                        output_refs=output_refs,
                        attempts=attempt,
                        validation_report=validation_report,
                    )

                attempt += 1

        raise StageRuntimeError(f'Stage {stage_id} exceeded max repair rounds.')

    def _persist_stage_output(self, stage_id: str, output: dict[str, Any]) -> list[ArtifactRef]:
        if stage_id == 'ground':
            return self._persist_ground_output(output)
        if stage_id == 'logical':
            return self._persist_logical_output(output)
        if stage_id == 'physical':
            return self._persist_physical_output(output)
        raise StageRuntimeError(f'Unsupported stage: {stage_id}')

    def _validate_stage_output(self, stage_id: str, output: dict[str, Any]) -> ValidationReport | None:
        if self.checkpoint_runner is None or stage_id == 'ground':
            return None

        with self.tracer.validation_run(stage_id=stage_id):
            if stage_id == 'logical':
                model = LogicalOutput.model_validate(output)
                payload = model.model_dump(mode='json')
                return self.checkpoint_runner(
                    self._resolve_logical_graph(payload),
                    payload['logical_checkpoints'],
                    str(self.artifact_store.root / 'logical' / 'artifacts'),
                )

            if stage_id == 'physical':
                model = PhysicalOutput.model_validate(output)
                payload = model.model_dump(mode='json')
                return self.checkpoint_runner(
                    self._resolve_physical_graph(payload),
                    payload['physical_checkpoints'],
                    str(self.artifact_store.root / 'physical' / 'artifacts'),
                )

        return None

    def _persist_ground_output(self, output: dict[str, Any]) -> list[ArtifactRef]:
        model = GroundOutput.model_validate(output)
        assert_ground_valid(model)
        payload = model.model_dump(mode='json')
        refs = [
            self.artifact_store.write('ground', 'node_patterns', payload['node_patterns']),
            self.artifact_store.write(
                'ground',
                'expanded_node_ids',
                expand_node_patterns(model.node_patterns),
            ),
            self.artifact_store.write('ground', 'logical_constraints', payload['logical_constraints']),
            self.artifact_store.write('ground', 'physical_constraints', payload['physical_constraints']),
        ]
        return refs

    def _persist_logical_output(self, output: dict[str, Any]) -> list[ArtifactRef]:
        model = LogicalOutput.model_validate(output)
        assert_logical_valid(model)
        payload = model.model_dump(mode='json')
        graph = self._resolve_logical_graph(payload)
        refs = [
            self.artifact_store.write('logical', 'logical_checkpoints', payload['logical_checkpoints']),
            self.artifact_store.write('logical', 'tgraph_logical', graph),
        ]
        if payload['logical_validator_script'] is not None:
            refs.append(
                self.artifact_store.write(
                    'logical',
                    'logical_validator_script',
                    payload['logical_validator_script'],
                )
            )
        return refs

    def _persist_physical_output(self, output: dict[str, Any]) -> list[ArtifactRef]:
        model = PhysicalOutput.model_validate(output)
        assert_physical_valid(model)
        payload = model.model_dump(mode='json')
        graph = self._resolve_physical_graph(payload)
        refs = [
            self.artifact_store.write('physical', 'physical_checkpoints', payload['physical_checkpoints']),
            self.artifact_store.write('physical', 'tgraph_physical', graph),
        ]
        if payload['physical_validator_script'] is not None:
            refs.append(
                self.artifact_store.write(
                    'physical',
                    'physical_validator_script',
                    payload['physical_validator_script'],
                )
            )
        return refs

    def _resolve_logical_graph(self, payload: dict[str, Any]) -> dict[str, Any]:
        graph = payload.get('tgraph_logical') or {}
        if graph:
            return graph
        return apply_patch_ops({'profile': 'logical.v1', 'nodes': [], 'links': []}, payload.get('logical_patch_ops', []))

    def _resolve_physical_graph(self, payload: dict[str, Any]) -> dict[str, Any]:
        graph = payload.get('tgraph_physical') or {}
        if graph:
            return graph
        return apply_patch_ops({'profile': 'taal.default.v1', 'nodes': [], 'links': []}, payload.get('physical_patch_ops', []))
