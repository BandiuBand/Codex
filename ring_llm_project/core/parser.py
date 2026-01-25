# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Tuple

from core.types import CommandCall


_KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\- ]{0,40}):\s*$")


@dataclass(frozen=True)
class ParseError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def parse_command_block(cmd_block: str) -> CommandCall:
    """Parse a single <CMD>...</CMD> content (without the tags).

    Expected:
        COMMAND_NAME\n
        KEY1:\n
        <multi-line value>\n
        KEY2:\n
        ...

    The first non-empty line is the command name.
    Everything after is payload_text; additionally we parse KEY: sections into payload dict.
    """
    raw = cmd_block.strip("\n")
    lines = raw.splitlines()
    # command name
    name = ""
    i = 0
    while i < len(lines):
        if lines[i].strip() != "":
            name = lines[i].strip()
            i += 1
            break
        i += 1
    if not name:
        raise ParseError("Empty command block")

    payload_lines = lines[i:]
    payload_text = "\n".join(payload_lines).strip("\n")
    payload = _parse_kv_sections(payload_lines)
    return CommandCall(name=name.upper(), payload_text=payload_text, payload=payload)


def _parse_kv_sections(lines: list[str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    cur_key = None
    cur_buf: list[str] = []

    def flush():
        nonlocal cur_key, cur_buf
        if cur_key is None:
            return
        # Preserve newlines inside value but strip outer blank lines
        value = "\n".join(cur_buf).strip("\n")
        out[cur_key] = value
        cur_key, cur_buf = None, []

    for line in lines:
        m = _KEY_LINE.match(line)
        if m:
            flush()
            cur_key = m.group(1).strip().upper().replace(" ", "_")
            cur_buf = []
        else:
            if cur_key is None:
                # Ignore leading noise before first KEY:
                # (kept in payload_text anyway)
                continue
            cur_buf.append(line)

    flush()
    return out
