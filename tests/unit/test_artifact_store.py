import json
import shutil
from pathlib import Path

from artifacts.store import ArtifactStore


def test_store_writes_incrementing_versions() -> None:
    temp_dir = Path('.test_tmp/artifact-store-case')
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        store = ArtifactStore(temp_dir)

        first = store.write(stage='ground', name='expanded_node_ids', data=['PLC1'])
        second = store.write(stage='ground', name='expanded_node_ids', data=['PLC1', 'PLC2'])

        assert first.version == 1
        assert second.version == 2
        assert first.path != second.path
        assert json.loads(Path(second.path).read_text()) == ['PLC1', 'PLC2']
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
