from tgraph import TGraph


def test_target_registry_lists_only_iac_targets():
    from tgraph.targets import list_targets

    assert list_targets() == ["pulumi", "terraform", "tosca"]
    assert "tgraph-json" not in list_targets()


def test_placeholder_emitters_return_not_implemented():
    from tgraph import emit_target

    graph = TGraph.model_validate({"stage": "physical", "nodes": [], "links": []})

    result = emit_target("terraform", graph)

    assert result.ok is False
    assert result.target == "terraform"
    assert result.files == []
    assert result.error == {
        "code": "target_not_implemented",
        "message": "target emitter is not implemented: terraform",
    }


def test_unknown_target_returns_target_error():
    from tgraph import emit_target

    graph = TGraph.model_validate({"stage": "physical", "nodes": [], "links": []})

    result = emit_target("cloudformation", graph)

    assert result.ok is False
    assert result.error["code"] == "target_error"

