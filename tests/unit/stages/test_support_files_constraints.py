from trace.stages.support_files import load_constraint_entries


def test_load_constraint_entries_reads_support_file_payload() -> None:
    entries = load_constraint_entries(
        support_files={
            "ground/logical_constraints.json": (
                '{"lc1": {"kind": "logical.topology.chain", "statement": "WEB -> SW_DMZ -> R_CORE"}}'
            )
        },
        constraint_files={"logical": "ground/logical_constraints.json"},
        scope="logical",
        default_path="ground/logical_constraints.json",
    )

    assert entries == [
        {
            "id": "lc1",
            "kind": "logical.topology.chain",
            "statement": "WEB -> SW_DMZ -> R_CORE",
        }
    ]


def test_load_constraint_entries_falls_back_to_default_path() -> None:
    entries = load_constraint_entries(
        support_files={"ground/logical_constraints.json": '{"lc2": {"kind": "logical.custom", "statement": "x"}}'},
        constraint_files={},
        scope="logical",
        default_path="ground/logical_constraints.json",
    )

    assert entries == [{"id": "lc2", "kind": "logical.custom", "statement": "x"}]
