from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import orjson

from app.contracts import ArtifactRef


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def write(self, stage: str, name: str, data: Any) -> ArtifactRef:
        target_dir = self.root / stage / 'artifacts'
        target_dir.mkdir(parents=True, exist_ok=True)
        version = self._next_version(target_dir, name)
        path = target_dir / f'{name}.v{version}.json'
        payload = orjson.dumps(data, option=orjson.OPT_INDENT_2)
        path.write_bytes(payload)
        sha256 = hashlib.sha256(payload).hexdigest()
        return ArtifactRef(
            stage=stage,
            name=name,
            version=version,
            path=str(path),
            sha256=sha256,
        )

    def read(self, artifact: ArtifactRef) -> Any:
        return orjson.loads(Path(artifact.path).read_bytes())

    def read_latest(self, stage: str, name: str) -> tuple[ArtifactRef, Any] | None:
        target_dir = self.root / stage / 'artifacts'
        candidates = sorted(target_dir.glob(f'{name}.v*.json'))
        if not candidates:
            return None

        path = candidates[-1]
        version_text = path.stem.rsplit('.v', maxsplit=1)[-1]
        payload = path.read_bytes()
        artifact = ArtifactRef(
            stage=stage,
            name=name,
            version=int(version_text),
            path=str(path),
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        return artifact, orjson.loads(payload)

    def _next_version(self, target_dir: Path, name: str) -> int:
        current = self.read_latest(target_dir.parent.name, name)
        if current is None:
            return 1
        artifact, _ = current
        return artifact.version + 1
