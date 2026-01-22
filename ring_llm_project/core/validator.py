# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional

from config import ValidationMode
from utils.text import strip_thoughts


CMD_LINE = re.compile(r"(?m)^\s*CMD\s+[A-Z_]+(?:\s+.*)?\s*$")


@dataclass
class ValidationResult:
    ok: bool
    command_line: Optional[str] = None
    error: Optional[str] = None
    cleaned_text: Optional[str] = None


class SyntaxValidator:
    def __init__(self, allowed_commands: Dict[str, object], mode: ValidationMode):
        self.allowed = set(allowed_commands.keys())
        self.mode = mode

    def validate(self, raw_output: str) -> ValidationResult:
        cleaned = strip_thoughts(raw_output)

        if self.mode == ValidationMode.STRICT_CMD_ONLY:
            if not cleaned:
                return ValidationResult(
                    False, error="empty_output_after_thought_strip", cleaned_text=cleaned
                )
            # must be exactly one CMD line
            lines = [ln.strip() for ln in cleaned.split("\n") if ln.strip()]
            if len(lines) != 1:
                return ValidationResult(
                    False, error="strict_mode_requires_single_line", cleaned_text=cleaned
                )
            line = lines[0]
            if not line.startswith("CMD "):
                return ValidationResult(
                    False, error="strict_mode_missing_CMD_prefix", cleaned_text=cleaned
                )
            if not self._command_name_allowed(line):
                return ValidationResult(False, error="unknown_command", cleaned_text=cleaned)
            return ValidationResult(True, command_line=line, cleaned_text=cleaned)

        # EXTRACT_FROM_TEXT
        matches = CMD_LINE.findall(cleaned)
        if not matches:
            return ValidationResult(False, error="no_CMD_line_found", cleaned_text=cleaned)
        line = matches[-1].strip()
        if not self._command_name_allowed(line):
            return ValidationResult(False, error="unknown_command", cleaned_text=cleaned)
        return ValidationResult(True, command_line=line, cleaned_text=cleaned)

    def _command_name_allowed(self, cmd_line: str) -> bool:
        # cmd line: "CMD NAME ..."
        parts = cmd_line.strip().split(None, 2)
        if len(parts) < 2:
            return False
        name = parts[1].strip().upper()
        return name in self.allowed
