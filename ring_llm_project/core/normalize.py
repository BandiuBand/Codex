from __future__ import annotations
import re
from dataclasses import dataclass


_THINK_PATTERNS = [
    # <think> ... </think>
    re.compile(r"^\s*<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE),
    # <analysis> ... </analysis>
    re.compile(r"^\s*<analysis>.*?</analysis>\s*", re.DOTALL | re.IGNORECASE),
    # ```think ... ```
    re.compile(r"^\s*```think\s*.*?```\s*", re.DOTALL | re.IGNORECASE),
    # [THOUGHTS] ... [/THOUGHTS]
    re.compile(r"^\s*\[THOUGHTS\].*?\[/THOUGHTS\]\s*", re.DOTALL | re.IGNORECASE),
]


@dataclass(frozen=True)
class NormalizeConfig:
    strip_thoughts_only_if_prefix: bool = True


class Normalizer:
    def __init__(self, cfg: NormalizeConfig):
        self.cfg = cfg

    def normalize(self, text: str) -> str:
        if not text:
            return ""
        t = text
        if self.cfg.strip_thoughts_only_if_prefix:
            changed = True
            while changed:
                changed = False
                for rx in _THINK_PATTERNS:
                    m = rx.match(t)
                    if m:
                        t = t[m.end():]
                        changed = True
        return t
