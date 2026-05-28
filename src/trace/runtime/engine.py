from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from trace.config.settings import TraceSettings, load_settings
from trace.observability.tracing import TraceObserver
from trace.runtime.role_client import LangChainRoleClient, RoleClient
from trace.stages.ground import run_ground_stage
from trace.stages.ground.schemas import GroundArtifact
from trace.stages.logical import run_logical_stage
from trace.stages.logical.schemas import LogicalArtifact
from trace.stages.physical import run_physical_stage
from trace.stages.physical.schemas import PhysicalArtifact
from trace.storage.run_storage import RunStorage


RUN_STAGE_ORDER = ("ground", "logical", "physical", "finalize")
REQUIRED_RESUME_ARTIFACTS = {
    "ground": (),
    "logical": ("ground",),
    "physical": ("ground", "logical"),
    "finalize": ("ground", "logical", "physical"),
}


class RunState(TypedDict, total=False):
    run_id: str
    intent: str
    status: str
    current_stage: str | None
    artifacts: dict[str, dict[str, Any]]
    stage_reports: dict[str, dict[str, Any]]
    attempt_counters: dict[str, int]
    support_files: dict[str, str]
    events: Annotated[list[dict[str, Any]], operator.add]
    escalation_history: Annotated[list[dict[str, Any]], operator.add]
    error: dict[str, Any] | None
    config_snapshot: dict[str, Any]
    resume: dict[str, Any]


