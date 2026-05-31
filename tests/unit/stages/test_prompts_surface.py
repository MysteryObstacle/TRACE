from pathlib import Path

PROMPT_ROOT = Path(__file__).resolve().parents[3] / "src" / "trace" / "stages"
AGENT_PROMPT_ROOTS = [
    PROMPT_ROOT / "logical" / "prompts",
    PROMPT_ROOT / "physical" / "prompts",
]
STRUCTURED_PROMPT_ROOTS = [PROMPT_ROOT / "ground" / "prompts"]


def _agent_prompts() -> list[Path]:
    return [p for root in AGENT_PROMPT_ROOTS for p in root.glob("*.md")]


def _structured_prompts() -> list[Path]:
    return [p for root in STRUCTURED_PROMPT_ROOTS for p in root.glob("*.md")]


def test_no_tgraph_api_listings_in_agent_prompts():
    forbidden = (
        "tgraph.check_subnet",
        "tgraph.check_interface",
        "tgraph.check_direct_link",
        "tgraph.check_chain",
        "tgraph.check_ring",
        "tgraph.check_star",
        "tgraph.check_mesh",
        "tgraph.check_image_exact",
        "tgraph.check_flavor_minimum",
        "tgraph.check_flavor_exact",
        "tgraph.ensure_direct_link",
        "tgraph.ensure_chain",
        "tgraph.ensure_ring",
        "tgraph.ensure_star",
        "tgraph.ensure_mesh",
        "tgraph.ensure_subnet",
        "tgraph.ensure_interface",
        "tgraph.set_image",
        "tgraph.set_flavor",
    )
    for path in _agent_prompts():
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if path.name == "author.md" and "Kind→Tool" in text and token in {
                "tgraph.check_image_exact",
                "tgraph.check_flavor_exact",
                "tgraph.check_flavor_minimum",
            }:
                continue
            assert token not in text, f"{path} still mentions {token}"


def test_agent_prompts_end_with_final_message_constraint():
    for path in _agent_prompts():
        text = path.read_text(encoding="utf-8")
        assert "Final message MUST be a one-sentence action summary" in text, f"{path.name} missing constraint"


def test_structured_prompts_do_not_carry_final_message_constraint():
    for path in _structured_prompts():
        text = path.read_text(encoding="utf-8")
        assert "Final message MUST be a one-sentence action summary" not in text


def test_physical_author_prompt_has_kind_tool_decision_table():
    text = (PROMPT_ROOT / "physical" / "prompts" / "author.md").read_text(encoding="utf-8")
    assert "Kind" in text and "tgraph.check_image_exact" in text
    assert "physical.image.exact" in text
    assert "physical.image.capability" in text


def test_logical_builder_prompt_does_not_forbid_segment_keyword():
    text = (PROMPT_ROOT / "logical" / "prompts" / "builder.md").read_text(encoding="utf-8")
    assert "Do not invent unsupported IR fields such as `segment`" not in text


def test_physical_builder_prompt_forbids_catalog_inside_mutation():
    text = (PROMPT_ROOT / "physical" / "prompts" / "builder.md").read_text(encoding="utf-8")
    assert "not callable inside `mutate(tgraph)`" in text or "never inside" in text.lower() or "Forbidden in mutation" in text
    assert "set_node_image" in text


def test_logical_builder_prompt_uses_incremental_guidance():
    text = (PROMPT_ROOT / "logical" / "prompts" / "builder.md").read_text(encoding="utf-8")
    assert "First inspect the current graph state" in text or "inspect the current graph" in text.lower()
    assert "incremental" in text.lower() or "only the" in text.lower()


def test_physical_builder_prompt_uses_incremental_guidance():
    text = (PROMPT_ROOT / "physical" / "prompts" / "builder.md").read_text(encoding="utf-8")
    assert "First inspect the current graph state" in text or "inspect the current graph" in text.lower()
    assert "prepare" in text.lower() and "inventory" in text.lower()


def test_logical_repair_prompt_mentions_diff_against_previous_attempt():
    text = (PROMPT_ROOT / "logical" / "prompts" / "repair.md").read_text(encoding="utf-8")
    assert "against=" in text or "previous_attempt" in text


def test_physical_repair_prompt_mentions_diff_against_previous_attempt():
    text = (PROMPT_ROOT / "physical" / "prompts" / "repair.md").read_text(encoding="utf-8")
    assert "against=" in text or "previous_attempt" in text
