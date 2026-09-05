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
#   bash tests/run-all.sh --fail-fast          # остановиться на первом красном
#   bash tests/run-all.sh --targeted           # только сьюты по карте (git-диф)
#   bash tests/run-all.sh --targeted --changed <path> [<path> ...]
#
# LPD-003-1 (замер G0, 743 квитанции): полный прогон — 82% машинного слоя, и
# он же был входом по умолчанию для однофайловой правки. `--targeted` берёт
# набор из `.itd/IMPACT_GRAPH.json` через scripts/itd_regression_select.py
# (тот же аудированный источник, что и профили); неизвестный путь или битая
# карта = strict, то есть полный прогон, а не тихое сужение. `--fail-fast`
# прекращает доигрывание уже красного прогона (128 из 859 минут истории).
#
# Зелёно = exit 0 и «DONE fails:none». Скрипт зеркалит оба workflow
# (meta-review.yml + windows-verify.yml, их общую python-часть) и держится
# в синхроне с ними; при добавлении verify-теста в workflow — добавь его и
# сюда (drift ловится глазами ревью; авто-дрифт-гард — кандидат в backlog).
# Live-модель не вызывается локальным suite повторно: свежий сохранённый прогон
# replay-проверяет verify_live_model_benchmark; регулярный внешний запуск живёт
# в .github/workflows/fixture-smoke.yml и не имеет permanent-disable guard.
# =============================================================================
set -u
cd "$(dirname "$0")/.." || exit 1

PY="${PYTHON:-python3}"
"$PY" -c "print(1)" >/dev/null 2>&1 || PY=python

QUICK=0
FAIL_FAST="${ITD_RUNALL_FAIL_FAST:-0}"
TARGETED=0
CHANGED_QUOTED=""
CHANGED_COUNT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --quick) QUICK=1 ;;
    --fail-fast) FAIL_FAST=1 ;;
    --targeted) TARGETED=1 ;;
    --changed)
      shift
      while [ $# -gt 0 ]; do
        case "$1" in
          # `--` — конец опций в обычном смысле: ВСЁ, что после него, это
          # пути. Прежняя форма (`shift; break`) выходила из внутреннего
          # цикла и возвращала остаток внешнему разбору опций, поэтому
          # `--changed -- --dashed.py` падал с «unknown flag» — ровно тот
          # случай, ради которого `--` и вводился (находка cross-vendor
          # ревьюера; закрыта после ложного отчёта о закрытии в r29).
          --)
            shift
            while [ $# -gt 0 ]; do
              CHANGED_QUOTED="$CHANGED_QUOTED '$(printf '%s' "$1" | sed "s/'/'\\\\''/g")'"
              CHANGED_COUNT=$((CHANGED_COUNT + 1))
              shift
            done
            break
            ;;
          --*) break ;;
          *)
            CHANGED_QUOTED="$CHANGED_QUOTED '$(printf '%s' "$1" | sed "s/'/'\\\\''/g")'"
            CHANGED_COUNT=$((CHANGED_COUNT + 1))
            shift
            ;;
        esac
      done
      if [ "$CHANGED_COUNT" -eq 0 ]; then
        # `--changed` без путей раньше молча превращался в срез из git:
        # малформленный ввод трактовался как другой режим (находка
        # cross-vendor ревьюера).
        echo "WHY: --changed was given without any path"
        echo "FIX: name at least one path, or drop --changed to use the git slice"
        exit 2
      fi
      continue
      ;;
    *)
      echo "WHY: unknown flag $1"
      echo "FIX: use --quick, --fail-fast, --targeted [--changed <paths>]"
      exit 2
      ;;
  esac
  shift
done

