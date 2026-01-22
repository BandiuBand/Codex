# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Tuple

GREEDY_KEYS = {"text", "summary", "value"}

_CMD_RE = re.compile(r"^\s*CMD\s+([A-Z_]+)\s*(.*)\s*$")


def parse_cmd_line(line: str) -> Tuple[str, Dict[str, str]]:
    line = (line or "").strip()
    m = _CMD_RE.match(line)
    if not m:
        raise ValueError("Команда має бути одним рядком і починатись з 'CMD '")

    cmd = m.group(1).strip().upper()
    tail = m.group(2).strip()

    kv: Dict[str, str] = {}
    if not tail:
        return cmd, kv

    i = 0
    n = len(tail)
    while i < n:
        while i < n and tail[i].isspace():
            i += 1
        if i >= n:
            break

        eq = tail.find("=", i)
        if eq == -1:
            raise ValueError("Очікувався формат key=value")
        key = tail[i:eq].strip()
        if not key:
            raise ValueError("Порожній key у key=value")
        i = eq + 1

        if key in GREEDY_KEYS:
            kv[key] = tail[i:].strip()
            break

        j = i
        while j < n and not tail[j].isspace():
            j += 1
        kv[key] = tail[i:j].strip()
        i = j

    return cmd, kv
