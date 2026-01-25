# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple


CMD_OPEN = "<CMD>"
CMD_CLOSE = "</CMD>"


@dataclass(frozen=True)
class CommandValidationResult:
    ok: bool
    error: Optional[str]
    cmd_blocks: List[str]


class CommandValidator:
    """Extracts <CMD> blocks and validates whether the assistant response is a command.

    Modes:
      - strict: after stripping whitespace, the whole response must be exactly one command block
      - mixed: return any <CMD> blocks embedded in text
    """

    def __init__(self, mode: str = "strict"):
        if mode not in ("strict", "mixed"):
            raise ValueError("mode must be 'strict' or 'mixed'")
        self.mode = mode

    def extract_blocks(self, text: str) -> List[str]:
        blocks: List[str] = []
        i = 0
        while True:
            start = text.find(CMD_OPEN, i)
            if start < 0:
                break
            end = text.find(CMD_CLOSE, start + len(CMD_OPEN))
            if end < 0:
                break
            inner = text[start + len(CMD_OPEN) : end]
            blocks.append(inner.strip("\n\r\t "))
            i = end + len(CMD_CLOSE)
        return blocks

    def validate(self, text: str) -> CommandValidationResult:
        blocks = self.extract_blocks(text)
        if not blocks:
            return CommandValidationResult(False, "no_cmd_block", [])

        if self.mode == "strict":
            stripped = text.strip()
            expected = f"{CMD_OPEN}{blocks[0]}{CMD_CLOSE}" if len(blocks) == 1 else None
            # Rebuild a canonical single-block string and compare by removing outer whitespace/newlines
            canonical = f"{CMD_OPEN}\n{blocks[0]}\n{CMD_CLOSE}".strip()
            if len(blocks) != 1:
                return CommandValidationResult(False, "multiple_cmd_blocks_in_strict_mode", blocks)
            if stripped != canonical:
                return CommandValidationResult(False, "non_command_text_in_strict_mode", blocks)

        return CommandValidationResult(True, None, blocks)
