from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, StateGraph

from trace.config.settings import TraceSettings, load_settings
from trace.observability.tracing import TraceObserver
from trace.runtime.reducers import merge_run_state
from trace.runtime.role_client import LangChainRoleClient, RoleClient
from trace.stages.ground import run_ground_stage
from trace.stages.logical import run_logical_stage
from trace.stages.physical import run_physical_stage
from trace.storage.run_storage import RunStorage


class RunState(TypedDict, total=False):
    run_id: str
    intent: str
    status: str
    current_stage: str | None
    artifacts: dict[str, dict[str, Any]]
    stage_reports: dict[str, dict[str, Any]]
    attempt_counters: dict[str, int]
    events: list[dict[str, Any]]
    error: dict[str, Any] | None
    config_snapshot: dict[str, Any]


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
            "events": [{"type": "run.started"}],
            "error": None,
            "config_snapshot": {
                "langsmith_enabled": self.settings.langsmith.enabled,
                "roles": {name: settings.model_dump(mode="json") for name, settings in self.settings.roles.items()},
            },
        }
        self.storage.initialize_run(run_id=resolved_run_id, run_payload=initial)
        with self.observer.root_run(run_id=resolved_run_id, intent=intent):
            graph = self._build_run_graph()
            final_state = graph.invoke(initial)
        self.storage.write_run_state(run_id=resolved_run_id, run_payload=final_state)
        self.storage.append_run_events(run_id=resolved_run_id, events=final_state.get("events", []))
        return final_state

    def _build_run_graph(self):
        graph = StateGraph(RunState)
        graph.add_node("ground", self._run_ground)
        graph.add_node("logical", self._run_logical)
        graph.add_node("physical", self._run_physical)
        graph.add_node("finalize", self._finalize)
        graph.set_entry_point("ground")
        graph.add_edge("ground", "logical")
        graph.add_edge("logical", "physical")
        graph.add_edge("physical", "finalize")
        graph.add_edge("finalize", END)
        return graph.compile()

    def _run_ground(self, state: RunState) -> RunState:
        with self.observer.stage_run("ground", run_id=state["run_id"]):
            result = run_ground_stage(
                intent=state["intent"],
                role_client=self.role_client,
                settings=self.settings,
            )
        return self._merge_stage_result(state, "ground", result)

    def _run_logical(self, state: RunState) -> RunState:
        with self.observer.stage_run("logical", run_id=state["run_id"]):
            result = run_logical_stage(
                ground_artifact=state["artifacts"]["ground"],
                role_client=self.role_client,
                settings=self.settings,
            )
        return self._merge_stage_result(state, "logical", result)

    def _run_physical(self, state: RunState) -> RunState:
        with self.observer.stage_run("physical", run_id=state["run_id"]):
            result = run_physical_stage(
                logical_artifact=state["artifacts"]["logical"],
                ground_artifact=state["artifacts"]["ground"],
                role_client=self.role_client,
                settings=self.settings,
            )
        return self._merge_stage_result(state, "physical", result)

    def _finalize(self, state: RunState) -> RunState:
        return merge_run_state(
            state,
            {
                "status": "completed",
                "current_stage": None,
                "events": [{"type": "run.completed"}],
            },
        )

    def _merge_stage_result(self, state: RunState, stage_id: str, result: dict[str, Any]) -> RunState:
        updated = merge_run_state(
            state,
            {
                "current_stage": stage_id,
                "artifacts": {stage_id: result["artifact"]},
                "stage_reports": {
                    stage_id: {
                        "stage_id": stage_id,
                        "attempts_used": result["attempts_used"],
                        "evaluation_summary": result["evaluation_summary"],
                    }
                },
                "attempt_counters": {stage_id: result["attempts_used"]},
                "events": result["events"],
            },
        )
        self.storage.write_run_state(run_id=updated["run_id"], run_payload=updated)
        self.storage.write_stage_snapshot(
            run_id=updated["run_id"],
            stage_id=stage_id,
            artifact=result["artifact"],
            evaluation=result["evaluation_summary"] or {"ok": True, "issues": []},
            summary={"attempts_used": result["attempts_used"]},
            messages=result["messages"],
            tool_journal=result["tool_journal"],
            history_name=_stage_history_name(stage_id),
            history_entries=result[_stage_history_name(stage_id)],
            events=result["events"],
        )
        return updated


def _stage_history_name(stage_id: str) -> str:
    if stage_id == "ground":
        return "retry_history"
    return "repair_history"
