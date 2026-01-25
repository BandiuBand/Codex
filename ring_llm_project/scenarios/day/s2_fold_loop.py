from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ring_llm_project.commands.base import BaseCommand, CommandContext
from ring_llm_project.commands.registry import CommandRegistry
from ring_llm_project.core.llm_client import LLMClient
from ring_llm_project.core.parse_cmd import CommandParseError, CommandParser
from ring_llm_project.core.router import LLMRouter
from ring_llm_project.core.step import Step
from ring_llm_project.core.types import CommandCall, DispatchResult, ExecutionContext
from ring_llm_project.core.normalize import Normalizer
from ring_llm_project.core.validate import CommandValidator


@dataclass(frozen=True)
class FoldLoopParams:
    llm_key: str = "oss20b"
    max_body_chars: int = 9000
    goal: str = "Keep memory body compact while preserving meaning."
    fold_command_name: str = "FOLD"


class S2FoldLoopStep(Step):
    """
    One fold loop step:
    - If body is short: return LOOP DONE (no LLM call).
    - If body is long: call LLM to output exactly one <CMD>...</CMD>.
    """

    def __init__(
        self,
        router: LLMRouter,
        registry: CommandRegistry,
        normalizer: Normalizer,
        validator: CommandValidator,
        parser: CommandParser,
        params: Optional[FoldLoopParams] = None,
    ) -> None:
        self.router = router
        self.registry = registry
        self.normalizer = normalizer
        self.validator = validator
        self.parser = parser
        self.params = params or FoldLoopParams()

    def execute(self, memory, ctx: Optional[ExecutionContext] = None) -> DispatchResult:
        if isinstance(memory, DispatchResult):
            memory = memory.memory
        elif hasattr(memory, "memory") and not hasattr(memory, "memory_body_text"):
            memory = memory.memory
        body = memory.memory_body_text()

        if len(body) <= self.params.max_body_chars:
            cmd_block = "<CMD>\nLOOP DONE\n</CMD>"
        else:
            prompt = self._build_prompt(body)
            llm: LLMClient = self.router.get(self.params.llm_key)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a command-only controller. Output exactly one <CMD>...</CMD> block."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            raw = llm.chat(messages)
            normalized = self.normalizer.normalize(raw)
            cmd_block = self._extract_single_cmd_block(normalized)

        return self._dispatch_cmd_block(memory, cmd_block)

    def _extract_single_cmd_block(self, text: str) -> str:
        ok, block = self.validator.extract_command_block(text)
        if not ok or not block:
            raise ValueError("S2FoldLoopStep: no <CMD> block found in LLM output.")

        start = self.validator.cfg.fmt.start
        end = self.validator.cfg.fmt.end
        end_idx = text.find(end)
        tail = text[end_idx + len(end):] if end_idx >= 0 else ""
        if start in tail:
            raise ValueError("S2FoldLoopStep: multiple <CMD> blocks found in LLM output.")
        return block

    def _dispatch_cmd_block(self, memory, cmd_block: str) -> DispatchResult:
        try:
            parsed = self.parser.parse(cmd_block)
        except CommandParseError as exc:
            err = f"Command parse error: {exc}"
            memory.add_event("assistant", err, kind="note")
            return DispatchResult(memory=memory, user_output=err, stop_for_user_input=True, debug_note=err)

        try:
            cmd = self.registry.get(parsed.name)
        except KeyError:
            err = f"Unknown command: {parsed.name}"
            memory.add_event("assistant", err, kind="note")
            return DispatchResult(memory=memory, user_output=err, stop_for_user_input=True, debug_note=err)

        if isinstance(cmd, BaseCommand):
            call = CommandCall(raw=parsed.raw_block, name=parsed.name, args=parsed.args)
            return cmd.execute(memory, call, ExecutionContext())

        ctx = CommandContext(io=None, llms=self.router.llms)
        runner = getattr(cmd, "run", None) or getattr(cmd, "execute", None)
        if runner is None:
            raise AttributeError(f"Command {type(cmd).__name__} has neither run() nor execute()")
        result = runner(memory, parsed.args, ctx)
        if isinstance(result, DispatchResult):
            return result
        return DispatchResult(memory=result)

    def _build_prompt(self, body: str) -> str:
        return (
            "Task: compress the MEMORY BODY if it is too long/noisy.\n"
            "Rules:\n"
            "- You can only act using one command inside <CMD>...</CMD>.\n"
            "- You MUST NOT reference service sections (they are not shown to you).\n"
            "- Choose a contiguous span INSIDE the body using exact begin/end substrings that exist in the body.\n"
            "- If no safe fold is possible or folding is not needed, output LOOP DONE.\n"
            "\n"
            "Allowed commands:\n"
            f"1) {self.params.fold_command_name}:\n"
            "<CMD>\n"
            f"{self.params.fold_command_name}\n"
            "fold_id: <string>\n"
            "name: <short label>\n"
            "start: <exact substring that appears in body>\n"
            "end: <exact substring that appears in body after START>\n"
            "</CMD>\n"
            "2) LOOP DONE:\n"
            "<CMD>\n"
            "LOOP DONE\n"
            "</CMD>\n"
            "\n"
            "MEMORY BODY:\n"
            "-----\n"
            f"{body}\n"
            "-----\n"
        )
