"""Command line interface for NeuroHub."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .config import API_KEY_ENV, ConfigError, DEFAULT_MODELS
from .conversation import Conversation

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Unified AI chat client")
    parser.add_argument("prompt", nargs="*", help="One-shot prompt")
    parser.add_argument("-p", "--provider", choices=sorted(API_KEY_ENV), help="Provider to use")
    parser.add_argument("-m", "--model", help="Model name")
    return parser


async def run_once(prompt: str, provider: str | None, model: str | None) -> int:
    conversation = Conversation(provider=provider, model=model)
    async for _ in _stream_answer(conversation, prompt):
        pass
    return 0


async def run_chat(provider: str | None, model: str | None) -> int:
    conversation = Conversation(provider=provider, model=model)
    console.print(Panel.fit("NeuroHub — /help для команд, /exit для выхода", style="cyan"))
    while True:
        text = Prompt.ask("[bold green]Ты[/]").strip()
        if not text:
            continue
        if text in {"/exit", "/quit"}:
            return 0
        if text == "/help":
            console.print("/help /exit /clear /tokens /export /model")
            continue
        if text == "/clear":
            conversation.clear()
            console.print("История очищена")
            continue
        if text == "/model":
            cfg = conversation.client.config
            console.print(f"{cfg.provider}: {cfg.model} (default: {DEFAULT_MODELS[cfg.provider]})")
            continue
        if text == "/tokens":
            console.print(f"Сообщений в истории: {len(conversation.messages)}")
            continue
        if text.startswith("/export"):
            path = text.removeprefix("/export").strip() or f"neurohub-{datetime.now():%Y%m%d-%H%M%S}.json"
            console.print(f"Сохранено: {conversation.export(path)}")
            continue
        async for _ in _stream_answer(conversation, text):
            pass


async def _stream_answer(conversation: Conversation, text: str):
    answer = ""
    with Live(Markdown("_думаю..._"), console=console, refresh_per_second=12) as live:
        async for chunk in conversation.stream(text):
            if chunk.content:
                answer += chunk.content
                live.update(Markdown(answer))
                yield chunk
    console.print()


def main() -> None:
    args = build_parser().parse_args()
    prompt = " ".join(args.prompt).strip()
    try:
        code = asyncio.run(
            run_once(prompt, args.provider, args.model) if prompt else run_chat(args.provider, args.model)
        )
    except ConfigError as exc:
        console.print(f"[red]Ошибка конфигурации:[/] {exc}")
        raise SystemExit(2) from exc
    raise SystemExit(code)


if __name__ == "__main__":
    main()
