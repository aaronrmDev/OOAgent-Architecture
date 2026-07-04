"""plugins/tool_kit/calculator_tool.py — CalculatorTool.

Evaluates safe arithmetic expressions. Uses a restricted evaluator —
never eval() or exec() to avoid injection.
"""

from __future__ import annotations

import re
from typing import Any

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
        left = parse_pow()
        while peek() in ("*", "/"):
            op = consume()
            right = parse_pow()
            if op == "/" and right == 0:
                raise ValueError("Division by zero")
            left = left * right if op == "*" else left / right
        return left

    def parse_pow() -> float:
        base = parse_unary()
        if peek() == "**":
            consume()
            return base ** parse_unary()
        return base

    def parse_unary() -> float:
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
