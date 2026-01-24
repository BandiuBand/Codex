from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class CommandFormat:
    """
    Block format (multi-line safe):

    @CMD <NAME>
    key: value
    text: |
      multiline
      payload
    @END
    """
    start: str = "@CMD"
    end: str = "@END"


@dataclass(frozen=True)
class ValidateConfig:
    mode: str = "extract_anywhere"  # "strict_only_command" | "extract_anywhere"
    fmt: CommandFormat = CommandFormat()


class CommandValidator:
    def __init__(self, cfg: ValidateConfig):
        self.cfg = cfg

    def format_help_prompt(self) -> str:
        # This is the English-only prompt chunk for the model.
        # You can extend it later.
        return (
            "When you output a command, use ONLY this block format:\n"
            "@CMD <NAME>\n"
            "key: value\n"
            "text: |\n"
            "  multi-line text...\n"
            "@END\n"
            "Rules:\n"
            "- The command block must be valid and complete.\n"
            "- For multi-line values, use '|' and indent following lines by two spaces.\n"
            "- If you are not issuing a command, output normal assistant text with no @CMD block.\n"
        )

    def extract_command_block(self, text: str) -> Tuple[bool, Optional[str]]:
        if not text:
            return False, None

        s = self.cfg.fmt.start
        e = self.cfg.fmt.end

        if self.cfg.mode == "strict_only_command":
            stripped = text.strip()
            if not stripped.startswith(s) or not stripped.endswith(e):
                return False, None
            return True, stripped

        # extract_anywhere
        idx = text.find(s)
        if idx < 0:
            return False, None
        idx2 = text.find(e, idx)
        if idx2 < 0:
            return False, None
        block = text[idx: idx2 + len(e)]
        return True, block
