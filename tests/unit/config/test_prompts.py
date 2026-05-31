from pathlib import Path

from trace.stages.logical.schemas import LogicalArtifact
from trace.stages.physical.schemas import PhysicalArtifact
from trace.stages.prompt_contracts import load_tgraph_contract_for
from tgraph import TGraph


ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATHS = [
    "src/trace/stages/ground/prompts/author.md",
    "src/trace/stages/ground/prompts/evaluator.md",
    "src/trace/stages/logical/prompts/author.md",
    "src/trace/stages/logical/prompts/builder.md",
    "src/trace/stages/logical/prompts/repair.md",
    "src/trace/stages/physical/prompts/author.md",
    "src/trace/stages/physical/prompts/builder.md",
    "src/trace/stages/physical/prompts/repair.md",
]


def _prompt(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_stage_artifacts_use_standalone_tgraph_schema():
    assert LogicalArtifact.model_fields["graph"].annotation is TGraph
    assert PhysicalArtifact.model_fields["graph"].annotation is TGraph
    assert "tgraph_logical" not in LogicalArtifact.model_fields
    assert "tgraph_physical" not in PhysicalArtifact.model_fields


def test_all_model_facing_stage_prompts_are_english():
    for path in PROMPT_PATHS:
        prompt = _prompt(path)
        assert not any("\u4e00" <= char <= "\u9fff" for char in prompt), path
        assert prompt.startswith("You are TRACE") or prompt.startswith("Your task")


def test_prompt_contract_loader_uses_standalone_tgraph_playbooks():
    logical_author = load_tgraph_contract_for("logical_author")
    logical_builder = load_tgraph_contract_for("logical_builder")
    logical_repair = load_tgraph_contract_for("logical_repair")
    physical_builder = load_tgraph_contract_for("physical_builder")

    assert "graph" in logical_author
    assert "constraint_files" in logical_author
    assert "checkpoint_files" in logical_author
    assert "validator_script" not in logical_author
    assert "check_<constraint_id>" in logical_author or "check_" in logical_author
    assert "connect_nodes" not in logical_author
    assert "switch_has_subnet" not in logical_author
    assert "node_interface_on_segment" not in logical_author
    assert "neighboring" in logical_author.lower() or "segment is a function parameter" in logical_author
    assert "validate after every meaningful change" not in logical_author
    assert "tgraph_view_api.md" in logical_author
    assert "tgraph_editor_api.md" not in logical_author

    assert "ensure_direct_link" in logical_builder
    assert "ensure_link" in logical_builder
    assert "Logical Builder Contract" in logical_builder or "logical mutation" in logical_builder.lower()
    assert "Physical metadata APIs" in logical_builder
    assert "mutation_authoring.md" in logical_builder

    assert "coherent" in logical_repair.lower()
    assert "Logical Repair Contract" in logical_repair or "logical mutation" in logical_repair.lower()
    assert "set_node_image" not in logical_repair
    assert "find_images" not in logical_repair
    assert "graph/checkpoints/validator_script" not in logical_repair
    assert "validate, then repeat" not in logical_repair

    assert "Physical Builder Contract" in physical_builder or "set_node_image" in physical_builder
    assert "set_image" in physical_builder
    assert "ensure_direct_link" not in physical_builder


def test_logical_prompts_use_file_backed_checkpoint_and_mutation_contract():
    author_prompt = _prompt("src/trace/stages/logical/prompts/author.md")
    builder_prompt = _prompt("src/trace/stages/logical/prompts/builder.md")
    repair_prompt = _prompt("src/trace/stages/logical/prompts/repair.md")

    assert "ground/logical_constraints.json" in author_prompt
    assert "logical/constraints.json" not in author_prompt
    assert "logical/checkpoints.py" in author_prompt
    assert "write_checkpoint_file" in author_prompt
    assert "validate_checkpoint_file" in author_prompt
    assert "tgraph.escalate" in author_prompt
    assert "check_<constraint_id>" in author_prompt
    assert "logical_checkpoints" not in author_prompt
    assert "logical_validator_script" not in author_prompt
    assert "segment_id" not in author_prompt

    assert "write_mutation_file" in builder_prompt
    assert "execute_mutation_file" in builder_prompt
    assert "validate=true" not in builder_prompt
    assert "node completion" in builder_prompt.lower() or "completes this node" in builder_prompt.lower()
    assert "ensure_link" in builder_prompt
    assert "coherent" not in builder_prompt.lower()
    assert "logical/mutations/attempt_N.py" in builder_prompt
    assert "logical/mutations/build.py" not in builder_prompt
    assert "logical/constraints.json" not in builder_prompt
    assert "LogicalArtifact schema" not in builder_prompt
    assert "working graph" not in builder_prompt.lower()
    assert "working_graph" not in builder_prompt

    assert "write_mutation_file" in repair_prompt
    assert "execute_mutation_file" in repair_prompt
    assert "write_checkpoint_file" in repair_prompt
    assert "coherent" in repair_prompt.lower()
    assert "full-stage validation" in repair_prompt.lower()
    assert "apply_graph_patch" not in repair_prompt


def test_physical_prompts_use_catalog_and_file_backed_mutation_surface():
    author_prompt = _prompt("src/trace/stages/physical/prompts/author.md")
    builder_prompt = _prompt("src/trace/stages/physical/prompts/builder.md")
    repair_prompt = _prompt("src/trace/stages/physical/prompts/repair.md")

    assert "ground/physical_constraints.json" in author_prompt
    assert "physical/constraints.json" not in author_prompt
    assert "image_catalog_summary" in author_prompt
    assert "list_images" in author_prompt
    assert "find_images" in author_prompt
    assert "get_image" in author_prompt
    assert "Tool-time" in author_prompt or "tool-time" in author_prompt.lower()
    assert "physical/checkpoints.py" in author_prompt
    assert "write_checkpoint_file" in author_prompt
    assert "validate_checkpoint_file" in author_prompt
    assert "tgraph.escalate" in author_prompt
    assert "Kind→Tool" in author_prompt
    assert "tgraph.check_image_exact" in author_prompt

    assert "write_mutation_file" in builder_prompt
    assert "execute_mutation_file" in builder_prompt
    assert "validate=true" not in builder_prompt
    assert "node completion" in builder_prompt.lower() or "completes this node" in builder_prompt.lower()
    assert "set_image" in builder_prompt
    assert "physical/mutations/attempt_N.py" in builder_prompt
    assert "physical/mutations/build.py" not in builder_prompt
    assert "physical/constraints.json" not in builder_prompt
    assert "image" in builder_prompt
    assert "flavor" in builder_prompt
    assert "image_catalog_summary" in builder_prompt
    assert "list_images" in builder_prompt
    assert "find_images" in builder_prompt
    assert "type=computer" in builder_prompt
    assert "working_graph" not in builder_prompt

    assert "write_mutation_file" in repair_prompt
    assert "execute_mutation_file" in repair_prompt
    assert "coherent" in repair_prompt.lower()
    assert "replace_validator_script" not in repair_prompt
    assert "list_images" in repair_prompt
    assert "find_images" in repair_prompt
    assert "get_image" in repair_prompt
    assert "apply_graph_patch" not in repair_prompt
