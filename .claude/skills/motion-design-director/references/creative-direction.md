# Creative direction: brief → search → storyboard → motion

## 1. Decompose the brief into searchable characteristics

Write down a short spec before searching. Unknowns stay unknown. Don't invent a brand story.

- Visual style and mood: map it to MCP `mood` values (minimal, elegant, luxury, editorial, bold, playful,
  corporate, retro, futuristic, experimental, cinematic, brutalist, organic, technical).
- Animation technique: mask reveal, clip-path wipe, split-text line reveal, 3D tunnel, image
  shader distortion, parallax layers, stacked cards, carousel, morph, particle field, liquid or glass refraction.
- Camera: static lock-off, slow push-in, orbit, dolly through layers, crane, rack focus (blur).
- Lighting: dramatic rim light, softbox, spotlight sweep, specular glint pass, volumetric beam.
- Materials: chrome, brushed metal, glass, liquid, paper, fabric, matte.
- Typography: serif editorial, grotesk minimal, condensed display, mono technical, chrome type.
- Transitions: hard cut on beat, mask wipe, zoom-through, light-leak or flash, match cut.
- Pacing: calm luxury (long holds, 1.2 to 2 s moves), punchy social (0.3 to 0.6 s moves, cuts every 1 to 1.5 s).
- Background: void black, seamless white, gradient sweep, environment photo, abstract shader.
- Product presentation: hero float, turntable illusion, exploded or detail crops, lineup, packshot end card.

Turn the spec into 2 to 4 search queries. Combine free text with facets:
```
mp_catalog.py search "product reveal dramatic light" --mood luxury cinematic --use-case hero product-showcase
mp_catalog.py search "text reveal split lines mask" --use-case text-reveal --mood minimal elegant
mp_catalog.py search "image reveal clip-path wipe" --use-case image-reveal
mp_catalog.py search "webgl shader distortion background" --use-case background --mood futuristic
```
Searches run in Spanish or English and ignore accents. Category describes the look. `motion.trigger` and
`native_system` describe how a component moves.

## 2. Style → mechanic starting points (use as search hints, not answers)

- Luxury or cosmetics: long eased reveals (`power4.inOut`, 1.2 to 2 s), mask or curtain wipes, serif
  line reveals, specular sweep over the product, generous negative space, warm metallic accent.
- Apple-style minimal: seamless light background, product centered, slow push-in, big grotesk
  headline word-by-word, one feature callout at a time, nothing decorative.
- Futuristic or chrome: dark void, rim-light gradients, WebGL shader background (at most one), chrome
  type with a gradient-mapped sheen sweep, scanline or grid accents used sparingly.
- Liquid glass: blurred refraction layer (`backdrop-filter` or a shader), soft caustic highlights moving
  slowly, rounded glass cards over the product, a cool palette.
- Editorial: grid-based layout, image crops that change on beats, small caps and mono captions,
  clip-path reveals, asymmetric composition.
- Dark cinematic: letterboxed framing, light sweeps, slow dolly, grain (seeded), title card ending.
- Exploded view: the user needs several angle or part images, or you separate layers from one cutout.
  Stagger the parts outward along vectors, hold, then reassemble.
- Clean white packshot: soft contact shadow, gentle float (sine via `onFrame`), crisp type.

## 3. Evaluate candidates (score 1 to 5 and keep a short written note)

For each shortlisted slug (3 to 6), look at the contact sheet from `preview` and read `prompt.md`:
1. Style match with the brief.
2. Fit with the actual images. Does it need cutouts? Several images? Portrait images?
3. Relevance to the product or business.
4. Translatability to time-driven video (see library-integration.md). Prefer `load`, `scroll`
   scrub, and `webgl-raf` mechanics, which map cleanly.
5. Compatibility with the other picks: same or near motion system, at most one full-viewport WebGL.
6. Implementation cost within the render budget. Heavy WebGL renders on SwiftShader (CPU) in
   headless mode, so keep the shader simple at 1080p.

Pick **one primary mechanic** (the signature move) plus 0 to 2 supporting ones (a text reveal, a
transition). The result should be cohesive and art-directed, not a sampler of effects. Ask the user only if
two directions are equally strong and would produce substantially different films.

## 4. Storyboard template (adapt it, don't force it)

Write a beat sheet with absolute times. Example for 10 s:
```
0.0-1.5  OPEN     void + light bloom builds; tension
1.2-3.5  REVEAL   signature mechanic reveals the product (library mechanic X)
3.5-6.0  HERO     product hold with slow camera move + light sweep; headline line reveal
6.0-8.0  DETAIL   2nd image / feature words / detail crop (if assets allow)
8.0-10.0 END      packshot + logo + tagline; hold ≥1.2 s still-ish for readability
```
Scale it with the duration: about 6 s means OPEN, REVEAL and END. 15 to 30 s adds DETAIL beats and a
mid transition. 9:16 needs bigger type and vertical stacking, with the product in the upper-middle and text lower.

## 5. Motion craft rules

- Use one motion-system token set (`mp_catalog.py systems <name>`). Good defaults: `curtain-toggle` for
  luxury or editorial reveals, `entry-veil` for dramatic openers, `reveal-on-enter` for calm minimal pieces,
  `scrub-lagged` for flythrough or tunnel scrubs translated to time.
- Overlap moves by 20 to 40 %. Nothing should start from a dead stop after another move ends.
- Always keep something alive: a slow push-in (scale 1 to 1.04) or drift during holds. A frozen frame longer than 1 s
  reads as broken, unless it is the end card.
- Avoid bounce and elastic for premium work. Use `power2` to `power4` and `expo`, or custom bezier tokens.
- Reveal text by line or word with masks (`overflow: hidden` + `yPercent`). Don't fade whole paragraphs in.
- Keep at most 2 typefaces, a strong scale contrast, and text inside the 90 % safe area. Hold text at least 1.5 s per
  6 words.
- Keep the product sharp at its hero moment. Never scale a raster past about 100 % of its native pixels in
  the final frame. Blur and motion only during transitions.
- Keep the logo undistorted with clear space around it. Never recolor it unless it is a single-color mark and
  the brief asks for it.
- Use the palette from `inspect_assets.py`. The accent comes from the product or logo, not from a random
  gradient.
- Avoid: rainbow gradients, lens-flare spam, particles with no purpose, more than 3 transition types, stock
  "AI glow", centered everything in every beat.
