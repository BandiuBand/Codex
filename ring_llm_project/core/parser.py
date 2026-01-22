# -*- coding: utf-8 -*-
from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Dict


@dataclass
class ParsedCommand:
    name: str
    args: Dict[str, str]
    raw: str


class CommandParser:
    """
    Parses:
      CMD ASK wait=0 text="Hello world"
      CMD SETVAR key=ripple value="50mV"
    Uses shlex so quotes work.
    """

    def parse(self, cmd_line: str) -> ParsedCommand:
        raw = cmd_line.strip()
        if not raw.startswith("CMD "):
            raise ValueError("command_line_missing_CMD_prefix")

        tokens = shlex.split(raw)
        # tokens like: ["CMD", "ASK", "wait=0", "text=Hello"]
        if len(tokens) < 2:
            raise ValueError("command_line_too_short")

        name = tokens[1].strip().upper()
        args: Dict[str, str] = {}

        for tok in tokens[2:]:
            if "=" not in tok:
                # allow bare tokens by mapping to special key
                args.setdefault("_", "")
                args["_"] = (args["_"] + " " + tok).strip()
                continue
            k, v = tok.split("=", 1)
            args[k.strip()] = v.strip()

        return ParsedCommand(name=name, args=args, raw=raw)
