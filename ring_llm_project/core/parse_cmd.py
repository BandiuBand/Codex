from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
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

    @CMD ASK
    wait: 0
    text: |
      line1
      line2
    @END
    """

    _head = re.compile(r"^\s*@CMD\s+([A-Za-z0-9_\-]+)\s*$")
    _kv = re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*:\s*(.*)$")

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

        m = self._head.match(lines[i])
        if not m:
            raise CommandParseError("Invalid @CMD header")
        name = m.group(1)
        i += 1

        args: Dict[str, str] = {}
        while i < len(lines):
            line = lines[i].rstrip("\n")
            if line.strip() == "@END":
                break
            if not line.strip():
                i += 1
                continue

            mkv = self._kv.match(line)
            if not mkv:
                raise CommandParseError(f"Bad arg line: {line}")

            key = mkv.group(1)
            val = mkv.group(2)

            if val.strip() == "|":
                # multiline: read subsequent lines until next key or @END
                i += 1
                buf: List[str] = []
                while i < len(lines):
                    if lines[i].strip() == "@END":
                        break
                    # stop multiline if looks like next key: value at same indentation level
                    if self._kv.match(lines[i]) and not lines[i].startswith("  "):
                        break
                    # accept indented or raw lines
                    buf.append(lines[i][2:] if lines[i].startswith("  ") else lines[i])
                    i += 1
                args[key] = "\n".join(buf).rstrip()
                continue
            else:
                args[key] = val.strip()
                i += 1

        if i >= len(lines) or lines[i].strip() != "@END":
            raise CommandParseError("Missing @END")
        return ParsedCommand(name=name, args=args, raw_block=block)
