# AGENTS.md — Working Guide for AI Agents

This file tells any AI agent how to work effectively on the M365 Easy Button codebase.

---

## Architecture

M365 Easy Button is a **single-skill Copilot CLI plugin**. The runtime skill lives in `skills/m365-easy-button/SKILL.md`, and `plugin.json` makes the repository installable through the standard Copilot plugin flow. There are no sub-agents, no pipeline, no orchestration — just one comprehensive prompt that turns the Copilot CLI into a Google-to-Microsoft translator.

```
plugin.json
  └── Plugin metadata + skills path
skills/m365-easy-button/SKILL.md
  ├── Persona & tone rules
  ├── Answer format (Bridge → Steps → Next → Gotcha → Power Move → If This Fails)
  ├── App Router (30+ product mappings)
  ├── Mental Model Translations
  ├── Behavior Mapping tables (9 product areas)
  ├── Keyboard shortcut comparisons
  ├── Workflow translations (9 end-to-end tasks)
  ├── First Week Survival Guide
  ├── Power User Tips
  ├── AI Features comparison
  ├── Troubleshooting patterns (13)
  ├── CLI engagement elements (achievements, confidence meter, fun facts)
  └── Trigger phrases & activation
```

---

## File Ownership Map

| File | Purpose | Change Rules |
|------|---------|-------------|
| `plugin.json` | Plugin manifest | Required for normal `copilot plugin install` behavior. Keep metadata and the skills path accurate. |
| `skills/m365-easy-button/SKILL.md` | The runtime skill | Most critical file. Every edit affects runtime behavior. |
| `README.md` | Repo documentation | Keep in sync with SKILL.md coverage claims. |
| `SECURITY.md` | Vulnerability reporting | Update version table when releasing. |
| `CONTRIBUTING.md` | Contributor guide | Update if answer format or persona rules change. |
| `CHANGELOG.md` | Release history | Add entry for every meaningful SKILL.md change. |
| `.github/copilot-instructions.md` | Repo-specific Copilot rules | Rarely changes. |
| `.github/workflows/validate.yml` | CI validation | Update path and section checks if plugin layout or SKILL.md headings change. |

---

## Key Rules When Editing `skills/m365-easy-button/SKILL.md`

1. **Never break the translator persona.** The skill is a patient coworker, not tech support. Never say "it's easy" or "just do X."
2. **Every mapping starts from Google.** Even if the user didn't mention Google, the Bridge section connects to it.
3. **Be specific.** Menu paths, app names (web vs desktop), keyboard shortcuts. Vague advice helps no one.
4. **Stay neutral.** Never editorialize about Google vs Microsoft. Both have strengths.
5. **Stay in scope.** Day-to-day M365 apps only. No Azure/Intune/Entra admin deep-dives. Refer to IT for those.
6. **Keep tables consistent.** Google concept | Microsoft equivalent | Key difference.
7. **Test after editing.** Reinstall the plugin locally, restart the CLI session if needed, and query with real questions.

---

## How to Test Changes

```bash
# Install the plugin from the repo root
copilot plugin install .

# If you already have a personal copy of the skill, temporarily move it out of
# the way so it doesn't shadow the plugin during testing
mv ~/.copilot/skills/m365-easy-button ~/.copilot/skills/m365-easy-button.disabled

# Then test with:
# "easy button"
# "how do I share a file in OneDrive?"
# "what's the Microsoft version of Google Apps Script?"
# "I can't find my files in Teams"
#
# Restore the personal copy after testing, if you moved it:
# mv ~/.copilot/skills/m365-easy-button.disabled ~/.copilot/skills/m365-easy-button
```

Verify the skill responds with the Bridge → Steps → Next Step → Gotcha format and that the persona feels right.

---

## Common Pitfalls

- **Don't add Azure/Intune/Entra content.** That's out of scope. The skill explicitly refers users to IT for admin infrastructure.
- **Don't remove the Mental Model section.** It's the most innovative part — it explains *why* Microsoft feels different, not just *what* is different.
- **Don't hardcode dates or version numbers in SKILL.md.** The skill uses `web_search` to fetch current info.
- **Don't reintroduce a second canonical `SKILL.md`.** Keep `skills/m365-easy-button/SKILL.md` as the source of truth.
- **Don't duplicate product mappings.** Check the App Router table before adding a new one to a behavior mapping section.
- **Menu paths change frequently.** When updating steps, note whether they apply to web, desktop, or both.
