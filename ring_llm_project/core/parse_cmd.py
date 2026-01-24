from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
import re


@dataclass(frozen=True)
class ParsedCommand:
    name: str
    args: Dict[str, str]
    raw_block: str


class CommandParseError(Exception):
    pass


class CommandParser:
    """
    Parses:

    <CMD>
    ASK
    payload line1
    payload line2
    </CMD>
    """

    _head = re.compile(r"^\s*<CMD>\s*$")
    _end = re.compile(r"^\s*</CMD>\s*$")

    def parse(self, block: str) -> ParsedCommand:
        lines = block.splitlines()
        if not lines:
            raise CommandParseError("Empty command block")

        # find header line
        name: Optional[str] = None
        i = 0
        while i < len(lines) and not lines[i].strip():
            i += 1
        if i >= len(lines):
            raise CommandParseError("No header line")

        if not self._head.match(lines[i]):
            raise CommandParseError("Invalid <CMD> header")
        i += 1

        if i >= len(lines):
            raise CommandParseError("Missing command name")

        name = lines[i].strip()
        if not name:
            raise CommandParseError("Empty command name")
        i += 1

        payload_lines = []
        while i < len(lines):
            line = lines[i].rstrip("\n")
            if self._end.match(line):
                break
            payload_lines.append(lines[i])
            i += 1

        if i >= len(lines) or not self._end.match(lines[i]):
            raise CommandParseError("Missing </CMD>")

        payload = "\n".join(payload_lines).rstrip()
        args: Dict[str, str] = {"payload": payload}
        return ParsedCommand(name=name, args=args, raw_block=block)
