#!/bin/bash
# Continual Learning — single script, all events
# Usage: learn.sh <event>  (sessionStart | postToolUse | sessionEnd)
#
# Auto-initializes on first run. No manual setup needed.
# Two-tier memory: global (~/.copilot/learnings.db) + local (.copilot-memory/)

set -euo pipefail

[[ "${SKIP_CONTINUAL_LEARNING:-}" == "true" ]] && exit 0

EVENT="${1:-}"
INPUT=$(cat 2>/dev/null || echo "{}")

# --- Paths ---
GLOBAL_DB="$HOME/.copilot/learnings.db"
LOCAL_DIR=".copilot-memory"
LOCAL_DB="$LOCAL_DIR/learnings.db"

# --- Auto-init (creates everything on first run) ---
init_db() {
  local db="$1"
  mkdir -p "$(dirname "$db")"
  command -v sqlite3 &>/dev/null || return 0
  sqlite3 "$db" <<'SQL'
CREATE TABLE IF NOT EXISTS learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,          -- 'global' or 'local'
    category TEXT NOT NULL,       -- 'pattern', 'mistake', 'preference', 'tool_insight'
    content TEXT NOT NULL,
    source TEXT,                  -- repo name, session id, etc.
    created_at TEXT DEFAULT (datetime('now')),
    last_seen TEXT DEFAULT (datetime('now')),
    hit_count INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS tool_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_name TEXT,
    result TEXT,
    ts TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_learnings_scope ON learnings(scope);
CREATE INDEX IF NOT EXISTS idx_learnings_category ON learnings(category);
SQL
}

init_db "$GLOBAL_DB"
[[ -d ".git" ]] && init_db "$LOCAL_DB"

has_sqlite() { command -v sqlite3 &>/dev/null; }
has_jq() { command -v jq &>/dev/null; }
repo_name() { basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"; }

# ─── SESSION START ──────────────────────────────────────────
on_session_start() {
  has_sqlite || { echo "🧠 Continual learning active"; exit 0; }

  local context=""

  # Load global learnings (cross-project)
  local global_count
  global_count=$(sqlite3 "$GLOBAL_DB" "SELECT COUNT(*) FROM learnings;" 2>/dev/null || echo "0")
  if [[ "$global_count" -gt 0 ]]; then
    local top_global
    top_global=$(sqlite3 "$GLOBAL_DB" \
      "SELECT '• [' || category || '] ' || content FROM learnings
       ORDER BY hit_count DESC, last_seen DESC LIMIT 5;" 2>/dev/null || echo "")
    [[ -n "$top_global" ]] && context="Global learnings ($global_count total):\n$top_global"
  fi

  # Load local learnings (this repo)
  if [[ -f "$LOCAL_DB" ]]; then
    local local_count
    local_count=$(sqlite3 "$LOCAL_DB" "SELECT COUNT(*) FROM learnings;" 2>/dev/null || echo "0")
    if [[ "$local_count" -gt 0 ]]; then
      local top_local
      top_local=$(sqlite3 "$LOCAL_DB" \
        "SELECT '• [' || category || '] ' || content FROM learnings
         ORDER BY hit_count DESC, last_seen DESC LIMIT 5;" 2>/dev/null || echo "")
      [[ -n "$top_local" ]] && context="$context\n\nRepo learnings for $(repo_name) ($local_count total):\n$top_local"
    fi
  fi

  if [[ -n "$context" ]]; then
    echo "🧠 Continual learning — loaded prior knowledge"
    echo -e "$context" >&2
  else
    echo "🧠 Continual learning active — building knowledge from this session"
  fi
}

# ─── POST TOOL USE ──────────────────────────────────────────
on_post_tool_use() {
  has_sqlite || exit 0

  local tool_name="" result=""
  if has_jq; then
    tool_name=$(echo "$INPUT" | jq -r '.toolName // empty' 2>/dev/null || echo "")
    result=$(echo "$INPUT" | jq -r '.toolResult.resultType // "unknown"' 2>/dev/null || echo "unknown")
  fi
  [[ -z "$tool_name" ]] && exit 0

  # Log to global (tool patterns are cross-project)
  sqlite3 "$GLOBAL_DB" \
    "INSERT INTO tool_log (tool_name, result) VALUES ('$(echo "$tool_name" | tr "'" "''")','$result');" 2>/dev/null || true
}

# ─── SESSION END ────────────────────────────────────────────
on_session_end() {
  has_sqlite || { echo "🧠 Session ended"; exit 0; }

  # --- Analyze tool patterns ---
  local total failures
  total=$(sqlite3 "$GLOBAL_DB" \
    "SELECT COUNT(*) FROM tool_log WHERE ts > datetime('now','-4 hours');" 2>/dev/null || echo "0")
  failures=$(sqlite3 "$GLOBAL_DB" \
    "SELECT COUNT(*) FROM tool_log WHERE result='failure' AND ts > datetime('now','-4 hours');" 2>/dev/null || echo "0")

  # Detect repeated failure patterns → store as global learning
  local fail_tools
  fail_tools=$(sqlite3 "$GLOBAL_DB" \
    "SELECT tool_name FROM tool_log
     WHERE result='failure' AND ts > datetime('now','-4 hours')
     GROUP BY tool_name HAVING COUNT(*) > 2;" 2>/dev/null || echo "")

  if [[ -n "$fail_tools" ]]; then
    while IFS= read -r tool; do
      [[ -z "$tool" ]] && continue
      local safe_tool
      safe_tool=$(echo "$tool" | tr "'" "''")
      # Upsert: increment hit_count if learning already exists
      sqlite3 "$GLOBAL_DB" \
        "INSERT INTO learnings (scope, category, content, source)
         SELECT 'global','tool_insight','Tool \"$safe_tool\" frequently fails — check usage pattern','auto:$(date -u +%Y%m%d)'
         WHERE NOT EXISTS (SELECT 1 FROM learnings WHERE content LIKE '%$safe_tool%frequently fails%');
         UPDATE learnings SET hit_count = hit_count + 1, last_seen = datetime('now')
         WHERE content LIKE '%$safe_tool%frequently fails%';" 2>/dev/null || true
    done <<< "$fail_tools"
  fi

  # --- Compact: prune old tool logs (keep 7 days) ---
  sqlite3 "$GLOBAL_DB" "DELETE FROM tool_log WHERE ts < datetime('now','-7 days');" 2>/dev/null || true

  # --- Compact: decay old learnings (>60 days, low hit count) ---
  sqlite3 "$GLOBAL_DB" \
    "DELETE FROM learnings WHERE last_seen < datetime('now','-60 days') AND hit_count < 3;" 2>/dev/null || true
  [[ -f "$LOCAL_DB" ]] && sqlite3 "$LOCAL_DB" \
    "DELETE FROM learnings WHERE last_seen < datetime('now','-60 days') AND hit_count < 3;" 2>/dev/null || true

  echo "🧠 Session reflected — tools: $total, failures: $failures"
  [[ -n "$fail_tools" ]] && echo "  ⚠️ Stored failure patterns for: $(echo "$fail_tools" | tr '\n' ', ')"
}

# ─── Dispatch ───────────────────────────────────────────────
case "$EVENT" in
  sessionStart)   on_session_start ;;
  postToolUse)    on_post_tool_use ;;
  sessionEnd)     on_session_end ;;
  *)              echo "Usage: learn.sh <sessionStart|postToolUse|sessionEnd>" >&2; exit 1 ;;
esac

exit 0
