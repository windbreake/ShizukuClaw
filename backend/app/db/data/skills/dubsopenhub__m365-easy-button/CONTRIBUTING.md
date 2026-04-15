# Contributing to 🟢 M365 Easy Button

Thanks for helping make the Google-to-Microsoft transition smoother for everyone.

## Core Principles

1. **Translator, not advocate.** Never editorialize about Google vs Microsoft. Both have strengths. Your job is to bridge them.
2. **Start from Google.** Every mapping, workflow, and gotcha should connect to the Google equivalent first.
3. **Be specific.** Menu paths, app names (web vs desktop), keyboard shortcuts. Vague advice helps no one.
4. **Never say "it's easy."** If someone is asking, it's not easy for them.
5. **Stay in scope.** Day-to-day M365 apps only. No Azure/Intune/Entra admin deep-dives.

## What to Contribute

- **New product mappings** — Missing Google→Microsoft translations
- **Workflow translations** — Task-by-task guides ("I need to...")
- **Keyboard shortcuts** — Side-by-side comparisons
- **Troubleshooting patterns** — Real-world "it's not working" scenarios with fixes
- **Gotchas** — Things that work differently than expected
- **Corrections** — Menu paths change frequently; keep them current

## How to Contribute

1. Fork the repo and create a branch: `update/<topic>`
2. Edit `skills/m365-easy-button/SKILL.md` directly — it's the runtime skill
3. Follow the existing format (tables, Bridge→Steps→Gotcha structure)
4. Open a PR with a clear description of what you added or changed

## Testing Your Changes

Install your modified plugin locally:

```bash
copilot plugin install .
```

If you already have a personal copy at `~/.copilot/skills/m365-easy-button`, temporarily move it out of the way before testing so the plugin version is actually used.

Restart your Copilot CLI session if needed and test with queries like:
- "How do I share a file externally in OneDrive?"
- "What's the Microsoft version of Google Apps Script?"
- "I can't find my files in Teams"

Verify the skill responds with the Bridge→Steps→Next Step→Gotcha format.
