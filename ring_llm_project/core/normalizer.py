# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class NormalizeConfig:
    think_open: str = "<THINK>"
    think_close: str = "</THINK>"

    # Also strip these if they appear at the very start (case-insensitive)
    alt_think_pairs: tuple[tuple[str, str], ...] = (
        ("<think>", "</think>"),
        ("<analysis>", "</analysis>"),
        ("<thinking>", "</thinking>"),
    )


def strip_leading_thoughts(text: str, cfg: Optional[NormalizeConfig] = None) -> str:
    """Remove a leading "thoughts" block **only if it starts the answer**.

    If the tags appear later, we keep them (they may be part of the intended output).
    """
    if cfg is None:
        cfg = NormalizeConfig()

    s = text.lstrip()
    # Try main pair first, then alternates.
    pairs = ((cfg.think_open, cfg.think_close),) + cfg.alt_think_pairs

    for open_tag, close_tag in pairs:
        # Case-insensitive at the beginning.
        if s[: len(open_tag)].lower() == open_tag.lower():
            end_idx = s.lower().find(close_tag.lower(), len(open_tag))
            if end_idx != -1:
                s = s[end_idx + len(close_tag) :]
                return s.lstrip("\n\r\t ")

    # Also handle "```think" style leading blocks.
    m = re.match(r"^```\s*think\s*\n", s, flags=re.IGNORECASE)
    if m:
        end = re.search(r"\n```\s*\n?", s[m.end() :], flags=re.IGNORECASE)
        if end:
            s = s[m.end() + end.end() :]
            return s.lstrip("\n\r\t ")

    return text
