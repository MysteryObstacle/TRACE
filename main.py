"""Interactive demo for TRACE with streaming and manual approvals."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Callable, Tuple

from colorama import Fore, Style, init as colorama_init

# Allow running directly without installing the package (python main.py)
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trace_agent import AgentConfig, TraceAgent, build_qwen_vllm_chat_model
from trace_agent.memory import PlanStep, StepResult

colorama_init(autoreset=True)

THINK_TAG_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think_blocks(text: str) -> str:
    """Remove <think>...</think> blocks from console output."""

    return THINK_TAG_PATTERN.sub("", text).strip()


class ConsoleTheme:
    def heading(self, text: str) -> str:
        return f"{Style.BRIGHT}{Fore.CYAN}{text}{Style.RESET_ALL}"

    def section(self, text: str) -> str:
        return f"{Style.BRIGHT}{Fore.MAGENTA}{text}{Style.RESET_ALL}"

    def meta(self, text: str) -> str:
        return f"{Fore.YELLOW}{text}{Style.RESET_ALL}"

    def token(self, text: str) -> str:
        return f"{Fore.GREEN}{text}{Style.RESET_ALL}"

    def label(self, text: str) -> str:
        return f"{Style.BRIGHT}{text}{Style.RESET_ALL}"


class TokenPrinter:
    """Stream handler that avoids printing hidden <think> blocks (agent already filters)."""

    def __init__(self, theme: ConsoleTheme) -> None:
        self.theme = theme

    def __call__(self, token: str) -> None:
        sys.stdout.write(self.theme.token(token))
        sys.stdout.flush()


class ProgressPrinter:
    def __init__(self, theme: ConsoleTheme) -> None:
        self.theme = theme

    def __call__(self, message: str) -> None:
        print(self.theme.meta(message))


def _approval_prompt(step: PlanStep, result: StepResult, theme: ConsoleTheme) -> Tuple[bool, str | None]:
    think = strip_think_blocks(result.think)
    action = strip_think_blocks(result.action)
    observe = strip_think_blocks(result.observe)
    print(
        f"\n{theme.section(step.label)}\n  Think: {think}\n  Action: {action}\n  Observe: {observe}\n"
    )
    choice = input("继续执行? (y=继续, e=编辑Think后继续, n=停止): ").strip().lower()
    edited_think: str | None = None
    if choice.startswith("e"):
        edited_think = input("输入修改后的Think: ").strip()
        choice = input("确认继续? (y/n): ").strip().lower()
    return choice.startswith("y"), edited_think


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TRACE agent demo with streaming and approvals")
    parser.add_argument("intent", help="用户意图描述")
    parser.add_argument("--topo-summary", default="(空拓扑)", help="当前拓扑摘要")
    parser.add_argument(
        "--base-url",
        default="http://10.10.5.8:9000/v1",
        help="LLM服务地址，建议保留/v1前缀（会自动去掉/chat/completions结尾）",
    )
    parser.add_argument("--api-key", default="EMPTY", help="LLM API密钥，如vLLM可忽略")
    parser.add_argument("--model", default="Qwen3-8B", help="模型名称")
    parser.add_argument("--manual", action="store_true", help="关闭auto_execute，需人工确认每个step")
    parser.add_argument("--no-stream", action="store_true", help="关闭流式输出")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    theme = ConsoleTheme()
    token_printer: Callable[[str], None] | None = None if args.no_stream else TokenPrinter(theme)
    progress_printer = ProgressPrinter(theme)

    def approval(step: PlanStep, result: StepResult) -> Tuple[bool, str | None]:
        return _approval_prompt(step, result, theme)

    config = AgentConfig(
        auto_execute=not args.manual,
        stream=not args.no_stream,
        stream_handler=token_printer,
        progress_callback=progress_printer,
        approval_callback=None if not args.manual else approval,
    )

    llm = build_qwen_vllm_chat_model(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
    )
    agent = TraceAgent(llm, config)
    print(theme.heading("\n=== 开始执行 PLAN + ReAct ===\n"))
    plan = agent.run_plan(args.intent, topo_state={"summary": args.topo_summary})

    print(theme.heading("\n=== 最终结果 ===\n"))
    for step, results in plan.steps.items():
        for idx, result in enumerate(results, start=1):
            think = strip_think_blocks(result.think)
            action = strip_think_blocks(result.action)
            observe = strip_think_blocks(result.observe)
            print(
                f"{theme.section(f'{step.label} #{idx}')}\n"
                f"  Think: {think}\n  Action: {action}\n  Observe: {observe}\n"
            )


if __name__ == "__main__":
    main()
