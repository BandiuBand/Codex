# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from utils.text import remove_model_thoughts, normalize_newlines, strip_surrounding_whitespace_lines


@dataclass
class ValidationResult:
    cleaned_text: str
    command_line: Optional[str] = None
    message_text: Optional[str] = None
    reason: str = ""


class OutputValidator:
    def __init__(self, mode: str, cmd_start: str, cmd_end: str, msg_start: str, msg_end: str, require_blocks: bool):
        self.mode = mode
        self.cmd_start = cmd_start
        self.cmd_end = cmd_end
        self.msg_start = msg_start
        self.msg_end = msg_end
        self.require_blocks = require_blocks

    def validate(self, raw: str) -> ValidationResult:
        raw = normalize_newlines(raw)
        cleaned = remove_model_thoughts(raw)

        # 1) Prefer explicit MSG/CMD blocks
        cmd_block = self._extract_block(cleaned, self.cmd_start, self.cmd_end)
        msg_block = self._extract_block(cleaned, self.msg_start, self.msg_end)

        if cmd_block:
            cmd_line = strip_surrounding_whitespace_lines(cmd_block)
            cmd_line = self._first_nonempty_line(cmd_line)
            if cmd_line:
                return ValidationResult(cleaned_text=cleaned, command_line=cmd_line, reason="cmd_block")

        if msg_block:
            msg_text = strip_surrounding_whitespace_lines(msg_block)
            if msg_text:
                return ValidationResult(cleaned_text=cleaned, message_text=msg_text, reason="msg_block")

        # 2) If blocks are required, stop here
        if self.require_blocks:
            # If blocks required and none found, treat as message (safe fallback)
            return ValidationResult(cleaned_text=cleaned, message_text=cleaned, reason="no_blocks_fallback_message")

        # 3) Strict mode: accept only if the entire cleaned output is a single CMD line
        if self.mode == "strict":
            line = self._first_nonempty_line(cleaned)
            if line and line.lstrip().upper().startswith("CMD "):
                # ensure no other meaningful content besides that line
                rest = cleaned.replace(line, "", 1).strip()
                if not rest:
                    return ValidationResult(cleaned_text=cleaned, command_line=line.strip(), reason="strict_cmd_line")
            return ValidationResult(cleaned_text=cleaned, message_text=cleaned, reason="strict_message")

        # 4) Embedded mode: search for first line starting with CMD
        cmd_line = self._find_cmd_line(cleaned)
        if cmd_line:
            return ValidationResult(cleaned_text=cleaned, command_line=cmd_line, reason="embedded_cmd_line")

        return ValidationResult(cleaned_text=cleaned, message_text=cleaned, reason="embedded_message")

    def _extract_block(self, text: str, start: str, end: str) -> Optional[str]:
        # non-greedy block capture
        pattern = re.escape(start) + r"(.*?)" + re.escape(end)
        m = re.search(pattern, text, flags=re.DOTALL)
        if not m:
            return None
        return m.group(1)

    def _find_cmd_line(self, text: str) -> Optional[str]:
        for line in normalize_newlines(text).split("\n"):
            if line.lstrip().upper().startswith("CMD "):
                return line.strip()
        return None

    def _first_nonempty_line(self, text: str) -> Optional[str]:
        for line in normalize_newlines(text).split("\n"):
            if line.strip():
                return line.strip()
        return None
