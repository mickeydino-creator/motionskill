# Motion Design Director: a Claude Code skill

This skill turns product photos, logos and a plain-language style brief into a finished, art-directed
motion-graphics video (MP4). It finds animation mechanics in the
[motionprompts.dev](https://motionprompts.dev/) library, adapts them to the brand, builds the animation
in HTML/GSAP/Three.js, renders it frame by frame with Playwright and FFmpeg, and checks the result.

## Install

- In this repo: the skill lives in `.claude/skills/motion-design-director/` and loads automatically
  when you run Claude Code here.
- For every project: `./install.sh` copies the skill to `~/.claude/skills/motion-design-director`.
  Use `./install.sh --link` to symlink it instead.

Requirements: Python 3 with Pillow and numpy, Node 18 or later, Playwright with Chromium, and FFmpeg with libx264.
Internet access is needed for the library and for npm (gsap/three are vendored into each project).

## Use

```
/motion-design-director ./photos/bottle.jpg ./brand/logo.png  premium futuristic ad, chrome, dramatic light, 10s 9:16
```
You can also just ask: *"Use the motion design skill. These are my product images. Create a premium,
futuristic advertisement with chrome materials, dramatic lighting, and smooth cinematic camera movement."*

Defaults: 10 s, 16:9, 1920×1080, 30 fps. Other supported ratios: 9:16, 1:1, 4:5.

## What's inside

```
.claude/skills/motion-design-director/
  SKILL.md                         workflow: intake -> images -> search -> select -> storyboard -> build -> render -> QA
  references/library-integration.md  verified REST + MCP surfaces, web->video translation, licence
  references/creative-direction.md   brief decomposition, candidate scoring, storyboard, craft rules
  references/rendering-workflow.md   time contract, render + QA loop, troubleshooting
  scripts/mp_catalog.py            library client: cached catalog, MCP search, prompt/source fetch, previews, credits
  scripts/inspect_assets.py        image analysis (palette, background, bbox), background cutout, resize
  scripts/new_project.sh           project scaffold with vendored gsap/three
  scripts/mdd-runtime.js           deterministic timeline contract (MDD.register / MDD.seek)
  scripts/render_video.mjs         HTML -> MP4 renderer with ffprobe verification + QA stills/contact sheet
  assets/template/                 starter scene (plumbing only)
```

## Licence note

The motionprompts.dev components and prompts are licensed under **PolyForm Noncommercial 1.0.0** and require attribution.
Commercial work needs a licence from them. By default the skill uses the library as a
*mechanic reference* and writes original code. It records every reference it uses in the project's `CREDITS.md`.
