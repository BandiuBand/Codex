from __future__ import annotations

import json
import re
from typing import Any, Optional, Tuple


def extract_json_from_text(text: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Attempt to extract a JSON structure (dict or list) from an LLM response body.

    The strategy is intentionally permissive and tries multiple patterns:
      1) Treat the entire text as JSON.
      2) Look for a fenced ```json ... ``` block (case-insensitive) and parse its body.
      3) Look for any fenced ``` ... ``` block and parse its body.
      4) As a last resort, take the first balanced {...} block found in the text.

    Returns a tuple of (parsed, error):
      - parsed: the deserialized object when parsing succeeds; otherwise None
      - error: None on success, or a short human-readable error description
    """

    raw = text.strip()

    # 1) Try the whole text
    try:
        return json.loads(raw), None
    except Exception:
        pass

    # 2) Fenced ```json ... ``` block
    pattern_json = re.compile(r"```json\s*(.*?)```", re.IGNORECASE | re.DOTALL)
    match = pattern_json.search(text)
    if match:
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate), None
        except Exception:
            # fall through to the next strategy
            pass

    # 2b) Any fenced block ``` ... ```
    pattern_any = re.compile(r"```\s*(.*?)```", re.DOTALL)
    match = pattern_any.search(text)
    if match:
        candidate = match.group(1).strip()
        try:
            return json.loads(candidate), None
        except Exception:
            pass

    # 3) First balanced {...} block
    start = text.find("{")
    if start != -1:
        level = 0
        end: Optional[int] = None
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                level += 1
            elif ch == "}":
                level -= 1
                if level == 0:
                    end = i
                    break
        if end is not None:
            candidate = text[start : end + 1].strip()
            try:
                return json.loads(candidate), None
            except Exception as exc:
                return None, f"failed to parse candidate JSON block: {exc}"

    return None, "no valid JSON found in LLM output"
