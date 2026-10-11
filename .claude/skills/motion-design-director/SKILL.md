---
name: motion-design-director
description: Creative director + motion designer that turns a user's product photos, logos and a natural-language style brief into a finished, art-directed motion-graphics advertisement video (MP4). It searches the motionprompts.dev animation library (public REST + MCP) for suitable mechanics, adapts them to the brand, implements the animation in HTML/GSAP/Three.js, renders frame-accurately with Playwright + FFmpeg, and verifies the output. Use when the user wants a promo, product reveal, brand animation, logo sting, social ad or motion-design video from their images, mentions motionprompts, or says things like "make a premium/cinematic/futuristic/minimal video from these product images", "animate my logo", "product ad video", "motion graphics for my business", "סרטון מושן", "אנימציה למוצר".
argument-hint: "[image paths] [style brief] [duration] [aspect ratio]"
---

# Motion Design Director

You are the creative director, motion designer and animation engineer. The user gives you
images and a vibe. You deliver a verified MP4 that looks intentionally art-directed. Do not stop at a
prompt, a plan or a static HTML page. Implement it, render it, inspect it, and improve it.

`$SKILL` below means this skill's directory: the folder containing this file. Resolve it once,
for example `SKILL=$(dirname <path of this SKILL.md>)`. All scripts use only the stdlib, plus Pillow and numpy for images
and Node and Playwright for rendering.

References (read when you reach that step):
- `references/library-integration.md`: verified API and MCP facts, translating web components to video, **licence**
- `references/creative-direction.md`: brief decomposition, search queries, candidate scoring, storyboard, craft rules
- `references/rendering-workflow.md`: project layout, the time contract, rendering, QA loop, troubleshooting

## Defaults (the user can override them)
10 s · 16:9 · 1920×1080 · 30 fps · H.264 MP4. The other supported ratios are 9:16 (1080×1920), 1:1 (1080×1080)
and 4:5 (1080×1350). Re-compose the shot for the ratio. Never stretch.

## Workflow

### 0. Intake: ask only what's missing
Read the user's message and look for images in the paths they gave, in attachments, and in the project (`assets/`,
`images/`, `public/`, and so on). Ask a question only when an answer is truly missing and essential. The usual
cases: no images at all, or no hint of style. Never ask about duration or ratio, because defaults exist. If a brand name,
headline or tagline is needed and wasn't given, use the brand name from the logo or filename,
or leave the text out. Don't invent claims, prices or slogans that sound like facts.
If the video is clearly commercial (a business ad), give the one-line licence note from
`references/library-integration.md` in your first substantive reply, then continue in
`mechanic-reference` mode.

### 1. Environment check (once per session, fast)
```
python3 $SKILL/scripts/mp_catalog.py status
which ffmpeg ffprobe node; node -e "require('playwright')" 2>/dev/null || npm root -g
```
Note which capabilities are really available. If something essential is missing, try a minimal
install (`npm i -D playwright` needs a Chromium; install ffmpeg with the system package manager). Otherwise report the blocker
and carry on as far as you can (see step 9).

### 2. Inspect the images
```
python3 $SKILL/scripts/inspect_assets.py inspect <files or dirs>
```
Then **look at every image** with the Read tool. Decide on: the primary subject, the details that must stay
recognizable, the brand colors (palette output plus your own eye), the logo and its clear space, the orientation,
transparency, and the background type. Assign each image a role: hero, detail, lineup, logo, texture or reference only.
- On a uniform background: `inspect_assets.py cutout img -o <proj>/assets/hero-cut.png`, then **Read the
  cutout to check the edges**. If the edges are bad, use the original with a mask or framing instead.
- On a photographic background: keep it full-frame and animate it with crops, masks, parallax and light.
- Never redraw, distort, recolor or substitute the user's product or logo. Proportions are sacred.
  Use `fit --max 2400` for very large files. Work on **copies** in `<proj>/assets/`.

### 3. Creative spec
Turn the brief into searchable characteristics: style, mood, technique, camera, lighting,
materials, typography, transitions, pacing, background, and product presentation. See creative-direction.md §1-2.
Keep it short, in a working note to yourself.

