#!/usr/bin/env bash
# Manual alternative to the plugin marketplace: install the skill as a personal Claude Code skill
# (~/.claude/skills),
# so it is available in every project. Use --link to symlink instead of copying (keeps it in sync
# with this repo). Re-running updates the installed copy.
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/plugins/motion-design-director"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/motion-design-director"
mkdir -p "$(dirname "$DEST")"
if [[ -e "$DEST" || -L "$DEST" ]]; then
  if [[ -L "$DEST" ]]; then rm "$DEST"; else rm -rf "$DEST"; fi
fi
if [[ "${1:-}" == "--link" ]]; then ln -s "$SRC" "$DEST"; else cp -R "$SRC" "$DEST"; fi
chmod +x "$DEST"/scripts/*.py "$DEST"/scripts/*.sh "$DEST"/scripts/*.mjs
echo "installed: $DEST"
command -v ffmpeg >/dev/null || echo "note: ffmpeg not found - needed for MP4 export"
node -e "require('playwright')" 2>/dev/null || [[ -d "$(npm root -g 2>/dev/null)/playwright" ]] || echo "note: playwright not found - run 'npm i -g playwright' (needs Chromium)"
python3 -c "import PIL, numpy" 2>/dev/null || echo "note: pip install pillow numpy (image inspection/cutouts)"
