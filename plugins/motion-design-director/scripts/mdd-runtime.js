/*
 * mdd-runtime.js - deterministic timeline contract for motion-design-director videos.
 *
 * The page registers ONE master description of time:
 *
 *   MDD.register({
 *     duration: 10,            // seconds (required)
 *     fps: 30,                 // optional, renderer can override
 *     timeline: tl,            // optional paused GSAP timeline (master)
 *     onFrame: (t, p) => {},   // optional: draw canvas / three.js for absolute time t (s), progress p 0..1
 *   });
 *
 * The renderer (render_video.mjs) then calls `await MDD.seek(t)` for every frame and
 * screenshots. Nothing may depend on wall-clock time, requestAnimationFrame deltas,
 * Math.random() without a seed, scroll, pointer or hover. Use MDD.random(seed) for noise.
 *
 * In a normal browser (preview) the runtime plays the timeline in real time and loops,
 * so the same file is both the preview and the render source. Add ?t=4.2 to freeze on a
 * frame, ?debug to show a timecode overlay.
 */
(function () {
  const params = new URLSearchParams(location.search);
  const state = { cfg: null, rendering: !!window.__MDD_RENDER__, errors: [] };
  window.addEventListener("error", (e) => state.errors.push(String(e.message || e)));
  window.addEventListener("unhandledrejection", (e) => state.errors.push("unhandled: " + String(e.reason)));

  function waitImages() {
    const imgs = Array.from(document.images);
    return Promise.all(
      imgs.map((img) =>
        (img.complete ? Promise.resolve() : new Promise((r) => { img.onload = img.onerror = r; }))
          .then(() => (img.decode ? img.decode().catch(() => {}) : null))
          .then(() => { if (!img.naturalWidth) state.errors.push("image failed to load: " + img.currentSrc); })
      )
    );
  }

  const extraWaits = [];

  const MDD = {
    get rendering() { return state.rendering; },
    /** Register work that must finish before frame 0 (textures, models, fonts). */
    waitFor(promise) { extraWaits.push(promise); return promise; },
    register(cfg) {
      if (!cfg || !(cfg.duration > 0)) throw new Error("MDD.register needs a positive duration");
      state.cfg = Object.assign({ fps: 30 }, cfg);
      if (cfg.timeline) cfg.timeline.pause(0);
      if (window.gsap) {
        // Disconnect GSAP from wall-clock so only seek() moves time.
        gsap.ticker.lagSmoothing(0);
        if (state.rendering) gsap.ticker.sleep();
      }
      if (!state.rendering) MDD.ready.then(startPreview);
    },
    ready: null,
    info() {
      const c = state.cfg || {};
      return { duration: c.duration, fps: c.fps, width: innerWidth, height: innerHeight, errors: state.errors.slice() };
    },
    /** Put the whole page into the exact state for absolute time t (seconds). */
    async seek(t, settle = true) {
      const c = state.cfg;
      if (!c) throw new Error("MDD.register was never called");
      t = Math.max(0, Math.min(t, c.duration));
      if (c.timeline) c.timeline.time(t, false);
      // Web Animations / CSS animations: freeze at t (they must be authored for absolute time).
      for (const a of document.getAnimations()) { try { a.pause(); a.currentTime = t * 1000; } catch (_) {} }
      for (const v of document.querySelectorAll("video")) { v.pause(); v.currentTime = Math.min(t, v.duration || t); }
      if (c.onFrame) await c.onFrame(t, t / c.duration);
      // Let layout/paint settle: two animation frames.
      if (settle) await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    },
    /** Seeded PRNG (mulberry32) - use instead of Math.random for deterministic frames. */
    random(seed = 1) {
      let a = seed >>> 0;
      return function () {
        a |= 0; a = (a + 0x6d2b79f5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
      };
    },
    /** Helpers for aspect-aware layout: 'landscape' | 'portrait' | 'square'. */
    get orientation() {
      const r = innerWidth / innerHeight;
      return r > 1.15 ? "landscape" : r < 0.87 ? "portrait" : "square";
    },
  };

  MDD.ready = new Promise((resolve) => {
    const go = () => Promise.all([document.fonts ? document.fonts.ready : null, waitImages()])
      .then(() => Promise.all(extraWaits))
      .then(() => { document.documentElement.dataset.orientation = MDD.orientation; resolve(); });
    if (document.readyState === "complete") go(); else window.addEventListener("load", go);
  });

  function startPreview() {
    const c = state.cfg;
    const freeze = params.get("t");
    let hud;
    if (params.has("debug")) {
      hud = document.createElement("div");
      hud.style.cssText = "position:fixed;left:8px;bottom:8px;z-index:99999;font:12px ui-monospace,monospace;color:#0f0;background:#000a;padding:3px 6px";
      document.body.appendChild(hud);
    }
    if (freeze !== null) { MDD.seek(parseFloat(freeze)); return; }
    const t0 = performance.now();
    const loop = async () => {
      const t = ((performance.now() - t0) / 1000) % c.duration;
      await MDD.seek(t, false);
      if (hud) hud.textContent = t.toFixed(2) + "s / " + c.duration + "s";
      requestAnimationFrame(loop);
    };
    loop();
  }

  window.MDD = MDD;
})();
