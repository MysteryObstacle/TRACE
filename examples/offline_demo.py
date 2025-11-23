"""Offline demo showing how the TRACE agent stitches the PLAN + ReAct loop."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from trace_agent import TraceAgent


class StaticChatModel(BaseChatModel):
    """A deterministic chat model that replays canned answers."""

    def __init__(self, responses: list[str]):
        super().__init__()
        self.responses = responses
        self._idx = 0

    @property
    def _llm_type(self) -> str:
        return "static"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:  # type: ignore[override]
        content = self.responses[min(self._idx, len(self.responses) - 1)]
        self._idx += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


if __name__ == "__main__":
    canned = [
        "为混合云环境构建可伸缩的零信任网络拓扑",  # goal extraction
        "yes",  # classifier
        "Think: 需要确认业务域和安全域\nAction: N/A\nObserve: 用户意图明确：混合云零信任架构",  # Step 1
        "Think: 根据零信任需要认证网关、服务网关、工作负载节点\nAction: N/A\nObserve: 使用gateway、service、workload节点",  # Step 2
        "Think: 按云上/云下和安全域拆分\nAction: N/A\nObserve: 划分cloud/trust区与on-premises/trust区",  # Step 3
        "Think: 给每类节点补充镜像和规格\nAction: Image Catalog\nObserve: gateway使用qwen-gateway:1.0，service使用svc-std:2.0，workload使用app:latest",  # Step 4
        "Think: 产出拓扑JSON\nAction: N/A\nObserve: {\"summary\":\"零信任混合云\",\"nodes\":[{\"id\":\"gw-1\",\"type\":\"gateway\"}]} ",  # Step 5
        "Think: 转换为SceneGraph\nAction: SceneGraph Ops\nObserve: scene.createNode('gateway',{id:'gw-1'})",  # Step 6
        "Think: 校验代码与SDK\nAction: SceneGraph Op Detail\nObserve: 代码符合SceneGraph规范"  # Step 7
    ]

    model = StaticChatModel(canned)
    agent = TraceAgent(model)
    plan = agent.run_plan("构建混合云零信任拓扑", topo_state={"summary": "当前无资源"})
    for step, results in plan.steps.items():
        for idx, result in enumerate(results, start=1):
            print(f"{step.label} #{idx}\nThink: {result.think}\nAction: {result.action}\nObserve: {result.observe}\n")
