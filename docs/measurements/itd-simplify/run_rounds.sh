#!/bin/bash
# Repeated hook-bench rounds of the ITD simplification baseline (plan session 3, ADR-016): the section-8 commands of
# docs/measurements/ITD-SIMPLIFY-BASELINE.md, interleaved round by round over four combinations (WSL x ITD,
# WSL x buying, Windows x buying, Windows x ITD; each start after the WSL 1-minute load settles below 1.5), then the
# transcript stats. Summary: summarize_rounds.py <raw dir> <phase>... (baseline section 9).
# Owner's two-host stand: the paths below are the owner's WSL and Windows layout.
# Usage: bash run_rounds.sh <phase, e.g. before|after> [rounds per combination, default 3]
#        (RAW = output dir, default .itd-memory/host-inputs/ITD-PLAN-S3; SINCE = transcript window, default 2026-10-14)
set -u
PHASE=${1:?phase, e.g. before|after}
RUNS=${2:-3}
ROOT=/home/hihol/projects/idea-to-deploy
RAW=${RAW:-$ROOT/.itd-memory/host-inputs/ITD-PLAN-S3}
T=$ROOT/docs/measurements/itd-simplify
PY=/mnt/c/Users/Дмитрий/AppData/Local/Programs/Python/Python312/python.exe
SINCE=${SINCE:-2026-10-14}
WIN_TR="/mnt/c/Users/Дмитрий/.claude/projects/C--Users---------AI-buying"
mkdir -p "$RAW" /mnt/c/itd-src/baseline
cmp -s "$T/hook_bench.py" /mnt/c/itd-src/baseline/hook_bench.py || cp "$T/hook_bench.py" /mnt/c/itd-src/baseline/hook_bench.py
META=$RAW/meta-$PHASE.txt
: > "$META"
settle() { python3 -c 'import os,time
t=time.time()
while os.getloadavg()[0] >= 1.5 and time.time()-t < 900: time.sleep(5)
print(round(os.getloadavg()[0],2))'; }
T_ITD=$(ls -t ~/.claude/projects/-home-hihol-projects-idea-to-deploy/*.jsonl | sed -n 2p)
T_BUY=$(wslpath -w "$(ls -t "$WIN_TR"/*.jsonl | head -1)")
win_bench() {  # <windows project> <out>
  ( cd "$(wslpath -u "$1")" && "$PY" -X utf8 'C:\itd-src\baseline\hook_bench.py' --home 'C:/Users/Дмитрий/.claude' \
      --project "$1" --bash 'C:/Program Files/Git/bin/bash.exe' --runs 10 --transcript "$T_BUY" > "$2" 2>&1 )
}
for r in $(seq 1 "$RUNS"); do
  for combo in wsl-itd wsl-buying win-buying win-itd; do
    out="$RAW/bench-$PHASE-$combo-r$r.jsonl"
    echo "$combo r$r load_before=$(settle) at $(date -u +%FT%TZ) uptime=$(cut -d' ' -f1 /proc/uptime)" >> "$META"
    case $combo in
      wsl-itd) python3 -I -B "$T/hook_bench.py" --home ~/.claude --project "$ROOT" --runs 10 --transcript "$T_ITD" \
                 > "$out" 2>&1 ;;
      wsl-buying) python3 -I -B "$T/hook_bench.py" --home ~/.claude --project "/mnt/c/Users/Дмитрий/AI/buying" \
                 --runs 10 > "$out" 2>&1 ;;
      win-buying) win_bench 'C:/Users/Дмитрий/AI/buying' "$out" ;;
      win-itd) win_bench 'C:/itd-src/idea-to-deploy-1.109.2' "$out" ;;
    esac
    echo "$combo r$r exit=$? load_after=$(cut -d' ' -f1 /proc/loadavg)" >> "$META"
  done
done
python3 -I -B "$T/transcript_stats.py" ~/.claude/projects/-home-hihol-projects-idea-to-deploy --since "$SINCE" \
  > "$RAW/transcripts-$PHASE-wsl-itd.json" 2>&1; echo "transcripts-wsl-itd exit=$?" >> "$META"
python3 -I -B "$T/transcript_stats.py" "$WIN_TR" --since "$SINCE" > "$RAW/transcripts-$PHASE-win-buying.json" 2>&1
echo "transcripts-win-buying exit=$?" >> "$META"
echo "done $(date -u +%FT%TZ)" >> "$META"
