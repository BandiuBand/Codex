# Command ID: COPY
#
# Purpose:
#   Copy a substring from the *VISIBLE* memory text into the clipboard buffer.
#   Clipboard is ALWAYS overwritten.
#
# Expected command block (KV inside <CMD>...</CMD>):
#   <CMD>
#   id: COPY
#   start: <<<BEGIN>>>
#   end: <<<END>>>
#   </CMD>
#
# Notes:
# - "start" and "end" are exact sequences (may include newlines).
# - The copied text is BETWEEN them (exclusive).
# - We search only in the text that the model can see (rendered memory).
#
# This file is intentionally dependency-light. It tries to work with different
# Memory implementations by using a small set of optional hooks.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple
from datetime import datetime, timezone

from ring_llm_project.commands.base import CommandContext
from ring_llm_project.commands.kv import parse_kv_payload
from ring_llm_project.core.memory import Memory


class CommandError(RuntimeError):
    """Raised when a command cannot be executed due to invalid args or missing text."""


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_between(haystack: str, start: str, end: str) -> Tuple[str, int, int]:
    """
    Returns (extracted, start_index, end_index_exclusive_of_end_marker_region)
    Where extracted is haystack[i+len(start) : j]
    """
    i = haystack.find(start)
    if i < 0:
        raise CommandError("COPY: start marker not found in visible text.")
    j = haystack.find(end, i + len(start))
    if j < 0:
        raise CommandError("COPY: end marker not found in visible text (after start).")
    if j < i + len(start):
        raise CommandError("COPY: invalid marker order.")
    return haystack[i + len(start) : j], i, j


def _get_visible_text(memory: Any) -> str:
    """
    Best-effort: returns the same text that was (or will be) shown to the LLM.
    Prefer a cached 'last_prompt_text' if present, otherwise render current memory.
    """
    # 1) If Process/LLMClient cached the exact prompt memory snapshot:
    t = getattr(memory, "last_prompt_text", None)
    if isinstance(t, str) and t.strip():
        return t

    # 2) Common renderer names:
    for name in ("render_for_model", "render_for_llm", "to_llm_text", "to_text"):
        fn = getattr(memory, name, None)
        if callable(fn):
            try:
                # Some implementations accept include_end_marker / flags
                return fn(include_end_marker=False)  # type: ignore[arg-type]
            except TypeError:
                return fn()
            except Exception:
                pass

    # 3) Fallback:
    return str(memory)


def _clipboard_overwrite(memory: Any, content: str, meta: Dict[str, Any]) -> None:
    """
    Best-effort write into memory clipboard.
    Supported hooks (any of them):
      - memory.set_clipboard(text, meta=?)
      - memory.clipboard_set(text, meta=?)
      - memory.clipboard (attribute) or memory.buffers['clipboard']
    """
    # Prefer explicit method
    for name in ("set_clipboard", "clipboard_set", "write_clipboard"):
        fn = getattr(memory, name, None)
        if callable(fn):
            try:
                fn(content, meta=meta)
            except TypeError:
                fn(content, meta)
            return

    # Dict-based buffers
    buffers = getattr(memory, "buffers", None)
    if isinstance(buffers, dict):
        buffers["clipboard"] = {"text": content, "meta": meta}
        return

    # Plain attribute
    setattr(memory, "clipboard", {"text": content, "meta": meta})


def _record_event(memory: Any, event: Dict[str, Any]) -> None:
    """
    Optional: append event to memory history/log if supported.
    """
    for name in ("add_event", "append_event", "log_event"):
        fn = getattr(memory, name, None)
        if callable(fn):
            try:
                fn(event)
            except Exception:
                pass
            return

    # Or fallback to list attribute
    hist = getattr(memory, "history", None)
    if isinstance(hist, list):
        hist.append(event)


@dataclass(frozen=True)
class CopyCommand:
    """
    Command COPY: copies text between markers from VISIBLE memory text into clipboard.
    """
    name: str = "COPY"
    command_id: str = "COPY"

    def prompt_fragment(self) -> str:
        return (
            "Command COPY: copy text between two markers into clipboard (overwrite).\n"
            "Usage:\n"
            "<CMD>\n"
            "COPY\n"
            "start: <start_marker>\n"
            "end: <end_marker>\n"
            "</CMD>\n"
            "Behavior: finds first 'start', then first 'end' after it, copies text between them (exclusive)."
        )

    def prompt_help(self) -> str:
        return self.prompt_fragment()

    def run(self, mem: Memory, args: Dict[str, str], ctx: CommandContext) -> Memory:
        try:
            parsed = parse_kv_payload(args)
        except ValueError as exc:
            raise CommandError(f"COPY: {exc}") from exc
        return self.execute(mem, parsed)

    def execute(self, memory: Any, args: Dict[str, Any]) -> Any:
        """
        Args:
          memory: Memory object
          args: parsed KV from <CMD> block (must include 'start' and 'end')
        Returns:
          modified memory (same instance if memory is mutable)
        """
        start = args.get("start")
        end = args.get("end")

        if not isinstance(start, str) or start == "":
            raise CommandError("COPY: missing or invalid 'start' (must be non-empty string).")
        if not isinstance(end, str) or end == "":
            raise CommandError("COPY: missing or invalid 'end' (must be non-empty string).")
        if start == end:
            raise CommandError("COPY: 'start' and 'end' cannot be identical.")

        visible = _get_visible_text(memory)
        extracted, i, j = _extract_between(visible, start, end)

        meta = {
            "ts": _now_utc_iso(),
            "command": "COPY",
            "start_marker_len": len(start),
            "end_marker_len": len(end),
            "match_start_index": i,
            "match_end_index": j,
            "copied_len": len(extracted),
        }

        _clipboard_overwrite(memory, extracted, meta)

        _record_event(memory, {
            "ts": meta["ts"],
            "type": "cmd",
            "id": "COPY",
            "ok": True,
            "copied_len": len(extracted),
        })

        return memory
