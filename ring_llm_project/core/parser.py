# -*- coding: utf-8 -*-
from __future__ import annotations

import shlex
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class ParsedCommand:
    name: str
    args: Dict[str, str]
    raw: str


class CommandParser:
    """
    Robust parser: NEVER raises "No closing quotation".
    Accepts:
      - "CMD ASK wait=0 text=\"...\""
      - "ASK wait=0 text=..." (we still accept if validator already extracted)
    """

    def parse(self, raw: str) -> Optional[ParsedCommand]:
        raw = (raw or "").strip()
        if not raw:
            return None

        tokens = self._safe_split(raw)
        if not tokens:
            return None

        # allow optional leading CMD
        if tokens[0].upper() == "CMD":
            tokens = tokens[1:]
            if not tokens:
                return None

        name = tokens[0].upper()
        args: Dict[str, str] = {}

        for t in tokens[1:]:
            if "=" in t:
                k, v = t.split("=", 1)
                args[k.strip()] = v
            else:
                # positional fallback
                args.setdefault("_pos", "")
                args["_pos"] = (args["_pos"] + " " + t).strip()

        return ParsedCommand(name=name, args=args, raw=raw)

    def _safe_split(self, raw: str) -> List[str]:
        # 1) try normal shlex
        try:
            return shlex.split(raw)
        except ValueError:
            pass

        # 2) try to "balance" quotes by appending a closing quote at the end
        fixed = raw
        if fixed.count('"') % 2 == 1:
            fixed += '"'
        if fixed.count("'") % 2 == 1:
            fixed += "'"

        try:
            return shlex.split(fixed)
        except ValueError:
            pass

        # 3) last resort: whitespace split (never fails)
        return fixed.split()
