"""Restricted expression evaluator for the requirement knowledge base.

Used for KB `conditions` ("temp_min_c < 12") and `quantity_rule`
("ceil(duration_days / 2)").

There is no eval(), no compile() and no exec() here. Expressions are parsed
with ast.parse and then interpreted directly by a recursive walker that
understands a fixed set of node types. Anything outside that set raises
UnsafeExpression. KB files are authored by us, but they are still data, and
data does not get to execute arbitrary Python.

Fail-safe semantics: an expression referencing a slot the user has not
provided evaluates to False (condition) or falls back to the default
(quantity). An unknown requirement is simply not required -- never a crash
mid-demo.

Owner: Member 4 (Requirements/Optimization).
"""

from __future__ import annotations

import ast
import math
from typing import Any

__all__ = ["evaluate_condition", "evaluate_quantity", "UnsafeExpression", "MissingSlot"]


class UnsafeExpression(ValueError):
    """The expression used syntax the DSL does not allow."""


class MissingSlot(LookupError):
    """The expression referenced a slot that is not in the context."""


ALLOWED_FUNCTIONS: dict[str, Any] = {
    "ceil": lambda x: math.ceil(x),
    "floor": lambda x: math.floor(x),
    "min": min,
    "max": max,
    "abs": abs,
    "int": int,
    "round": round,
    "len": len,
}

_COMPARISONS = {
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}

_BINARY = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.FloorDiv: lambda a, b: a // b,
    ast.Mod: lambda a, b: a % b,
    ast.Pow: lambda a, b: a**b,
}

_UNARY = {
    ast.USub: lambda a: -a,
    ast.UAdd: lambda a: +a,
    ast.Not: lambda a: not a,
}

# Bare names that are values rather than slot lookups.
_LITERAL_NAMES = {"true": True, "false": False, "none": None, "null": None}


def _eval(node: ast.AST, context: dict) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, context)

    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        key = node.id
        if key.lower() in _LITERAL_NAMES:
            return _LITERAL_NAMES[key.lower()]
        if key not in context:
            raise MissingSlot(key)
        return context[key]

    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_eval(e, context) for e in node.elts]

    if isinstance(node, ast.UnaryOp):
        op = _UNARY.get(type(node.op))
        if op is None:
            raise UnsafeExpression(f"unary operator not allowed: {type(node.op).__name__}")
        return op(_eval(node.operand, context))

    if isinstance(node, ast.BinOp):
        op = _BINARY.get(type(node.op))
        if op is None:
            raise UnsafeExpression(f"operator not allowed: {type(node.op).__name__}")
        right = _eval(node.right, context)
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)) and right == 0:
            raise UnsafeExpression("division by zero")
        return op(_eval(node.left, context), right)

    if isinstance(node, ast.BoolOp):
        values = [_eval(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        return any(values)

    if isinstance(node, ast.Compare):
        left = _eval(node.left, context)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _COMPARISONS.get(type(op_node))
            if op is None:
                raise UnsafeExpression(
                    f"comparison not allowed: {type(op_node).__name__}"
                )
            right = _eval(comparator, context)
            # None is not orderable; treat any ordering against it as False
            # rather than raising, so a partially-filled profile still works.
            if left is None or right is None:
                if not isinstance(op_node, (ast.Eq, ast.NotEq, ast.In, ast.NotIn)):
                    return False
            if not op(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise UnsafeExpression("only plain function calls are allowed")
        fn = ALLOWED_FUNCTIONS.get(node.func.id)
        if fn is None:
            raise UnsafeExpression(f"function not allowed: {node.func.id}")
        if node.keywords:
            raise UnsafeExpression("keyword arguments are not allowed")
        return fn(*[_eval(a, context) for a in node.args])

    raise UnsafeExpression(f"syntax not allowed: {type(node).__name__}")


def _parse(expression: str) -> ast.Expression:
    try:
        return ast.parse(expression.strip(), mode="eval")
    except SyntaxError as exc:  # pragma: no cover - authoring error
        raise UnsafeExpression(f"could not parse {expression!r}: {exc}") from exc


def evaluate_condition(expression: str, context: dict, *, default: bool = False) -> bool:
    """Evaluate a KB condition.

    Returns `default` (False) when the expression references a slot the user
    has not supplied -- the item is simply not required, rather than the plan
    failing.
    """
    if not expression or not expression.strip():
        return True
    try:
        return bool(_eval(_parse(expression), context))
    except MissingSlot:
        return default
    except UnsafeExpression:
        raise
    except Exception:
        return default


def evaluate_quantity(expression: str | int | None, context: dict, *, default: int = 1) -> int:
    """Evaluate a KB quantity_rule to a positive integer."""
    if expression is None or expression == "":
        return default
    if isinstance(expression, int):
        return max(1, expression)
    try:
        value = _eval(_parse(str(expression)), context)
    except (MissingSlot, UnsafeExpression):
        return default
    except Exception:
        return default

    if value is None or isinstance(value, bool):
        return default
    try:
        return max(1, int(math.ceil(float(value))))
    except (TypeError, ValueError):
        return default
