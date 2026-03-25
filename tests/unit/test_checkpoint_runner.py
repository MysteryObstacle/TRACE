import shutil
from pathlib import Path

from app.checkpoint_runner import run_checkpoints


def test_checkpoint_runner_executes_builtin_function() -> None:
    temp_dir = Path('.test_tmp/checkpoint-runner-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        report = run_checkpoints(
            tgraph={'profile': 'logical.v1', 'nodes': [], 'links': []},
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
            '        return [{"code": "missing_node", "message": "node missing", "severity": "error", "scope": "node", "targets": [kwargs.get("required")], "json_paths": []}]\n'
            '    return []\n'
        )

        report = run_checkpoints(
            tgraph={'profile': 'logical.v1', 'nodes': [{'id': 'PLC1'}], 'links': []},
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


def test_checkpoint_runner_reports_script_function_mismatch_as_issue() -> None:
    temp_dir = Path('.test_tmp/checkpoint-script-mismatch-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        script_path = temp_dir / 'validator.py'
        script_path.write_text(
            'def another_name(tgraph, **kwargs):\n'
            '    return []\n'
        )

        report = run_checkpoints(
            tgraph={'profile': 'logical.v1', 'nodes': [], 'links': []},
            checkpoints=[
                {
                    'id': 'c3',
                    'function_name': 'custom_check',
                    'input_params': {},
                    'description': 'script mismatch',
                    'script_ref': str(script_path),
                }
            ],
            artifact_root=temp_dir,
        )

        assert report.ok is False
        assert report.issues[0].code == 'checkpoint_execution_error'
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_checkpoint_runner_supports_graph_view_helpers_for_scripts() -> None:
    temp_dir = Path('.test_tmp/checkpoint-script-graph-view-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        script_path = temp_dir / 'validator.py'
        script_path.write_text(
            'def reachability_check(tgraph, **kwargs):\n'
            '    source = kwargs["source"]\n'
            '    target = kwargs["target"]\n'
            '    if tgraph.get_node(source) is None:\n'
            '        return [{"code": "missing_source", "message": "source missing", "severity": "error", "scope": "node", "targets": [source], "json_paths": []}]\n'
            '    if not tgraph.check_reachability(source, target):\n'
            '        return [{"code": "unreachable", "message": "nodes are not connected", "severity": "error", "scope": "topology", "targets": [source, target], "json_paths": []}]\n'
            '    return []\n'
        )

        report = run_checkpoints(
            tgraph={
                'profile': 'logical.v1',
                'nodes': [
                    {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [{'id': 'PLC1:p1', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                    {'id': 'SW1', 'type': 'switch', 'label': 'SW1', 'ports': [{'id': 'SW1:p1', 'ip': '', 'cidr': '10.0.0.0/24'}], 'image': None, 'flavor': None},
                ],
                'links': [
                    {'id': 'PLC1:p1--SW1:p1', 'from_port': 'PLC1:p1', 'to_port': 'SW1:p1', 'from_node': 'PLC1', 'to_node': 'SW1'},
                ],
            },
            checkpoints=[
                {
                    'id': 'c4',
                    'function_name': 'reachability_check',
                    'input_params': {'source': 'PLC1', 'target': 'SW1'},
                    'description': 'graph helper check',
                    'script_ref': str(script_path),
                }
            ],
            artifact_root=temp_dir,
        )

        assert report.ok is True
        assert report.issues == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_checkpoint_runner_supports_link_and_via_helpers_for_scripts() -> None:
    temp_dir = Path('.test_tmp/checkpoint-script-path-helpers-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        script_path = temp_dir / 'validator.py'
        script_path.write_text(
            'def firewall_path_check(tgraph, **kwargs):\n'
            '    links = tgraph.get_links_for_node("PLC1")\n'
            '    if not links:\n'
            '        return [{"code": "missing_links", "message": "no links", "severity": "error", "scope": "link", "targets": ["PLC1"], "json_paths": []}]\n'
            '    if not tgraph.is_reachable("HMI1", "PLC1", via="FW1"):\n'
            '        return [{"code": "missing_fw_path", "message": "fw path missing", "severity": "error", "scope": "topology", "targets": ["HMI1", "PLC1", "FW1"], "json_paths": []}]\n'
            '    return []\n'
        )

        report = run_checkpoints(
            tgraph={
                'profile': 'logical.v1',
                'nodes': [
                    {'id': 'HMI1', 'type': 'computer', 'label': 'HMI1', 'ports': [{'id': 'HMI1:p1', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                    {'id': 'FW1', 'type': 'computer', 'label': 'FW1', 'ports': [{'id': 'FW1:p1', 'ip': '', 'cidr': ''}, {'id': 'FW1:p2', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                    {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [{'id': 'PLC1:p1', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                ],
                'links': [
                    {'id': 'HMI1:p1--FW1:p1', 'from_port': 'HMI1:p1', 'to_port': 'FW1:p1', 'from_node': 'HMI1', 'to_node': 'FW1'},
                    {'id': 'FW1:p2--PLC1:p1', 'from_port': 'FW1:p2', 'to_port': 'PLC1:p1', 'from_node': 'FW1', 'to_node': 'PLC1'},
                ],
            },
            checkpoints=[
                {
                    'id': 'c5',
                    'function_name': 'firewall_path_check',
                    'input_params': {},
                    'description': 'path helper check',
                    'script_ref': str(script_path),
                }
            ],
            artifact_root=temp_dir,
        )

        assert report.ok is True
        assert report.issues == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_checkpoint_runner_supports_get_links_and_find_paths_helpers() -> None:
    temp_dir = Path('.test_tmp/checkpoint-script-find-paths-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        script_path = temp_dir / 'validator.py'
        script_path.write_text(
            'def path_check(tgraph, **kwargs):\n'
            '    if not tgraph.get_links("PLC1"):\n'
            '        return [{"code": "missing_links", "message": "no links", "severity": "error", "scope": "link", "targets": ["PLC1"], "json_paths": []}]\n'
            '    paths = tgraph.find_paths("HMI1", "PLC1")\n'
            '    if not any("FW1" in path for path in paths):\n'
            '        return [{"code": "missing_path", "message": "fw path missing", "severity": "error", "scope": "topology", "targets": ["HMI1", "PLC1", "FW1"], "json_paths": []}]\n'
            '    return []\n'
        )

        report = run_checkpoints(
            tgraph={
                'profile': 'logical.v1',
                'nodes': [
                    {'id': 'HMI1', 'type': 'computer', 'label': 'HMI1', 'ports': [{'id': 'HMI1:p1', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                    {'id': 'FW1', 'type': 'computer', 'label': 'FW1', 'ports': [{'id': 'FW1:p1', 'ip': '', 'cidr': ''}, {'id': 'FW1:p2', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                    {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [{'id': 'PLC1:p1', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                ],
                'links': [
                    {'id': 'HMI1:p1--FW1:p1', 'from_port': 'HMI1:p1', 'to_port': 'FW1:p1', 'from_node': 'HMI1', 'to_node': 'FW1'},
                    {'id': 'FW1:p2--PLC1:p1', 'from_port': 'FW1:p2', 'to_port': 'PLC1:p1', 'from_node': 'FW1', 'to_node': 'PLC1'},
                ],
            },
            checkpoints=[
                {
                    'id': 'c6',
                    'function_name': 'path_check',
                    'input_params': {},
                    'description': 'path helper check',
                    'script_ref': str(script_path),
                }
            ],
            artifact_root=temp_dir,
        )

        assert report.ok is True
        assert report.issues == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_checkpoint_runner_supports_links_attribute_and_find_path_alias() -> None:
    temp_dir = Path('.test_tmp/checkpoint-script-links-attr-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        script_path = temp_dir / 'validator.py'
        script_path.write_text(
            'def path_check(tgraph, **kwargs):\n'
            '    if not any(link["to_node"] == "FW1" for link in tgraph.links):\n'
            '        return [{"code": "missing_fw_link", "message": "no firewall link", "severity": "error", "scope": "link", "targets": ["FW1"], "json_paths": []}]\n'
            '    reachable = tgraph.find_path("HMI1", ["PLC1"])\n'
            '    if "PLC1" not in reachable:\n'
            '        return [{"code": "missing_path", "message": "no reachable plc", "severity": "error", "scope": "topology", "targets": ["HMI1", "PLC1"], "json_paths": []}]\n'
            '    return []\n'
        )

        report = run_checkpoints(
            tgraph={
                'profile': 'logical.v1',
                'nodes': [
                    {'id': 'HMI1', 'type': 'computer', 'label': 'HMI1', 'ports': [{'id': 'HMI1:p1', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                    {'id': 'FW1', 'type': 'computer', 'label': 'FW1', 'ports': [{'id': 'FW1:p1', 'ip': '', 'cidr': ''}, {'id': 'FW1:p2', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                    {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [{'id': 'PLC1:p1', 'ip': '', 'cidr': ''}], 'image': None, 'flavor': None},
                ],
                'links': [
                    {'id': 'HMI1:p1--FW1:p1', 'from_port': 'HMI1:p1', 'to_port': 'FW1:p1', 'from_node': 'HMI1', 'to_node': 'FW1'},
                    {'id': 'FW1:p2--PLC1:p1', 'from_port': 'FW1:p2', 'to_port': 'PLC1:p1', 'from_node': 'FW1', 'to_node': 'PLC1'},
                ],
            },
            checkpoints=[
                {
                    'id': 'c7',
                    'function_name': 'path_check',
                    'input_params': {},
                    'description': 'links attr and find_path helper check',
                    'script_ref': str(script_path),
                }
            ],
            artifact_root=temp_dir,
        )

        assert report.ok is True
        assert report.issues == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_checkpoint_runner_supports_logical_namespace_fallback_for_generated_scripts() -> None:
    temp_dir = Path('.test_tmp/checkpoint-script-logical-namespace-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        script_path = temp_dir / 'validator.py'
        script_path.write_text(
            'def check_plc_image(plc_ids):\n'
            '    issues = []\n'
            '    for plc_id in plc_ids:\n'
            '        node = next((n for n in logical.tgraph_logical["nodes"] if n["id"] == plc_id), None)\n'
            '        if not node or node["image"]["id"] != "openplc-v3":\n'
            '            issues.append({"code": "bad_image", "message": "bad image", "severity": "error", "scope": "node", "targets": [plc_id], "json_paths": []})\n'
            '    return issues\n'
        )

        report = run_checkpoints(
            tgraph={
                'profile': 'taal.default.v1',
                'nodes': [
                    {'id': 'PLC1', 'type': 'computer', 'label': 'PLC1', 'ports': [], 'image': {'id': 'openplc-v3', 'name': 'OpenPLC v3'}, 'flavor': {'vcpu': 2, 'ram': 2048, 'disk': 20}},
                ],
                'links': [],
            },
            checkpoints=[
                {
                    'id': 'c8',
                    'function_name': 'check_plc_image',
                    'input_params': {'plc_ids': ['PLC1']},
                    'description': 'logical namespace fallback check',
                    'script_ref': str(script_path),
                }
            ],
            artifact_root=temp_dir,
        )

        assert report.ok is True
        assert report.issues == []
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
