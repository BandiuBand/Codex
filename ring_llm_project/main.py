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
from ring_llm_project.commands.base import IOAdapter


class ConsoleIO(IOAdapter):
    def show(self, text: str) -> None:
        print("\nASSISTANT>\n" + text + "\n")

    def ask(self, text: str) -> str:
        print("\nASSISTANT (ASK)>\n" + text + "\n")
        return input("YOU> ")


def build_registry() -> CommandRegistry:
    reg = CommandRegistry()
    reg.register(SayCommand())
    reg.register(AskCommand())
    reg.register(CopyCommand())
    reg.register(FoldCommand())
    reg.register(UnfoldCommand())
    return reg


def main():
    # 1) Create any number of LLM clients with any keys you want
    llms = {
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

    mem = Memory(
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

    io = ConsoleIO()  # replace later with Cherry Studio adapter

    process_cfg = ProcessConfig(control_llm_key="oss20b")
    behavior = ConsciousnessBuilder(
        cfg=process_cfg,
        router=router,
        registry=registry,
        io=io,
        debug=DebugFlags(
            show_class_calls=False,
            show_raw_model_output=True,
            show_extracted_command=True,
            show_memory=False,
        ),
    ).build()

    process = Process(
        cfg=process_cfg,
        mem=mem,
        behavior=behavior,
    )

    # Not "CLI mode": just a normal loop in a script, no args.
    while True:
        user = input("YOU> ").strip()
        if user.lower() in {"/exit", "exit", "quit"}:
            break
        process.handle_user_message(user)
        process.run_once()


if __name__ == "__main__":
    main()
