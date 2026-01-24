from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional

from .memory import Memory
from .fold import Folder
from .normalize import Normalizer, NormalizeConfig
from .validate import CommandValidator, ValidateConfig
from .parse_cmd import CommandParser, CommandParseError
from .prompt_builder import PromptBuilder, PromptConfig
from .router import LLMRouter
from ring_llm_project.commands.registry import CommandRegistry
from ring_llm_project.commands.base import CommandContext, IOAdapter


@dataclass
class DebugFlags:
    show_class_calls: bool = False
    show_raw_model_output: bool = True
    show_extracted_command: bool = True
    show_memory: bool = False


@dataclass
class ProcessConfig:
    control_llm_key: str
    auto_fold_keep_last_events: int = 30


class Process:
    def __init__(
        self,
        cfg: ProcessConfig,
        mem: Memory,
        router: LLMRouter,
        registry: CommandRegistry,
        io: Optional[IOAdapter] = None,
        debug: DebugFlags = DebugFlags(),
    ):
        self.cfg = cfg
        self.mem = mem
        self.router = router
        self.registry = registry
        self.io = io
        self.debug = debug

        self.folder = Folder(keep_last_events=cfg.auto_fold_keep_last_events)

        self.normalizer = Normalizer(NormalizeConfig(strip_thoughts_only_if_prefix=True))
        self.validator = CommandValidator(ValidateConfig(mode="extract_anywhere"))
        self.parser = CommandParser()

        self.prompt_builder = PromptBuilder(
            PromptConfig(),
            registry=self.registry,
            validator_help=self.validator.format_help_prompt(),
        )

    def handle_user_message(self, text: str) -> None:
        self.mem.add_event("user", text, kind="msg")

    def run_once(self) -> None:
        # fold if needed
        self.folder.auto_fold_if_needed(self.mem)

        if self.debug.show_memory:
            print(self.mem.to_text())

        # build prompt and call LLM
        messages = self.prompt_builder.build_messages(self.mem)
        llm = self.router.get(self.cfg.control_llm_key)

        if self.debug.show_class_calls:
            print("[CALL] LLMClient.chat")

        raw = llm.chat(messages)

        if self.debug.show_raw_model_output:
            print("\n--- RAW MODEL OUTPUT ---\n")
            print(raw)
            print("\n------------------------\n")

        # normalize (strip thoughts only if prefix)
        norm = self.normalizer.normalize(raw)

        # validate command block
        ok, block = self.validator.extract_command_block(norm)
        if not ok or not block:
            # normal assistant text
            text = norm.strip()
            if text:
                self.mem.add_event("assistant", text, kind="msg")
                if self.io:
                    self.io.show(text)
            return

        if self.debug.show_extracted_command:
            print("\n--- EXTRACTED COMMAND BLOCK ---\n")
            print(block)
            print("\n------------------------------\n")

        # parse command
        try:
            parsed = self.parser.parse(block)
        except CommandParseError as e:
            err = f"Command parse error: {e}"
            self.mem.add_event("assistant", err, kind="note")
            if self.io:
                self.io.show(err)
            return

        # dispatch
        try:
            cmd = self.registry.get(parsed.name)
        except KeyError:
            err = f"Unknown command: {parsed.name}"
            self.mem.add_event("assistant", err, kind="note")
            if self.io:
                self.io.show(err)
            return

        ctx = CommandContext(io=self.io, llms=self.router.llms)
        self.mem = cmd.run(self.mem, parsed.args, ctx)
