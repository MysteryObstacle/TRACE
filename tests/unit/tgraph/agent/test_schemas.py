import json
from pathlib import Path


AGENT_ROOT = Path("src/tgraph/agent")


def test_agent_schema_files_exist_and_describe_required_contracts():
    expected = {
        "tgraph.schema.json": {"stage", "nodes", "links"},
        "validation-report.schema.json": {"ok", "issues"},
        "inspect-result.schema.json": set(),
    }

    for name, required in expected.items():
        path = AGENT_ROOT / "schemas" / name
        assert path.exists(), name
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["type"] == "object"
        assert required.issubset(set(schema.get("required", [])))

    assert not (AGENT_ROOT / "schemas" / "patch.schema.json").exists()


def test_agent_playbooks_keep_workflow_and_knowledge_outside_tgraph():
    for name in ("repair.md", "authoring.md", "validation.md", "emission.md"):
        text = (AGENT_ROOT / "playbooks" / name).read_text(encoding="utf-8")
        lowered = text.lower()

        assert "inspect" in lowered
        assert "mutation" in lowered or name == "emission.md"
        assert "validate" in lowered
        assert "do not invent" in lowered
        assert "knowledge" in lowered
        assert "catalog" in lowered
        assert "workflow" in lowered


def test_protocol_module_exports_schema_locations():
    from tgraph.agent.protocol import doc_paths, playbook_paths, schema_paths

    paths = schema_paths()

    assert "tgraph" in paths
    assert paths["tgraph"].name == "tgraph.schema.json"
    assert "patch" not in paths

    playbooks = playbook_paths()

    assert "capabilities" in playbooks
    assert playbooks["capabilities"].name == "capabilities.md"

    docs = doc_paths()

    assert "fact_kinds" in docs
    assert docs["fact_kinds"].name == "fact-kinds.md"
