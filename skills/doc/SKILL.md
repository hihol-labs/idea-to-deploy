---
name: doc
description: 'Generate documentation — README, API docs, inline comments. Detects project style and follows existing conventions. TRIGGER when user says "напиши документацию", "создай README", "задокументируй API", "добавь комментарии", or when creating/updating public APIs. Docs are part of "done". See `## Trigger phrases` in body for full list.'
argument-hint: file, module, or "readme" or "api"
license: MIT
paths: ["**/README.md", "**/CHANGELOG.md", "**/docs/**"]
metadata:
  author: HiH-DimaN
  version: 1.2.0
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

## Troubleshooting

### Too many files to document
Focus on public API surface only. Skip internal helpers, tests, configs.

### Mixed documentation languages
Follow the majority. If 80% is in Russian, write in Russian.

### No existing style to follow
Default to: JSDoc for JS/TS, Google-style docstrings for Python, rustdoc for Rust.
