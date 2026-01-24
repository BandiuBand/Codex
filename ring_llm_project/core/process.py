from __future__ import annotations
from dataclasses import dataclass

from .behavior import BehaviorModel
from .memory import Memory


@dataclass
class ProcessConfig:
    control_llm_key: str
    auto_fold_keep_last_events: int = 30


class Process:
    def __init__(
        self,
        cfg: ProcessConfig,
        mem: Memory,
        behavior: BehaviorModel,
    ):
        self.cfg = cfg
        self.mem = mem
        self.behavior = behavior

    def handle_user_message(self, text: str) -> None:
        self.mem.add_event("user", text, kind="msg")

    def run_once(self) -> None:
        self.mem = self.behavior.run(self.mem)
