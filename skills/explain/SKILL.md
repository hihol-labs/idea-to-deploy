---
name: explain
description: Explain how code works — architecture, data flow, key decisions. Uses ASCII diagrams and step-by-step walkthroughs. TRIGGER when user says "объясни код", "как это работает", "explain this", "что делает эта функция", or asks any question about how existing code works.
argument-hint: file, function, module, or concept
license: MIT
effort: low
metadata:
  author: HiH-DimaN
  version: 1.0.0
  category: code-understanding
  tags: [code-review, architecture, learning]
---


# Explain

## Instructions

### Step 1: Purpose
What does this code do and why does it exist? (1-2 sentences)

### Step 2: How it works
Step-by-step walkthrough of the logic flow. Reference specific line numbers.

### Step 3: Key concepts
Explain any patterns, algorithms, or domain concepts used.

### Step 4: Data flow
What goes in, what comes out, what gets transformed along the way.

```
Input → [Step A] → intermediate → [Step B] → Output
```

Use ASCII diagrams for architecture or complex flows:
```
Client → API Gateway → Auth Middleware → Handler → DB
                                            ↓
                                        Response
```

### Step 5: Dependencies
What does this code depend on, and what depends on it?

### Step 6: Gotchas
Non-obvious behavior, edge cases, or common mistakes.

Adapt the explanation depth to the complexity of the code.

## Examples

### Example 1: Explain a function
User says: "объясни функцию processPayment в src/services/billing.ts"

Result:
- Purpose: Processes a payment via YuKassa, updates order status
- Flow: validate amount → create YuKassa payment → poll status → update DB
- Gotcha: YuKassa webhook may arrive before polling returns — handled by idempotency key

### Example 2: Explain architecture
User says: "как работает авторизация в проекте"

Result:
- ASCII diagram of auth flow (login → token → middleware → protected route)
- Key files involved with line references
- Why JWT + refresh token was chosen over sessions

## Troubleshooting

### Code is too large to explain at once
Break into layers: "Let me explain the API layer first, then the service layer, then the data layer."

### Code has no comments and unclear naming
Focus on WHAT it does (trace inputs/outputs), not WHY (that requires domain knowledge — ask the user).
