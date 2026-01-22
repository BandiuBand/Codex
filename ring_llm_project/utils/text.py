# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from typing import Optional


THINK_XML = re.compile(r"(?is)<think>.*?</think>")
FENCED_THINK = re.compile(r"(?is)```(?:thinking|thoughts|think)\s*.*?```")


def normalize_newlines(s: Optional[str]) -> str:
    if not s:
        return ""
    return s.replace("\r\n", "\n").replace("\r", "\n")


def strip_thoughts(raw: str) -> str:
    """
    Remove common 'thought' formats from raw model output.
    Does NOT destroy newlines.
    """
    s = normalize_newlines(raw)
    s = THINK_XML.sub("", s)
    s = FENCED_THINK.sub("", s)
    return s.strip()


def clamp(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[:n] + "..."


def safe_int(x: str, default: int) -> int:
    try:
        return int(x)
    except Exception:
        return default
