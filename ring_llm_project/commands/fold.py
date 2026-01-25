from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from ring_llm_project.commands.base import CommandContext
from ring_llm_project.commands.kv import parse_kv_payload
from ring_llm_project.core.memory import Memory


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

    for open_tag, close_tag in (
        ("[STATE]", "[/STATE]"),
        ("[HISTORY]", "[/HISTORY]"),
        ("[CLIPBOARD]", "[/CLIPBOARD]"),
        ("[DEBUG]", "[/DEBUG]"),
    ):
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
        if a <= y and b >= x:
            return True
    return False


def _memory_body_span(text: str) -> Tuple[int, int]:
    start_marker = "===MEMORY==="
    end_marker = "===END_MEMORY==="
    start_idx = text.find(start_marker)
    if start_idx < 0:
        raise CommandError("FOLD: missing ===MEMORY=== marker")
    end_idx = text.find(end_marker)
    if end_idx < 0:
        raise CommandError("FOLD: missing ===END_MEMORY=== marker")
    if end_idx < start_idx:
        raise CommandError("FOLD: invalid memory marker order")

    _, start_line_end = _line_span(text, start_idx)
    end_line_start, _ = _line_span(text, end_idx)

    if start_line_end > end_line_start:
        raise CommandError("FOLD: invalid memory marker order")

    return start_line_end, end_line_start


def _folded_placeholder(fold_id: str, name: str) -> str:
    return f'<FOLD id="{fold_id}" name="{name}"/>'


def _unfolded_open_exact(fold_id: str, name: str) -> str:
    return f'<FOLD id="{fold_id}" name="{name}">'


def _unfolded_close() -> str:
    return "</FOLD>"


@dataclass(frozen=True)
class FoldCommand:
    name: str = "FOLD"
    command_id: str = "FOLD"

    def prompt_fragment(self) -> str:
        return (
            "Command FOLD: create a new fold or refold an existing unfolded fold.\n"
            "Usage (create new fold by markers; fold_id must not exist):\n"
            "<CMD>\n"
            "FOLD\n"
            "fold_id: <string>\n"
            "name: <short label>\n"
            "start: <start_marker>\n"
            "end: <end_marker>\n"
            "</CMD>\n"
            "Usage (refold an unfolded fold):\n"
            "<CMD>\n"
            "FOLD\n"
            "fold_id: <string>\n"
            "</CMD>\n"
        )

    def prompt_help(self) -> str:
        return self.prompt_fragment()

    def run(self, mem: Memory, args: Dict[str, str], ctx: CommandContext) -> Memory:
        try:
            parsed = parse_kv_payload(args)
        except ValueError as exc:
            raise CommandError(f"FOLD: {exc}") from exc
        return self.execute(mem, parsed)

    def execute(self, memory: Memory, args: Dict[str, Any]) -> Memory:
        fold_id = args.get("fold_id")
        if not isinstance(fold_id, str) or not fold_id.strip():
            raise CommandError("FOLD: missing/invalid 'fold_id'")
        fold_id = fold_id.strip()

        start = args.get("start")
        end = args.get("end")
        name = args.get("name")

        doc = memory.get_document()
        body_start, body_end = _memory_body_span(doc)
        prot = _protected_spans(doc)

        # -------- Mode B: fold-back existing unfolded fold (no markers) --------
        if start is None and end is None:
            fold = memory.fold_get(fold_id)
            if fold.state != "unfolded":
                raise CommandError(f"FOLD: fold '{fold_id}' is not unfolded (cannot fold back)")

            # find unfolded block <FOLD id="..." name="..."> ... </FOLD>
            open_tag = _unfolded_open_exact(fold.fold_id, fold.name)
            pos = doc.find(open_tag)
            if pos < 0:
                # if name changed externally — be strict: require exact match
                raise CommandError("FOLD: unfolded block not found (exact open tag mismatch)")

            content_start = pos + len(open_tag)
            close_pos = doc.find(_unfolded_close(), content_start)
            if close_pos < 0:
                raise CommandError("FOLD: malformed unfolded block (missing </FOLD>)")

            content = doc[content_start:close_pos]

            # protect service areas
            if _overlaps_any(content_start, close_pos, prot):
                raise CommandError("FOLD: target overlaps protected (service) region")
            if (
                pos < body_start
                or close_pos + len(_unfolded_close()) > body_end
            ):
                raise CommandError("FOLD: refold target outside memory body")

            # update stored content (fold object persists)
            memory.fold_update_content(fold_id, content)

            placeholder = _folded_placeholder(fold.fold_id, fold.name)
            new_doc = doc[:pos] + placeholder + doc[close_pos + len(_unfolded_close()):]
            memory.set_document(new_doc)

            memory.fold_set_state(fold_id, "folded")
            fold.mark_access({"ts": _now_utc_iso(), "type": "refold"})
            memory.folds_sync_index_into_document()

            memory.add_event({
                "ts": _now_utc_iso(),
                "type": "cmd",
                "id": "FOLD",
                "ok": True,
                "mode": "refold",
                "fold_id": fold_id,
                "stored_len": len(content),
            })
            return memory

        # -------- Mode A: create new fold by markers --------
        if not (isinstance(start, str) and isinstance(end, str) and start and end):
            raise CommandError("FOLD: for creation mode you must provide valid 'start' and 'end'")
        if not (isinstance(name, str) and name.strip()):
            raise CommandError("FOLD: for creation mode you must provide valid 'name'")

        name = name.strip()

        # create only once
        if fold_id in memory.folds:
            raise CommandError("FOLD: fold_id already exists (creation forbidden). Use fold-back mode instead.")

        i = doc.find(start)
        if i < 0:
            raise CommandError("FOLD: start marker not found")
        j = doc.find(end, i + len(start))
        if j < 0:
            raise CommandError("FOLD: end marker not found after start")

        a = i + len(start)
        b = j
        if a > b:
            raise CommandError("FOLD: invalid marker order")

        if _overlaps_any(i, i + len(start), prot):
            raise CommandError("FOLD: start marker overlaps protected (service) region")
        if _overlaps_any(j, j + len(end), prot):
            raise CommandError("FOLD: end marker overlaps protected (service) region")
        if _overlaps_any(a, b, prot):
            raise CommandError("FOLD: target overlaps protected (service) region")
        if a < body_start or b > body_end:
            raise CommandError("FOLD: target outside memory body")

        content = doc[a:b]
        memory.fold_put(fold_id=fold_id, name=name, content=content)

        placeholder = _folded_placeholder(fold_id, name)
        new_doc = doc[:a] + placeholder + doc[b:]
        memory.set_document(new_doc)

        memory.folds_sync_index_into_document()
        memory.add_event({
            "ts": _now_utc_iso(),
            "type": "cmd",
            "id": "FOLD",
            "ok": True,
            "mode": "create",
            "fold_id": fold_id,
            "name": name,
            "stored_len": len(content),
        })
        return memory
