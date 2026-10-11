#!/usr/bin/env bash
# new_project.sh <dir> [--three] [--three-addons]
# Scaffold a motion-design-director video project:
#   <dir>/index.html        starter scene (from assets/template) wired to the MDD runtime
#   <dir>/mdd-runtime.js    deterministic timeline contract (copied, not linked)
#   <dir>/assets/           put the user's images here (copies, never move originals)
#   <dir>/vendor/           gsap (+ three with --three, + examples/jsm addons with --three-addons) from npm,
#                           so renders work offline
#   <dir>/out/              renders + QA stills
# Never overwrites an existing index.html.
set -euo pipefail
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="${1:?usage: new_project.sh <dir> [--three] [--three-addons]}"
WANT_THREE=0; WANT_ADDONS=0
for a in "${@:2}"; do
  case "$a" in --three) WANT_THREE=1 ;; --three-addons) WANT_THREE=1; WANT_ADDONS=1 ;; esac
done

mkdir -p "$DIR"/{assets,vendor,out}
cp "$SKILL_DIR/scripts/mdd-runtime.js" "$DIR/mdd-runtime.js"
if [[ -e "$DIR/index.html" ]]; then
  echo "index.html exists - left untouched"
else
  cp "$SKILL_DIR/assets/template/index.html" "$DIR/index.html"
  [[ -e "$DIR/assets/placeholder.svg" ]] || cp "$SKILL_DIR/assets/template/placeholder.svg" "$DIR/assets/"
fi

# Vendor libraries locally (cached in ~/.cache so repeated projects don't re-download).
CACHE="${MDD_CACHE_DIR:-$HOME/.cache/motion-design-director}/npm"
mkdir -p "$CACHE"
PKGS=(gsap); [[ $WANT_THREE == 1 ]] && PKGS+=(three)
need=0
for p in "${PKGS[@]}"; do [[ -d "$CACHE/node_modules/$p" ]] || need=1; done
if [[ $need == 1 ]]; then
  (cd "$CACHE" && { [[ -f package.json ]] || npm init -y >/dev/null; } && npm i --no-audit --no-fund "${PKGS[@]}" >/dev/null) \
    || echo "WARN: npm install failed - fall back to CDN <script> tags (cdn.jsdelivr.net) in index.html"
fi
if [[ -d "$CACHE/node_modules/gsap" ]]; then
  mkdir -p "$DIR/vendor/gsap"
  cp "$CACHE"/node_modules/gsap/dist/{gsap.min.js,CustomEase.min.js,SplitText.min.js,MotionPathPlugin.min.js} "$DIR/vendor/gsap/" 2>/dev/null || true
  echo "gsap $(node -p "require('$CACHE/node_modules/gsap/package.json').version") -> vendor/gsap"
fi
if [[ $WANT_THREE == 1 && -d "$CACHE/node_modules/three" ]]; then
  mkdir -p "$DIR/vendor/three"
  cp "$CACHE"/node_modules/three/build/{three.module.js,three.core.js} "$DIR/vendor/three/" 2>/dev/null || cp "$CACHE"/node_modules/three/build/three.module.js "$DIR/vendor/three/"
  [[ $WANT_ADDONS == 1 ]] && cp -r "$CACHE/node_modules/three/examples/jsm" "$DIR/vendor/three/jsm"  # ~10 MB: GLTFLoader, EffectComposer...
  echo "three $(node -p "require('$CACHE/node_modules/three/package.json').version") -> vendor/three (import map: three -> ./vendor/three/three.module.js)"
fi
echo "project ready: $DIR"
