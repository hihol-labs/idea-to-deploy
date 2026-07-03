#!/usr/bin/env python3
"""Regression cases for verify_snapshot's _API_ENDPOINT_RE (v1.43.1).

The live fixture-01 headless run (2026-07-03) produced endpoints as
`| GET | /api/v1/... |` (method in its own table cell) and scored a false
0/15. This suite pins all four legitimate shapes AND the negative cases the
reviewer asked to lock down (table headers, prose with method words).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_snapshot import count_api_endpoints  # noqa: E402

PASS = FAIL = 0


def check(name: str, text: str, expected: int) -> None:
    global PASS, FAIL
    got = count_api_endpoints(text)
    if got == expected:
        PASS += 1
        print(f"PASS  {name}")
    else:
        FAIL += 1
        print(f"FAIL  {name} — expected {expected}, got {got}: {text!r}")


# --- positive: the four legitimate shapes ------------------------------------
check("plain line", "GET /api/v1/users\nPOST /api/v1/users", 2)
check("backtick line", "`GET /api/v1/users`", 1)
check("numbered table row", "| 1 | GET | /api/v1/users | list |", 1)
check("method+path in one cell", "| GET /api/v1/users | list users |", 1)
check("method in own cell, path next (v1.43.1)",
      "| GET | /api/v1/auth/login | вход | all |\n"
      "| POST | `/api/v1/auth/refresh` | обновление | all |", 2)
check("path param braces", "| DELETE | /api/v1/patients/{id} | удалить | admin |", 1)

# --- negative: must NOT count -------------------------------------------------
check("table header", "| Метод | Путь | Описание | Роль |", 0)
check("separator row", "|---|---|---|---|", 0)
check("prose with method word", "The GET requests are cached for 60 seconds.", 0)
check("method word in cell without path",
      "| GET requests | are cached | 60s |", 0)
check("plain text mention", "используем POST для записи", 0)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
