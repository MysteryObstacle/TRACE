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


def _artifact() -> dict:
    return {
        "tgraph_logical": {"profile": "logical.v1", "nodes": [], "links": []},
        "logical_checkpoints": [],
        "logical_validator_script": None,
    }


def test_apply_patch_script_writes_output_from_arbitrary_cwd(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    patch_path = tmp_path / "patch.json"
    out_path = tmp_path / "artifact.out.json"
    _write_json(artifact_path, _artifact())
    _write_json(
        patch_path,
        {
            "graph_patch": [{"op": "ensure_node", "id": "R1", "type": "router", "label": "R1"}],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"]},
        },
    )

    result = _run_script(
        "tgraph_apply_patch.py",
        ["--artifact", str(artifact_path), "--patch", str(patch_path), "--stage", "logical", "--out", str(out_path)],
        cwd=tmp_path,
    )

    stdout = json.loads(result.stdout)
    written = json.loads(out_path.read_text(encoding="utf-8"))
    assert result.returncode == 0
    assert stdout["ok"] is True
    assert stdout["artifact"] is None
    assert written["tgraph_logical"]["nodes"][0]["id"] == "R1"


def test_apply_patch_script_dry_run_does_not_write_output(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    patch_path = tmp_path / "patch.json"
    out_path = tmp_path / "artifact.out.json"
    _write_json(artifact_path, _artifact())
    _write_json(
        patch_path,
        {
            "graph_patch": [{"op": "ensure_node", "id": "R1", "type": "router", "label": "R1"}],
            "options": {"stage": "logical", "validate": ["f1", "f2", "f3"]},
        },
    )

    result = _run_script(
        "tgraph_apply_patch.py",
        [
            "--artifact",
            str(artifact_path),
            "--patch",
            str(patch_path),
            "--stage",
            "logical",
            "--out",
            str(out_path),
            "--dry-run",
        ],
        cwd=tmp_path,
    )

    stdout = json.loads(result.stdout)
    assert result.returncode == 0
    assert stdout["ok"] is True
    assert stdout["committed"] is False
    assert not out_path.exists()


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


def test_inspect_script_outputs_topology(tmp_path):
    artifact_path = tmp_path / "artifact.json"
    _write_json(
        artifact_path,
        {
            "tgraph_logical": {
                "profile": "logical.v1",
                "nodes": [{"id": "R1", "type": "router", "label": "R1", "ports": []}],
                "links": [],
            },
            "logical_checkpoints": [],
            "logical_validator_script": None,
        },
    )

    result = _run_script(
        "tgraph_inspect.py",
        ["--artifact", str(artifact_path), "--stage", "logical", "--query", "topology"],
        cwd=tmp_path,
    )

    stdout = json.loads(result.stdout)
    assert result.returncode == 0
    assert stdout == {"nodes": ["R1"], "links": []}


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
    assert exported == {"profile": "logical.v1", "nodes": [], "links": []}
