from __future__ import annotations

import json
import re
from typing import Any, Optional, Tuple


def extract_first_json(text: str) -> Tuple[Optional[Any], Optional[str]]:
    raw = text or ""
    fenced_pattern = re.compile(r"```json\s*(.*?)```", re.IGNORECASE | re.DOTALL)
    fenced = fenced_pattern.search(raw)
    if fenced:
        candidate = fenced.group(1).strip()
        try:
            return json.loads(candidate), None
        except Exception as exc:  # noqa: BLE001
            return None, f"failed to parse fenced json: {exc}"

    first_object = _find_first_json_like(raw)
    if first_object:
        try:
            return json.loads(first_object), None
        except Exception as exc:  # noqa: BLE001
            return None, f"failed to parse inline json: {exc}"

    return None, "no valid JSON found"


def _find_first_json_like(text: str) -> Optional[str]:
    start_indexes = [i for i, ch in enumerate(text) if ch in "[{"]
    if not start_indexes:
        return None
    start = min(start_indexes)
    stack = []
    for idx in range(start, len(text)):
        ch = text[idx]
        if ch in "[{":
            stack.append(ch)
        elif ch in "]}":
            if not stack:
                continue
            stack.pop()
            if not stack:
                return text[start : idx + 1]
    return None


__all__ = ["extract_first_json"]