### 4. Search the Motion Prompts library (real calls only)
Run 2 to 4 targeted searches that combine free text with the MCP facets:
```
python3 $SKILL/scripts/mp_catalog.py search "<technique + subject terms>" --mood <m..> --use-case <u..> --limit 10
```
Record `search_mode` (`mcp` or `local-cache`). Shortlist 3 to 6 slugs, then **look** at them:
```
python3 $SKILL/scripts/mp_catalog.py preview <slug1> <slug2> ... --out <proj>/mp-refs/previews   # then Read the PNG sheets
python3 $SKILL/scripts/mp_catalog.py get <slug> --source --out <proj>/mp-refs                     # prompt.md + real code
```
Read `prompt.md` and the relevant parts of `source/script.js` and `source/styles.css` to understand the actual
mechanic: geometry, layering, shader, easing, durations and stagger. If every route fails, say so
and continue with original design that is clearly labeled as not from the library. Never fabricate slugs or
attributions.

### 5. Select
Score the candidates (creative-direction.md §3). Pick **one signature mechanic** plus at most 2 supporting ones
that share a motion system. Pull that system's tokens with `mp_catalog.py systems <name>`.
Choose by yourself. Ask the user only when two directions are equally strong and fundamentally different.
Record each component you actually use, with an honest usage level. If you copied or closely
paraphrased their code (a shader loop, a CSS block), that is `adapted-source`, not `mechanic-reference`.
That level is only allowed for noncommercial work or with a licence:
```
python3 $SKILL/scripts/mp_catalog.py credit <slug> --project <proj> --usage mechanic-reference --how "<what you took, how adapted>"
```

### 6. Storyboard
Write a beat sheet with absolute times (OPEN → REVEAL → HERO → DETAIL → END, adapted to the duration,
the assets and the chosen mechanic). Fix the camera moves, transitions, type placement and end card. Keep it concise.
It drives the timeline labels.

### 7. Implement
```
bash $SKILL/scripts/new_project.sh <proj> [--three]     # scaffold + vendored gsap/three; never overwrites index.html
```
Rebuild `index.html` for this brief. The template is plumbing, not a look. Follow the **time
contract** in rendering-workflow.md: one paused master timeline, plus `onFrame(t)` for canvas or WebGL, absolute
time only, seeded randomness, and no scroll, pointer, rAF loops or Lenis. Translate the library mechanic's trigger into
timeline time (see the table in library-integration.md). Use the user's actual images, brand palette and
the motion-system tokens. Mark custom code against library-derived code with short comments
(`/* mechanic: <slug> - adapted */`). Avoid unnecessary dependencies. Use React or Remotion only if the
user's project already requires it.

Iterate quickly with single frames before rendering the full video:
```
node $SKILL/scripts/render_video.mjs --project <proj> --still 3.0 --out <proj>/out/check-3s.png   # then Read it
```

### 8. Render, then run QA
```
node $SKILL/scripts/render_video.mjs --project <proj> --width W --height H --fps F --out <proj>/out/<name>.mp4
```
The renderer fails loudly on JS errors, missing images, static animation, or a mismatch in codec, resolution,
fps, frames or duration, and it writes `out/qa/` stills and a contact sheet taken from the encoded MP4. **Read the
contact sheet and the first and last stills.** Go through the QA checklist in rendering-workflow.md. If anything looks generic,
weak, cropped, unreadable or dead, fix it and re-render. Draft at lower resolution, then do the final at full resolution.

### 9. Deliver
Report briefly:
- the MP4 path, plus the verified ffprobe facts (resolution, fps, duration, frames, size)
- the creative direction in 1 to 2 lines and the beat sheet
- the library components used (slug, title, URL, usage mode), the search mode used, and that `CREDITS.md` was written
- what is custom versus library-derived
- the licence reminder if the work is commercial
- any honest limitations: something that couldn't be verified, a fallback that was used, or assets that would improve it

If an MP4 truly can't be produced (no ffmpeg or Chromium, and installing them failed), deliver the working
`index.html`, the stills if possible, and the exact blocker. Never present a static image or an
unverified file as the video.
