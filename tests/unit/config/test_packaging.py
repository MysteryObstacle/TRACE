from pathlib import Path


def test_pyproject_pins_supported_langchain_stack():
    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")

    assert '"langchain>=1.2,<1.3"' in content
    assert '"langgraph>=1.1.1,<1.2"' in content
    assert '"langchain-openai>=1.1,<1.2"' in content
    assert '"langsmith>=0.7,<0.8"' in content


def test_pyproject_routes_trace_console_script_through_non_conflicting_wrapper():
    pyproject = Path(__file__).resolve().parents[3] / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")

    assert 'trace = "trace_cli:app"' in content
