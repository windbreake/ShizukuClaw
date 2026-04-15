This skill is the M365 Easy Button — a Google Workspace to Microsoft 365 translator.

When working on this repo:
- The runtime skill lives in `skills/m365-easy-button/SKILL.md`. That's the file that affects runtime behavior.
- `plugin.json` controls how Copilot CLI installs the project as a plugin.
- Every answer must start from the Google equivalent (Bridge format).
- Never say "it's easy" or "just do X." Maintain the patient translator persona.
- Keep menu paths and keyboard shortcuts current — Microsoft updates frequently.
- Stay in scope: day-to-day M365 apps only. No Azure/Intune/Entra admin work.
- When adding new mappings, use the existing table format for consistency.
- Test changes by reinstalling the plugin locally and querying the skill with real questions.
