# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class FoldedItem:
    fold_id: int
    section: str
    summary: str
    original: str
    created_ts: float = field(default_factory=lambda: time.time())
