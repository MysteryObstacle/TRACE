import shutil
from pathlib import Path

from app.checkpoint_runner import run_checkpoints


def test_checkpoint_runner_executes_builtin_function() -> None:
    temp_dir = Path('.test_tmp/checkpoint-runner-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        report = run_checkpoints(
            tgraph={'nodes': [], 'edges': []},
            checkpoints=[
                {
                    'id': 'c1',
                    'function_name': 'f1_format',
                    'input_params': {},
                    'description': 'format check',
                    'script_ref': None,
                }
            ],
            artifact_root=temp_dir,
        )

        assert report.ok is True
        assert report.issues == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_checkpoint_runner_executes_generated_script() -> None:
    temp_dir = Path('.test_tmp/checkpoint-script-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        script_path = temp_dir / 'validator.py'
        script_path.write_text(
            'def custom_check(tgraph, **kwargs):\n'
            '    if kwargs.get("required") not in {node["id"] for node in tgraph.get("nodes", [])}:\n'
            '        return [{"code": "missing_node", "message": "node missing", "severity": "error", "scope": "node_ids", "targets": [kwargs.get("required")], "json_paths": []}]\n'
            '    return []\n'
        )

        report = run_checkpoints(
            tgraph={'nodes': [{'id': 'PLC1'}], 'edges': []},
            checkpoints=[
                {
                    'id': 'c2',
                    'function_name': 'custom_check',
                    'input_params': {'required': 'PLC2'},
                    'description': 'script check',
                    'script_ref': str(script_path),
                }
            ],
            artifact_root=temp_dir,
        )

        assert report.ok is False
        assert report.issues[0].code == 'missing_node'
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
