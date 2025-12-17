from __future__ import annotations

import ast
from typing import Any, Callable


class _SafeEvaluator(ast.NodeVisitor):
    def __init__(self, resolver: Callable[[str], Any]) -> None:
        self.resolver = resolver

    def visit(self, node: ast.AST) -> Any:  # type: ignore[override]
        method = "visit_" + node.__class__.__name__
        visitor = getattr(self, method, None)
        if visitor is None:
            raise ValueError(f"Unsupported expression node: {node.__class__.__name__}")
        return visitor(node)

    def visit_Expression(self, node: ast.Expression) -> Any:  # noqa: D401
        return self.visit(node.body)

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:  # noqa: D401
        values = [self.visit(v) for v in node.values]
        if isinstance(node.op, ast.And):
            result = True
            for val in values:
                result = bool(result and val)
            return result
        if isinstance(node.op, ast.Or):
            result = False
            for val in values:
                result = bool(result or val)
            return result
        raise ValueError("Unsupported boolean operator")

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:  # noqa: D401
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return not bool(operand)
        raise ValueError("Unsupported unary operator")

    def visit_Compare(self, node: ast.Compare) -> Any:  # noqa: D401
        left = self.visit(node.left)
        comparisons = zip(node.ops, node.comparators)
        current = left
        for op, comparator in comparisons:
            right = self.visit(comparator)
            if isinstance(op, ast.Eq):
                ok = current == right
            elif isinstance(op, ast.NotEq):
                ok = current != right
            elif isinstance(op, ast.Lt):
                ok = current < right
            elif isinstance(op, ast.LtE):
                ok = current <= right
            elif isinstance(op, ast.Gt):
                ok = current > right
            elif isinstance(op, ast.GtE):
                ok = current >= right
            else:
                raise ValueError("Unsupported comparison operator")
            if not ok:
                return False
            current = right
        return True

    def visit_Constant(self, node: ast.Constant) -> Any:  # noqa: D401
        return node.value

    def visit_Call(self, node: ast.Call) -> Any:  # noqa: D401
        if not isinstance(node.func, ast.Name) or node.func.id != "resolve":
            raise ValueError("Only resolve() calls are allowed")
        if len(node.args) != 1 or node.keywords:
            raise ValueError("resolve() expects a single argument")
        arg = self.visit(node.args[0])
        if not isinstance(arg, str):
            raise ValueError("resolve() argument must be string")
        return self.resolver(arg)

    def visit_Name(self, node: ast.Name) -> Any:  # noqa: D401
        if node.id in {"True", "False"}:
            return node.id == "True"
        raise ValueError(f"Unexpected identifier '{node.id}'")

    def visit_Str(self, node: ast.Str) -> Any:  # pragma: no cover - Python <3.8 compatibility
        return node.s


def _normalize_expr(expr: str) -> str:
    normalized = expr.replace("true", "True").replace("false", "False")
    return normalized


def _inject_resolve(expr: str) -> str:
    import re

    pattern = re.compile(r"\$[A-Za-z0-9_.]+(?:\.[A-Za-z0-9_]+)*")

    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        return f"resolve('{token}')"

    return pattern.sub(repl, expr)


def eval_expr(expr: str, resolver: Callable[[str], Any]) -> bool:
    """Оцінити простий вираз з використанням resolve() для адрес."""

    if not expr:
        return True
    transformed = _inject_resolve(_normalize_expr(expr))
    tree = ast.parse(transformed, mode="eval")
    evaluator = _SafeEvaluator(resolver)
    result = evaluator.visit(tree)
    return bool(result)


__all__ = ["eval_expr"]
