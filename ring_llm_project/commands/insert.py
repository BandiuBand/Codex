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
class InsertCommand:
    """
    INSERT: insert text into memory between markers.
    If 'text' is omitted, inserts clipboard contents.
    """
    command_id: str = "INSERT"

    def prompt_help(self) -> str:
        return (
            "INSERT — insert text into memory (does not overwrite).\n"
            "Syntax:\n"
            "<CMD>\n"
            "id: INSERT\n"
            "start: <start_marker>\n"
            "end: <end_marker>\n"
            "text: <optional text; if omitted clipboard is used>\n"
            "</CMD>\n"
            "Behavior: finds first start, then first end after it, inserts right after start.\n"
            "Note: service regions (HISTORY/DEBUG/memory_fill markers) are protected."
        )

    def execute(self, memory: Memory, args: Dict[str, Any]) -> Memory:
        start = args.get("start")
        end = args.get("end")
        text_arg = args.get("text")

        if not isinstance(start, str) or not start:
            raise CommandError("INSERT: missing/invalid 'start'")
        if not isinstance(end, str) or not end:
            raise CommandError("INSERT: missing/invalid 'end'")
        if start == end:
            raise CommandError("INSERT: start and end cannot be identical")

        insert_text: Optional[str]
        if isinstance(text_arg, str) and text_arg != "":
            insert_text = text_arg
        else:
            insert_text = memory.clipboard_get()
            if insert_text is None:
                raise CommandError("INSERT: no 'text' provided and clipboard is empty")

        doc = memory.get_document()
        prot = _protected_spans(doc)

        i = doc.find(start)
        if i < 0:
            raise CommandError("INSERT: start marker not found")
        j = doc.find(end, i + len(start))
        if j < 0:
            raise CommandError("INSERT: end marker not found after start")

        pos = i + len(start)

        # insertion point cannot be inside protected spans
        if _overlaps_any(pos, pos + 1, prot):
            raise CommandError("INSERT: insertion point is inside protected (service) region")

        new_doc = doc[:pos] + insert_text + doc[pos:]
        memory.set_document(new_doc)

        memory.add_event({
            "ts": _now_utc_iso(),
            "type": "cmd",
            "id": "INSERT",
            "ok": True,
            "inserted_len": len(insert_text),
        })
        return memory
