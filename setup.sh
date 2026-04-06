#!/bin/bash
#
# obsidian-wiki setup — configures skill discovery for all supported AI agents.
#
# Usage: bash setup.sh
#
# What it does:
#   1. Creates .env from .env.example (if not present)
#   2. Symlinks .skills/* into each agent's expected skills directory:
#      - .claude/skills/    (Claude Code)
#      - .cursor/skills/    (Cursor)
#      - .windsurf/skills/  (Windsurf)
#      - .agents/skills/    (Antigravity / generic agents)
#   3. Prints a summary of what's ready
#
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILLS_DIR="$SCRIPT_DIR/.skills"

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║         obsidian-wiki — Agent Setup              ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Step 1: .env ──────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
  cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
  echo "✅  Created .env from .env.example"
  echo "    → Edit .env and set OBSIDIAN_VAULT_PATH before using skills."
else
  echo "✅  .env already exists"
fi

# ── Step 2: Symlink skills into agent directories ─────────────
AGENT_DIRS=(
  ".claude/skills"
  ".cursor/skills"
  ".windsurf/skills"
  ".agents/skills"
)

for agent_dir in "${AGENT_DIRS[@]}"; do
  target="$SCRIPT_DIR/$agent_dir"
  mkdir -p "$target"

  for skill in "$SKILLS_DIR"/*/; do
    skill_name="$(basename "$skill")"
    link_path="$target/$skill_name"

    if [ -L "$link_path" ]; then
      # Already a symlink — update it
      rm "$link_path"
    elif [ -d "$link_path" ]; then
      # Real directory exists — skip to avoid data loss
      echo "⚠️   $agent_dir/$skill_name is a real directory, skipping symlink"
      continue
    fi

    ln -s "$skill" "$link_path"
  done

  echo "✅  Symlinked skills → $agent_dir/"
done

# ── Step 3: Summary ──────────────────────────────────────────
SKILL_COUNT=$(ls -d "$SKILLS_DIR"/*/ 2>/dev/null | wc -l | tr -d ' ')

echo ""
echo "───────────────────────────────────────────────────"
echo " Setup complete!"
echo ""
echo " Skills found:    $SKILL_COUNT"
echo " Agents ready:    Claude Code, Cursor, Windsurf, Antigravity/Gemini"
echo ""
echo " Bootstrap files:"
echo "   CLAUDE.md       → Claude Code"
echo "   GEMINI.md       → Gemini / Antigravity"
echo "   AGENTS.md       → Codex / OpenAI"
echo "   .cursor/rules/  → Cursor"
echo "   .windsurf/rules/ → Windsurf"
echo "   .github/copilot-instructions.md → GitHub Copilot"
echo ""
echo " Next steps:"
echo "   1. Set OBSIDIAN_VAULT_PATH in .env"
echo "   2. Open this project in your agent"
echo "   3. Say: \"Set up my wiki\""
echo "───────────────────────────────────────────────────"
echo ""
