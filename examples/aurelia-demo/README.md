# Example: AURELIA (test run of the skill)

The product and logo are **synthetic test images** made for this test. AURELIA is not a real brand.
Brief: *"premium, futuristic advertisement with chrome materials, dramatic lighting, smooth cinematic camera movement"*. 10 s, rendered at both 16:9 and 9:16 from the same `index.html`.

- `renders/`: the verified MP4s (H.264, 30 fps, 300 frames) and contact sheets
- `CREDITS.md`: the motionprompts.dev components used and the usage level of each one (this demo is noncommercial)

To re-render, vendor the libraries first and then render:
```
bash ../../.claude/skills/motion-design-director/scripts/new_project.sh . --three   # keeps index.html
node ../../.claude/skills/motion-design-director/scripts/render_video.mjs --project . --out out/a.mp4
```
