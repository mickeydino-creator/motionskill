#!/usr/bin/env bash
# Build dist/motion-design-director.zip: an upload-ready skill archive (for claude.ai / Claude apps
# "Upload skill", or any tool that takes a zipped skill folder).
# Contains only the skill folder with SKILL.md at its root. No symlinks, no plugin manifest,
# no caches. Only the standard frontmatter fields (name, description) are kept.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$ROOT/plugins/motion-design-director"
OUT="$ROOT/dist/motion-design-director.zip"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
DEST="$TMP/motion-design-director"
mkdir -p "$DEST" "$ROOT/dist"
# -L dereferences any symlink into a real file, so the archive never contains links
(cd "$SRC" && find . -type f ! -path './.claude-plugin/*' ! -path '*/__pycache__/*' ! -name '*.pyc' ! -name '.DS_Store' -print0 \
  | while IFS= read -r -d '' f; do mkdir -p "$DEST/$(dirname "$f")"; cp -L "$f" "$DEST/$f"; done)
# keep only standard frontmatter keys
python3 - "$DEST/SKILL.md" <<'PY'
import re, sys
p = sys.argv[1]; s = open(p, encoding="utf-8").read()
m = re.match(r"---\n(.*?)\n---\n", s, re.S)
keep = [l for l in m.group(1).splitlines() if re.match(r"(name|description):", l)]
open(p, "w", encoding="utf-8").write("---\n" + "\n".join(keep) + "\n---\n" + s[m.end():])
PY
rm -f "$OUT"
(cd "$TMP" && zip -q -r -X "$OUT" motion-design-director)
if zipinfo "$OUT" | awk '{print $1}' | grep -q '^l'; then echo "ERROR: symlink in archive" >&2; exit 1; fi
echo "built $OUT ($(du -h "$OUT" | cut -f1), $(zipinfo -1 "$OUT" | grep -vc '/$') files)"
