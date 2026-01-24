from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class CommandFormat:
    """
    Block format (multi-line safe):

    <CMD>
    <NAME>
    payload
    </CMD>
    """
    start: str = "<CMD>"
    end: str = "</CMD>"


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
            "<CMD>\n"
            "<NAME>\n"
            "payload...\n"
            "</CMD>\n"
            "Rules:\n"
            "- The command block must be valid and complete.\n"
            "- The first line after <CMD> is the command name.\n"
            "- Everything after the name (including newlines) is the payload.\n"
            "- Do not use key/value pairs or '|' blocks.\n"
            "- If you are not issuing a command, output normal assistant text with no <CMD> block.\n"
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
