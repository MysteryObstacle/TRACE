from pathlib import Path


CAPABILITIES_PATH = Path("src/tgraph/agent/playbooks/capabilities.md")


def test_tgraph_capability_contract_forbids_unsupported_ir_fields() -> None:
    text = CAPABILITIES_PATH.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "software" in lowered
    assert "packages" in lowered
    assert "segment" in lowered
    assert "cannot" in lowered


def test_tgraph_capability_contract_explains_image_translation() -> None:
    text = CAPABILITIES_PATH.read_text(encoding="utf-8").lower()

    assert "install software" in text
    assert "image" in text


def test_agent_playbooks_use_file_backed_checkpoint_shape() -> None:
    for path in (
        "src/tgraph/agent/playbooks/authoring.md",
        "src/tgraph/agent/playbooks/repair.md",
        "src/tgraph/agent/playbooks/validation.md",
    ):
        text = Path(path).read_text(encoding="utf-8")
        assert "graph" in text
        assert "constraint_files" in text
        assert "checkpoint_files" in text
        assert "validator_script" not in text
        assert "tgraph_logical" not in text
        assert "profile" not in text


def test_agent_protocol_examples_use_mutation_files() -> None:
    text = Path("src/tgraph/agent/protocol.py").read_text(encoding="utf-8").lower()

    assert "mutation files" in text
    assert "checkpoint_files" in text
    assert "transaction" not in text
