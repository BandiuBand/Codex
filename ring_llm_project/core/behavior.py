from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ring_llm_project.commands.base import CommandContext, IOAdapter
from ring_llm_project.commands.registry import CommandRegistry

from .fold import Folder
from .llm_client import LLMClient
from .memory import Memory
from .normalize import Normalizer
from .parse_cmd import CommandParser, CommandParseError
from .prompt_builder import PromptBuilder
from .router import LLMRouter
from .sequence import StepSequence
from .step import (
    RUNTIME_COMMAND_BLOCK_KEY,
    RUNTIME_NORMALIZED_OUTPUT_KEY,
    RUNTIME_RAW_OUTPUT_KEY,
    Step,
    mark_stop,
)
from .validate import CommandValidator


@dataclass
class DebugFlags:
    show_class_calls: bool = False
    show_raw_model_output: bool = True
    show_extracted_command: bool = True
    show_memory: bool = False


@dataclass
class BehaviorModel:
    sequence: StepSequence
    name: str = "default"

    def run(self, memory: Memory) -> Memory:
        return self.sequence.run(memory)


class FoldStep(Step):
    def __init__(self, folder: Folder, debug: DebugFlags):
        self.folder = folder
        self.debug = debug

    def execute(self, memory: Memory) -> Memory:
        self.folder.auto_fold_if_needed(memory)
        if self.debug.show_memory:
            print(memory.to_text())
        return memory


class PromptAndCallStep(Step):
    def __init__(
        self,
        prompt_builder: PromptBuilder,
        router: LLMRouter,
        control_llm_key: str,
        debug: DebugFlags,
    ):
        self.prompt_builder = prompt_builder
        self.router = router
        self.control_llm_key = control_llm_key
        self.debug = debug

    def execute(self, memory: Memory) -> Memory:
        messages = self.prompt_builder.build_messages(memory)
        llm: LLMClient = self.router.get(self.control_llm_key)

        if self.debug.show_class_calls:
            print("[CALL] LLMClient.chat")

        raw = llm.chat(messages)

        if self.debug.show_raw_model_output:
            print("\n--- RAW MODEL OUTPUT ---\n")
            print(raw)
            print("\n------------------------\n")

        memory.vars[RUNTIME_RAW_OUTPUT_KEY] = raw
        return memory


class NormalizeStep(Step):
    def __init__(self, normalizer: Normalizer):
        self.normalizer = normalizer

    def execute(self, memory: Memory) -> Memory:
        raw = memory.vars.get(RUNTIME_RAW_OUTPUT_KEY, "")
        normalized = self.normalizer.normalize(raw)
        memory.vars[RUNTIME_NORMALIZED_OUTPUT_KEY] = normalized
        return memory


class CommandBlockStep(Step):
    def __init__(
        self,
        validator: CommandValidator,
        io: Optional[IOAdapter],
        debug: DebugFlags,
    ):
        self.validator = validator
        self.io = io
        self.debug = debug

    def execute(self, memory: Memory) -> Memory:
        normalized = memory.vars.get(RUNTIME_NORMALIZED_OUTPUT_KEY, "")
        ok, block = self.validator.extract_command_block(normalized)
        if not ok or not block:
            text = normalized.strip()
            if text:
                memory.add_event("assistant", text, kind="msg")
                if self.io:
                    self.io.show(text)
            mark_stop(memory)
            return memory

        if self.debug.show_extracted_command:
            print("\n--- EXTRACTED COMMAND BLOCK ---\n")
            print(block)
            print("\n------------------------------\n")

        memory.vars[RUNTIME_COMMAND_BLOCK_KEY] = block
        return memory


class CommandDispatchStep(Step):
    def __init__(
        self,
        parser: CommandParser,
        registry: CommandRegistry,
        router: LLMRouter,
        io: Optional[IOAdapter],
    ):
        self.parser = parser
        self.registry = registry
        self.router = router
        self.io = io

    def execute(self, memory: Memory) -> Memory:
        block = memory.vars.get(RUNTIME_COMMAND_BLOCK_KEY, "")
        if not block:
            mark_stop(memory)
            return memory

        try:
            parsed = self.parser.parse(block)
        except CommandParseError as exc:
            err = f"Command parse error: {exc}"
            memory.add_event("assistant", err, kind="note")
            if self.io:
                self.io.show(err)
            mark_stop(memory)
            return memory

        try:
            cmd = self.registry.get(parsed.name)
        except KeyError:
            err = f"Unknown command: {parsed.name}"
            memory.add_event("assistant", err, kind="note")
            if self.io:
                self.io.show(err)
            mark_stop(memory)
            return memory

        ctx = CommandContext(io=self.io, llms=self.router.llms)
        return cmd.run(memory, parsed.args, ctx)