fails=""
blocked=""
stopped_early=""
run_py() {
  local t="$1"
  # Уже остановились по --fail-fast: ничего не запускаем, но и не притворяемся
  # зелёными — итог печатается ниже вместе с именем сьюта-виновника.
  [ -n "$stopped_early" ] && return 0
  if [ ! -f "tests/$t.py" ]; then
    # Отсутствующий файл сьюта — такой же красный, как упавший сьют: без этого
    # --fail-fast доигрывал остаток прогона (находка cross-vendor ревьюера).
    echo "FAIL $t (required test file missing)"
    fails="$fails $t"
    if [ "$FAIL_FAST" = "1" ]; then
      stopped_early="$t"
      echo "STOP --fail-fast: first red suite is $t; the remaining suites are"
      echo "  not evidence of anything until this one is green."
    fi
    return 0
  fi
  case "$t" in
    verify_independent_review_efficacy)
      # The efficacy oracle refuses to trust a repository-supplied keyring: the
      # expected digest is host-owned input, so the runner must supply it and
      # fail closed when the host has not provisioned it.
      host_pin=".itd-memory/host-inputs/GPG-003_REVIEW_EFFICACY_KEYRING.sha256"
      if [ ! -f "$host_pin" ]; then
        # Отдельный КЛАСС, а не красный сьют: вход принадлежит хосту, а
        # `.itd-memory/` git-ignored, поэтому в изолированном дереве машинного
        # продюсера его нет по построению. Раньше это печаталось как FAIL и
        # было неотличимо от сломанного кандидата (LPD-003-1, false-red).
        # Код выхода остаётся ненулевым — молчаливый пропуск был бы false-green.
        echo "BLOCKED $t (host-owned input is not provisioned: $host_pin)"
        echo "  WHY: the verifier refuses a repository-supplied keyring digest;"
        echo "       the value belongs to the host, not to the candidate tree."
        echo "  FIX: provision the pin on this host, or declare it into the"
        echo "       isolated oracle run:"
        echo "       sh skills/_shared/itd_py.sh skills/_shared/itd_verification_loop.py \\"
        echo "         machine --root . --unit-id <unit> --risk-tier <tier> \\"
        echo "         --input $host_pin --command \"regression=bash tests/run-all.sh\""
        blocked="$blocked $t"
        return 0
      fi
      out=$("$PY" "tests/$t.py" --expected-keyring-sha256-file "$host_pin" 2>&1); rc=$?
      ;;
    *)
      out=$("$PY" "tests/$t.py" 2>&1); rc=$?
      ;;
  esac
  if [ $rc -ne 0 ]; then
    fails="$fails $t"
    echo "FAIL $t rc=$rc"
    # LPD002-A9: красный сьют называет свои упавшие проверки, а не только
    # хвост вывода — иначе флейк неотличим от дефекта и невоспроизводим
    # (verify_state_hardening 90/1 на R5: имя проверки не сохранилось).
    echo "$out" | grep -E '^(FAIL|FAILED)' | head -20
    echo "$out" | tail -6
    if [ "$FAIL_FAST" = "1" ]; then
      stopped_early="$t"
      echo "STOP --fail-fast: first red suite is $t; the remaining suites are"
      echo "  not evidence of anything until this one is green."
    fi
  fi
}

# Хвостовые проверки полного профиля. Они НЕ сьюты tests/verify_*.py, поэтому
# карта воздействия их не описывает и `mirror_suites()` про них не знает — но
# targeted-прогон обязан их исполнять, иначе правка scripts/verify_skill_profiles.py
# или scripts/sync-to-active.sh в targeted-режиме не проверялась бы ничем
# (находка cross-vendor ревьюера). Стоимость измерена: три проверки вместе
# укладываются в доли секунды, поэтому они гоняются всегда, а не по карте.
# --fail-fast их тоже охватывает.
run_tail() {
  [ -n "$stopped_early" ] && return 0
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    return 0
  fi
  echo "FAIL $name"
  fails="$fails $name"
  if [ "$FAIL_FAST" = "1" ]; then
    stopped_early="$name"
    echo "STOP --fail-fast: first red check is $name; the remaining checks are"
    echo "  not evidence of anything until this one is green."
  fi
}

run_tail_checks() {
  run_tail skill_profiles "$PY" scripts/verify_skill_profiles.py
  run_tail sync_verify bash scripts/verify-sync-to-active.sh
  run_tail snapshot "$PY" tests/verify_snapshot.py --all
}

