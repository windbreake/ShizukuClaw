---
name: 'Continual Learning'
description: 'Hooks that enable AI coding agents to learn, reflect, and persist knowledge across sessions'
tags: ['learning', 'memory', 'reflection', 'productivity', 'featured']
---

# Continual Learning Hook

Your agent forgets everything between sessions. This hook fixes that.

## Quick Start

```bash
cp -r hooks/continual-learning .github/hooks/
```

That's it. The hook auto-initializes on first session — no config, no setup, no manual steps.

## What It Does

- **Session start** — Loads learnings from previous sessions (global + this repo)
- **During session** — Tracks tool outcomes silently
- **Session end** — Reflects on patterns, stores insights, compacts old data

## Two-Tier Memory

| Scope | Location | What goes here |
|-------|----------|----------------|
| **Global** | `~/.copilot/learnings.db` | Tool patterns, cross-project insights |
| **Local** | `.copilot-memory/learnings.db` | Repo conventions, project-specific mistakes |

Global learnings follow you everywhere. Local learnings stay with the project.

Both auto-create on first run. Local memory only activates inside a git repo.

## How It Compounds

| Time | Effect |
|------|--------|
| Day 1 | Agent starts fresh — hook begins observing |
| Week 2 | Failure patterns detected, surfaced at session start |
| Month 2 | Rich context loaded — agent avoids known pitfalls |

Old low-value learnings decay automatically (60-day TTL, low hit count). High-value learnings persist and rank higher.

## Adding Learnings Manually

The agent can also write learnings directly using its built-in `store_memory` tool or SQL:

```sql
-- Agent writes a repo-specific learning
INSERT INTO learnings (scope, category, content, source)
VALUES ('local', 'mistake', 'Use semantic_configuration_name= not semantic_configuration=', 'user_correction');
```

## Architecture

```
learn.sh <event>          ← Single script handles all lifecycle events
    │
    ├── sessionStart      → Query both DBs, surface top learnings
    ├── postToolUse       → Log tool name + result (3ms overhead)
    └── sessionEnd        → Analyze patterns, persist insights, compact old data
```

## Disable

```bash
export SKIP_CONTINUAL_LEARNING=true
```

## Requirements

- `sqlite3` (pre-installed on macOS and most Linux)
- `jq` (optional — gracefully degrades without it)
