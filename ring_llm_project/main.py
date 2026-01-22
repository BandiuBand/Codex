# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List

from config import AppConfig
from core.memory import Memory
from core.validator import SyntaxValidator
from core.parser import CommandParser
from core.dispatcher import CommandDispatcher
from core.commands.base import CommandContext
from llm.ollama_client import OllamaClient
from llm.prompt_builder import PromptBuilder
from utils.log import to_one_line_for_log


def run_cli() -> None:
    cfg = AppConfig()

    memory = Memory(
        max_chars=cfg.memory.max_chars,
        history_max_events=cfg.memory.history_max_events,
    )

    # (optional) seed memory example
    if not memory.goal:
        memory.set_goal(
            "Design a real DC-DC boost converter: 18V -> 80V / 10A, input current limit 20A."
        )
        memory.set_var("controller", "TL494+ESP32")
        memory.set_var("freq_eff", "150kHz")
        memory.set_var("iout", "10A")
        memory.set_var("phases", "3")
        memory.set_var("topology", "multiphase_boost_sync")
        memory.set_var("vin_range", "18..24V")
        memory.set_var("vout", "80V")
        memory.set_plan(
            steps=[
                "Collect missing specs/constraints (parts, ripple, thermal, MOSFET/driver, current sharing).",
                "Choose per-phase switching frequency and phase shift strategy.",
                "Compute per-phase current, inductors, ripple, peak currents.",
                "Select MOSFETs/diodes/synchronous rectification method + gate drive.",
                "Define TL494 sync/phase generation + ESP32 supervision (current limit & protections).",
                "Draft schematic blocks and BOM.",
            ],
            current="Collect missing specs/constraints.",
        )

    llm = OllamaClient(cfg.llm)
    prompt_builder = PromptBuilder(cfg)
    validator = SyntaxValidator(cfg.commands, cfg.validation_mode)
    parser = CommandParser()
    dispatcher = CommandDispatcher()

    executed_recent_cmds: List[str] = []

    print("=== Command-driven LLM runner ===")
    print("Type your message. Type '/exit' to stop.\n")

    while True:
        user_text = input("YOU> ").strip()
        if not user_text:
            continue
        if user_text.lower() in ["/exit", "exit", "quit", "/quit"]:
            break

        # Store user message into history (this forms the "memory fingerprint" of your dialogue)
        memory.add_history(f"USER: {user_text}")

        # optional auto-fold
        if cfg.memory.auto_fold:
            memory.auto_fold_if_needed(cfg.memory.auto_fold_keep_last_events)

        # LLM call loop: allow immediate retry if validation fails
        for attempt in range(1, 6):
            messages = prompt_builder.build_messages(memory, user_text)
            raw = llm.chat(messages)

            # keep raw in debug for transparency (but do not break parsing)
            memory.add_debug(
                f"RAW_LLM_OUTPUT(attempt={attempt}): {to_one_line_for_log(raw)}"
            )

            v = validator.validate(raw)
            if not v.ok or not v.command_line:
                memory.add_debug(f"VALIDATION_FAILED: {v.error}")
                # fail-closed: add a protocol reminder and retry
                memory.add_history("SYSTEM: validation_failed; requesting CMD-only output.")
                user_text = (
                    "Protocol violation: you did not output a valid CMD line. "
                    "Return exactly one line: CMD <NAME> key=value ..."
                )
                continue

            cmd = parser.parse(v.command_line)

            # record executed for loop protection
            signature = cmd.name
            if cmd.name == "ASK":
                signature = f"ASK|{cmd.args.get('text','').strip()}"
            executed_recent_cmds.append(signature)
            if len(executed_recent_cmds) > 1000:
                executed_recent_cmds = executed_recent_cmds[-1000:]

            ctx = CommandContext(
                executed_recent_cmds=executed_recent_cmds,
                repeat_ask_window=cfg.repeat_ask_window,
                repeat_ask_limit=cfg.repeat_ask_limit,
            )

            disp = dispatcher.dispatch(cmd.name, cmd.args, memory, ctx)
            res = disp.result

            # print memory snapshot every cycle (this is your "memory imprint")
            print("\n" + "=" * 80)
            print(memory.to_text(include_end_marker=True))
            print("=" * 80 + "\n")

            if res.user_message:
                print("Повідомлення користувачу:")
                print("----------------------------------------")
                print(res.user_message)
                print("----------------------------------------\n")

            if res.wait_user:
                # wait for user reply and store it as conversation result
                reply = input("USER_REPLY> ").strip()
                memory.add_history(f"USER_REPLY: {reply}")
                # after getting user reply, continue outer loop to accept next YOU> input
                break

            if res.stop:
                print("Зупинено командою DONE/ERROR.\n")
                return

            # command executed without needing user input; continue asking LLM for next command?
            # In your original logs you were iterating; here we stop after 1 command per user turn.
            break
        else:
            print("Too many failed validation attempts. Stopping.")
            return


if __name__ == "__main__":
    run_cli()