class TraceRuntime:
    def __init__(
        self,
        *,
        settings: TraceSettings | None = None,
        role_client: RoleClient | None = None,
        output_root: str | Path = "runs",
    ) -> None:
        self.settings = settings or load_settings()
        self.observer = TraceObserver(self.settings.langsmith)
        self.role_client = role_client or LangChainRoleClient(self.settings, observer=self.observer)
        self.storage = RunStorage(output_root)

    def run(self, intent: str, run_id: str | None = None) -> dict[str, Any]:
        resolved_run_id = run_id or uuid4().hex[:8]
        initial: RunState = {
            "run_id": resolved_run_id,
            "intent": intent,
            "status": "running",
            "current_stage": "ground",
            "artifacts": {},
            "stage_reports": {},
            "attempt_counters": {},
            "support_files": {},
            "events": [{"type": "run.started"}],
            "error": None,
            "config_snapshot": self._config_snapshot(),
        }
        self.storage.initialize_run(run_id=resolved_run_id, run_payload=initial)
        with self.observer.root_run(run_id=resolved_run_id, intent=intent):
            graph = self._build_run_graph()
            final_state = graph.invoke(initial)
        self.storage.write_run_state(run_id=resolved_run_id, run_payload=final_state)
        self.storage.append_run_events(run_id=resolved_run_id, events=final_state.get("events", []))
        return final_state

    def resume(
        self,
        run_id: str,
        *,
        from_stage: str,
        new_run_id: str | None = None,
        in_place: bool = False,
    ) -> dict[str, Any]:
        resume_stage = _normalize_resume_stage(from_stage)
        if in_place and new_run_id is not None:
            raise ValueError("new_run_id cannot be used with in_place resume")

        source_state = self.storage.read_run_state(run_id)
        target_run_id = run_id if in_place else new_run_id or self._next_resume_run_id(run_id, resume_stage)
        if not in_place and target_run_id == run_id:
            raise ValueError("new_run_id must differ from source run_id unless in_place=True")
        reused_stages = list(REQUIRED_RESUME_ARTIFACTS[resume_stage])
        artifacts = self._load_resume_artifacts(source_run_id=run_id, from_stage=resume_stage)
        intent = str(source_state.get("intent") or "")
        initial: RunState = {
            "run_id": target_run_id,
            "intent": intent,
            "status": "running",
            "current_stage": resume_stage,
            "artifacts": artifacts,
            "stage_reports": {},
            "attempt_counters": {},
            "support_files": self._load_resume_support_files(source_run_id=run_id, from_stage=resume_stage),
            "events": [
                {
                    "type": "run.resumed",
                    "source_run_id": run_id,
                    "from_stage": resume_stage,
                    "target_run_id": target_run_id,
                    "reused_stages": reused_stages,
                }
            ],
            "error": None,
            "config_snapshot": self._config_snapshot(),
            "resume": {
                "source_run_id": run_id,
                "from_stage": resume_stage,
                "reused_stages": reused_stages,
            },
        }
        self.storage.initialize_run(run_id=target_run_id, run_payload=initial)
        if not in_place:
            for stage_id in reused_stages:
                self.storage.copy_stage_snapshot(
                    source_run_id=run_id,
                    target_run_id=target_run_id,
                    stage_id=stage_id,
                )
        with self.observer.root_run(run_id=target_run_id, intent=intent):
            graph = self._build_run_graph(entry_stage=resume_stage)
            final_state = graph.invoke(initial)
        self.storage.write_run_state(run_id=target_run_id, run_payload=final_state)
        self.storage.append_run_events(run_id=target_run_id, events=final_state.get("events", []))
        return final_state

    def _build_run_graph(self, *, entry_stage: str = "ground"):
        if entry_stage not in RUN_STAGE_ORDER:
            raise ValueError(f"unsupported run graph entry stage: {entry_stage}")
        graph = StateGraph(RunState)
        graph.add_node("ground", self._run_ground)
        graph.add_node("logical", self._run_logical)
        graph.add_node("physical", self._run_physical)
        graph.add_node("finalize", self._finalize)
        graph.set_entry_point(entry_stage)
        graph.add_conditional_edges("ground", _next_unless_failed("logical"), {"next": "logical", "failed": END})
        graph.add_conditional_edges("logical", _next_unless_failed("physical"), {"next": "physical", "failed": END})
        graph.add_conditional_edges("physical", _next_unless_failed("finalize"), {"next": "finalize", "failed": END})
        graph.add_edge("finalize", END)
        return graph.compile()

    def _run_ground(self, state: RunState) -> dict[str, Any]:
        try:
            with self.observer.stage_run("ground", run_id=state["run_id"]):
                result = run_ground_stage(
                    intent=state["intent"],
                    role_client=self.role_client,
                    settings=self.settings,
                )
            return self._merge_stage_result(state, "ground", result)
        except Exception as exc:  # noqa: BLE001
            return self._merge_stage_exception(state, "ground", exc)

    def _run_logical(self, state: RunState) -> dict[str, Any]:
        try:
            with self.observer.stage_run("logical", run_id=state["run_id"]):
                result = run_logical_stage(
                    ground_artifact=state["artifacts"]["ground"],
                    inherited_support_files=state.get("support_files", {}),
                    role_client=self.role_client,
                    settings=self.settings,
                )
            return self._merge_stage_result(state, "logical", result)
        except Exception as exc:  # noqa: BLE001
            return self._merge_stage_exception(state, "logical", exc)

    def _run_physical(self, state: RunState) -> dict[str, Any]:
        try:
            with self.observer.stage_run("physical", run_id=state["run_id"]):
                result = run_physical_stage(
                    logical_artifact=state["artifacts"]["logical"],
                    ground_artifact=state["artifacts"]["ground"],
                    inherited_support_files=state.get("support_files", {}),
                    role_client=self.role_client,
                    settings=self.settings,
                )
            return self._merge_stage_result(state, "physical", result)
        except Exception as exc:  # noqa: BLE001
            return self._merge_stage_exception(state, "physical", exc)

    def _finalize(self, state: RunState) -> dict[str, Any]:
        return {
            "status": "completed",
            "current_stage": None,
            "events": [{"type": "run.completed"}],
        }

    def _merge_stage_result(self, state: RunState, stage_id: str, result: dict[str, Any]) -> dict[str, Any]:
        partial: dict[str, Any] = {
            "current_stage": stage_id,
            "artifacts": {**state.get("artifacts", {}), stage_id: result["artifact"]},
            "stage_reports": {
                **state.get("stage_reports", {}),
                stage_id: {
                    "stage_id": stage_id,
                    "attempts_used": result["attempts_used"],
                    "evaluation_summary": result["evaluation_summary"],
                },
            },
            "attempt_counters": {**state.get("attempt_counters", {}), stage_id: result["attempts_used"]},
            "support_files": {**state.get("support_files", {}), **result.get("support_files", {})},
            "events": result["events"],
        }
        self.storage.write_run_state(run_id=state["run_id"], run_payload={**state, **partial})
        self.storage.write_stage_snapshot(
            run_id=state["run_id"],
            stage_id=stage_id,
            artifact=result["artifact"],
            evaluation=result["evaluation_summary"] or {"ok": True, "issues": []},
            summary={"attempts_used": result["attempts_used"]},
            messages=result["messages"],
            tool_journal=result["tool_journal"],
            history_name=_stage_history_name(stage_id),
            history_entries=result[_stage_history_name(stage_id)],
            events=result["events"],
            support_files=result.get("support_files", {}),
        )
        return partial

    def _merge_stage_exception(self, state: RunState, stage_id: str, exc: Exception) -> dict[str, Any]:
        error = {"stage_id": stage_id, "type": type(exc).__name__, "message": str(exc)}
        partial = {
            "status": "failed",
            "current_stage": stage_id,
            "error": error,
            "events": [{"type": "run.stage_failed", "stage_id": stage_id, "error": error}],
        }
        merged = {**state, **partial}
        self.storage.write_run_state(run_id=merged["run_id"], run_payload=merged)
        self.storage.write_stage_snapshot(
            run_id=merged["run_id"],
            stage_id=stage_id,
            artifact=merged.get("artifacts", {}).get(stage_id, {}),
            evaluation={"ok": False, "passed": False, "issues": [{"message": error["message"], "details": error}]},
            summary={"attempts_used": merged.get("attempt_counters", {}).get(stage_id, 0), "failed": True},
            messages=[],
            tool_journal=[],
            history_name=_stage_history_name(stage_id),
            history_entries=[],
            events=partial["events"],
            support_files={},
        )
        return partial

    def _load_resume_support_files(self, *, source_run_id: str, from_stage: str) -> dict[str, str]:
        del from_stage
        run_root = self.storage.root / source_run_id
        if not run_root.exists():
            return {}
        files: dict[str, str] = {}
        for path in run_root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in {".json", ".py"}:
                continue
            relative = path.relative_to(run_root).as_posix()
            if relative.startswith("ground/") or "/mutations/" in relative or relative.endswith("checkpoints.py"):
                files[relative] = path.read_text(encoding="utf-8")
        return files

    def _load_resume_artifacts(self, *, source_run_id: str, from_stage: str) -> dict[str, dict[str, Any]]:
        artifacts: dict[str, dict[str, Any]] = {}
        for stage_id in REQUIRED_RESUME_ARTIFACTS[from_stage]:
            try:
                payload = self.storage.read_stage_artifact(source_run_id, stage_id)
            except FileNotFoundError as exc:
                raise ValueError(
                    f"Cannot resume run {source_run_id!r} from {from_stage!r}: missing {stage_id!r} artifact snapshot."
                ) from exc
            artifacts[stage_id] = _validate_resume_artifact(stage_id, payload)
        return artifacts

    def _next_resume_run_id(self, source_run_id: str, from_stage: str) -> str:
        base = f"{source_run_id}-resume-{from_stage}"
        if not self.storage.run_exists(base):
            return base
        index = 1
        while self.storage.run_exists(f"{base}-{index:03d}"):
            index += 1
        return f"{base}-{index:03d}"

    def _config_snapshot(self) -> dict[str, Any]:
        return {
            "langsmith_enabled": self.settings.langsmith.enabled,
            "roles": {name: settings.model_dump(mode="json") for name, settings in self.settings.roles.items()},
        }


def _stage_history_name(stage_id: str) -> str:
    if stage_id == "ground":
        return "retry_history"
    return "repair_history"


def _next_unless_failed(next_node: str):
    del next_node

    def route(state: RunState) -> str:
        return "failed" if state.get("status") == "failed" else "next"

    return route


def _normalize_resume_stage(stage: str) -> str:
    normalized = str(stage).strip().lower()
    if normalized not in REQUIRED_RESUME_ARTIFACTS:
        allowed = ", ".join(RUN_STAGE_ORDER)
        raise ValueError(f"unsupported resume stage: {stage!r}; expected one of: {allowed}")
    return normalized


def _validate_resume_artifact(stage_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        if stage_id == "ground":
            GroundArtifact.model_validate(payload)
            return payload
        if stage_id == "logical":
            LogicalArtifact.model_validate(payload)
            return payload
        if stage_id == "physical":
            PhysicalArtifact.model_validate(payload)
            return payload
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Cannot resume from invalid {stage_id!r} artifact snapshot: {exc}") from exc
    raise ValueError(f"unsupported artifact stage: {stage_id}")
