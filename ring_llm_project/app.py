# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from commands.ask import AskCommand
from commands.copy import CopyCommand
from commands.cut import CutCommand
from commands.delete import DeleteCommand
from commands.fold import FoldCommand
from commands.insert import InsertCommand
from commands.loop_done import LoopDoneCommand
from commands.say import SayCommand
from commands.unfold import UnfoldCommand
from core.dispatcher import CommandDispatcher, CommandRegistry
from core.io import ConsoleIO, IOAdapter
from core.llm_client import LLMClient, LLMConfig
from core.memory import Memory
from scenarios.day.engine import DayEngine


@dataclass
class AgentApp:
    llm_pool: Dict[str, LLMClient]
    dispatcher: CommandDispatcher
    day_engine: DayEngine
    memory: Memory

    @classmethod
    def build_default(cls, *, llm_pool: Dict[str, LLMConfig], io: Optional[IOAdapter] = None) -> "AgentApp":
        io = io or ConsoleIO()

        pool: Dict[str, LLMClient] = {k: LLMClient(cfg) for k, cfg in llm_pool.items()}

        registry = CommandRegistry()
        # Atomic commands
        registry.register(CopyCommand())
        registry.register(InsertCommand())
        registry.register(CutCommand())
        registry.register(DeleteCommand())
        registry.register(FoldCommand())
        registry.register(UnfoldCommand())
        registry.register(LoopDoneCommand())
        registry.register(SayCommand())
        registry.register(AskCommand())

        dispatcher = CommandDispatcher(registry)
        day = DayEngine(dispatcher=dispatcher, llm_pool=pool, io=io)
        mem = Memory()
        return cls(llm_pool=pool, dispatcher=dispatcher, day_engine=day, memory=mem)

    def run_once(self, user_text: str) -> str:
        """One app tick: add user's message into BODY and run day S2 fold-loop."""
        if user_text.strip():
            self.memory.append_body(f"USER: {user_text}\n")
        res = self.day_engine.run_s2_fold_loop(self.memory)
        self.memory = res.memory
        return self.memory.to_text()
