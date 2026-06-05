// plugins/tool-kit/calculator-tool.ts — CalculatorTool
// Evaluates safe arithmetic expressions. Uses a restricted evaluator —
// never eval() or Function() to avoid injection.
import { BaseTool } from '../../adapters/tools/base.js'
import {
  JSONSchema,
  ToolExecutionError,
} from '../../core/protocols.js'

// Recursive descent parser for arithmetic expressions.
// Supports: + - * / ** ( ) and numeric literals (int, float, scientific notation).
function safeEval(expr: string): number {
  const tokens = tokenize(expr)
  let pos = 0

  function peek() { return tokens[pos] }
  function consume() { return tokens[pos++] }
  function expect(t: string) {
    if (consume() !== t) throw new Error(`Expected '${t}'`)
  }

  function parseExpr(): number { return parseAddSub() }

  function parseAddSub(): number {
    let left = parseMulDiv()
    while (peek() === '+' || peek() === '-') {
      const op = consume()
      const right = parseMulDiv()
      left = op === '+' ? left + right : left - right
    }
    return left
  }

  function parseMulDiv(): number {
    let left = parsePow()
    while (peek() === '*' || peek() === '/') {
      const op = consume()
      const right = parsePow()
      if (op === '/' && right === 0) throw new Error('Division by zero')
      left = op === '*' ? left * right : left / right
    }
    return left
  }

  function parsePow(): number {
    const base = parseUnary()
    if (peek() === '**') { consume(); return base ** parseUnary() }
    return base
  }

  function parseUnary(): number {
    if (peek() === '-') { consume(); return -parsePrimary() }
    if (peek() === '+') { consume(); return parsePrimary() }
    return parsePrimary()
  }

  function parsePrimary(): number {
    const tok = peek()
    if (tok === '(') {
      consume()
      const v = parseExpr()
      expect(')')
      return v
    }
    if (tok !== undefined && /^-?\d/.test(tok)) {
      consume()
      return parseFloat(tok)
    }
    throw new Error(`Unexpected token: ${tok}`)
  }

  const result = parseExpr()
  if (pos !== tokens.length) throw new Error(`Unexpected token: ${tokens[pos]}`)
  return result
}

function tokenize(expr: string): string[] {
  const re = /(\d+\.?\d*(?:[eE][+-]?\d+)?|\*\*|[+\-*/()])/g
  return (expr.replace(/\s/g, '').match(re) ?? [])
}

export class CalculatorTool extends BaseTool {
  readonly name        = 'calculator'
  readonly description = 'Evaluates a safe arithmetic expression and returns the numeric result.'

  inputSchema(): JSONSchema {
    return {
      type: 'object',
      properties: {
        expression: {
          type: 'string',
          description: 'Arithmetic expression using +, -, *, /, **, ( ). Example: "(2 + 3) * 4 ** 2"',
        },
      },
      required: ['expression'],
    }
  }

  async execute(args: Record<string, unknown>): Promise<unknown> {
    const expr = args.expression
    if (typeof expr !== 'string' || !expr.trim()) {
      throw new ToolExecutionError(this.name, args, new Error('expression must be a non-empty string'))
    }
    try {
      const result = safeEval(expr)
      return { expression: expr, result, unit: 'dimensionless' }
    } catch (err) {
      throw new ToolExecutionError(this.name, args, err)
    }
  }

}
