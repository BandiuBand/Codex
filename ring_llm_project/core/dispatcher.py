# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Type

from core.memory import Memory
from core.commands.base import Command, CommandContext, CommandResult
from core.commands.ask import AskCommand
from core.commands.note import NoteCommand
from core.commands.setvar import SetVarCommand
from core.commands.setgoal import SetGoalCommand
from core.commands.plan import PlanCommand
from core.commands.fold_cmd import FoldCommand
from core.commands.done import DoneCommand
from core.commands.error import ErrorCommand


@dataclass
class DispatcherResult:
    result: CommandResult
    new_memory: Memory


class CommandDispatcher:
    def __init__(self):
        self.registry: Dict[str, Type[Command]] = {
            "ASK": AskCommand,
            "NOTE": NoteCommand,
            "SETVAR": SetVarCommand,
            "SETGOAL": SetGoalCommand,
            "PLAN": PlanCommand,
            "FOLD": FoldCommand,
            "DONE": DoneCommand,
            "ERROR": ErrorCommand,
        }

    def dispatch(
        self, cmd_name: str, args: Dict[str, str], memory: Memory, ctx: CommandContext
    ) -> DispatcherResult:
        cmd_name = cmd_name.upper()
        if cmd_name not in self.registry:
            raise ValueError(f"unknown_command:{cmd_name}")
        cmd_cls = self.registry[cmd_name]
        cmd: Command = cmd_cls()
        res = cmd.execute(args=args, memory=memory, ctx=ctx)
        return DispatcherResult(result=res, new_memory=memory)
