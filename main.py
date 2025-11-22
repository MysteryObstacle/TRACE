"""Interactive demo for TRACE with streaming and manual approvals."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Tuple

# Allow running directly without installing the package (python main.py)
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trace_agent import AgentConfig, TraceAgent, build_qwen_vllm_chat_model
from trace_agent.memory import PlanStep, StepResult


def _token_printer(token: str) -> None:
    sys.stdout.write(token)
    sys.stdout.flush()


def _approval_prompt(step: PlanStep, result: StepResult) -> Tuple[bool, str | None]:
    print(f"\n{step.label}\nThink: {result.think}\nAction: {result.action}\nObserve: {result.observe}\n")
    choice = input("继续执行? (y=继续, e=编辑Think后继续, n=停止): ").strip().lower()
    edited_think = None
    if choice.startswith("e"):
        edited_think = input("输入修改后的Think: ").strip()
        choice = input("确认继续? (y/n): ").strip().lower()
    return choice.startswith("y"), edited_think


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRACE agent demo with streaming and approvals")
    parser.add_argument("intent", help="用户意图描述")
    parser.add_argument("--topo-summary", default="(空拓扑)", help="当前拓扑摘要")
    parser.add_argument("--base-url", default="http://localhost:8000/v1", help="LLM服务地址，包含/v1前缀")
    parser.add_argument("--api-key", default="EMPTY", help="LLM API密钥，如vLLM可忽略")
    parser.add_argument("--model", default="Qwen3-8B", help="模型名称")
    parser.add_argument("--manual", action="store_true", help="关闭auto_execute，需人工确认每个step")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式输出")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = AgentConfig(
        auto_execute=not args.manual,
        stream=not args.no_stream,
        stream_handler=None if args.no_stream else _token_printer,
        approval_callback=None if not args.manual else _approval_prompt,
    )

    llm = build_qwen_vllm_chat_model(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
    )
    agent = TraceAgent(llm, config)
    print("\n--- 开始执行 PLAN + ReAct ---\n")
    plan = agent.run_plan(args.intent, topo_state={"summary": args.topo_summary})

    print("\n--- 最终结果 ---\n")
    for step, results in plan.steps.items():
        for idx, result in enumerate(results, start=1):
            print(f"{step.label} #{idx}\nThink: {result.think}\nAction: {result.action}\nObserve: {result.observe}\n")


if __name__ == "__main__":
    main()
