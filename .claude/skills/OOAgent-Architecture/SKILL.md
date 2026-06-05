```markdown
# OOAgent-Architecture Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill introduces the core development patterns and conventions used in the OOAgent-Architecture repository, a TypeScript codebase focused on object-oriented agent architecture. The repository emphasizes clean code practices, conventional commit messages, and a consistent approach to file organization, imports, and exports. This guide will help you quickly understand and adopt the project's standards for contributing effectively.

## Coding Conventions

### File Naming
- Use **camelCase** for file names.
  - Example: `agentManager.ts`, `userSessionHandler.ts`

### Import Style
- Use **relative imports** for referencing modules within the project.
  - Example:
    ```typescript
    import { Agent } from './agent';
    import { SessionManager } from '../session/sessionManager';
    ```

### Export Style
- Use **named exports** rather than default exports.
  - Example:
    ```typescript
    // agent.ts
    export interface Agent {
      id: string;
      performTask(): void;
    }
    ```

### Commit Messages
- Follow **Conventional Commits** with the `feat` prefix for new features.
  - Example:
    ```
    feat: add agent lifecycle management to session handler
    ```

## Workflows

### Feature Development
**Trigger:** When adding a new feature or module  
**Command:** `/feature-development`

1. Create a new file using camelCase naming.
2. Write TypeScript code using named exports.
3. Use relative imports to include other modules.
4. Write or update corresponding test files (`*.test.*`).
5. Commit changes using the `feat:` prefix and a concise, descriptive message.

### Testing
**Trigger:** When verifying code correctness or before submitting a pull request  
**Command:** `/run-tests`

1. Identify or create test files matching the `*.test.*` pattern.
2. Run the project's test runner (framework is unspecified; check project documentation or scripts).
3. Review test results and address any failures.
4. Ensure all new code is covered by tests.

## Testing Patterns

- Test files follow the `*.test.*` naming convention (e.g., `agentManager.test.ts`).
- The specific testing framework is not specified; check for existing test runner scripts or documentation.
- Place tests alongside implementation files or in a dedicated `tests` directory as per project structure.

### Example Test File
```typescript
// agentManager.test.ts
import { AgentManager } from './agentManager';

describe('AgentManager', () => {
  it('should initialize with zero agents', () => {
    const manager = new AgentManager();
    expect(manager.count()).toBe(0);
  });
});
```

## Commands
| Command              | Purpose                                         |
|----------------------|-------------------------------------------------|
| /feature-development | Start a new feature following project patterns  |
| /run-tests           | Run all tests in the repository                 |
```
