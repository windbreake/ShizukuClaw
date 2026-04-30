#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# M365 Easy Button — one command, zero experience needed
# Installs GitHub Copilot CLI (if needed), adds the M365 Easy
# Button skill, and launches the CLI ready to go.
# ─────────────────────────────────────────────────────────────
set -euo pipefail

SKILL_REPO="DUBSOpenHub/m365-easy-button"
SKILL_NAME="m365-easy-button"
SKILL_DIR="$HOME/.copilot/skills/$SKILL_NAME"
SKILL_URL="https://raw.githubusercontent.com/$SKILL_REPO/main/skills/$SKILL_NAME/SKILL.md"

echo ""
echo "🟢 M365 Easy Button"
echo "─────────────────────────────────────────"

# ── Step 1: Install Copilot CLI if not present ──────────────
if command -v copilot >/dev/null 2>&1; then
  echo "✅ Copilot CLI already installed ($(copilot --version 2>/dev/null || echo 'installed'))"
else
  echo "📦 Installing GitHub Copilot CLI..."
  if [[ "$(uname)" == "Darwin" ]] || [[ "$(uname)" == "Linux" ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install copilot-cli
    else
      curl -fsSL https://gh.io/copilot-install | bash
    fi
  else
    echo "⚠️  Windows detected — please install manually:"
    echo "   winget install GitHub.Copilot"
    echo "   Then re-run this script."
    exit 1
  fi

  # Verify installation
  if ! command -v copilot >/dev/null 2>&1; then
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v copilot >/dev/null 2>&1; then
      echo "❌ Installation failed. Try manually: brew install copilot-cli"
      exit 1
    fi
  fi
  echo "✅ Copilot CLI installed!"
fi

# ── Step 2: Download the M365 Easy Button skill ────────────
echo "📥 Adding M365 Easy Button skill..."
mkdir -p "$SKILL_DIR"
if curl -fsSL "$SKILL_URL" -o "$SKILL_DIR/SKILL.md"; then
  echo "✅ Skill installed to $SKILL_DIR"
else
  echo "❌ Failed to download skill. Check your internet connection."
  exit 1
fi

# ── Step 3: Launch ──────────────────────────────────────────
echo ""
echo "─────────────────────────────────────────"
echo "🟢 Launching Copilot CLI..."
echo "   Just type: easy button"
echo "─────────────────────────────────────────"
echo ""

exec copilot < /dev/tty
