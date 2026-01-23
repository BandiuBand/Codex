# -*- coding: utf-8 -*-
from __future__ import annotations

import re


def normalize_newlines(s: str) -> str:
    if s is None:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    return s


def strip_surrounding_whitespace_lines(s: str) -> str:
    s = normalize_newlines(s)
    # keep internal newlines, remove leading/trailing empty lines
    return s.strip("\n").strip()


_THINK_BLOCKS = [
    re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE),
    re.compile(r"```thinking.*?```", re.DOTALL | re.IGNORECASE),
    re.compile(r"```thought.*?```", re.DOTALL | re.IGNORECASE),
    re.compile(r"```reasoning.*?```", re.DOTALL | re.IGNORECASE),
]


def remove_model_thoughts(s: str) -> str:
    s = normalize_newlines(s)

    for rgx in _THINK_BLOCKS:
        s = rgx.sub("", s)

    # Remove "THOUGHTS:" block until "FINAL:" if present (common pattern)
    # Example:
    # THOUGHTS:
    # ...
    # FINAL:
    # ...
    m = re.search(r"(?is)\bTHOUGHTS\s*:\s*(.*?)\bFINAL\s*:\s*", s)
    if m:
        # keep from FINAL: onward
        idx = m.end()
        s = s[idx:]

    # Also remove leading "Final:" label only
    s = re.sub(r"(?im)^\s*FINAL\s*:\s*", "", s)

    return strip_surrounding_whitespace_lines(s)
