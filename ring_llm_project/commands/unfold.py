from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from core.memory_contract import Memory


class CommandError(RuntimeError):
    pass


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _placeholder_exact(fold_id: str, name: str) -> str:
    # canonical folded form
    return f'<FOLD id="{fold_id}" name="{name}"/>'


def _block_open(fold_id: str, name: str) -> str:
    return f'<FOLD id="{fold_id}" name="{name}">'


def _block_close() -> str:
    return "</FOLD>"


@dataclass(frozen=True)
class UnfoldCommand:
    command_id: str = "UNFOLD"

    def prompt_help(self) -> str:
        return (
            "UNFOLD — expands an existing fold into inline block form.\n"
            "Syntax:\n"
            "<CMD>\n"
            "id: UNFOLD\n"
            "fold_id: <string>\n"
            "</CMD>\n"
            "Effect: replaces <FOLD id=\"...\" name=\"...\"/> with "
            "<FOLD id=\"...\" name=\"...\"> ... </FOLD>.\n"
        )

    def execute(self, memory: Memory, args: Dict[str, Any]) -> Memory:
        fold_id = args.get("fold_id")
        if not isinstance(fold_id, str) or not fold_id.strip():
            raise CommandError("UNFOLD: missing/invalid 'fold_id'")
        fold_id = fold_id.strip()

        fold = memory.fold_get(fold_id)
        if fold.state != "folded":
            raise CommandError(f"UNFOLD: fold '{fold_id}' is not folded")

        doc = memory.get_document()

        placeholder = _placeholder_exact(fold.fold_id, fold.name)
        pos = doc.find(placeholder)
        if pos < 0:
            raise CommandError("UNFOLD: folded placeholder not found in document")

        block = _block_open(fold.fold_id, fold.name) + fold.content + _block_close()
        new_doc = doc[:pos] + block + doc[pos + len(placeholder):]
        memory.set_document(new_doc)

        memory.fold_set_state(fold_id, "unfolded")
        fold.mark_access({"ts": _now_utc_iso(), "type": "unfold"})

        memory.folds_sync_index_into_document()

        memory.add_event({
            "ts": _now_utc_iso(),
            "type": "cmd",
            "id": "UNFOLD",
            "ok": True,
            "fold_id": fold_id,
        })
        return memory
