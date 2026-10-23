#!/bin/bash
# Repeated hook-bench rounds of the ITD simplification baseline (plan session 3, ADR-016): the section-8 commands of
# docs/measurements/ITD-SIMPLIFY-BASELINE.md, interleaved round by round over four combinations (WSL x ITD,
# WSL x buying, Windows x buying, Windows x ITD; each start after the WSL 1-minute load settles below 1.5), then the
# transcript stats. Summary: summarize_rounds.py <raw dir> <phase>... (baseline section 9).
# A round whose load does not settle within 900 s is skipped and logged as load_timeout; that and any nonzero step
# exit make the script exit 1, and summarize_rounds.py rejects the phase from the same meta-<phase>.txt records.
# Owner's two-host stand: the paths below are the owner's WSL and Windows layout.
# The Windows rounds run a copy of hook_bench.py (WIN_SRC); a copy that cannot be refreshed would measure stale code,
# so a failed refresh stops the script with exit 1 before any round.
# Usage: bash run_rounds.sh <phase, e.g. before|after> [rounds per combination, default 3]
#        (RAW = output dir, default .itd-memory/host-inputs/ITD-PLAN-S3; SINCE = transcript window, default 2026-10-14;
#        WIN_SRC = WSL path of the Windows copy, default /mnt/c/itd-src/baseline)
set -u
FAILED=0
PHASE=${1:?phase, e.g. before|after}
RUNS=${2:-3}
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
RAW=${RAW:-$ROOT/.itd-memory/host-inputs/ITD-PLAN-S3}
T=$ROOT/docs/measurements/itd-simplify
PY=/mnt/c/Users/Дмитрий/AppData/Local/Programs/Python/Python312/python.exe
SINCE=${SINCE:-2026-10-14}
WIN_TR="/mnt/c/Users/Дмитрий/.claude/projects/C--Users---------AI-buying"
WIN_SRC=${WIN_SRC:-/mnt/c/itd-src/baseline}
mkdir -p "$RAW" || exit 1
cmp -s "$T/hook_bench.py" "$WIN_SRC/hook_bench.py" || { mkdir -p "$WIN_SRC" && cp "$T/hook_bench.py" "$WIN_SRC/hook_bench.py" \
  && cmp -s "$T/hook_bench.py" "$WIN_SRC/hook_bench.py"; } || { echo "cannot refresh $WIN_SRC/hook_bench.py" >&2; exit 1; }
META=$RAW/meta-$PHASE.txt
: > "$META"
settle() { python3 -c 'import os,sys,time
t=time.time()
while os.getloadavg()[0] >= 1.5:
    if time.time()-t >= 900:
        print(round(os.getloadavg()[0],2)); sys.exit(1)
    time.sleep(5)
print(round(os.getloadavg()[0],2))'; }
T_ITD=$(ls -t ~/.claude/projects/-home-hihol-projects-idea-to-deploy/*.jsonl | sed -n 2p)
T_BUY=$(wslpath -w "$(ls -t "$WIN_TR"/*.jsonl | head -1)")
win_bench() {  # <windows project> <out>
  ( cd "$(wslpath -u "$1")" && "$PY" -X utf8 "$(wslpath -w "$WIN_SRC/hook_bench.py")" --home 'C:/Users/Дмитрий/.claude' \
      --project "$1" --bash 'C:/Program Files/Git/bin/bash.exe' --runs 10 --transcript "$T_BUY" > "$2" 2>&1 )
}
for r in $(seq 1 "$RUNS"); do
  for combo in wsl-itd wsl-buying win-buying win-itd; do
    out="$RAW/bench-$PHASE-$combo-r$r.jsonl"
    if ! load=$(settle); then
      echo "$combo r$r load_timeout load=$load at $(date -u +%FT%TZ)" >> "$META"
      FAILED=1
      continue
    fi
    echo "$combo r$r load_before=$load at $(date -u +%FT%TZ) uptime=$(cut -d' ' -f1 /proc/uptime)" >> "$META"
    case $combo in
      wsl-itd) python3 -I -B "$T/hook_bench.py" --home ~/.claude --project "$ROOT" --runs 10 --transcript "$T_ITD" \
                 > "$out" 2>&1 ;;
      wsl-buying) python3 -I -B "$T/hook_bench.py" --home ~/.claude --project "/mnt/c/Users/Дмитрий/AI/buying" \
                 --runs 10 > "$out" 2>&1 ;;
      win-buying) win_bench 'C:/Users/Дмитрий/AI/buying' "$out" ;;
      win-itd) win_bench 'C:/itd-src/idea-to-deploy-1.109.2' "$out" ;;
    esac
    rc=$?
    echo "$combo r$r exit=$rc load_after=$(cut -d' ' -f1 /proc/loadavg)" >> "$META"
    [ "$rc" -eq 0 ] || FAILED=1
  done
done
python3 -I -B "$T/transcript_stats.py" ~/.claude/projects/-home-hihol-projects-idea-to-deploy --since "$SINCE" \
  > "$RAW/transcripts-$PHASE-wsl-itd.json" 2>&1
rc=$?; echo "transcripts-wsl-itd exit=$rc" >> "$META"; [ "$rc" -eq 0 ] || FAILED=1
python3 -I -B "$T/transcript_stats.py" "$WIN_TR" --since "$SINCE" > "$RAW/transcripts-$PHASE-win-buying.json" 2>&1
rc=$?; echo "transcripts-win-buying exit=$rc" >> "$META"; [ "$rc" -eq 0 ] || FAILED=1
echo "done $(date -u +%FT%TZ) failed=$FAILED" >> "$META"
exit "$FAILED"
