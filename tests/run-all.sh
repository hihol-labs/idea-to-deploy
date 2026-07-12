#!/usr/bin/env bash
# =============================================================================
# tests/run-all.sh — ОДНА команда «прогнать всё локально» (v1.79.0).
# -----------------------------------------------------------------------------
# Cold-start гэп (упражнение «5 вопросов новичка», 2026-07-10): полный набор
# проверок жил только внутри .github/workflows/*.yml — новичок не мог ответить
# «как проверять систему» без чтения CI-конфигов, а «локальный минимум» из
# docs/CI.md не гарантировал зелёный CI. Этот скрипт — исполняемый ответ:
#
#   bash tests/run-all.sh          # весь локальный CI-эквивалент
#   bash tests/run-all.sh --quick  # только быстрый статический костяк
#
# Зелёно = exit 0 и «DONE fails:none». Скрипт зеркалит оба workflow
# (meta-review.yml + windows-verify.yml, их общую python-часть) и держится
# в синхроне с ними; при добавлении verify-теста в workflow — добавь его и
# сюда (drift ловится глазами ревью; авто-дрифт-гард — кандидат в backlog).
# Не покрыто локально: поведенческий fixture-smoke на живой модели (в CI
# отключён по стоимости, см. .github/workflows/fixture-smoke.yml).
# =============================================================================
set -u
cd "$(dirname "$0")/.." || exit 1

PY="${PYTHON:-python3}"
"$PY" -c "print(1)" >/dev/null 2>&1 || PY=python

QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

fails=""
run_py() {
  local t="$1"
  [ -f "tests/$t.py" ] || { echo "SKIP $t (no file)"; return 0; }
  out=$("$PY" "tests/$t.py" 2>&1); rc=$?
  if [ $rc -ne 0 ]; then
    fails="$fails $t"
    echo "FAIL $t rc=$rc"
    echo "$out" | tail -6
  fi
}

# --- быстрый статический костяк (--quick) -----------------------------------
CORE="meta_review verify_triggers verify_gate_taxonomy verify_registration_and_counts verify_hook_table_completeness"
# --- полный python-набор обоих workflow --------------------------------------
FULL="verify_dod_gate verify_skill_enforcement verify_agent_review_sentinel \
verify_review_autoping verify_refute_fleet verify_model_risk_monotonic \
verify_dod_coverage verify_stall_fallback verify_feature_ledger \
verify_feature_ledger_completeness verify_feature_ledger_fallbacks \
verify_retro_abstention_review verify_feature_ledger_adoptions \
verify_init_contracts verify_cost_tracker verify_review_report_file \
verify_state_hardening verify_source_read_contract \
verify_completion_signals_powershell \
verify_completion_signal_classes \
verify_platform_tmp_and_new_hooks verify_goal_tools verify_retro_scan \
verify_v147_fixes verify_hook_depth verify_narration_final \
verify_verdict_contract verify_worktree_hook_safety verify_hook_count_words \
verify_fable_snippets verify_routing verify_completion_gate \
verify_completion_ledger verify_harness_map_fixtures verify_runall_drift \
verify_no_bare_python3 verify_model_policy_hint \
verify_py_launcher_encoding verify_unit_log verify_goal_verify_shell \
verify_project_checks verify_review_import"

for t in $CORE; do run_py "$t"; done
if [ "$QUICK" = "0" ]; then
  for t in $FULL; do run_py "$t"; done
  "$PY" scripts/verify_skill_profiles.py >/dev/null 2>&1 || { echo "FAIL verify_skill_profiles"; fails="$fails skill_profiles"; }
  bash scripts/verify-sync-to-active.sh >/dev/null 2>&1 || { echo "FAIL verify-sync-to-active"; fails="$fails sync_verify"; }
  "$PY" tests/verify_snapshot.py --all >/dev/null 2>&1 || { echo "FAIL verify_snapshot --all"; fails="$fails snapshot"; }
fi

echo "DONE fails:${fails:-none}"
[ -z "$fails" ] || exit 1
