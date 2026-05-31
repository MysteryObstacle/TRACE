from __future__ import annotations

from pathlib import Path


"""Agent protocol helpers for standalone TGraph.

Agents operate on the outer stage-artifact shape:
- graph
- constraint_files
- checkpoint_files

Mutations must use controlled TGraphEditor operations through mutation files.
Stepwise one-off edit APIs are not part of this protocol surface.
"""


def schema_paths() -> dict[str, Path]:
    root = Path(__file__).resolve().parent / "schemas"
    return {
        "tgraph": root / "tgraph.schema.json",
        "validation_report": root / "validation-report.schema.json",
        "inspect_result": root / "inspect-result.schema.json",
    }


def playbook_paths() -> dict[str, Path]:
    root = Path(__file__).resolve().parent / "playbooks"
    return {
        "authoring": root / "authoring.md",
        "author_contract": root / "author_contract.md",
        "logical_author_contract": root / "logical_author_contract.md",
        "physical_author_contract": root / "physical_author_contract.md",
        "builder_contract": root / "builder_contract.md",
        "logical_builder_contract": root / "logical_builder_contract.md",
        "physical_builder_contract": root / "physical_builder_contract.md",
        "repair": root / "repair.md",
        "repair_contract": root / "repair_contract.md",
        "logical_repair_contract": root / "logical_repair_contract.md",
        "physical_repair_contract": root / "physical_repair_contract.md",
        "validation": root / "validation.md",
        "emission": root / "emission.md",
        "capabilities": root / "capabilities.md",
    }


def doc_paths() -> dict[str, Path]:
    root = Path(__file__).resolve().parent / "docs"
    return {
        "artifact_files": root / "artifact-files.md",
        "catalogs": root / "catalogs.md",
        "checkpoint_files": root / "checkpoint-files.md",
        "fact_kinds": root / "fact-kinds.md",
        "mutation_files": root / "mutation-files.md",
        "naming": root / "naming.md",
        "readme": root / "README.md",
    }
