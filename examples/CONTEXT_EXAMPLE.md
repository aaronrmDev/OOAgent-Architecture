# UnitConversion Context — v1.0 (Worked CONTEXT.md Example)

> This file is a worked example of the `CONTEXT.md` format required by
> CLAUDE.md §14 for every `IDomainContext` implementation. It documents
> `UnitConversionContext`, the domain context defined in
> `examples/domain_context_agent.py` (sub-project A's golden-path
> example). Real domain contexts under `contexts/<domain>/` should ship a
> `CONTEXT.md` in this same format, alongside their source — not as a
> standalone example file like this one.

## 1. Scope

Handles queries about converting a quantity from one measurement unit to
another (e.g., meters to feet). Declares one problem class,
`UnitConversion`, but does not implement a solver for it — `solvers()`
returns `{}` deliberately. This context exists to demonstrate *context
resolution and injection* (CLAUDE.md §9): a query mentioning "meters" or
"feet" resolves to `UnitConversionContext` instead of falling back to
`NullContext`. It does NOT demonstrate solver dispatch (CLAUDE.md §4's
Strategy pattern entry) — see Known Limitations below.

## 2. Vocabulary (canonical terms)

| Term | Definition | Canonical? |
|---|---|---|
| meters | SI unit of length | Yes |
| feet | imperial unit of length | Yes |
| kilograms | SI unit of mass | Yes |
| pounds | imperial unit of mass | Yes |

## 3. Problem Classes

| Name | Description | Required Inputs | Solver |
|---|---|---|---|
| UnitConversion | Convert a quantity from one unit to another | none declared (`required_inputs()` returns `[]`) | `unit_converter` (name only — no `ISolver` implementation is registered under it; a matched query falls through to the LLM/tool loop) |

## 4. Invariants

| Name | Condition | Severity | Rationale |
|---|---|---|---|
| unit-tagged-result | every converted quantity carries its target unit | error | a bare number without a unit is not a valid conversion result |

## 5. Anti-Patterns

None declared (`anti_patterns()` returns `[]`) — this minimal example
predates any anti-pattern discovered from production use of this context.

## 6. Stack Defaults (if applicable)

Not applicable — this context has no code-generation or stack-specific
behavior.

## 7. Artifact Preferences

`preferred_formats: ["text"]`, `type_hints_required: False`,
`comment_policy: "none"` — plain-text conversion answers, no code
artifact expected.

## 8. System Prompt Extension

The exact text injected into the LLM system prompt when this context is
active:

> "UnitConversion v1.0 is active. Convert between the requested units and
> always state the target unit alongside the number."

## 9. Extension Points

To turn this into a real, solver-backed domain context: implement an
`ISolver` that performs the actual unit-conversion arithmetic, register it
under the name `unit_converter` in `solvers()`, and add `required_inputs()`
entries for the source quantity, source unit, and target unit. To combine
this domain with another, compose rather than subclass (CLAUDE.md §8b's
`HybridContext` pattern) — merge vocabularies with `|` and concatenate
invariant lists.

## 10. Known Limitations

This context resolves but does not solve — every query correctly routed
here still falls through to the LLM/tool loop (`_llm_tool_loop`), because
`solvers()` is empty and `resolve_intent()` always returns `None`. It
exists purely to demonstrate `ContextRegistry.resolve()`'s vocabulary-
scoring algorithm (CLAUDE.md §9). A production unit-conversion context
should implement a real `ISolver` for deterministic, non-hallucinated
arithmetic rather than relying on the LLM to compute the conversion.
