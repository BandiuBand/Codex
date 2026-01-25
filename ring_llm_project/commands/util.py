# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class PayloadError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def need(payload: Dict[str, str], key: str) -> str:
    if key not in payload:
        raise PayloadError(f"Missing field: {key}")
    val = payload[key]
    if val is None:
        raise PayloadError(f"Empty field: {key}")
    return val


def opt(payload: Dict[str, str], key: str, default: str = "") -> str:
    v = payload.get(key, default)
    return v if v is not None else default
