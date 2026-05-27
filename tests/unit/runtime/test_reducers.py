from langgraph.graph import END, StateGraph

from trace.runtime.engine import RunState


def test_run_state_events_accumulate_via_reducer():
    graph = StateGraph(RunState)
    graph.add_node("node_a", lambda state: {"events": [{"type": "a"}]})
    graph.add_node("node_b", lambda state: {"events": [{"type": "b"}]})
    graph.set_entry_point("node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    compiled = graph.compile()
    result = compiled.invoke({"run_id": "test", "intent": "x", "status": "running"})
    types = [event["type"] for event in result.get("events", [])]
    assert types == ["a", "b"]


def test_escalation_history_accumulates_via_reducer():
    graph = StateGraph(RunState)
    graph.add_node("node_a", lambda state: {"escalation_history": [{"round": 1}]})
    graph.add_node("node_b", lambda state: {"escalation_history": [{"round": 2}]})
    graph.set_entry_point("node_a")
    graph.add_edge("node_a", "node_b")
    graph.add_edge("node_b", END)
    compiled = graph.compile()
    result = compiled.invoke({"run_id": "t", "intent": "x", "status": "running"})
    rounds = [item["round"] for item in result.get("escalation_history", [])]
    assert rounds == [1, 2]


def test_logical_state_repair_history_accumulates():
    from trace.stages.logical.state import LogicalState

    graph = StateGraph(LogicalState)
    graph.add_node("a", lambda state: {"repair_history": [{"round": 1}]})
    graph.add_node("b", lambda state: {"repair_history": [{"round": 2}]})
    graph.set_entry_point("a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    compiled = graph.compile()
    result = compiled.invoke({})
    rounds = [item["round"] for item in result.get("repair_history", [])]
    assert rounds == [1, 2]


def test_ground_state_does_not_define_next_action():
    from trace.stages.ground.state import GroundState

    assert "next_action" not in GroundState.__optional_keys__


def test_logical_state_does_not_define_next_action():
    from trace.stages.logical.state import LogicalState

    assert "next_action" not in LogicalState.__optional_keys__


def test_physical_state_does_not_define_next_action():
    from trace.stages.physical.state import PhysicalState

    assert "next_action" not in PhysicalState.__optional_keys__
