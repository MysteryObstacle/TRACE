from src.trace_agent import TraceAgent, build_qwen_vllm_chat_model

llm = build_qwen_vllm_chat_model(
    base_url="http://10.10.5.8:9000/v1",
    api_key="EMPTY",              # vLLM’s default OpenAI-compatible key
    model="Qwen3-8B",             # matches your served model
)
agent = TraceAgent(llm)
plan = agent.run_plan(
    "我想要构建一个工业控制网络的靶场场景",
    topo_state={"summary": "当前拓扑状态，可填空"},
)
for step, results in plan.steps.items():
    for idx, result in enumerate(results, start=1):
        print(step.label, result.think, result.action, result.observe)
