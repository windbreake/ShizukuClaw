# Changelog

All notable changes to M365 Easy Button will be documented in this file.

## [1.1.0] - 2026-03-06

### Added
- Root `plugin.json` manifest so the repository can be installed with the standard Copilot CLI plugin flow
- `skills/m365-easy-button/SKILL.md` plugin layout with required skill frontmatter

### Changed
- Replaced the incorrect `/skills add` install guidance with `copilot plugin install` / `/plugin install`
- Moved the canonical skill file into plugin layout and updated docs, contributor guidance, and CI validation to match
- Added testing guidance for personal-skill precedence so plugin verification does not produce false positives

## [1.0.0] - 2026-03-05

### Added
- Complete SKILL.md with 854 lines of Google→Microsoft translations
- 30+ product mappings (Gmail→Outlook, Drive→OneDrive/SharePoint, Apps Script→Power Automate, etc.)
- Mental Model Translations explaining why Microsoft feels structurally different
- Detailed behavior mapping tables for Email, Calendar, Files, Chat, Documents, Automation, BI, Tasks, Admin
- Keyboard shortcut comparisons (Gmail↔Outlook, Meet↔Teams, Docs↔Word, Sheets↔Excel)
- 9 end-to-end workflow translations (standup, doc review, external sharing, onboarding, project tracking, etc.)
- First Week Survival Guide with 10 day-one setup items
- Power User Tips for Outlook, Teams, OneDrive/SharePoint, Power Automate
- AI Features comparison (Google Workspace AI vs M365 Copilot) with licensing info
- 13 real-world troubleshooting patterns with step-by-step fixes
- Web search integration for fetching current Microsoft docs
- Voice Do/Don't table and Emotional Calibration for consistent persona
- "If This Fails" fallback section in answer format
- Example opening lines for common questions

### How It Was Built
- Havoc Hackathon with 14 AI models competing across 2 heats
- 6 finalists judged on completeness, depth, usability, persona fidelity, and innovation
- Final output synthesized from Claude Sonnet 4.6, Claude Opus 4.5, GPT-5.2, GPT-5.3 Codex, GPT-5.1, and Claude Sonnet 4.5
