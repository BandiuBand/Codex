# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

from .config import SyntaxMode


_CMD_LINE_RE = re.compile(r"^\s*CMD\s+[A-Z_]+(?:\s+.*)?\s*$")
_CMD_ANY_RE = re.compile(r"(?m)^\s*CMD\s+[A-Z_]+(?:\s+.*)?\s*$")


@dataclass
class SyntaxValidator:
    mode: SyntaxMode = "strict_line"

    def clean_and_extract(self, raw: str) -> Tuple[bool, str, str]:
        """
        Повертає:
          (ok, cmd_line, reason_if_not_ok)
        """
        raw = (raw or "").strip()

        # Забороняємо backslash в відповіді (це системне правило)
        if "\\" in raw:
            return False, "", "Знайдено заборонений символ backslash у відповіді."

        if self.mode == "strict_line":
            # приймаємо тільки якщо весь вивід = одна команда
            if "\n" in raw or "\r" in raw:
                return False, "", "Strict mode: вивід має бути одним рядком."
            if not _CMD_LINE_RE.match(raw):
                return False, "", "Strict mode: рядок не є командою CMD."
            return True, raw.strip(), ""

        # extract modes: шукаємо командні рядки в багаторядковому тексті
        matches = _CMD_ANY_RE.findall(raw)
        if not matches:
            return False, "", "Не знайдено жодного рядка CMD у тексті."

        if self.mode == "extract_first_cmd":
            return True, matches[0].strip(), ""

        if self.mode == "extract_last_cmd":
            return True, matches[-1].strip(), ""

        return False, "", f"Невідомий режим syntax validator: {self.mode}"
