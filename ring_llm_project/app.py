from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ring_llm_project.core.llm_client import LLMClient, LLMConfig
from ring_llm_project.core.memory import Memory
from ring_llm_project.core.router import LLMRouter
from ring_llm_project.main import build_registry
from ring_llm_project.scenarios.day import DayEngine, DayEngineConfig


@dataclass
class AgentApp:
    llms: Optional[dict[str, LLMClient]] = None
    memory: Optional[Memory] = None
    day_cfg: DayEngineConfig = DayEngineConfig()

    def __post_init__(self) -> None:
        if self.llms is None:
            self.llms = {
                "oss20b": LLMClient(
                    LLMConfig(
                        base_url="http://127.0.0.1:1234",
                        model="openai/gpt-oss-20b",
                        temperature=0.0,
                    )
                )
            }
        self.router = LLMRouter(llms=self.llms)
        self.registry = build_registry()
        if self.memory is None:
            self.memory = Memory(
                goal="Keep working memory compact.",
                max_chars=30_000,
            )
        self.day = DayEngine(router=self.router, registry=self.registry, cfg=self.day_cfg)

    def run_once(self, user_text: str) -> str:
        if user_text:
            self.memory.add_event("user", user_text, kind="msg")
        result = self.day.run_s2(self.memory)
        self.memory = result.memory
        return result.user_output or ""
