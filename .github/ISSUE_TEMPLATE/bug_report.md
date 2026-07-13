---
name: Bug report
about: File a defect against OOAgent
title: 'fix(<scope>): <short description>'
labels: bug
assignees: ''
---

## Describe the bug

<!-- Clear description of what is wrong -->

## Reproduction

```python
# Minimal reproduction case
```

## Expected behavior

<!-- What should happen? -->

## Actual behavior

<!-- What happens instead? Error message, stack trace, FSM state? -->

## FSM State at Failure

<!-- If the agent crashed or hung, what FSM state was it in?
     Check SessionState.fsm and the FSMTrace. -->

- FSM state: <!-- IDLE / GATHERING / AWAITING / MODELING / SOLVING / VALIDATING / DELIVERING / FAILURE -->
- Turn number: <!-- SessionState.turn -->
- Active context: <!-- IDomainContext.name + version -->

## AI Safety Gate Impact

<!-- Did this bug cause or could it cause a safety guard failure?
     If yes, which guard and why? -->

- [ ] No AI safety impact
- [ ] Potential safety impact on Guard(s): <!-- list -->

## Environment

- OOAgent version: <!-- e.g. 2026.06.01 -->
- LLM backend: <!-- Anthropic / OpenAI / Gemini / Ollama -->
- Model ID: <!-- e.g. claude-opus-4-8 -->
- Python version:
- OS:
