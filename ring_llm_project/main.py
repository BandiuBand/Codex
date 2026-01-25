from __future__ import annotations

from ring_llm_project.core.llm_client import LLMClient, LLMConfig
from ring_llm_project.core.router import LLMRouter
from ring_llm_project.core.memory import Memory
from ring_llm_project.core.behavior import DebugFlags
from ring_llm_project.core.consciousness_builder import ConsciousnessBuilder
from ring_llm_project.core.process import Process, ProcessConfig
from ring_llm_project.commands.registry import CommandRegistry
from ring_llm_project.commands.say import SayCommand
from ring_llm_project.commands.builtin_ask import AskCommand
from ring_llm_project.commands.copy import CopyCommand
from ring_llm_project.commands.fold import FoldCommand
from ring_llm_project.commands.unfold import UnfoldCommand
from ring_llm_project.commands.loop_done import LoopDoneCommand
from ring_llm_project.commands.base import IOAdapter


def build_registry() -> CommandRegistry:
    reg = CommandRegistry()
    reg.register(SayCommand())
    reg.register(AskCommand())
    reg.register(CopyCommand())
    reg.register(FoldCommand())
    reg.register(UnfoldCommand())
    reg.register(LoopDoneCommand())
    return reg


def create_process(
    *,
    io: IOAdapter,
    mem: Memory | None = None,
    llms: dict[str, LLMClient] | None = None,
    process_cfg: ProcessConfig | None = None,
    debug: DebugFlags | None = None,
) -> Process:
    # 1) Create any number of LLM clients with any keys you want
    llms = llms or {
        # Cherry Studio / LM Studio OpenAI-compatible server:
        "oss20b": LLMClient(LLMConfig(
            base_url="http://127.0.0.1:1234",
            model="openai/gpt-oss-20b",
            temperature=0.2,
        )),
        # add more if you want:
        # "small": LLMClient(LLMConfig(base_url="http://127.0.0.1:1234", model="...", temperature=0.2)),
    }

    router = LLMRouter(llms=llms)
    registry = build_registry()

    mem = mem or Memory(
        goal="Design power electronics converters.",
        vars={"controller": "TL494+ESP32"},
        plan=[
            "Collect constraints",
            "Pick topology and frequency",
            "Compute magnetics and currents",
            "Select power stage and drivers",
            "Protections + validation",
        ],
        max_chars=30_000,
    )

    process_cfg = process_cfg or ProcessConfig(control_llm_key="oss20b")
    debug = debug or DebugFlags(
        show_class_calls=False,
        show_raw_model_output=True,
        show_extracted_command=True,
        show_memory=False,
    )
    behavior = ConsciousnessBuilder(
        cfg=process_cfg,
        router=router,
        registry=registry,
        io=io,
        debug=debug,
    ).build()

    return Process(
        cfg=process_cfg,
        mem=mem,
        behavior=behavior,
    )


def run_once(process: Process, user_message: str) -> None:
    process.handle_user_message(user_message)
    process.run_once()
