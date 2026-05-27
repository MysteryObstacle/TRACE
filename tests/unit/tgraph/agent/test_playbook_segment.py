from tgraph.agent.protocol import doc_paths, playbook_paths


def test_authoring_playbook_mentions_check_interface_and_marks_segment_required():
    text = playbook_paths()["authoring"].read_text(encoding="utf-8")
    assert "check_interface" in text
    assert "ensure_interface" in text
    para = next(p for p in text.split("\n\n") if "check_interface" in p or "ensure_interface" in p)
    assert "required" in para.lower() or "must" in para.lower()


def test_authoring_playbook_clarifies_segment_meaning():
    text = playbook_paths()["authoring"].read_text(encoding="utf-8")
    assert "neighboring" in text.lower() or "switch node id" in text.lower() or "not an IR field" in text.lower()


def test_capabilities_playbook_no_longer_lists_segment_as_unsupported_ir_field():
    text = playbook_paths()["capabilities"].read_text(encoding="utf-8")
    forbidden_line_fragments = [
        "`software`, `packages`, `zone`, `segment`",
        "`software`, `packages`, `segment`",
        "`segment`, `firewall_rules`",
    ]
    for fragment in forbidden_line_fragments:
        assert fragment not in text


def test_repair_playbook_mentions_image_tools():
    text = playbook_paths()["repair"].read_text(encoding="utf-8")
    assert "find_images" in text
    assert "get_image" in text


def test_tgraph_check_api_doc_marks_segment_required():
    text = doc_paths()["readme"].parent.joinpath("tgraph_check_api.md").read_text(encoding="utf-8")
    assert "segment" in text
    assert "required" in text.lower() or "must" in text.lower() or "parameter" in text.lower()


def test_tgraph_editor_api_doc_marks_segment_required():
    text = doc_paths()["readme"].parent.joinpath("tgraph_editor_api.md").read_text(encoding="utf-8")
    assert "ensure_interface" in text
    assert "segment" in text
    assert "parameter" in text.lower() or "neighboring" in text.lower()
