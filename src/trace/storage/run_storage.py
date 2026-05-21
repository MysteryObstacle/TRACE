from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage
from pydantic import BaseModel


class RunStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def initialize_run(self, *, run_id: str, run_payload: dict[str, Any]) -> Path:
        run_root = self.root / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        self._write_json(run_root / "run.json", run_payload)
        (run_root / "events.jsonl").touch(exist_ok=True)
        return run_root

    def write_run_state(self, *, run_id: str, run_payload: dict[str, Any]) -> Path:
        run_root = self.root / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        self._write_json(run_root / "run.json", run_payload)
        return run_root

    def append_run_events(self, *, run_id: str, events: list[dict[str, Any]]) -> Path:
        run_root = self.root / run_id
        run_root.mkdir(parents=True, exist_ok=True)
        path = run_root / "events.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            for item in events:
                handle.write(json.dumps(item, ensure_ascii=True))
                handle.write("\n")
        return path

    def write_stage_snapshot(
        self,
        *,
        run_id: str,
        stage_id: str,
        artifact: dict[str, Any],
        evaluation: dict[str, Any],
        summary: dict[str, Any],
        messages: list[dict[str, Any]],
        tool_journal: list[dict[str, Any]],
        history_name: str,
        history_entries: list[dict[str, Any]],
        events: list[dict[str, Any]],
    ) -> Path:
        stage_root = self.root / run_id / stage_id
        stage_root.mkdir(parents=True, exist_ok=True)
        self._write_json(stage_root / "artifact.json", artifact)
        self._write_json(stage_root / "evaluation.json", evaluation)
        self._write_json(stage_root / "summary.json", summary)
        self._write_json(stage_root / "messages.json", messages)
        self._write_json(stage_root / "tool_journal.json", tool_journal)
        self._write_json(stage_root / f"{history_name}.json", history_entries)
        self._write_jsonl(stage_root / "events.jsonl", events)
        return stage_root

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=True, default=_json_default), encoding="utf-8")

    @staticmethod
    def _write_jsonl(path: Path, payloads: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as handle:
            for item in payloads:
                handle.write(json.dumps(item, ensure_ascii=True, default=_json_default))
                handle.write("\n")


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseMessage):
        return value.model_dump(mode="json")
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")