# --- быстрый статический костяк (--quick) -----------------------------------
CORE="meta_review verify_triggers verify_gate_taxonomy verify_registration_and_counts verify_hook_table_completeness verify_host_adapters verify_cross_platform_runtime verify_session_hygiene_quality verify_live_model_benchmark verify_harness_conformance verify_tool_trust_inventory verify_practical_effectiveness verify_operational_cold_start verify_operational_continuation verify_bypass_friction verify_learning_loop verify_external_outcome_contract verify_external_pilot_collection verify_graduated_trust verify_all_hard_gate_host_parity verify_host_neutral_memory verify_fresh_session_resume verify_strict_completion_policy verify_completion_policy_calibration verify_observed_token_telemetry verify_efficiency_attribution verify_proportionality_benchmark verify_work_deadline_contract verify_goal_tools verify_verification_profiles verify_verification_loop verify_adjudication_channel verify_free_reviewer_producer verify_copilot_reviewer verify_reviewer_provider_freshness verify_independent_review_efficacy verify_api_reviewer verify_api_reviewer_curl_transport verify_external_reviewer_release verify_fail_closed_hygiene verify_review_broker_policy verify_review_broker_primitives verify_review_broker verify_review_broker_server verify_review_broker_operator verify_review_broker_deployment verify_github_app_manifest verify_machine_oracle verify_gate_control verify_gate_profile_doctor verify_gate_registry_profiles verify_gate_registry_isolation verify_push_gate_adjudicated verify_reviewer_independence_policy verify_gate_registry_binding verify_itd_cli verify_itd_runtime_install verify_git_gate_hooks verify_external_write_gate verify_model_risk_monotonic verify_model_policy_hint verify_work_deadline_docs verify_control_quality verify_harness_docs_freshness verify_predeploy_independent_review verify_predeploy_gate verify_blueprint_provenance_reviewer verify_scrubber_precision verify_sync_manifest verify_tree_pin_debris verify_review_evidence"
# --- полный python-набор обоих workflow --------------------------------------
FULL="verify_cmp_protocol verify_dod_gate verify_skill_enforcement verify_agent_review_sentinel \
verify_review_cache verify_review_sentinel_diffbind verify_risk_score \
verify_review_autoping verify_refute_fleet \
verify_dod_coverage verify_stall_fallback verify_feature_ledger \
verify_feature_ledger_completeness verify_feature_ledger_fallbacks \
verify_retro_abstention_review verify_feature_ledger_adoptions \
verify_init_contracts verify_review_report_file \
verify_state_hardening verify_source_read_contract \
verify_execution_trace_outcome \
verify_signal_attribution \
verify_verify_signal_and_watchdog \
verify_task_deployment_baseline \
verify_completion_signals_powershell \
verify_completion_signal_classes \
verify_task_contract_advisory \
verify_review_evalset \
verify_otel_export \
verify_platform_tmp_and_new_hooks verify_ledger_reconciliation verify_goal_bounded_autonomy verify_goal_five_star verify_retro_scan verify_completion_adversarial_corpus \
verify_v147_fixes verify_hook_depth verify_narration_final \
verify_verdict_contract verify_blind_protocol verify_worktree_hook_safety verify_hook_count_words \
verify_fable_snippets verify_routing verify_completion_gate \
verify_harness_map_fixtures verify_runall_drift \
verify_no_bare_python3 \
verify_unit_log verify_goal_verify_shell \
verify_project_checks verify_review_import verify_work_deadline_benchmark verify_authority_check verify_targeted_regression \
verify_stop_rule \
verify_adopt_context verify_brownfield_and_gate verify_commit_completeness_gate \
verify_cost_gate verify_cross_review_precommit verify_endpoint_regex \
verify_fresh_session_worktree verify_harness_demo_capture_schema \
verify_harness_demo_portable verify_incremental_diagnostics \
verify_mandatory_keyless_review verify_pii_egress verify_redteam_multihost \
verify_semantic_navigation verify_skill_completeness_gate verify_task_piv_lite"

