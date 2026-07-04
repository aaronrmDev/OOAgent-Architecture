"""plugins/tool_kit/calculator_tool.py — CalculatorTool.

Evaluates safe arithmetic expressions. Uses a restricted evaluator —
never eval() or exec() to avoid injection.
"""

from __future__ import annotations

import re
from typing import Any, cast

from ooagent.adapters.tools.base import BaseTool
from ooagent.core.protocols import JSONSchema, ToolExecutionError

_TOKEN_RE = re.compile(r"(\d+\.?\d*(?:[eE][+-]?\d+)?|\*\*|[+\-*/()])")


def _tokenize(expr: str) -> list[str]:
    stripped = re.sub(r"\s", "", expr)
    return _TOKEN_RE.findall(stripped)


def _safe_eval(expr: str) -> float:
    """Recursive descent parser for arithmetic expressions.

    Supports: + - * / ** ( ) and numeric literals (int, float, scientific
    notation). Mirrors the TS `safeEval` implementation exactly, including
    its lack of support for chained `**` (e.g. `2 ** 3 ** 2` is rejected).

    Unary sign binds looser than `**`, matching standard math/Python
    precedence: `-2 ** 2 == -4.0`, not `(-2) ** 2 == 4.0`. `parse_signed_pow`
    applies an optional leading sign around the full `parse_pow()` result.
    The exponent position (`parse_exponent_unary`) separately allows its own
    single leading sign — so `2 ** -2 == 0.25` still works — without
    permitting a second `**` there, so chained exponentiation stays rejected.
    """
    tokens = _tokenize(expr)
    pos = 0

    def peek() -> str | None:
        return tokens[pos] if pos < len(tokens) else None

    def consume() -> str | None:
        nonlocal pos
        tok = tokens[pos] if pos < len(tokens) else None
        pos += 1
        return tok

    def expect(t: str) -> None:
        if consume() != t:
            raise ValueError(f"Expected '{t}'")

    def parse_expr() -> float:
        return parse_add_sub()

    def parse_add_sub() -> float:
        left = parse_mul_div()
        while peek() in ("+", "-"):
            op = consume()
            right = parse_mul_div()
            left = left + right if op == "+" else left - right
        return left

    def parse_mul_div() -> float:
        left = parse_signed_pow()
        while peek() in ("*", "/"):
            op = consume()
            right = parse_signed_pow()
            if op == "/" and right == 0:
                raise ValueError("Division by zero")
            left = left * right if op == "*" else left / right
        return left

    def parse_signed_pow() -> float:
        # Sign applies AFTER exponentiation, matching standard math/Python
        # precedence: -2 ** 2 == -4.0, not (-2) ** 2 == 4.0.
        if peek() == "-":
            consume()
            return -parse_pow()
        if peek() == "+":
            consume()
            return parse_pow()
        return parse_pow()

    def parse_pow() -> float:
        base = parse_primary()
        if peek() == "**":
            consume()
            # float.__pow__ is typed to return `Any` (base ** exponent can be
            # complex for a negative base with a fractional exponent); cast to
            # match this function's declared float return type. NOTE: this is
            # a pre-existing runtime divergence from the TS source (JS
            # `Math.pow` yields NaN in that case, Python yields a complex
            # number) — not something this type-only pass changes.
            return cast(float, base ** parse_exponent_unary())
        return base

    def parse_exponent_unary() -> float:
        # Exponent slot only: a single leading sign then a primary — no
        # further ** here, so 2 ** -2 == 0.25 still works but chained
        # exponentiation (2 ** 3 ** 2) is still rejected, same as before.
        if peek() == "-":
            consume()
            return -parse_primary()
        if peek() == "+":
            consume()
            return parse_primary()
        return parse_primary()

    def parse_primary() -> float:
        tok = peek()
        if tok == "(":
            consume()
            v = parse_expr()
            expect(")")
            return v
        if tok is not None and re.match(r"^-?\d", tok):
            consume()
            return float(tok)
        raise ValueError(f"Unexpected token: {tok}")

    result = parse_expr()
    if pos != len(tokens):
        raise ValueError(f"Unexpected token: {tokens[pos]}")
    return result


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Evaluates a safe arithmetic expression and returns the numeric result."

    def input_schema(self) -> JSONSchema:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": (
                        "Arithmetic expression using +, -, *, /, **, ( ). "
                        'Example: "(2 + 3) * 4 ** 2"'
                    ),
                },
            },
            "required": ["expression"],
        }

    async def execute(self, args: dict[str, Any]) -> Any:
        expr = args.get("expression")
        if not isinstance(expr, str) or not expr.strip():
            raise ToolExecutionError(
                self.name, args, ValueError("expression must be a non-empty string")
            )
        try:
            result = _safe_eval(expr)
            return {"expression": expr, "result": result, "unit": "dimensionless"}
        except Exception as err:
            raise ToolExecutionError(self.name, args, err) from err
