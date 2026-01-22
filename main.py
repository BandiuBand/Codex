# -*- coding: utf-8 -*-

from __future__ import annotations

from app.config import AppConfig
from app.io_adapter import ConsoleIO
from app.llm_client import LLMClient
from app.memory import Memory
from app.policy import PolicyValidator
from app.validator import SyntaxValidator
from app.executor import CommandExecutor, CommandRegistry

from app.commands.builtins import (
    FoldReplyCommand,
    AskCommand,
    SetCurrentCommand,
    AppendPlanCommand,
    RewritePlanCommand,
    FoldSectionCommand,
    DeleteSectionCommand,
    UnfoldCommand,
)


def make_default_memory() -> Memory:
    mem = Memory()
    mem.goal = "Design a real DC-DC boost converter: 18V -> 80V / 10A, input current limit 20A."
    mem.vars = {
        "controller": "TL494+ESP32",
        "freq_eff": "150kHz",
        "iout": "10A",
        "phases": "3",
        "topology": "multiphase_boost_sync",
        "vin_range": "18..24V",
        "vout": "80V",
    }
    mem.plan_items = [
        "Collect missing specs/constraints (parts, ripple, thermal, MOSFET/driver, current sharing).",
        "Choose per-phase switching frequency and phase shift strategy.",
        "Compute per-phase current, inductors, ripple, peak currents.",
        "Select MOSFETs/diodes/synchronous rectification method + gate drive.",
        "Define TL494 sync/phase generation + ESP32 supervision (current limit & protections).",
        "Draft schematic blocks and BOM.",
    ]
    mem.current_step = "Collect missing specs/constraints."
    return mem


def build_registry(cfg: AppConfig) -> CommandRegistry:
    # Тут можна фільтрувати по cfg.allowed_commands, якщо хочеш
    commands = {
        "FOLD_REPLY": FoldReplyCommand(),
        "ASK": AskCommand(),
        "SET_CURRENT": SetCurrentCommand(),
        "APPEND_PLAN": AppendPlanCommand(),
        "REWRITE_PLAN": RewritePlanCommand(),
        "FOLD_SECTION": FoldSectionCommand(),
        "DELETE_SECTION": DeleteSectionCommand(),
        "UNFOLD": UnfoldCommand(),
    }
    return CommandRegistry(commands=commands)


def main() -> None:
    cfg = AppConfig()

    mem = Memory.load(cfg.state_file)
    if mem is None:
        mem = make_default_memory()
        mem.save(cfg.state_file)

    io = ConsoleIO()
    llm = LLMClient(cfg)
    syntax = SyntaxValidator(mode=cfg.syntax_mode)
    policy = PolicyValidator(
        memory_fold_threshold_percent=cfg.memory_fold_threshold_percent,
        max_context_chars=cfg.max_context_chars,
    )
    executor = CommandExecutor(
        registry=build_registry(cfg),
        io=io,
    )

    print("Оркестратор запущено. Ctrl+C — вихід.\n")

    while True:
        try:
            snapshot = mem.snapshot(cfg.max_context_chars)
            print("=" * 80)
            print(snapshot)
            print("=" * 80)
            print()

            raw = llm.call(snapshot)
            print(f"LLM(raw) -> {raw}\n")

            ok, cmd_line, reason = syntax.clean_and_extract(raw)
            if not ok:
                mem.add_debug(f"SYNTAX_REJECT: {reason}")
                mem.add_history(f"LLM_BAD_OUTPUT {raw}")
                mem.save(cfg.state_file)
                continue

            # policy validation — треба знати cmd/kv, але policy дивиться на kv (wait/var/text)
            # Тому швидко парсимо тут без виконання.
            from app.command_parser import parse_cmd_line
            try:
                cmd, kv = parse_cmd_line(cmd_line)
            except Exception as e:
                mem.add_debug(f"PARSE_REJECT: {e}")
                mem.add_history(f"LLM_BAD_CMDLINE {cmd_line}")
                mem.save(cfg.state_file)
                continue

            perr = policy.validate(mem, cmd, kv)
            if perr:
                mem.add_debug(f"POLICY_REJECT: {perr}")
                mem.add_history(f"REJECTED_CMD {cmd} reason={perr}")
                mem.save(cfg.state_file)
                continue

            # виконання
            try:
                mem = executor.run_validated_cmd_line(mem, cmd_line)
            except Exception as e:
                mem.add_debug(f"EXEC_ERROR: {e}")
                mem.add_history(f"CMD_FAILED {cmd} error={e}")
                mem.save(cfg.state_file)
                continue

            mem.save(cfg.state_file)

        except KeyboardInterrupt:
            print("\nЗупинено користувачем.")
            mem.save(cfg.state_file)
            break
        except Exception as e:
            print(f"\nФАТАЛЬНА ПОМИЛКА: {e}")
            mem.save(cfg.state_file)
            break


if __name__ == "__main__":
    main()
