# Memory System Rules

## Layering
- Short-term memory: keep recent turns and active task details.
- Mid-term memory: keep episodic summaries of completed blocks and unresolved threads.
- Long-term memory: keep durable facts, user preferences, and stable decisions.

## Compression Policy
- Trigger compaction when short-term exceeds token budget.
- Summarize old chunks into mid-term memory without deleting key facts.
- Consolidate oversized mid-term memory into long-term memory periodically.

## Quality Rules
- Prefer factual points over wording style.
- Preserve unresolved tasks and explicit user requirements.
- Do not store sensitive secrets unless explicitly required by user.
