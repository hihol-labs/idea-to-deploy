---
name: doc
description: 'Generate documentation — README, API docs, inline comments. Detects project style and follows existing conventions.'
argument-hint: file, module, or "readme" or "api"
license: MIT
allowed-tools: Read Write Edit Glob Grep
paths: ["**/README.md", "**/CHANGELOG.md", "**/docs/**"]
metadata:
  author: HiH-DimaN
  version: 1.3.1
  category: documentation
  tags: [readme, api-docs, comments, jsdoc]
---


# Doc


## Trigger phrases

These are the user phrases (Russian and English) that should auto-invoke this skill. They are kept here, not in the description, to avoid diluting the embedding-based matcher in the frontmatter. The hook `hooks/check-skills.sh` also uses this list — keep them in sync.

- напиши документацию, создай README, обнови README, задокументируй API
- опиши API, добавь комментарии, inline комментарии
- JSDoc, docstrings, changelog, changelog.md
- сгенери doc, generate documentation, write docs
- автоматически после нетривиальной фичи

## Recommended model

**sonnet** — Pattern-matching against existing project doc style. Sonnet is the right balance of quality and speed.

Set via `/model {model}` before invoking this skill, or via the project's default model in `~/.claude/settings.json`.


## Instructions

### Step 1: Detect context
Read the target and determine documentation type:
- File/module → docstrings/JSDoc/comments
- "readme" → README.md
- "api" → API reference

### Step 2: Check existing style
Read 2-3 already documented files in the project to match:
- Comment format (JSDoc, docstrings, rustdoc, etc.)
- Language (Russian/English)
- Level of detail

### Step 3: Generate documentation

**For a file/module:**
- Add docstrings/comments only to public API and complex internal logic
- Do NOT over-document obvious code like `getUser` or simple getters

**For README.md:**
```markdown
# Project Name
One-line description.

## Quick Start
Install + run in under 30 seconds.

## Features
- Bullet list of key features

## Configuration
Environment variables table.

## Project Structure
Brief tree of key directories.
```

**For API docs:**
```markdown
## POST /api/users
Create a new user.

**Request:**
{ "email": "user@example.com", "name": "John" }

**Response (201):**
{ "id": "uuid", "email": "...", "created_at": "..." }

**Errors:**
- 400: Invalid email format
- 409: Email already exists
```

### Step 4: Validate
Ensure all public functions/endpoints are covered. No orphan references.

## Examples

### Example 1: Document a Python module
User says: "задокументируй src/services/payment.py"

Actions:
1. Read the file, identify public functions
2. Check existing docstring style in the project
3. Add Google-style docstrings to public functions with Args, Returns, Raises

### Example 2: Generate API docs
User says: "создай документацию API"

Actions:
1. Find all route handlers (app.get, app.post, router.*)
2. For each: method, path, description, request body, response, errors
3. Group by resource (users, orders, payments)

## Rules

1. Перед написанием документации прочитай 2-3 уже задокументированных файла проекта и точно следуй их стилю (формат комментариев, язык, уровень детализации)
2. Не документируй неизменённый код — если файл не менялся в текущей задаче и уже имеет документацию, не трогай его
3. Язык документации определяется по проекту: если README на русском — пиши на русском, если docstrings на английском — пиши на английском. Не смешивай языки в одном файле
4. Не документируй очевидное — `get_user()`, простые геттеры, однострочные утилиты не нуждаются в docstring длиннее одной строки
5. Каждый пример в API-документации должен быть валидным JSON/запросом, который можно скопировать и выполнить


## Self-validation

Before presenting documentation to user, verify:
- [ ] Documentation matches the current state of code (not stale)
- [ ] All public functions/endpoints documented
- [ ] Code examples compile/run (if included)
- [ ] Language matches user's request (Russian/English)
- [ ] Documentation style matches existing project conventions

## Troubleshooting

### Too many files to document
Focus on public API surface only. Skip internal helpers, tests, configs.

### Mixed documentation languages
Follow the majority. If 80% is in Russian, write in Russian.

### No existing style to follow
Default to: JSDoc for JS/TS, Google-style docstrings for Python, rustdoc for Rust.
