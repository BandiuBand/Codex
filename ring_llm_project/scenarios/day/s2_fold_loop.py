# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass

from core.dispatcher import CommandDispatcher
from core.llm_client import LLMClient
from core.memory import Memory
from core.normalizer import NormalizeConfig, strip_leading_thoughts
from core.parser import parse_command_block
from core.step_loop import Step
from core.types import DispatchResult, ExecutionContext
from core.validator import CommandValidator


@dataclass
class S2FoldLoopStep(Step):
    """Iteratively folds noisy/long parts of BODY until the model responds with LOOP DONE."""

    dispatcher: CommandDispatcher
    llm: LLMClient
    normalize_cfg: NormalizeConfig = NormalizeConfig()
    max_body_chars: int = 6000  # just to keep prompts bounded

    def execute(self, memory: Memory, ctx: ExecutionContext) -> DispatchResult:
        body = memory.body_text()
        if len(body) > self.max_body_chars:
            body_view = body[-self.max_body_chars:]
        else:
            body_view = body

        cmd_help = self.dispatcher.registry.prompt_help_all()

        prompt = (
            "You are a memory manager. You see ONLY the BODY of memory. "
            "Your job is to reduce noise/length by folding chunks into folds.\n\n"
            "Rules:\n"
            "- Output MUST be exactly one <CMD> block and nothing else.\n"
            "- If folding is helpful, output a FOLD command.\n"
            "- If no more folding is needed, output LOOP DONE.\n"
            "- For FOLD, you must provide START and END substrings that exist in BODY.\n\n"
            "Available commands:\n"
            f"{cmd_help}\n\n"
            "BODY:\n"
            "-----\n"
            f"{body_view}\n"
            "-----\n"
        )

        raw = self.llm.chat([
            {"role": "system", "content": "Return only a <CMD> block."},
            {"role": "user", "content": prompt},
        ])
        cleaned = strip_leading_thoughts(raw, self.normalize_cfg)

        validator = CommandValidator(strict=True)
        v = validator.validate(cleaned)
        if not v.ok:
            # keep raw assistant message for debugging, but do not break execution
            memory.add_history(f"[S2_PARSE_ERROR] {v.error}\nRAW:\n{raw}")
            return DispatchResult(memory=memory, output_text=None)

        block = v.cmd_blocks[0]
        call = parse_command_block(block)

        # LOOP DONE should not be logged as a command (invisible loop control)
        if call.name.upper().strip() == "LOOP DONE":
            return self.dispatcher.dispatch(memory, call, ctx)

        # Dispatch and let the command log itself if desired
        return self.dispatcher.dispatch(memory, call, ctx)
