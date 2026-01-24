from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from core.memory_contract import Memory


class CommandError(RuntimeError):
    pass


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _line_span(text: str, idx: int) -> Tuple[int, int]:
    ls = text.rfind("\n", 0, idx)
    ls = 0 if ls < 0 else ls + 1
    le = text.find("\n", idx)
    le = len(text) if le < 0 else le + 1
    return ls, le


def _find_block_span(text: str, open_tag: str, close_tag: str) -> Optional[Tuple[int, int]]:
    a = text.find(open_tag)
    if a < 0:
        return None
    b = text.find(close_tag, a + len(open_tag))
    if b < 0:
        return None
    return a, b + len(close_tag)


def _protected_spans(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []

    for marker in ("===MEMORY===", "===END_MEMORY==="):
        i = text.find(marker)
        if i >= 0:
            spans.append(_line_span(text, i))

    i = text.find("memory_fill=")
    if i >= 0:
        spans.append(_line_span(text, i))

    for open_tag, close_tag in (("[HISTORY]", "[/HISTORY]"), ("[DEBUG]", "[/DEBUG]")):
        sp = _find_block_span(text, open_tag, close_tag)
        if sp:
            spans.append(sp)

    spans.sort()
    merged: List[Tuple[int, int]] = []
    for a, b in spans:
        if not merged or a > merged[-1][1]:
            merged.append((a, b))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
    return merged


def _overlaps_any(a: int, b: int, spans: List[Tuple[int, int]]) -> bool:
    for x, y in spans:
        if a < y and b > x:
            return True
    return False


@dataclass(frozen=True)
class DeleteCommand:
    """
    DELETE: delete text between markers (exclusive).
    Protected service regions cannot be modified.
    """
    command_id: str = "DELETE"

    def prompt_help(self) -> str:
        return (
            "DELETE — delete text between two markers (exclusive). Markers stay.\n"
            "Syntax:\n"
            "<CMD>\n"
            "id: DELETE\n"
            "start: <start_marker>\n"
            "end: <end_marker>\n"
            "</CMD>\n"
            "Note: service regions (HISTORY/DEBUG/memory_fill markers) are protected."
        )

    def execute(self, memory: Memory, args: Dict[str, Any]) -> Memory:
        start = args.get("start")
        end = args.get("end")

        if not isinstance(start, str) or not start:
            raise CommandError("DELETE: missing/invalid 'start'")
        if not isinstance(end, str) or not end:
            raise CommandError("DELETE: missing/invalid 'end'")
        if start == end:
            raise CommandError("DELETE: start and end cannot be identical")

        doc = memory.get_document()
        prot = _protected_spans(doc)

        i = doc.find(start)
        if i < 0:
            raise CommandError("DELETE: start marker not found")
        j = doc.find(end, i + len(start))
        if j < 0:
            raise CommandError("DELETE: end marker not found after start")

        a = i + len(start)
        b = j
        if a > b:
            raise CommandError("DELETE: invalid marker order")

        if _overlaps_any(a, b, prot):
            raise CommandError("DELETE: target overlaps protected (service) region")

        new_doc = doc[:a] + doc[b:]
        memory.set_document(new_doc)

        memory.add_event({
            "ts": _now_utc_iso(),
            "type": "cmd",
            "id": "DELETE",
            "ok": True,
            "deleted_len": (b - a),
        })
        return memory
