# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DispatchResult:
    user_message: Optional[str] = None
    stop_for_user_input: bool = False
    debug: str = ""