# --- targeted-профиль (--targeted) ------------------------------------------
# Набор берётся из аудированной карты воздействия одним селектором; strict
# (rc=3) означает «сузить нельзя» и честно откатывает на полный прогон, а не
# печатает зелёное на пустом наборе.
if [ "$TARGETED" = "1" ]; then
  if [ "$CHANGED_COUNT" -gt 0 ]; then
    # Пути передаются позиционными аргументами, а не одной строкой: путь с
    # пробелом раньше разъезжался на два и молча менял срез (находка
    # cross-vendor ревьюера).
    eval "set -- $CHANGED_QUOTED"
    # `--format json` идёт ПЕРЕД `--changed --`: всё после `--` argparse
    # отдаёт в позиционный хвост, поэтому флаг, поставленный после путей,
    # был бы прочитан как ещё один путь. Сам `--` обязателен — без него
    # путь, начинающийся с дефисов, argparse примет за опцию.
    payload=$("$PY" scripts/itd_regression_select.py --format json --changed -- "$@" 2>&1); rc=$?
  else
    payload=$("$PY" scripts/itd_regression_select.py --changed-from-git --format json 2>&1); rc=$?
  fi
  if [ $rc -eq 0 ]; then
    selected=$(printf '%s' "$payload" | "$PY" -c 'import json,sys; print(" ".join(json.load(sys.stdin)["suites"]))')
    outside=$(printf '%s' "$payload" | "$PY" -c 'import json,sys; print(" ".join(json.load(sys.stdin)["outsideMirror"]))')
    count=$(printf '%s\n' $selected | grep -c .)
    echo "TARGETED: $count suites selected from .itd/IMPACT_GRAPH.json"
    if [ -n "$outside" ]; then
      # Названы, но НЕ прогнаны: этим сьютам нужен свой флаг, свой кандидат или
      # свой пин, и безусловный прогон дал бы false-red. Тихий пропуск был бы
      # false-green — поэтому граница гарантии печатается.
      echo "OUTSIDE-MIRROR (named, not run):$outside"
      echo "  WHY: the map links them to this change, but the mirror never runs"
      echo "       them - they need their own phase flag, candidate or pin."
      echo "  FIX: run each with its own context, or close the debt so the"
      echo "       mirror can run it unconditionally (BACKLOG: orphan suites)."
    fi
    noimpact=$(printf '%s' "$payload" | "$PY" -c 'import json,sys; print(" ".join(json.load(sys.stdin)["ruledNoImpact"]))')
    if [ -n "$noimpact" ]; then
      # Названы поимённо: исключение по правилу обязано быть видимым.
      echo "NO-IMPACT by rule (.itd/IMPACT_PATTERNS.json):$noimpact"
    fi
    for t in $selected; do run_py "$t"; done
    run_tail_checks
    echo "DONE fails:${fails:-none}${blocked:+ blocked:$blocked}${stopped_early:+ stopped-early:$stopped_early} mode:targeted"
    [ -z "$fails" ] && [ -z "$blocked" ] || exit 1
    exit 0
  fi
  # Печатается именно payload: на strict-ветке $selected ещё не присвоен, и
  # операторов раньше встречала пустая строка вместо WHY+FIX селектора.
  echo "$payload"
  # Профиль называется тот, который РЕАЛЬНО будет прогнан: с --quick strict
  # откатывается на CORE, и обещание «полное зеркало» было бы шире факта
  # (находка cross-vendor ревьюера).
  if [ "$QUICK" = "1" ]; then
    echo "TARGETED -> STRICT: falling back to the quick profile (CORE only,"
    echo "  because --quick was requested; drop --quick for the full mirror)."
  else
    echo "TARGETED -> STRICT: falling back to the full mirror (nothing is skipped)."
  fi
fi

for t in $CORE; do run_py "$t"; done
if [ "$QUICK" = "0" ]; then
  for t in $FULL; do run_py "$t"; done
  run_tail_checks
fi

# Честная граница зелёного: «DONE fails:none» означает «зеркало зелёное», а не
# «прогнаны все сьюты». Часть tests/verify_*.py по построению требует своего
# контекста (фаза, кандидат, релизный пин) и в зеркало не входит — LPD-003-1
# делает это число видимым, чтобы зелёная строка не читалась шире, чем есть.
# Сюда исполнение доходит ТОЛЬКО после полного зеркала: targeted-ветка со
# своим выбором заканчивается собственным exit выше, а strict-fallback
# намеренно проваливается сюда и гоняет всё. Прежнее условие по флагу
# `--targeted` было тавтологией и ничего не охраняло (находка ревьюера,
# LPD-003-1) — гарантию держит поток управления, и её проверяет поведенческий
# тест в tests/verify_targeted_regression.py, а не совпадение строки.
# Счёт обязан совпадать с тем, что РЕАЛЬНО прогнано: в --quick исполняется
# только CORE, и прежняя сумма CORE+FULL завышала покрытие — ровно тот класс
# переоценки, который эта строка и должна была закрыть (находка ревьюера,
# LPD-003-1, раунд 4).
# Числитель и знаменатель обязаны считать ОДНО И ТО ЖЕ множество: знаменатель
# перечисляет tests/verify_*.py, поэтому meta_review (не verify_-сьют, гоняется
# всегда) в числитель не входит — иначе строка сравнивала бы разные множества
# (находка ревьюера, LPD-003-1, раунд 5).
if [ "$QUICK" = "1" ]; then
  mirror_total=$(printf '%s\n' $CORE | grep -c '^verify_')
  mirror_label="quick profile"
else
  mirror_total=$(printf '%s\n' $CORE $FULL | grep -c '^verify_')
  mirror_label="full mirror"
fi
suites_total=$(ls tests/verify_*.py 2>/dev/null | grep -c .)
echo "MIRROR-COVERAGE: $mirror_total of $suites_total tests/verify_*.py run here ($mirror_label)"
echo "  (the rest need their own phase flag, candidate or release pin)"
echo "DONE fails:${fails:-none}${blocked:+ blocked:$blocked}${stopped_early:+ stopped-early:$stopped_early}"
# blocked = вход не предоставлен; это НЕ зелено (иначе false-green), но и не
# дефект кандидата — классы различаются машинно по строке выше.
[ -z "$fails" ] && [ -z "$blocked" ] || exit 1
