#!/usr/bin/env bash
# check_files.sh -- Post-write integrity check for a web-project-starter app.
# Run after any file modification. Exit code 0 = all clear; non-zero = failures found.
# Usage: ./check_files.sh
# From project root (the "app" folder this starter was cloned into): bash check_files.sh
#
# Blueprint modules and templates are auto-discovered under app/blueprints/
# and app/templates/ -- nothing here needs editing per-project. See
# check_structure.py's docstring for the discovery convention.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dir="${BASH_SOURCE[0]}"&&echo "$(dirname "$dir")")" && pwd)"
cd "$SCRIPT_DIR"

FAIL=0

# -- Discover blueprint .py modules and template .html files the same way
#    check_structure.py does, for the quick existence/syntax pass below.
mapfile -t PY_FILES < <(find app/blueprints -mindepth 2 -maxdepth 2 -name '*.py' -not -path '*/__pycache__/*' 2>/dev/null | sort)
mapfile -t HTML_FILES < <(find app/templates -name '*.html' 2>/dev/null | sort)

check_html() {
  local file="$1"; local min_lines=10
  if [ ! -f "$file" ]; then
    echo "MISSING  $file"
    FAIL=1; return
  fi
  local lines
  lines=$(wc -l < "$file")
  local tail_content
  tail_content=$(tail -3 "$file")
  if [ "$lines" -lt "$min_lines" ]; then
    echo "TRUNCATED  $file  ($lines lines, expected >=$min_lines)"
    FAIL=1
  elif ! echo "$tail_content" | grep -Eq '</html>|endblock'; then
    echo "BAD TAIL  $file  (last 3 lines contain neither </html> nor endblock)"
    echo "          actual tail: $(tail -1 "$file")"
    FAIL=1
  else
    echo "OK  $file  ($lines lines)"
  fi
}

check_python() {
  local file="$1"; local min_lines=3
  if [ ! -f "$file" ]; then
    echo "MISSING  $file"
    FAIL=1; return
  fi
  local lines
  lines=$(wc -l < "$file")
  if [ "$lines" -lt "$min_lines" ]; then
    echo "TRUNCATED  $file  ($lines lines, expected >=$min_lines)"
    FAIL=1; return
  fi
  local result
  result=$(python3 -c "import ast; ast.parse(open('$file').read()); print('OK')" 2>&1)
  if [ "$result" != "OK" ]; then
    echo "SYNTAX ERR  $file: $result"
    FAIL=1
  else
    echo "OK  $file  ($lines lines)"
  fi
}

echo "=== Web project file integrity check ==="
echo ""

echo "-- Templates (auto-discovered under app/templates/) --"
if [ "${#HTML_FILES[@]}" -eq 0 ]; then
  echo "  (none found yet)"
else
  for f in "${HTML_FILES[@]}"; do check_html "$f"; done
fi

echo ""
echo "-- Python modules (auto-discovered under app/blueprints/) --"
if [ "${#PY_FILES[@]}" -eq 0 ]; then
  echo "  (none found yet)"
else
  for f in "${PY_FILES[@]}"; do check_python "$f"; done
fi

echo ""
echo "-- Reference docs (one level up, in the project root -- outside this git repo) --"
check_html_or_doc() {
  # Reference docs are plain markdown -- just confirm they exist and aren't empty.
  local file="$1"; local min_lines="$2"
  if [ ! -f "$file" ]; then
    echo "MISSING  $file"
    FAIL=1; return
  fi
  local lines
  lines=$(wc -l < "$file")
  if [ "$lines" -lt "$min_lines" ]; then
    echo "TRUNCATED  $file  ($lines lines, expected >=$min_lines)"
    FAIL=1
  else
    echo "OK  $file  ($lines lines)"
  fi
}
check_html_or_doc "../CLAUDE.md"           30
check_html_or_doc "../PROJECT_STATE.md"    20
check_html_or_doc "../STANDING_RULES.md"   30
check_html_or_doc "../SESSION_LOG.md"      10
check_html_or_doc "../CLAUDE_problems.md"  10

echo ""
echo "-- Structural integrity --"
if ! python3 "$(dirname "$0")/check_structure.py"; then FAIL=1; fi

echo ""
echo "-- CSS coverage --"
if ! python3 "$(dirname "$0")/check_css.py"; then FAIL=1; fi

echo ""
echo "-- JS function coverage --"
if ! python3 "$(dirname "$0")/check_js.py"; then FAIL=1; fi

echo ""
echo "-- Route smoke test --"
if ! python3 "$(dirname "$0")/check_routes.py"; then FAIL=1; fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "=== ALL FILES OK ==="
else
  echo "=== FAILURES DETECTED -- do not deploy ==="
  exit 1
fi
