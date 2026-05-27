import json

from trace.stages.support_files import _FilterParams, filtered_view


SAMPLE_JSON = json.dumps(
    {
        "lc1": {"statement": "SW_DMZ is subnet 10.10.10.0/24.", "kind": "logical.addressing.subnet"},
        "lc17": {"statement": "Routers require fixed IPv4.", "kind": "logical.custom"},
    },
    indent=2,
)


def test_filter_params_defaults_all_none():
    params = _FilterParams()
    assert params.match is None and params.keys is None and params.head_lines is None


def test_filtered_view_returns_full_content_when_no_filter():
    assert filtered_view(SAMPLE_JSON) == SAMPLE_JSON


def test_filtered_view_match_returns_line_window():
    out = filtered_view(SAMPLE_JSON, match="lc17")
    assert "lc17" in out
    assert "Routers require fixed IPv4" in out
    assert 'lc1"' not in out


def test_filtered_view_keys_returns_subdocument():
    out = filtered_view(SAMPLE_JSON, keys=["lc17"])
    parsed = json.loads(out)
    assert list(parsed.keys()) == ["lc17"]


def test_filtered_view_keys_ignored_when_not_json_object():
    plain = "line a\nline b\nline c\n"
    assert filtered_view(plain, keys=["a"]) == plain


def test_filtered_view_head_lines():
    plain = "\n".join(f"line {i}" for i in range(20))
    out = filtered_view(plain, head_lines=3)
    assert out.splitlines() == ["line 0", "line 1", "line 2"]


def test_filtered_view_priority_match_over_keys_over_head_lines():
    out = filtered_view(SAMPLE_JSON, match="lc17", keys=["lc1"], head_lines=2)
    assert "lc17" in out
    assert 'lc1"' not in out
