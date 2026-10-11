# Spotify: kinetic type spec ad with music (16:9, 15 s)

> **Unofficial spec work.** This is a portfolio exercise made to demonstrate the skill. It is not affiliated with, sponsored by or endorsed by Spotify. Spotify and the Spotify logo are trademarks of Spotify AB. The logo file is **not** included in this repository, and the copy ("Press play on every mood", "Listen now") was written for this exercise.

![contact sheet](renders/contact-sheet.jpg)

**Brief:** *"Make it 16:9 with this logo, with music, 15 seconds."*

**What the skill did:**
- Removed the background from the new logo and checked the edges.
- Generated an **original synthesised music bed** with `make_music.py`: 120 BPM, A minor, drop at 5 s, snare roll at 11 to 12 s, impact at 12 s. No samples and no copyrighted music.
- Cut every visual hit to that grid. It uses the same two library mechanics as the 9:16 version, plus beat flashes and an impact end card.

**Beats:**
- 0 to 5 s: stretch words.
- 5 s drop: the logo slams in with shock rings and the marquees run.
- 9.5 to 11.5 s: one genre per beat.
- 11.5 to 12 s: squeeze to white.
- 12 to 15 s: logo, wordmark and CTA.

QA fixed a leftover word under the drop, undersized flash words, an off-centre end card, and a text/logo overlap.

**Render:** [`spotify-16x9-music.mp4`](renders/spotify-16x9-music.mp4) (H.264 + AAC stereo). Credits: [`CREDITS.md`](CREDITS.md).

**Re-render:**
```
python3 ../../plugins/motion-design-director/scripts/make_music.py --out assets/music.wav --duration 15 --bpm 120 --drop 5 --impact 12
# add your own transparent logo as assets/logo-cut@3x.png (not shipped)
bash ../../plugins/motion-design-director/scripts/new_project.sh .
node ../../plugins/motion-design-director/scripts/render_video.mjs --project . --audio assets/music.wav --out out/a.mp4
```
