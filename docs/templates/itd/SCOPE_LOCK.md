# Scope Lock

## Current Task

- Replace this line with the current task.

## Allowed Change Areas

- Replace this line with files/modules/behaviors that may change.

## Forbidden Change Areas

- Replace this line with files/modules/behaviors that must not change in this task.

## Review Rule

If the diff touches an area outside allowed scope, pause and reclassify the task before continuing.

> Plugin-native enforcement: `hooks/freeze.sh` already implements a directory-level scope freeze. This file is the human-readable, per-task contract that `freeze.sh` and `/review` check against.
