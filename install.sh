#!/usr/bin/env bash
# Install these skills for Claude Code.
#
#   ./install.sh                 → link into ~/.claude/skills (all projects on this machine)
#   ./install.sh /path/to/app    → link into /path/to/app/.claude/skills and add CLAUDE.md include
#   ./install.sh --copy [path]   → copy instead of symlink (for committing skills into a project)
#
# Symlinks mean `git pull` in this repo updates every project automatically.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="link"
if [[ "${1:-}" == "--copy" ]]; then MODE="copy"; shift; fi
TARGET_PROJECT="${1:-}"

if [[ -n "$TARGET_PROJECT" ]]; then
  PROJECT="$(cd "$TARGET_PROJECT" && pwd)"
  DEST="$PROJECT/.claude/skills"
else
  DEST="$HOME/.claude/skills"
fi
mkdir -p "$DEST"

installed=0; skipped=0
for skill in "$REPO_DIR"/skills/*/; do
  name="$(basename "$skill")"
  target="$DEST/$name"
  if [[ -e "$target" && ! -L "$target" ]]; then
    echo "  ! $target exists and is not a symlink — skipped (remove it to use this repo's version)"
    skipped=$((skipped + 1)); continue
  fi
  rm -f "$target"
  if [[ "$MODE" == "copy" ]]; then cp -r "$skill" "$target"; else ln -s "${skill%/}" "$target"; fi
  installed=$((installed + 1))
done
echo "✓ $installed skills ${MODE}ed into $DEST ($skipped skipped)"

if [[ -n "$TARGET_PROJECT" ]]; then
  CLAUDE_MD="$PROJECT/CLAUDE.md"
  MARKER="<!-- frappe-skills -->"
  if ! grep -q "$MARKER" "$CLAUDE_MD" 2>/dev/null; then
    { echo ""; echo "$MARKER"; cat "$REPO_DIR/index.md"; } >> "$CLAUDE_MD"
    echo "✓ Added skills guide to $CLAUDE_MD"
  else
    echo "• $CLAUDE_MD already has the skills guide"
  fi
  if [[ "$MODE" == "link" && -d "$PROJECT/.git" ]] && ! grep -qx ".claude/skills/frappe-\*" "$PROJECT/.gitignore" 2>/dev/null; then
    echo ".claude/skills/frappe-*" >> "$PROJECT/.gitignore"
    echo "✓ Ignored skill symlinks in $PROJECT/.gitignore"
  fi
else
  echo "Tip: add the contents of $REPO_DIR/index.md to ~/.claude/CLAUDE.md so every session knows when to use them."
fi
