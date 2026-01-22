# -*- coding: utf-8 -*-
from __future__ import annotations

from utils.text import clamp


def to_one_line_for_log(s: str, limit: int = 500) -> str:
    """
    ONLY for logs. Never use for parsing.
    """
    s = (s or "").replace("\n", "\\n")
    return clamp(s, limit)
