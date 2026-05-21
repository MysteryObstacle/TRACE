from trace.stages.ground.nodes.author import author_node
from trace.stages.ground.schemas import GroundDraftArtifact


class CapturingRoleClient:
    def __init__(self):
        self.calls = []

    def invoke_structured(self, *, role_name, messages, schema):
        self.calls.append({"role_name": role_name, "messages": messages, "schema": schema})
        return {
            "node_groups": [{"type": "computer", "members": ["HOST1"]}],
            "logical_constraints": [],
            "physical_constraints": [],
        }


def _human_content(call):
    return "\n\n".join(message["content"] for message in call["messages"] if message["role"] == "human")


def test_ground_author_initial_draft_mode_is_injected_by_node():
    client = CapturingRoleClient()

    author_node(
        {
            "intent": "Build a network with HOST1.",
            "attempt": 1,
            "max_attempts": 3,
            "events": [],
            "status": "preparing",
        },
        client,
    )

    call = client.calls[0]
    human = _human_content(call)
    assert call["role_name"] == "ground_author"
    assert call["schema"] is GroundDraftArtifact
    assert "当前任务模式：`initial_draft`" in human
    assert "[author_mode]\ninitial_draft" in human
    assert "[intent]\nBuild a network with HOST1." in human
    assert "开放式 archetype 中由 author 主动引入的 functional role nodes" in human
    assert "physical_constraints 只能来自 intent 中显式" not in human
    assert "feedback_revision" not in human
    assert "evaluation_feedback" not in human
    assert "previous_artifact" not in human


def test_ground_author_feedback_revision_mode_is_injected_by_node():
    client = CapturingRoleClient()
    previous_artifact = {
        "node_groups": [{"type": "computer", "members": ["HOST1"]}],
        "logical_constraints": [],
        "physical_constraints": [],
    }
    evaluation_report = {
        "passed": False,
        "issues": [{"code": "missing_switch", "message": "SW1 is missing"}],
        "optimizer_brief": {
            "node_groups": [{"type": "switch", "members": ["SW1"]}],
            "logical_constraints": [],
            "physical_constraints": [],
            "notes": [],
        },
    }

    author_node(
        {
            "intent": "Build a network with HOST1 and SW1.",
            "attempt": 2,
            "max_attempts": 3,
            "events": [],
            "status": "preparing",
            "draft_artifact": previous_artifact,
            "evaluation_report": evaluation_report,
        },
        client,
    )

    human = _human_content(client.calls[0])
    assert "当前任务模式：`feedback_revision`" in human
    assert "[author_mode]\nfeedback_revision" in human
    assert "[evaluation_feedback]" in human
    assert "[previous_artifact]" in human
    assert "禁止输出 delta patch" in human
    assert "initial_draft" not in human
