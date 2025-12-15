from __future__ import annotations

import ast
from dataclasses import dataclass, field

from agentfw.core.models import ConditionDefinition
from agentfw.core.state import AgentState


@dataclass
class ExpressionEvaluator:
    """Safely evaluates expression-based conditions."""

    def eval(self, expression: str, variables: dict[str, object]) -> bool:
        """Evaluate an expression using the given variable mapping."""
        tree = ast.parse(expression, mode="eval")

        _SafeExpressionValidator().visit(tree)

        compiled = compile(tree, "<expression>", "eval")
        result = eval(compiled, {}, dict(variables))  # noqa: S307
        return bool(result)


class _SafeExpressionValidator(ast.NodeVisitor):
    """Validate AST nodes to ensure expressions are safe to execute."""

    _allowed_bool_ops = (ast.And, ast.Or)
    _allowed_compare_ops = (ast.Eq, ast.NotEq, ast.Gt, ast.Lt, ast.In)
    def visit(self, node: ast.AST) -> None:  # type: ignore[override]
        super().visit(node)

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.Load, ast.Expr, ast.Expression)):
            super().generic_visit(node)
            return
        raise ValueError(f"Unsupported expression element: {type(node).__name__}")

    def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802
        if not isinstance(node.op, self._allowed_bool_ops):
            raise ValueError("Only 'and'/'or' boolean operators are allowed")
        for value in node.values:
            self.visit(value)

    def visit_Compare(self, node: ast.Compare) -> None:  # noqa: N802
        for op in node.ops:
            if not isinstance(op, self._allowed_compare_ops):
                raise ValueError("Only ==, !=, >, <, and 'in' comparisons are allowed")
        self.visit(node.left)
        for comparator in node.comparators:
            self.visit(comparator)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if node.id.startswith("__"):
            raise ValueError("Access to dunder variables is not allowed")

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        if "__" in node.attr:
            raise ValueError("Access to dunder attributes is not allowed")
        self.visit(node.value)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        raise ValueError("Function calls are not allowed in expressions")

    def visit_Subscript(self, node: ast.Subscript) -> None:  # noqa: N802
        self.visit(node.value)
        self.visit(node.slice)

    def visit_Index(self, node: ast.Index) -> None:  # type: ignore[override]  # noqa: N802
        self.visit(node.value)

    def visit_Constant(self, node: ast.Constant) -> None:  # noqa: N802
        return

    def visit_List(self, node: ast.List) -> None:  # noqa: N802
        for elt in node.elts:
            self.visit(elt)

    def visit_Tuple(self, node: ast.Tuple) -> None:  # noqa: N802
        for elt in node.elts:
            self.visit(elt)

    def visit_Dict(self, node: ast.Dict) -> None:  # noqa: N802
        for key in node.keys:
            if key is not None:
                self.visit(key)
        for value in node.values:
            if value is not None:
                self.visit(value)

    def visit_Set(self, node: ast.Set) -> None:  # noqa: N802
        for elt in node.elts:
            self.visit(elt)

    def visit_IfExp(self, node: ast.IfExp) -> None:  # noqa: N802
        raise ValueError("Conditional expressions are not allowed")


@dataclass
class ConditionEvaluator:
    """Evaluates condition definitions against agent state."""

    expression_evaluator: ExpressionEvaluator = field(default_factory=ExpressionEvaluator)

    def evaluate(self, condition: ConditionDefinition, state: AgentState) -> bool:
        """Return True when the provided condition evaluates to true."""
        if condition.type == "always":
            return True

        if condition.type == "equals":
            if condition.value_from not in state.variables:
                return False
            return state.variables[condition.value_from] == condition.value

        if condition.type == "not_equals":
            return state.variables.get(condition.value_from) != condition.value

        if condition.type == "greater_than":
            value = state.variables.get(condition.value_from)
            return value is not None and value > condition.value

        if condition.type == "less_than":
            value = state.variables.get(condition.value_from)
            return value is not None and value < condition.value

        if condition.type == "contains":
            container = state.variables.get(condition.value_from)
            try:
                return condition.value in container
            except TypeError:
                return False

        if condition.type == "expression":
            if not condition.expression:
                return False
            try:
                return self.expression_evaluator.eval(condition.expression, state.variables)
            except Exception:  # noqa: BLE001
                return False

        raise ValueError(f"Unsupported condition type: {condition.type}")
