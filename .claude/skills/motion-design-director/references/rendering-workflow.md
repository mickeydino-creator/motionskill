# Implementation and rendering workflow

## Project layout (created by `scripts/new_project.sh <dir> [--three]`)
```
<dir>/index.html        the film (one page = one video), opens in a browser as a looping preview
<dir>/mdd-runtime.js    deterministic time contract (MDD.register / MDD.seek)
<dir>/assets/           COPIES of the user's images, cutouts, fonts
<dir>/vendor/gsap/      gsap.min.js, CustomEase, SplitText, MotionPathPlugin (UMD, global `gsap`)
<dir>/vendor/three/     three.module.js + jsm/ addons (with --three; use an import map)
<dir>/mp-refs/          fetched library prompts/sources/previews (reference only)
<dir>/out/              video.mp4 + qa/ stills + contact sheet
<dir>/CREDITS.md        library components used (written by mp_catalog.py credit)
```

## The time contract (critical)

The renderer does not play the page in real time. For every frame it calls
`await MDD.seek(i / fps)` and takes a screenshot. So:

- Build **one paused GSAP master timeline** and pass it in: `MDD.register({ duration, fps, timeline: tl })`.
  Nest scene timelines with `tl.add(sceneTl, "label")`.
- Canvas, WebGL or three.js: put the drawing in `onFrame(t, p)` and derive everything from absolute `t`.
  Call `renderer.render(scene, camera)` inside `onFrame`. Do **not** start your own rAF loop. To animate
  three.js values with GSAP, tween plain objects or uniforms on the master timeline and render in `onFrame`.
- Async setup (textures, GLTF, fonts): wrap it in `MDD.waitFor(promise)` before registering.
  `MDD.ready` already waits for `document.fonts` and every `<img>`.
- Randomness: `const rnd = MDD.random(42)`. Generate it once at setup, not per frame.
- CSS `@keyframes` and transitions are frozen at `t`, but tie them to absolute time and avoid them for
  anything important. Prefer GSAP.
- No scroll, pointer, hover, `Date.now()`, `performance.now()`, `setTimeout` choreography, or Lenis.
- Preview: open `index.html` served over http to see it loop in real time. `?t=4.5` freezes on a frame
  and `?debug` shows timecode.

## Aspect ratios

Render resolution equals the viewport. Size everything in `vmin`, `vw` or `vh`, and use
`[data-orientation="portrait|landscape|square"]` (set by the runtime) to re-layout:
- 16:9 → 1920×1080. 9:16 → 1080×1920. 1:1 → 1080×1080. 4:5 → 1080×1350.
- Re-compose the shot for each ratio. Don't stretch it. In portrait, stack the product above the text, make the type
  larger relative to width, and keep the product within the central 80 % of the width.

## Render

```
node $SKILL/scripts/render_video.mjs --project <dir> --width 1920 --height 1080 --fps 30 \
     --out <dir>/out/<name>.mp4 [--duration 10] [--audio track.mp3] [--stills 0,1.5,4,9.9]
```
- Single-frame check while iterating, which is fast: `--still 4.2 --out <dir>/out/f4.png`
- Draft render: `--width 960 --height 540 --frame-format jpeg`, or `--start 3 --end 6`.
- Output is H.264 (libx264), yuv420p, CRF 18, +faststart. It plays everywhere.
- Speed: about 4 to 6 frames/s at 720p for DOM scenes. WebGL on SwiftShader is slower, so keep shaders modest.
  A 10 s, 1080p, 30 fps render takes about 1 to 3 min. Run long renders in the background.

What the renderer verifies automatically, with a non-zero exit code if any check fails:
- page errors, console errors, failed requests, HTTP ≥ 400, images that failed to load
- a static-animation check: the distinct-frame ratio and the longest frozen run
- ffprobe: the container is MP4, the codec is h264, and resolution, fps, frame count and duration match
- QA stills (first, 25 %, 50 %, 75 %, last, or `--stills`) plus `qa/contact-sheet.png`, extracted
  **from the encoded MP4**

## QA loop (do it, don't skip it)

1. Read `qa/contact-sheet.png` and the first and last stills with the Read tool.
2. Check: Is the product recognizable and sharp at the hero beat? Is the logo intact and not cropped?
   Is the text readable and inside the safe area? Is anything empty or black where it shouldn't be?
   Does it look art-directed or generic? Does the end card hold?
3. Check timing from the renderer log. Is the longest identical run longer than about 1.2 s outside the end card?
   That's a dead spot. Is anything popping in a single frame? Use `--still` around the beat.
4. Fix, then re-render. Iterate at least once if anything looks weak. Use lower-resolution drafts for iterations
   and do the final render at full resolution.

## Troubleshooting

- `page never called MDD.register`: a script error happened before registration. Check the "problems" list.
- Blank WebGL: the context failed. The renderer launches with SwiftShader flags. Use `preserveDrawingBuffer: true`
  on the renderer if frames come out empty.
- Fonts differ between preview and render: self-host them in `assets/fonts` with `@font-face`, and make sure
  `document.fonts.ready` resolves (use the font once in the DOM).
- Huge images slow the render: `inspect_assets.py fit img -o assets/x.jpg --max 2400`.
- No Playwright or Chromium: `npm i -D playwright` in the project (needs Chromium). There is no ffmpeg:
  install it with the system package manager. If neither can be installed, report the blocker, and deliver
  the working `index.html` plus stills if possible. Never deliver a fake MP4.
- Something gets dimmed or covered unexpectedly: any element with `transform`, `filter` or `opacity` below 1 creates a
  stacking context, so a `::before` with `z-index:-1` inside it can still cover earlier siblings. Fade such
  backings in only during their beat. This is exactly the kind of bug the 9:16 QA pass catches.
- A long render dies with "Target page, context or browser has been closed": the process was killed, often because a background job was
  stopped. Run the final render in the foreground (Bash timeout up to 10 min), or split it with `--start`/`--end`.
- Remotion is not required. Use it only if the user's project already runs Remotion.
