from __future__ import annotations

from pathlib import Path

from tools.tgraph.model import LOGICAL_V1, TGraph
from tools.tgraph.io.gml_loader import load_tgraph_gml
from tools.tgraph.io.gns3_loader import load_tgraph_gns3
from tools.tgraph.io.json_loader import load_tgraph_json


FORMAT_BY_SUFFIX = {
    ".json": "json",
    ".gml": "gml",
    ".gns3": "gns3",
}


def detect_format(source: str | Path, format: str = "auto") -> str:
    if format != "auto":
        return format.lower()

    suffix = Path(source).suffix.lower()
    if suffix in FORMAT_BY_SUFFIX:
        return FORMAT_BY_SUFFIX[suffix]

    raise ValueError(f"unsupported_import_format:{suffix or 'unknown'}")


def load_tgraph(source: str | Path, format: str = "auto", target_profile: str = LOGICAL_V1) -> TGraph:
    resolved = detect_format(source, format=format)
    if resolved == "json":
        return load_tgraph_json(source)
    if resolved == "gml":
        return load_tgraph_gml(source, target_profile=target_profile)
    if resolved == "gns3":
        return load_tgraph_gns3(source, target_profile=target_profile)
    raise ValueError(f"unsupported_import_format:{resolved}")
