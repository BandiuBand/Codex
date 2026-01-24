from __future__ import annotations

from typing import Dict


def parse_kv_payload(args: Dict[str, str]) -> Dict[str, str]:
    payload = args.get("payload", "")
    parsed: Dict[str, str] = {}
    if payload:
        for raw_line in payload.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            key, sep, value = line.partition(":")
            if not sep:
                raise ValueError(f"Expected 'key: value' line, got: {raw_line}")
            key = key.strip()
            value = value.strip()
            if not key:
                raise ValueError(f"Empty key in line: {raw_line}")
            parsed[key] = value

    for key, value in args.items():
        if key in ("payload", "text"):
            continue
        parsed[key] = value
    return parsed
