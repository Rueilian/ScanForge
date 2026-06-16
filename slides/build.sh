#!/usr/bin/env bash
# Build the deck. Usage: build.sh [light]  (default dark). Output: ./main.pdf
#   dark  → tectonic(自帶套件/字型),否則 lualatex
#   light → lualatex(注入 \slidemode=light;tectonic 不便注入字串)
# 註:本機 TeX Live 2021 的 luaotfload 是手動補裝在 ~/texmf,lualatex 預設環境即可編。
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"; cd "$DIR"
MODE="${1:-dark}"
TECT="${TECTONIC:-$HOME/.local/bin/tectonic}"

run_lualatex() {  # $1 = 可選的 \def 前綴
  for _ in 1 2; do
    lualatex -interaction=nonstopmode -halt-on-error "${1}\\input{main}"
  done
}

if [[ "$MODE" == "light" ]]; then
  run_lualatex "\\def\\slidemode{light}"
elif [[ -x "$TECT" ]]; then
  "$TECT" -X compile main.tex --outdir . --keep-logs
else
  run_lualatex ""
fi

[[ -f main.pdf ]] || { echo "ERROR: no main.pdf produced" >&2; exit 1; }
if grep -qi "overfull" main.log 2>/dev/null; then
  echo "WARN: overfull boxes — check main.log (拆頁/縮圖,勿縮字)"
fi
echo "Wrote $DIR/main.pdf (mode=$MODE)"
