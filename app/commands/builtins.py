# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Dict

from .base import Command, CommandResult
from ..fold import FoldedItem
from ..memory import Memory, safe_one_line
from ..io_adapter import IOAdapter


class FoldReplyCommand(Command):
    name = "FOLD_REPLY"

    def run(self, mem: Memory, kv: Dict[str, str], io: IOAdapter) -> CommandResult:
        if not mem.inbox:
            raise ValueError("Немає INBOX reply для FOLD_REPLY.")

        rid_s = kv.get("id", "").strip()
        var = kv.get("var", "").strip()
        value = kv.get("value", "").strip()

        if not rid_s.isdigit():
            raise ValueError("FOLD_REPLY вимагає id=<reply_id> (число).")
        rid = int(rid_s)
        if not var:
            raise ValueError("FOLD_REPLY вимагає var=<name>.")
        if value == "":
            raise ValueError("FOLD_REPLY вимагає value=<...>.")

        # pending binding: якщо чекаємо var — треба саме її
        if mem.pending_var and var != mem.pending_var:
            raise ValueError(f"FOLD_REPLY має використовувати pending var={mem.pending_var}, отримано var={var}")

        reply_text = mem.pop_reply_by_id(rid)
        if reply_text is None:
            raise ValueError(f"INBOX не містить reply id={rid}")

        mem.vars[var] = value

        mem.pending_var = ""
        mem.pending_question = ""

        mem.add_history(f"CMD FOLD_REPLY id={rid} var={var} value={value}")
        mem.add_history(f"FOLDED_FROM_REPLY id={rid} text={safe_one_line(reply_text)}")

        return CommandResult(memory=mem)


class AskCommand(Command):
    name = "ASK"

    def run(self, mem: Memory, kv: Dict[str, str], io: IOAdapter) -> CommandResult:
        wait = kv.get("wait", "").strip()
        var = kv.get("var", "").strip()
        text = kv.get("text", "").strip()

        if wait != "1":
            raise ValueError("ASK: wait має бути 1")
        if not var:
            raise ValueError("ASK: потрібен var=<name>")
        if not text:
            raise ValueError("ASK: потрібен text=<question>")

        if mem.pending_var:
            raise ValueError(f"Вже очікуємо відповідь по var={mem.pending_var}, не можна робити ASK")

        mem.pending_var = var
        mem.pending_question = text
        mem.add_history(f"CMD ASK var={var} wait=1 text={text}")

        # blocking: питаємо користувача тут і кладемо в inbox
        user_reply = io.ask_user(text)
        rid = mem.push_reply(user_reply)

        return CommandResult(memory=mem)


class SetCurrentCommand(Command):
    name = "SET_CURRENT"

    def run(self, mem: Memory, kv: Dict[str, str], io: IOAdapter) -> CommandResult:
        text = kv.get("text", "").strip()
        if not text:
            raise ValueError("SET_CURRENT вимагає text=<...>")
        mem.current_step = text
        mem.add_history(f"CMD SET_CURRENT text={text}")
        return CommandResult(memory=mem)


class AppendPlanCommand(Command):
    name = "APPEND_PLAN"

    def run(self, mem: Memory, kv: Dict[str, str], io: IOAdapter) -> CommandResult:
        text = kv.get("text", "").strip()
        if not text:
            raise ValueError("APPEND_PLAN вимагає text=<...>")
        mem.plan_items.append(text)
        mem.add_history(f"CMD APPEND_PLAN text={text}")
        return CommandResult(memory=mem)


class RewritePlanCommand(Command):
    name = "REWRITE_PLAN"

    def run(self, mem: Memory, kv: Dict[str, str], io: IOAdapter) -> CommandResult:
        text = kv.get("text", "").strip()
        if not text:
            raise ValueError("REWRITE_PLAN вимагає text=<...>")
        mem.plan_items = [text]
        mem.current_step = ""
        mem.add_history(f"CMD REWRITE_PLAN text={text}")
        return CommandResult(memory=mem)


class FoldSectionCommand(Command):
    name = "FOLD_SECTION"

    def run(self, mem: Memory, kv: Dict[str, str], io: IOAdapter) -> CommandResult:
        section = kv.get("section", "").strip().upper()
        summary = kv.get("summary", "").strip()
        if not section or not summary:
            raise ValueError("FOLD_SECTION вимагає section=<name> summary=<...>")

        original = ""
        fid = mem.next_fold_id
        mem.next_fold_id += 1

        if section == "HISTORY":
            original = "\n".join(mem.history)
            mem.history = [f"(folded id={fid}) {summary}"]
        elif section == "DEBUG":
            original = "\n".join(mem.debug)
            mem.debug = [f"(folded id={fid}) {summary}"]
        elif section == "PLAN":
            original = "\n".join(mem.plan_items) + (("\nCURRENT: " + mem.current_step) if mem.current_step else "")
            mem.plan_items = [f"(folded id={fid}) {summary}"]
            mem.current_step = ""
        else:
            raise ValueError("Дозволено fold тільки для section=HISTORY|DEBUG|PLAN у цій реалізації.")

        mem.folded[fid] = FoldedItem(
            fold_id=fid,
            section=section,
            summary=summary,
            original=original,
        )
        mem.add_history(f"CMD FOLD_SECTION section={section} summary={summary}")
        return CommandResult(memory=mem)


class DeleteSectionCommand(Command):
    name = "DELETE_SECTION"

    def run(self, mem: Memory, kv: Dict[str, str], io: IOAdapter) -> CommandResult:
        section = kv.get("section", "").strip().upper()
        if not section:
            raise ValueError("DELETE_SECTION вимагає section=<name>")

        if section == "HISTORY":
            mem.history.clear()
        elif section == "DEBUG":
            mem.debug.clear()
        elif section == "INBOX":
            mem.inbox.clear()
        elif section == "PLAN":
            mem.plan_items.clear()
            mem.current_step = ""
        elif section == "VARS":
            mem.vars.clear()
        elif section == "FOLDED":
            mem.folded.clear()
        elif section == "PENDING":
            mem.pending_var = ""
            mem.pending_question = ""
        else:
            raise ValueError("Невідомий section для DELETE_SECTION.")

        mem.add_history(f"CMD DELETE_SECTION section={section}")
        return CommandResult(memory=mem)


class UnfoldCommand(Command):
    name = "UNFOLD"

    def run(self, mem: Memory, kv: Dict[str, str], io: IOAdapter) -> CommandResult:
        fid_s = kv.get("id", "").strip()
        if not fid_s.isdigit():
            raise ValueError("UNFOLD вимагає id=<folded_id> (число)")
        fid = int(fid_s)
        if fid not in mem.folded:
            raise ValueError(f"Немає folded id={fid}")

        it = mem.folded.pop(fid)
        lines = [x for x in (it.original or "").split("\n") if x.strip()]

        if it.section == "HISTORY":
            mem.history = lines
        elif it.section == "DEBUG":
            mem.debug = lines
        elif it.section == "PLAN":
            cur = ""
            plan = []
            for ln in lines:
                if ln.startswith("CURRENT:"):
                    cur = ln[len("CURRENT:"):].strip()
                else:
                    plan.append(ln)
            mem.plan_items = plan
            mem.current_step = cur
        else:
            raise ValueError("UNFOLD: невідома секція у folded item")

        mem.add_history(f"CMD UNFOLD id={fid}")
        return CommandResult(memory=mem)
