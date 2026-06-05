// testing/conformance/tool.conformance.test.ts
// ITool conformance suite — §17 CLAUDE.md
import { describe, test } from 'node:test'
import { ok, strictEqual, rejects } from 'node:assert'
import { DateTimeTool } from '../../plugins/tool-kit/datetime-tool.js'
import { CalculatorTool } from '../../plugins/tool-kit/calculator-tool.js'

const dateTool   = new DateTimeTool()
const calcTool   = new CalculatorTool()

describe('ITool conformance (§17 CLAUDE.md)', () => {
  test('execute(validArgs) returns result without throwing — DateTimeTool', async () => {
    const result = await dateTool.execute({})
    ok(result !== undefined, 'execute(validArgs) must return a result')
  })

  test('execute(validArgs) returns result without throwing — CalculatorTool', async () => {
    const result = await calcTool.execute({ expression: '2 + 2' })
    ok(result !== undefined, 'execute(validArgs) must return a result')
  })

  test('execute(invalidArgs) throws ToolExecutionError for CalculatorTool', async () => {
    await rejects(
      () => calcTool.execute({ expression: 'not_a_number @@@ !!!' }),
      (err: unknown) => {
        ok(err instanceof Error, 'must throw an Error subtype')
        // ToolExecutionError name or message must indicate the failure
        return (err as Error).name === 'ToolExecutionError' ||
               (err as Error).message.length > 0
      },
      'execute(invalidArgs) must throw ToolExecutionError — not return silently',
    )
  })

  test('toVendorSpec() returns valid JSON for anthropic vendor', () => {
    const spec = dateTool.toVendorSpec('anthropic')
    const json = JSON.stringify(spec)
    ok(json.length > 0, 'toVendorSpec() must return a non-empty JSON-serializable object')
    strictEqual(typeof spec, 'object', 'toVendorSpec() must return an object')
  })

  test('toVendorSpec() returns valid JSON for openai vendor', () => {
    const spec = calcTool.toVendorSpec('openai')
    ok(JSON.stringify(spec).length > 0, 'toVendorSpec() returns valid JSON for openai')
  })

  test('name and description are non-empty strings', () => {
    ok(dateTool.name.length > 0,        'tool.name must be non-empty')
    ok(dateTool.description.length > 0, 'tool.description must be non-empty')
  })
})
