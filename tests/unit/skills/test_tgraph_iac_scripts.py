from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = ROOT / "skills" / "tgraph-iac"


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _run_script(script_name: str, args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SKILL_ROOT / "scripts" / script_name), "--trace-root", str(ROOT), *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )


def _artifact(stage: str = "logical") -> dict:
    return {
        "graph": {"stage": stage, "nodes": [], "links": []},
        "constraint_files": {},
        "checkpoint_files": {},
    }


def test_apply_patch_script_is_not_shipped():
    assert not (SKILL_ROOT / "scripts" / "tgraph_apply_patch.py").exists()


def test_validate_script_outputs_validation_report(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    _write_json(artifact_path, _artifact())

    result = _run_script(
        "tgraph_validate.py",
        ["--artifact", str(artifact_path), "--stage", "logical", "--levels", "f1,f2,f3"],
        cwd=tmp_path,
    )

    stdout = json.loads(result.stdout)
    assert result.returncode == 0
    assert stdout["ok"] is True
    assert stdout["issues"] == []


def test_validate_physical_script_accepts_logical_reference_artifact(tmp_path):
    logical_artifact_path = tmp_path / "logical.json"
    physical_artifact_path = tmp_path / "physical.json"
    _write_json(
        logical_artifact_path,
        {
            "graph": {
                "stage": "logical",
                "nodes": [{"id": "PLC1", "type": "computer", "label": "PLC1", "ports": []}],
                "links": [],
            },
            "constraint_files": {},
            "checkpoint_files": {},
        },
    )
    _write_json(
        physical_artifact_path,
        {
            "graph": {
                "stage": "physical",
                "nodes": [
                    {
                        "id": "PLC1",
                        "type": "computer",
                        "label": "PLC1",
                        "ports": [],
                        "image": {"id": "img_openplc", "name": "OpenPLC Runtime"},
                        "flavor": {"vcpu": 1, "ram": 512, "disk": 4},
                    }
                ],
                "links": [],
            },
            "constraint_files": {},
            "checkpoint_files": {},
        },
    )

    result = _run_script(
        "tgraph_validate.py",
        [
            "--artifact",
            str(physical_artifact_path),
            "--stage",
            "physical",
            "--logical-artifact",
            str(logical_artifact_path),
            "--levels",
            "f1,f2,f3,f4",
        ],
        cwd=tmp_path,
    )

    stdout = json.loads(result.stdout)
    assert result.returncode == 0
    assert stdout["ok"] is True


def test_inspect_script_outputs_summary(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    _write_json(
        artifact_path,
        {
            "graph": {
                "stage": "logical",
                "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}],
                "links": [],
            },
            "constraint_files": {},
            "checkpoint_files": {},
        },
    )

    result = _run_script(
        "tgraph_inspect.py",
        ["--artifact", str(artifact_path), "--stage", "logical", "--query", "summary"],
        cwd=tmp_path,
    )

    stdout = json.loads(result.stdout)
    assert result.returncode == 0
    assert stdout == {"stage": "logical", "node_count": 1, "link_count": 0, "node_types": {"router": 1}}


def test_export_script_writes_tgraph_json_file(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    out_dir = tmp_path / "generated"
    _write_json(artifact_path, _artifact())

    result = _run_script(
        "tgraph_export.py",
        ["--artifact", str(artifact_path), "--stage", "logical", "--target", "tgraph-json", "--out", str(out_dir)],
        cwd=tmp_path,
    )

    stdout = json.loads(result.stdout)
    exported = json.loads((out_dir / "tgraph.json").read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert stdout["ok"] is True
    assert stdout["files"] == [{"path": str(out_dir / "tgraph.json")}]
    assert exported == {"stage": "logical", "nodes": [], "links": []}
