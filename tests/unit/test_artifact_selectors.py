import shutil
from pathlib import Path

from app.contracts import ArtifactSelector
from artifacts.selectors import resolve_inputs
from artifacts.store import ArtifactStore


def test_resolve_inputs_returns_latest_versions() -> None:
    temp_dir = Path('.test_tmp/artifact-selector-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1'])
        store.write(stage='ground', name='expanded_node_ids', data=['PLC1', 'PLC2'])

        resolved = resolve_inputs(
            store,
            [ArtifactSelector(stage='ground', name='expanded_node_ids')],
        )

        assert resolved['ground.expanded_node_ids'] == ['PLC1', 'PLC2']
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
