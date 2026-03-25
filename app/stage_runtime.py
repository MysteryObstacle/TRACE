from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from agent.langchain.tracing import TraceRecorder
from agent.ports import ReasonerPort
from agent.types import AgentRequest
from app.contracts import ArtifactRef, FailureType, StageMode, ValidationReport
from app.errors import StageRuntimeError
from app.progress import ProgressReporter
from app.stage_graphs import build_logical_skeleton, build_physical_skeleton
from artifacts.summarizer import build_repair_context
from artifacts.selectors import resolve_inputs
from artifacts.store import ArtifactStore
from stages.ground.guard import assert_valid as assert_ground_valid
from stages.ground.normalize import expand_node_patterns
from stages.ground.output_schema import GroundOutput, sanitize_ground_output
from stages.logical.guard import assert_valid as assert_logical_valid
from stages.logical.output_schema import LogicalOutput
from stages.physical.guard import assert_valid as assert_physical_valid
from stages.physical.output_schema import PhysicalOutput
from validators.patching import apply_patch_ops, apply_patch_result


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
        reporter: ProgressReporter | None = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.agent_facade = agent_facade
        self.stage_specs = stage_specs
        self.checkpoint_runner = checkpoint_runner
        self.tracer = tracer or TraceRecorder(enabled=False)
        self.reporter = reporter or ProgressReporter()

    def bind_artifact_store(self, artifact_store: ArtifactStore) -> None:
        self.artifact_store = artifact_store

    def run_stage(self, stage_id: str) -> StageRunResult:
        if stage_id == 'logical':
            return self._run_logical_stage()
        if stage_id == 'physical':
            return self._run_physical_stage()

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

                self.reporter.repair_round(stage_id, attempt + 1, spec.max_rounds)
                attempt += 1

        raise StageRuntimeError(f'Stage {stage_id} exceeded max repair rounds.')

    def _run_logical_stage(self) -> StageRunResult:
        spec = self.stage_specs['logical']
        attempt = 1

        with self.tracer.stage_run(stage_id='logical'):
            inputs = resolve_inputs(self.artifact_store, spec.inputs)
            base_graph = build_logical_skeleton(inputs['ground.expanded_node_ids'])
            payload = self._run_logical_author_and_builder(spec.prompt_path, inputs)
            current_graph, patch_report = self._try_resolve_logical_graph(payload, base_graph)
            validation_report = patch_report
            output_refs: list[ArtifactRef] = []
            if current_graph is not None:
                output_refs = self._persist_logical_output(payload, current_graph)
                validation_report = self._validate_logical_output(payload, current_graph)

                if validation_report is None or validation_report.ok or spec.repair_mode == 'none':
                    return StageRunResult(
                        stage_id='logical',
                        inputs=inputs,
                        output_refs=output_refs,
                        attempts=attempt,
                        validation_report=validation_report,
                    )
            else:
                current_graph = base_graph

            while attempt < spec.max_rounds:
                attempt += 1
                self.reporter.repair_round('logical', attempt, spec.max_rounds)
                payload = self._run_logical_repair(
                    spec.prompt_path,
                    inputs,
                    payload,
                    current_graph,
                    validation_report,
                )
                next_graph, patch_report = self._try_resolve_logical_graph(payload, current_graph)
                if next_graph is None:
                    validation_report = patch_report
                    continue

                current_graph = next_graph
                output_refs = self._persist_logical_output(payload, current_graph)
                validation_report = self._validate_logical_output(payload, current_graph)
                if validation_report is None or validation_report.ok:
                    return StageRunResult(
                        stage_id='logical',
                        inputs=inputs,
                        output_refs=output_refs,
                        attempts=attempt,
                        validation_report=validation_report,
                    )

        raise StageRuntimeError('Stage logical exceeded max repair rounds.')

    def _run_physical_stage(self) -> StageRunResult:
        spec = self.stage_specs['physical']
        attempt = 1

        with self.tracer.stage_run(stage_id='physical'):
            inputs = resolve_inputs(self.artifact_store, spec.inputs)
            logical_graph = inputs['logical.tgraph_logical']
            base_graph = build_physical_skeleton(logical_graph)
            payload = self._run_physical_author_and_builder(spec.prompt_path, inputs)
            current_graph, patch_report = self._try_resolve_physical_graph(payload, base_graph, logical_graph)
            validation_report = patch_report
            output_refs: list[ArtifactRef] = []
            if current_graph is not None:
                output_refs = self._persist_physical_output(payload, current_graph)
                validation_report = self._validate_physical_output(payload, current_graph)

                if validation_report is None or validation_report.ok or spec.repair_mode == 'none':
                    return StageRunResult(
                        stage_id='physical',
                        inputs=inputs,
                        output_refs=output_refs,
                        attempts=attempt,
                        validation_report=validation_report,
                    )

                self._raise_if_stage_boundary_report(validation_report, 'physical')
            else:
                current_graph = base_graph

            while attempt < spec.max_rounds:
                attempt += 1
                self.reporter.repair_round('physical', attempt, spec.max_rounds)
                payload = self._run_physical_repair(
                    spec.prompt_path,
                    inputs,
                    payload,
                    current_graph,
                    validation_report,
                )
                next_graph, patch_report = self._try_resolve_physical_graph(payload, current_graph, logical_graph)
                if next_graph is None:
                    validation_report = patch_report
                    continue

                current_graph = next_graph
                output_refs = self._persist_physical_output(payload, current_graph)
                validation_report = self._validate_physical_output(payload, current_graph)
                if validation_report is None or validation_report.ok:
                    return StageRunResult(
                        stage_id='physical',
                        inputs=inputs,
                        output_refs=output_refs,
                        attempts=attempt,
                        validation_report=validation_report,
                    )
                self._raise_if_stage_boundary_report(validation_report, 'physical')

        raise StageRuntimeError('Stage physical exceeded max repair rounds.')

    def _persist_stage_output(self, stage_id: str, output: dict[str, Any]) -> list[ArtifactRef]:
        if stage_id == 'ground':
            return self._persist_ground_output(output)
        if stage_id == 'logical':
            return self._persist_logical_output(output)
        if stage_id == 'physical':
            return self._persist_physical_output(output)
        raise StageRuntimeError(f'Unsupported stage: {stage_id}')

    def _validate_stage_output(self, stage_id: str, output: dict[str, Any]) -> ValidationReport | None:
        return None

    def _persist_ground_output(self, output: dict[str, Any]) -> list[ArtifactRef]:
        model = sanitize_ground_output(GroundOutput.model_validate(output))
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

    def _persist_logical_output(self, output: dict[str, Any], graph: dict[str, Any] | None = None) -> list[ArtifactRef]:
        model = LogicalOutput.model_validate(output)
        assert_logical_valid(model)
        payload = model.model_dump(mode='json')
        resolved_graph = graph or self._resolve_logical_graph(payload, {'profile': 'logical.v1', 'nodes': [], 'links': []})
        self._materialize_validator_script('logical', payload['logical_checkpoints'], payload['logical_validator_script'])
        refs = [
            self.artifact_store.write('logical', 'logical_checkpoints', payload['logical_checkpoints']),
            self.artifact_store.write('logical', 'tgraph_logical', resolved_graph),
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

    def _persist_physical_output(self, output: dict[str, Any], graph: dict[str, Any] | None = None) -> list[ArtifactRef]:
        model = PhysicalOutput.model_validate(output)
        assert_physical_valid(model)
        payload = model.model_dump(mode='json')
        resolved_graph = graph or self._resolve_physical_graph(payload, {'profile': 'taal.default.v1', 'nodes': [], 'links': []}, {'profile': 'logical.v1', 'nodes': [], 'links': []})
        self._materialize_validator_script('physical', payload['physical_checkpoints'], payload['physical_validator_script'])
        refs = [
            self.artifact_store.write('physical', 'physical_checkpoints', payload['physical_checkpoints']),
            self.artifact_store.write('physical', 'tgraph_physical', resolved_graph),
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

    def _resolve_logical_graph(self, payload: dict[str, Any], base_graph: dict[str, Any]) -> dict[str, Any]:
        graph = payload.get('tgraph_logical') or {}
        if graph:
            return graph
        return apply_patch_ops(base_graph, payload.get('logical_patch_ops', []))

    def _resolve_physical_graph(
        self,
        payload: dict[str, Any],
        base_graph: dict[str, Any],
        logical_graph: dict[str, Any],
    ) -> dict[str, Any]:
        self._assert_physical_boundary(payload, logical_graph)
        graph = payload.get('tgraph_physical') or {}
        if graph:
            self._assert_physical_graph_matches_logical(graph, logical_graph)
            return graph
        patched = apply_patch_ops(base_graph, payload.get('physical_patch_ops', []))
        self._assert_physical_graph_matches_logical(patched, logical_graph)
        return patched

    def _try_resolve_logical_graph(
        self,
        payload: dict[str, Any],
        base_graph: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, ValidationReport | None]:
        graph = payload.get('tgraph_logical') or {}
        if graph:
            return graph, None
        patch_ops = payload.get('logical_patch_ops', [])
        with self.tracer.patch_run(
            stage_id='logical',
            patch_count=len(patch_ops),
            graph_profile=base_graph.get('profile'),
        ):
            result = apply_patch_result(base_graph, patch_ops)
        if result.ok and result.graph is not None:
            return result.graph, None
        return None, ValidationReport(ok=False, issues=result.issues)

    def _try_resolve_physical_graph(
        self,
        payload: dict[str, Any],
        base_graph: dict[str, Any],
        logical_graph: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, ValidationReport | None]:
        self._assert_physical_boundary(payload, logical_graph)
        graph = payload.get('tgraph_physical') or {}
        if graph:
            self._assert_physical_graph_matches_logical(graph, logical_graph)
            return graph, None
        patch_ops = payload.get('physical_patch_ops', [])
        with self.tracer.patch_run(
            stage_id='physical',
            patch_count=len(patch_ops),
            graph_profile=base_graph.get('profile'),
        ):
            result = apply_patch_result(base_graph, patch_ops)
        if not result.ok or result.graph is None:
            return None, ValidationReport(ok=False, issues=result.issues)
        self._assert_physical_graph_matches_logical(result.graph, logical_graph)
        return result.graph, None

    @staticmethod
    def _needs_logical_graph_builder(payload: dict[str, Any]) -> bool:
        return bool(payload.get('logical_checkpoints')) and not payload.get('tgraph_logical') and not payload.get('logical_patch_ops')

    @staticmethod
    def _assert_logical_author_payload(payload: dict[str, Any]) -> None:
        if not payload.get('logical_checkpoints'):
            raise ValueError('Logical check-author output must include at least one checkpoint.')

    @staticmethod
    def _needs_physical_graph_builder(payload: dict[str, Any]) -> bool:
        return bool(payload.get('physical_checkpoints')) and not payload.get('tgraph_physical') and not payload.get('physical_patch_ops')

    @staticmethod
    def _assert_physical_author_payload(payload: dict[str, Any]) -> None:
        if not payload.get('physical_checkpoints'):
            raise ValueError('Physical check-author output must include at least one checkpoint.')

    def _load_latest_artifact(self, stage: str, name: str) -> Any:
        latest = self.artifact_store.read_latest(stage, name)
        if latest is None:
            return None
        _, payload = latest
        return payload

    def _run_logical_author_and_builder(self, prompt: str, inputs: dict[str, Any]) -> dict[str, Any]:
        response = self.agent_facade.invoke(
            AgentRequest(
                stage_id='logical',
                prompt=prompt,
                inputs={**inputs, 'runtime.mode': StageMode.CHECK_AUTHOR.value},
            )
        )
        model = LogicalOutput.model_validate(response.output)
        payload = model.model_dump(mode='json')

        if not self._needs_logical_graph_builder(payload):
            return payload

        self._assert_logical_author_payload(payload)
        response = self.agent_facade.invoke(
            AgentRequest(
                stage_id='logical',
                prompt=prompt,
                inputs={
                    **inputs,
                    'runtime.mode': StageMode.GRAPH_BUILDER.value,
                    'runtime.logical_checkpoints': payload['logical_checkpoints'],
                    'runtime.logical_validator_script': payload['logical_validator_script'],
                },
            )
        )
        builder_model = LogicalOutput.model_validate(response.output)
        return self._merge_logical_payloads(payload, builder_model.model_dump(mode='json'))

    def _run_logical_repair(
        self,
        prompt: str,
        inputs: dict[str, Any],
        payload: dict[str, Any],
        current_graph: dict[str, Any],
        validation_report: ValidationReport,
    ) -> dict[str, Any]:
        response = self.agent_facade.invoke(
            AgentRequest(
                stage_id='logical',
                prompt=prompt,
                inputs={
                    **inputs,
                    'runtime.mode': StageMode.REPAIR.value,
                    'runtime.current_graph': current_graph,
                    'runtime.validation_report': validation_report.model_dump(mode='json'),
                    'runtime.repair_context': build_repair_context(
                        current_graph,
                        validation_report.model_dump(mode='json'),
                        payload.get('logical_patch_ops', []),
                    ),
                    'runtime.logical_checkpoints': payload.get('logical_checkpoints', []),
                    'runtime.logical_validator_script': payload.get('logical_validator_script'),
                },
            )
        )
        repair_model = LogicalOutput.model_validate(response.output)
        return self._merge_logical_payloads(payload, repair_model.model_dump(mode='json'))

    def _run_physical_author_and_builder(self, prompt: str, inputs: dict[str, Any]) -> dict[str, Any]:
        response = self.agent_facade.invoke(
            AgentRequest(
                stage_id='physical',
                prompt=prompt,
                inputs={**inputs, 'runtime.mode': StageMode.CHECK_AUTHOR.value},
            )
        )
        model = PhysicalOutput.model_validate(response.output)
        payload = model.model_dump(mode='json')

        if not self._needs_physical_graph_builder(payload):
            return payload

        self._assert_physical_author_payload(payload)
        response = self.agent_facade.invoke(
            AgentRequest(
                stage_id='physical',
                prompt=prompt,
                inputs={
                    **inputs,
                    'runtime.mode': StageMode.GRAPH_BUILDER.value,
                    'runtime.physical_checkpoints': payload['physical_checkpoints'],
                    'runtime.physical_validator_script': payload['physical_validator_script'],
                },
            )
        )
        builder_model = PhysicalOutput.model_validate(response.output)
        return self._merge_physical_payloads(payload, builder_model.model_dump(mode='json'))

    def _run_physical_repair(
        self,
        prompt: str,
        inputs: dict[str, Any],
        payload: dict[str, Any],
        current_graph: dict[str, Any],
        validation_report: ValidationReport,
    ) -> dict[str, Any]:
        response = self.agent_facade.invoke(
            AgentRequest(
                stage_id='physical',
                prompt=prompt,
                inputs={
                    **inputs,
                    'runtime.mode': StageMode.REPAIR.value,
                    'runtime.current_graph': current_graph,
                    'runtime.validation_report': validation_report.model_dump(mode='json'),
                    'runtime.repair_context': build_repair_context(
                        current_graph,
                        validation_report.model_dump(mode='json'),
                        payload.get('physical_patch_ops', []),
                    ),
                    'runtime.physical_checkpoints': payload.get('physical_checkpoints', []),
                    'runtime.physical_validator_script': payload.get('physical_validator_script'),
                },
            )
        )
        repair_model = PhysicalOutput.model_validate(response.output)
        return self._merge_physical_payloads(payload, repair_model.model_dump(mode='json'))

    def _validate_logical_output(self, payload: dict[str, Any], graph: dict[str, Any]) -> ValidationReport | None:
        if self.checkpoint_runner is None:
            return None
        self._materialize_validator_script('logical', payload['logical_checkpoints'], payload.get('logical_validator_script'))
        logical_checkpoints = self._resolve_checkpoint_script_refs('logical', payload['logical_checkpoints'])
        with self.tracer.validation_run(
            stage_id='logical',
            checkpoint_count=len(logical_checkpoints),
            graph_profile=graph.get('profile'),
        ):
            return self.checkpoint_runner(
                graph,
                logical_checkpoints,
                str(self._artifact_dir('logical')),
            )

    def _validate_physical_output(self, payload: dict[str, Any], graph: dict[str, Any]) -> ValidationReport | None:
        if self.checkpoint_runner is None:
            return None
        self._materialize_validator_script('physical', payload['physical_checkpoints'], payload.get('physical_validator_script'))
        logical_checkpoints = self._resolve_checkpoint_script_refs(
            'logical',
            self._load_latest_artifact('logical', 'logical_checkpoints') or [],
        )
        physical_checkpoints = self._resolve_checkpoint_script_refs('physical', payload['physical_checkpoints'])
        merged_checkpoints = [*logical_checkpoints, *physical_checkpoints]
        with self.tracer.validation_run(
            stage_id='physical',
            checkpoint_count=len(merged_checkpoints),
            graph_profile=graph.get('profile'),
        ):
            return self.checkpoint_runner(
                graph,
                merged_checkpoints,
                str(self._artifact_dir('physical')),
            )

    @staticmethod
    def _merge_logical_payloads(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        merged = dict(overlay)
        if not merged.get('logical_checkpoints'):
            merged['logical_checkpoints'] = base.get('logical_checkpoints', [])
        if merged.get('logical_validator_script') is None:
            merged['logical_validator_script'] = base.get('logical_validator_script')
        return merged

    @staticmethod
    def _merge_physical_payloads(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
        merged = dict(overlay)
        if not merged.get('physical_checkpoints'):
            merged['physical_checkpoints'] = base.get('physical_checkpoints', [])
        if merged.get('physical_validator_script') is None:
            merged['physical_validator_script'] = base.get('physical_validator_script')
        return merged

    def _materialize_validator_script(
        self,
        stage_id: str,
        checkpoints: list[dict[str, Any]],
        script_content: str | None,
    ) -> None:
        if script_content is None:
            return
        refs = sorted({item.get('script_ref') for item in checkpoints if item.get('script_ref')})
        if not refs:
            refs = [f'{stage_id}_validator.py']
        artifact_dir = self._artifact_dir(stage_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        for ref in refs:
            target = artifact_dir / str(ref)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(script_content, encoding='utf-8')

    def _artifact_dir(self, stage_id: str) -> Path:
        return self.artifact_store.root / stage_id / 'artifacts'

    def _resolve_checkpoint_script_refs(
        self,
        stage_id: str,
        checkpoints: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        artifact_dir = self._artifact_dir(stage_id)
        resolved: list[dict[str, Any]] = []
        for item in checkpoints:
            checkpoint = dict(item)
            script_ref = checkpoint.get('script_ref')
            if script_ref:
                script_path = Path(str(script_ref))
                if not script_path.is_absolute():
                    checkpoint['script_ref'] = str(artifact_dir / script_path)
            resolved.append(checkpoint)
        return resolved

    @staticmethod
    def _assert_physical_boundary(payload: dict[str, Any], logical_graph: dict[str, Any]) -> None:
        patch_ops = payload.get('physical_patch_ops') or []
        if any(op.get('op') != 'batch_update_nodes' for op in patch_ops):
            raise StageRuntimeError(
                'Physical stage boundary violated: physical patch ops must not change logical connectivity.',
                failure_type=FailureType.STAGE_BOUNDARY_ERROR,
            )
        graph = payload.get('tgraph_physical') or {}
        if graph:
            StageRuntime._assert_physical_graph_matches_logical(graph, logical_graph)

    @staticmethod
    def _assert_physical_graph_matches_logical(graph: dict[str, Any], logical_graph: dict[str, Any]) -> None:
        logical_links = logical_graph.get('links', [])
        if graph.get('links', []) != logical_links:
            raise StageRuntimeError(
                'Physical stage boundary violated: physical graph must preserve logical links.',
                failure_type=FailureType.STAGE_BOUNDARY_ERROR,
            )
        logical_node_ids = sorted(node.get('id') for node in logical_graph.get('nodes', []))
        graph_node_ids = sorted(node.get('id') for node in graph.get('nodes', []))
        if graph_node_ids != logical_node_ids:
            raise StageRuntimeError(
                'Physical stage boundary violated: physical graph must preserve logical node identities.',
                failure_type=FailureType.STAGE_BOUNDARY_ERROR,
            )

    @staticmethod
    def _raise_if_stage_boundary_report(report: ValidationReport, stage_id: str) -> None:
        boundary_codes = {'stage_boundary_error', 'physical_requires_logical_redesign'}
        if any(issue.code in boundary_codes for issue in report.issues):
            raise StageRuntimeError(
                f'Stage boundary error during {stage_id} validation.',
                failure_type=FailureType.STAGE_BOUNDARY_ERROR,
            )
