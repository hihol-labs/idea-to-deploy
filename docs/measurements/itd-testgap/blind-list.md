# Слепой список кандидатов в попадание (протокол, раздел 3, шаг 2)

Рубрика: «да» - блокер называет то же поведение кода, что эталон, и говорит, что тест его не проверяет или что нарушение пройдет незамеченным; «нет» - все остальное.

## f7a518
- Эталон: подтверждение не привязано к `tool_name`; подтверждение без сессии принимается
- Блокер: `tests/verify_codex_ask_gates.py` - AC2 'binds ... tool': removing toolName from approval_hash keeps 19/0. [19] checks script and cwd, [5] checks input; no check that another tool_name with the same input gets a different hash or does not pass.

## e42f1c
- Эталон: подтверждение не привязано к `tool_name`; подтверждение без сессии принимается
- Блокер: `tests/verify_codex_ask_gates.py` - AC2 'binds ... tool': ни одна проверка не меняет только tool_name при том же скрипте, input и cwd; мутант без toolName в approval_hash проходит 19/19, хотя одобрение одного инструмента может пропустить другой с тем же input.

## 1f7cce
- Эталон: подтверждение не привязано к `tool_name`; подтверждение без сессии принимается
- Блокер: `tests/verify_codex_ask_gates.py` - AC2 says the hash binds the tool, but no check varies tool_name. Check [19] is titled 'binds script, tool, exact input and cwd' yet only varies script and cwd. Removing "toolName" from approval_hash in hooks/codex-dispatch.py leaves the test green (19 passed, 0 failed).

