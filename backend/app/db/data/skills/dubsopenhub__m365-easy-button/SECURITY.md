# Security Policy 🔒

## Supported Versions

| Version | Supported |
| ------- | --------- |
| v1.1.x  | ✅ |
| < v1.1  | ❌ |

## Reporting a Vulnerability

**Do not open a GitHub issue for security vulnerabilities.**

If you discover a security vulnerability (for example: prompt injection susceptibility, context contamination, or sensitive data exposure in skill responses), please report it privately.

### Preferred channel

- **GitHub Security Advisories** (if enabled on the repository)

### What to include

- A clear description of the issue
- Steps to reproduce
- Potential impact
- Any proof-of-concept artifacts

## Response Timeline

- **Acknowledgment:** within 48 hours
- **Assessment:** within 1 week
- **Resolution:** depends on severity; critical issues are prioritized

## Scope

**In scope:**
- Prompt safety and injection resistance
- Skill responses that could expose sensitive org configuration details
- Misleading guidance that could cause data loss or security misconfiguration

**Out of scope:**
- Vulnerabilities in GitHub Copilot CLI itself
- Vulnerabilities in underlying LLM providers
- Inaccurate Microsoft 365 product information (file an issue instead)
