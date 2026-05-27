from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command

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
ESCALATION_LIMIT = 2


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
    escalation_report: dict[str, Any] | None
    unsolvable_notes: list[str]
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
            "escalation_history": [],
            "error": None,
            "config_snapshot": self._config_snapshot(),
        }
        self.storage.initialize_run(run_id=resolved_run_id, run_payload=initial)
        with self._checkpointer_for(resolved_run_id) as checkpointer:
            with self.observer.root_run(run_id=resolved_run_id, intent=intent):
                graph = self._build_run_graph(checkpointer=checkpointer)
                final_state = graph.invoke(
                    initial,
                    config={"configurable": {"thread_id": resolved_run_id}},
                )
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

        sqlite_path = self.storage.root / run_id / "state.sqlite"
        target_run_id = run_id if in_place else new_run_id or self._next_resume_run_id(run_id, resume_stage)
        if not in_place and target_run_id == run_id:
            raise ValueError("new_run_id must differ from source run_id unless in_place=True")

        sqlite_usable = in_place and sqlite_path.exists()
        if sqlite_usable:
            return self._resume_via_sqlite(
                source_run_id=run_id,
                target_run_id=target_run_id,
                resume_stage=resume_stage,
            )
        return self._resume_via_run_storage(
            source_run_id=run_id,
            target_run_id=target_run_id,
            resume_stage=resume_stage,
            in_place=in_place,
        )

    def _checkpointer_for(self, run_id: str):
        run_root = self.storage.root / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        sqlite_path = run_root / "state.sqlite"
        return SqliteSaver.from_conn_string(str(sqlite_path))

    def _build_run_graph(self, *, entry_stage: str = "ground", checkpointer: SqliteSaver | None = None):
        if entry_stage not in RUN_STAGE_ORDER:
            raise ValueError(f"unsupported run graph entry stage: {entry_stage}")
        graph = StateGraph(RunState)
        graph.add_node("ground", self._run_ground)
        graph.add_node("logical", self._run_logical)
        graph.add_node("physical", self._run_physical)
        graph.add_node("finalize", self._finalize)
        graph.set_entry_point(entry_stage)
        graph.add_edge("finalize", END)
        return graph.compile(checkpointer=checkpointer)

    def _run_ground(self, state: RunState) -> Command:
        escalation_report = state.get("escalation_report")
        try:
            with self.observer.stage_run("ground", run_id=state["run_id"]):
                result = run_ground_stage(
                    intent=state["intent"],
                    role_client=self.role_client,
                    settings=self.settings,
                    escalation_report=escalation_report,
                )
        except Exception as exc:  # noqa: BLE001
            return self._merge_stage_exception(state, "ground", exc)

        if result.get("status") == "unsolvable":
            partial = self._merge_stage_outcome(state, "ground", result)
            partial["status"] = "unsolvable"
            partial["unsolvable_notes"] = result.get("unsolvable_notes", [])
            return Command(goto=END, update=partial)

        partial = self._merge_stage_result(state, "ground", result)
        if escalation_report is not None:
            partial = {**partial, "escalation_report": None}
        return Command(goto="logical", update=partial)

    def _run_logical(self, state: RunState) -> Command:
        try:
            with self.observer.stage_run("logical", run_id=state["run_id"]):
                result = run_logical_stage(
                    ground_artifact=state["artifacts"]["ground"],
                    inherited_support_files=state.get("support_files", {}),
                    role_client=self.role_client,
                    settings=self.settings,
                )
        except Exception as exc:  # noqa: BLE001
            return self._merge_stage_exception(state, "logical", exc)

        if result.get("status") == "escalated":
            return self._handle_stage_escalation(state, "logical", result)

        partial = self._merge_stage_result(state, "logical", result)
        return Command(goto="physical", update=partial)

    def _run_physical(self, state: RunState) -> Command:
        try:
            with self.observer.stage_run("physical", run_id=state["run_id"]):
                result = run_physical_stage(
                    logical_artifact=state["artifacts"]["logical"],
                    ground_artifact=state["artifacts"]["ground"],
                    inherited_support_files=state.get("support_files", {}),
                    role_client=self.role_client,
                    settings=self.settings,
                )
        except Exception as exc:  # noqa: BLE001
            return self._merge_stage_exception(state, "physical", exc)

        if result.get("status") == "escalated":
            return self._handle_stage_escalation(state, "physical", result)

        partial = self._merge_stage_result(state, "physical", result)
        return Command(goto="finalize", update=partial)

    def _finalize(self, state: RunState) -> dict[str, Any]:
        return {
            "status": "completed",
            "current_stage": None,
            "events": [{"type": "run.completed"}],
        }

    def _handle_stage_escalation(self, state: RunState, stage_id: str, result: dict[str, Any]) -> Command:
        escalation_counter = (state.get("attempt_counters") or {}).get("escalation", 0)
        escalation_report = result.get("escalation_report") or {}
        payload: dict[str, Any] = {
            "events": [{"type": f"{stage_id}.escalation_received", "stage": stage_id, "counter": escalation_counter + 1}],
            "escalation_history": [{
                "stage": stage_id,
                "counter": escalation_counter + 1,
                "report": escalation_report,
            }],
            "attempt_counters": {**(state.get("attempt_counters") or {}), "escalation": escalation_counter + 1},
        }
        if escalation_counter + 1 > ESCALATION_LIMIT:
            return Command(
                goto=END,
                update={
                    **payload,
                    "status": "failed",
                    "error": {
                        "stage_id": stage_id,
                        "type": "EscalationLimitExceeded",
                        "message": f"escalation limit ({ESCALATION_LIMIT}) reached at {stage_id}",
                    },
                },
            )
        return Command(
            goto="ground",
            update={
                **payload,
                "escalation_report": escalation_report,
                "current_stage": "ground",
            },
        )

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

    def _merge_stage_outcome(self, state: RunState, stage_id: str, result: dict[str, Any]) -> dict[str, Any]:
        partial: dict[str, Any] = {
            "current_stage": stage_id,
            "stage_reports": {
                **state.get("stage_reports", {}),
                stage_id: {
                    "stage_id": stage_id,
                    "attempts_used": result.get("attempts_used", 1),
                    "evaluation_summary": result.get("evaluation_summary"),
                },
            },
            "attempt_counters": {**state.get("attempt_counters", {}), stage_id: result.get("attempts_used", 1)},
            "support_files": {**state.get("support_files", {}), **result.get("support_files", {})},
            "events": result.get("events", []),
        }
        self.storage.write_run_state(run_id=state["run_id"], run_payload={**state, **partial})
        return partial

    def _merge_stage_exception(self, state: RunState, stage_id: str, exc: Exception) -> Command:
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
        return Command(goto=END, update=partial)

    def _resume_via_sqlite(self, *, source_run_id: str, target_run_id: str, resume_stage: str) -> dict[str, Any]:
        source_state = self.storage.read_run_state(source_run_id)
        intent = str(source_state.get("intent") or "")
        with self._checkpointer_for(target_run_id) as checkpointer:
            graph = self._build_run_graph(entry_stage=resume_stage, checkpointer=checkpointer)
            config = {"configurable": {"thread_id": source_run_id}}
            with self.observer.root_run(run_id=target_run_id, intent=intent):
                history = list(graph.get_state_history(config))
                target_checkpoint = None
                for snapshot in history:
                    state_dict = snapshot.values if isinstance(snapshot.values, dict) else {}
                    if state_dict.get("current_stage") == resume_stage:
                        target_checkpoint = snapshot
                        break
                if target_checkpoint is None:
                    raise ValueError(
                        f"sqlite checkpoint for stage {resume_stage!r} not found in {source_run_id!r}"
                    )
                checkpoint_id = target_checkpoint.config["configurable"].get("checkpoint_id")
                final_state = graph.invoke(
                    None,
                    config={"configurable": {"thread_id": source_run_id, "checkpoint_id": checkpoint_id}},
                )
        self.storage.write_run_state(run_id=target_run_id, run_payload=final_state)
        self.storage.append_run_events(run_id=target_run_id, events=final_state.get("events", []))
        return final_state

    def _resume_via_run_storage(
        self,
        *,
        source_run_id: str,
        target_run_id: str,
        resume_stage: str,
        in_place: bool,
    ) -> dict[str, Any]:
        source_state = self.storage.read_run_state(source_run_id)
        reused_stages = list(REQUIRED_RESUME_ARTIFACTS[resume_stage])
        artifacts = self._load_resume_artifacts(source_run_id=source_run_id, from_stage=resume_stage)
        intent = str(source_state.get("intent") or "")
        initial: RunState = {
            "run_id": target_run_id,
            "intent": intent,
            "status": "running",
            "current_stage": resume_stage,
            "artifacts": artifacts,
            "stage_reports": {},
            "attempt_counters": {},
            "support_files": self._load_resume_support_files(source_run_id=source_run_id, from_stage=resume_stage),
            "events": [
                {
                    "type": "run.resumed",
                    "source_run_id": source_run_id,
                    "from_stage": resume_stage,
                    "target_run_id": target_run_id,
                    "reused_stages": reused_stages,
                }
            ],
            "escalation_history": [],
            "error": None,
            "config_snapshot": self._config_snapshot(),
            "resume": {
                "source_run_id": source_run_id,
                "from_stage": resume_stage,
                "reused_stages": reused_stages,
            },
        }
        self.storage.initialize_run(run_id=target_run_id, run_payload=initial)
        if not in_place:
            for stage_id in reused_stages:
                self.storage.copy_stage_snapshot(
                    source_run_id=source_run_id,
                    target_run_id=target_run_id,
                    stage_id=stage_id,
                )
        with self._checkpointer_for(target_run_id) as checkpointer:
            with self.observer.root_run(run_id=target_run_id, intent=intent):
                graph = self._build_run_graph(entry_stage=resume_stage, checkpointer=checkpointer)
                final_state = graph.invoke(
                    initial,
                    config={"configurable": {"thread_id": target_run_id}},
                )
        self.storage.write_run_state(run_id=target_run_id, run_payload=final_state)
        self.storage.append_run_events(run_id=target_run_id, events=final_state.get("events", []))
        return final_state

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
