# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Dict, List

from core.commands.base import Command, CommandContext, CommandResult
from core.memory import Memory
from utils.text import normalize_newlines


class PlanCommand(Command):
    def execute(self, args: Dict[str, str], memory: Memory, ctx: CommandContext) -> CommandResult:
        steps_raw = normalize_newlines(args.get("steps", "")).strip()
        current = normalize_newlines(args.get("current", "")).strip()

        steps: List[str] = []
        if steps_raw:
            # allow either numbered list or newline-separated
            for ln in steps_raw.split("\n"):
                ln = ln.strip()
                if not ln:
                    continue
                # strip leading numbering like "1)" or "1."
                ln2 = ln
                if len(ln2) >= 2 and (ln2[0].isdigit() and ln2[1] in [")", "."]):
                    ln2 = ln2[2:].strip()
                steps.append(ln2)

        memory.set_plan(steps=steps, current=current)
        memory.add_history("CMD PLAN (updated)")
        return CommandResult(ok=True)
