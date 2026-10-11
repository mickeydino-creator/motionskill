# Motion Prompts library integration

Verified against https://motionprompts.dev/developers/ and `/llms.txt` on 2026-10-11.
All surfaces are public, read-only and key-free. Re-verify with `mp_catalog.py status`
before you rely on them, since this file can go stale.

## Verified surfaces

REST, static JSON, rate limit 30 req/s per IP with burst 60, 429 + `Retry-After`:
- `/api/v1/components.json` returns all components (248 at verification) with `motion` metadata
  (trigger, libs, engine, complexity, cluster, ease_family, duration_range, native_system,
  motion_signature, assets_required), `capabilities`, `conflicts_with`, and URLs
  (`page`, `prompt`, `demo`, `thumb`, `preview` webm).
- `/api/v1/motion-systems.json` returns 8 motion systems with ease/duration/stagger tokens taken from real code.
- `/api/v1/composition-rules.json` returns the hard and soft rules for composing several components on one *web page*.
- `/prompts/<slug>.md` returns the build prompt for one component as markdown.
- `/api/v1/openapi.json` returns the OpenAPI 3.1 spec.

MCP, `https://motionprompts.dev/mcp`, Streamable HTTP, stateless, no auth. `tools/list` returned these tools:
`search_components` (free text + facets mood/useCase/level/category/deps/maxPerfCost/mobileSafe),
`get_component` (include meta|preview|prompt|source; `source` is the REAL index.html/styles.css/script.js),
`list_facets`, `list_components`, `list_motion_systems`, `get_motion_system`,
`search_components_motion` (by trigger/libs/complexity/system), `get_integration_contract`,
`plan_imagery`, `plan_page`, `suggest_mechanics`, `suggest_page_treatments`,
`get_component_prompt` (verbatim prompt + motion-system tokens + adaptation instruction).
`render_prompt` is deprecated.

`scripts/mp_catalog.py` calls the MCP endpoint directly with plain JSON-RPC POSTs, so no MCP
client registration is needed. If the user has registered the server
(`claude mcp add --transport http motionprompts https://motionprompts.dev/mcp`), the
`mcp__motionprompts__*` tools work too, and either route is fine.

## mp_catalog.py commands

```
python3 $SKILL/scripts/mp_catalog.py status                      # cache age + REST/MCP reachability
python3 $SKILL/scripts/mp_catalog.py search "<brief terms>" --mood luxury cinematic --use-case hero product-showcase --limit 10
python3 $SKILL/scripts/mp_catalog.py search "<terms>" --local    # offline search over cached components.json
python3 $SKILL/scripts/mp_catalog.py preview <slug> <slug> --out <proj>/mp-refs/previews   # contact sheets to LOOK at
python3 $SKILL/scripts/mp_catalog.py get <slug> --source --out <proj>/mp-refs               # prompt.md + real source + meta.json
python3 $SKILL/scripts/mp_catalog.py systems [name]              # motion-system tokens
python3 $SKILL/scripts/mp_catalog.py mcp <tool> '<json args>'    # any verified MCP tool, e.g. list_facets
python3 $SKILL/scripts/mp_catalog.py credit <slug> --project <proj> --usage mechanic-reference --how "..."
```

Search facets that MCP accepts:
- mood: minimal elegant luxury editorial bold playful corporate retro futuristic experimental cinematic brutalist organic technical
- useCase: hero preloader page-transition navigation footer gallery slider card-deck scroll-story image-reveal text-reveal hover-interaction cursor-effect logo background product-showcase marquee team-section cta contact

How the cache works: `~/.cache/motion-design-director/*.json` holds the catalog with a 7-day TTL. You can override
the location with `MDD_CACHE_DIR` and the TTL with `MDD_CACHE_TTL`. The whole catalog is a single request of about 600 KB, so never fetch
per-component JSON in a loop. If a refresh fails, the stale cache is used and a warning goes to stderr.
Every search result carries `source: "mcp"` or `"local-cache"`, and the output carries
`search_mode`. Report the actual mode to the user.

## Honest-failure rules

- If `status` shows both REST and MCP unreachable and there is no cache, say so plainly. Then proceed with
  original motion design, and label it as **not from the library**.
- Never invent a slug. `get` and `credit` refuse unknown slugs on purpose.
- Never say a mechanic "comes from motionprompts" unless you fetched that component's prompt or source
  in this session, or it appears in the cached catalog.

## The library is web-first, so translate it to video

These components are complete web demo pages. They are driven by scroll, wheel, pointer, hover,
click or load, and they often depend on Lenis or ScrollTrigger. A video has one input, which is time. Take the
**mechanic** (the geometry, the layering, the shader, the reveal choreography, the easing and timing)
and drive it from the master timeline:

- `scroll` / `wheel` scrub (ScrollTrigger `scrub`, Lenis): progress = timeline time over a segment. Replace
  `onUpdate(self.progress)` with a tween on a proxy object, or compute it in `onFrame(t)`. Drop Lenis and ScrollTrigger completely.
- Scrub with lag (`scrub: 1`, lerp): ease the proxy tween (`power2.out`) instead of lerping per frame. Lerp loops depend on
  frame time and are not deterministic.
- `load` (preloaders, text reveals, entry veils): mostly works as-is. Make sure the timeline is the paused master, not autoplay.
  Replace `setTimeout`/`Date.now()` counters with tweens.
- `pointer` / cursor-follow / hover: script a camera or "virtual cursor" path with keyframes (a proxy `{x,y}` tweened on the
  timeline, MotionPath, or a sine path seeded from MDD.random).
- `click` / step-advance sliders: step through the states at fixed beats on the timeline (labels such as `slide2`).
- rAF loops (`webgl-raf`, `raf-lerp`, `physics`): move the per-frame update into `onFrame(t)`, using **absolute t**. Never use
  deltas or `clock.getDelta()`. Ping-pong feedback simulations (fluid sims) are stateful: replace them with a closed-form
  function of t, or pre-simulate with a fixed step and index by frame.
- `Math.random()`: `MDD.random(seed)`.

What still applies from the composition rules in a video: use **one motion system** (its tokens) for the
whole piece, allow **at most one full-viewport WebGL** context, and don't stack two entry veils. The
scroll-owner, document-height and fixed-bar rules are web-page concerns and do not apply.

Known contract gaps reported by the library itself (llms.txt):
- 194 of 248 components use absolute `/c/<slug>/…` asset paths. Never hotlink them, and replace them with the
  user's images anyway.
- No CSS scoping. Scope the selectors when you merge two components.
- The source uses bare `import gsap from "gsap"` specifiers. In this skill, use the vendored UMD
  `vendor/gsap/gsap.min.js` (global `gsap`) or an import map for three.

## Licence: tell the user, don't bury it

The components and prompts use the **PolyForm Noncommercial 1.0.0** licence with **mandatory visible attribution**
to motionprompts.dev. Commercial use needs a separate licence from them (contact@vanguardia.dev).
Business and brand advertisements are usually commercial use. So:

1. For any commercial or client job, say this once, briefly, in your first substantive reply.
2. The default usage mode is **`mechanic-reference`**. You study the prompt and source to understand the mechanic, then write
   original code for the video. You do not copy their code verbatim. The `credit` command still records the
   reference in `CREDITS.md`.
3. Use `adapted-source` or `verbatim-source` (copying real code from `get --source`) only when the user
   confirms noncommercial use or holds a commercial licence. Keep the notice and credit motionprompts.dev.
4. This is not legal advice. If the stakes matter, tell the user to check the licence text.

GSAP (vendored from npm) is free for commercial use under its standard licence. three.js is MIT-licensed.
