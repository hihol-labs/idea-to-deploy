# HANDOFF — ROUTE-DEBTS close (release 1.103.1 + native rollout + installed-proof + ledger-close + FOLLOWUP-A13)

Дата: 2026-09-07. Ветка релиза: `chore/release-v1.103.1` (от origin/main 49e1c95).
Леджерные черновики (DECISIONS/BACKLOG/events для ledger-close) лежат в
`git stash` с меткой `route-debts-ledger-close-drafts` (снято с codex/route-debts).

## План (WIP=1, юнит ROUTE-DEBTS остаётся in_progress до installed-proof)
1. Релиз 1.103.1: бамп 10 мест (plugin.json x2, marketplace, docs-state, README x2,
   conformance, rc-contract, release-oracle VERSION, CHANGELOG) — СДЕЛАНО в рабочем дереве.
   Оракулы: meta_review + run-all --quick (лог в scratchpad). Ревью: machine receipt
   (unit-id ROUTE-DEBTS, risk high) + Sol producer по шаблону
   `.itd-memory/verification-loop/ROUTE-DEBTS-run-sol-a14.py` -> adjudicate -> cache ->
   commit -> `itd pr create` -> CI -> merge -> `gh release create v1.103.1 --target <full sha>`.
2. Раскатка: `bash scripts/sync-to-active.sh`; `CLAUDE_HOME=/mnt/c/Users/Дмитрий/.claude bash scripts/sync-to-active.sh`;
   WSL: `python3 -I scripts/itd_install_cli.py --apply --replace-existing` + `itd_install_git_hooks.py --apply --replace-existing`;
   Windows: то же из Windows-python (`C:\Users\Дмитрий\AppData\Local\Programs\Python\Python312\python.exe`) через powershell;
   Codex cache: `bash .itd-memory/refresh_codex_caches.sh all` (+ проверить `codex plugin list --marketplace personal --json` version 1.103.1).
3. Installed-proof `.itd-memory/host-inputs/ROUTE-DEBTS/INSTALLED.json` (schema v2: version=2, release, runtimeSha256, hosts[Linux,Windows]);
   на каждом хосте: machine receipt unit `ROUTE-DEBTS:deployment-canary` risk low с командой
   `native=<sys.executable> -I -B tests/verify_route_debts.py --native-test-log <log>` (см. native_test_command),
   adjudicate, снапшоты в host-inputs, revalidationLog = вывод `--native-proof`, cliWrapper/prePushWrapper/adapters rows.
   Валидатор: tests/verify_route_debts.py validate_native_record / validate_native_canary / installed_proof.
4. ОТК: `sh skills/_shared/itd_py.sh skills/goal/scripts/itd_goal_verify.py ROUTE-DEBTS --verification-receipt .itd-memory/verification-loop/ROUTE-DEBTS-adjudicated-a13.json`
5. Ledger-close PR с новой ветки от main (stash pop + STATE/GOAL/events), затем /goal activate ROUTE-DEBTS-FOLLOWUP-A13 (поверхность из BACKLOG P1).
