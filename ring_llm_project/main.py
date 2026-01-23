# -*- coding: utf-8 -*-
from __future__ import annotations

from config import AppConfig
from core.memory import Memory
from core.validator import OutputValidator
from core.parser import CommandParser
from core.dispatcher import CommandDispatcher
from commands.registry import CommandRegistry
from commands.ask import AskCommand
from commands.set_goal import SetGoalCommand
from commands.set_var import SetVarCommand
from commands.add_inbox import AddInboxCommand
from commands.fold_now import FoldNowCommand
from commands.noop import NoopCommand
from llm.llm_client import OllamaClient, ChatMessage
from llm.prompt_builder import PromptBuilder
from utils.text import normalize_newlines


def build_registry() -> CommandRegistry:
    reg = CommandRegistry()
    reg.register(AskCommand())
    reg.register(SetGoalCommand())
    reg.register(SetVarCommand())
    reg.register(AddInboxCommand())
    reg.register(FoldNowCommand())
    reg.register(NoopCommand())
    return reg


def run_cli() -> None:
    cfg = AppConfig()

    memory = Memory(max_chars=cfg.memory.max_chars)

    llm = OllamaClient(
        base_url=cfg.llm.base_url,
        model=cfg.llm.model,
        timeout_s=cfg.llm.timeout_s,
    )
    prompt_builder = PromptBuilder(cfg)

    validator = OutputValidator(
        mode=cfg.validator.mode,
        cmd_start=cfg.cmd_start,
        cmd_end=cfg.cmd_end,
        msg_start=cfg.msg_start,
        msg_end=cfg.msg_end,
        require_blocks=cfg.validator.require_blocks,
    )
    parser = CommandParser()
    dispatcher = CommandDispatcher(build_registry())

    print("=== Command-driven LLM runner ===")
    print("Type your message. Type '/exit' to stop.\n")

    while True:
        user_in = input("YOU> ")
        if user_in.strip().lower() == "/exit":
            break

        user_in = normalize_newlines(user_in).rstrip()
        if not user_in.strip():
            continue

        # store user message
        memory.add_history(f"USER: {user_in}")

        # auto fold if too long BEFORE calling LLM
        memory.auto_fold_if_needed(cfg.memory.auto_fold_keep_last_events)

        system = prompt_builder.system_prompt(memory)
        messages = [
            ChatMessage(role="system", content=system),
            ChatMessage(role="user", content=user_in),
        ]

        raw_out = llm.chat(messages)
        v = validator.validate(raw_out)

        # If command
        if v.command_line:
            cmd = parser.parse(v.command_line)  # safe: never throws
            if cmd is None:
                memory.add_history(f"PARSE_FAIL: {v.command_line}")
                print("\n[ERROR] Could not parse command. Showing cleaned output:\n")
                print(v.cleaned_text)
                print(f"\n[MEM fp={memory.fingerprint()} fill={memory.memory_fill_percent()}%]\n")
                continue

            result = dispatcher.dispatch(memory, cmd)

            # show user message if any
            if result.user_message:
                print("\nASSISTANT>")
                print(result.user_message)
                print()

            # show memory fingerprint always (as you wanted)
            print(f"[MEM fp={memory.fingerprint()} fill={memory.memory_fill_percent()}%]\n")

            # ASK stops and waits for user — loop naturally continues
            continue

        # Else message
        msg = v.message_text or v.cleaned_text or ""
        msg = msg.strip()
        if msg:
            memory.add_history("ASSISTANT: " + msg)
            print("\nASSISTANT>")
            print(msg)
            print()

        print(f"[MEM fp={memory.fingerprint()} fill={memory.memory_fill_percent()}%]\n")


if __name__ == "__main__":
    run_cli()
