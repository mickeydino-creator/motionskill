#!/usr/bin/env node
/*
 * render_video.mjs - frame-accurate HTML -> MP4 renderer for motion-design-director.
 *
 * Serves the project folder on 127.0.0.1, opens the page in headless Chromium (Playwright),
 * calls `MDD.seek(t)` (see mdd-runtime.js) for every frame, screenshots it, pipes the frames
 * into ffmpeg (libx264, yuv420p, +faststart), then verifies the result with ffprobe and
 * extracts QA stills + a contact sheet FROM THE ENCODED MP4.
 *
 * Usage:
 *   node render_video.mjs --project ./my-video [--page index.html] [--out out/video.mp4]
 *        [--width 1920 --height 1080] [--fps 30] [--duration 10] [--crf 18]
 *        [--frame-format png|jpeg] [--start 0 --end 10] [--audio music.mp3]
 *        [--stills 0,2.5,5,9.9] [--sheet 12] [--no-verify]
 *   node render_video.mjs --project ./my-video --still 4.2 --out out/frame.png   # single frame
 *
 * Exit code is non-zero when the page throws, an image fails to load, or verification fails.
 */
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { spawn, execFileSync } from "node:child_process";
import { createRequire } from "node:module";

// ------------------------------------------------------------------ args
const argv = process.argv.slice(2);
const opt = (name, def) => {
  const i = argv.indexOf("--" + name);
  if (i === -1) return def;
  const v = argv[i + 1];
  return v === undefined || v.startsWith("--") ? true : v;
};
const project = path.resolve(opt("project", "."));
const pageName = opt("page", "index.html");
const W = parseInt(opt("width", 1920), 10);
const H = parseInt(opt("height", 1080), 10);
const stillAt = opt("still", null);
const out = path.resolve(opt("out", stillAt !== null ? path.join(project, "out", "still.png") : path.join(project, "out", "video.mp4")));
const crf = String(opt("crf", 18));
const preset = String(opt("preset", "medium"));
const frameFormat = opt("frame-format", "png") === "jpeg" ? "jpeg" : "png";
const audio = opt("audio", null);
const verify = !argv.includes("--no-verify");
const sheetN = parseInt(opt("sheet", 12), 10);
const scale = parseFloat(opt("scale", 1));

if (W % 2 || H % 2) die(`width/height must be even for yuv420p (got ${W}x${H})`);
if (!fs.existsSync(path.join(project, pageName))) die(`page not found: ${path.join(project, pageName)}`);

function die(msg) { console.error("✖ " + msg); process.exit(1); }
function log(msg) { console.log(msg); }

// ------------------------------------------------------------------ playwright (local or global)
async function loadPlaywright() {
  const req = createRequire(path.join(project, "package.json"));
  const tries = [() => req("playwright"), () => req("playwright-core"), () => req("@playwright/test")];
  try {
    const g = execFileSync("npm", ["root", "-g"], { encoding: "utf8" }).trim();
    tries.push(() => createRequire(path.join(g, "noop.js"))("playwright"));
  } catch (_) {}
  for (const t of tries) { try { return t(); } catch (_) {} }
  die("Playwright not found. Install it (npm i -D playwright) - Chromium must also be available.");
}

// ------------------------------------------------------------------ static server
const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript",
  ".css": "text/css", ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg", ".webp": "image/webp", ".avif": "image/avif", ".gif": "image/gif",
  ".svg": "image/svg+xml", ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
  ".otf": "font/otf", ".mp4": "video/mp4", ".webm": "video/webm", ".glb": "model/gltf-binary",
  ".gltf": "model/gltf+json", ".hdr": "application/octet-stream", ".wasm": "application/wasm",
  ".mp3": "audio/mpeg", ".wav": "audio/wav",
};
function serve(root) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const u = decodeURIComponent(new URL(req.url, "http://x").pathname);
      let f = path.normalize(path.join(root, u));
      if (!f.startsWith(root)) { res.writeHead(403).end(); return; }
      if (fs.existsSync(f) && fs.statSync(f).isDirectory()) f = path.join(f, "index.html");
      fs.readFile(f, (err, buf) => {
        if (err) { res.writeHead(404).end("not found"); return; }
        res.writeHead(200, { "Content-Type": MIME[path.extname(f).toLowerCase()] || "application/octet-stream", "Cache-Control": "no-store" });
        res.end(buf);
      });
    });
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

// ------------------------------------------------------------------ main
const { chromium } = await loadPlaywright();
const srv = await serve(project);
const url = `http://127.0.0.1:${srv.address().port}/${pageName}`;
const problems = [];

const browser = await chromium.launch({
  args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
         "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--font-render-hinting=none"],
});
const ctx = await browser.newContext({ viewport: { width: Math.round(W / scale), height: Math.round(H / scale) }, deviceScaleFactor: scale });
const page = await ctx.newPage();
await page.addInitScript(() => { window.__MDD_RENDER__ = true; });
page.on("pageerror", (e) => problems.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") problems.push("console.error: " + m.text()); });
page.on("requestfailed", (r) => problems.push(`request failed: ${r.url()} (${r.failure()?.errorText})`));
page.on("response", (r) => { if (r.status() >= 400) problems.push(`HTTP ${r.status()}: ${r.url()}`); });

const cleanup = async () => { await browser.close().catch(() => {}); srv.close(); };

try {
  await page.goto(url, { waitUntil: "load", timeout: 60000 });
  await page.waitForFunction(() => window.MDD && window.MDD.info().duration > 0, null, { timeout: 30000 })
    .catch(() => { throw new Error("page never called MDD.register({duration,...}) - include mdd-runtime.js and register a timeline"); });
  await page.evaluate(() => window.MDD.ready);
  const info = await page.evaluate(() => window.MDD.info());
  const fps = parseFloat(opt("fps", info.fps || 30));
  const duration = parseFloat(opt("duration", info.duration));
  const t0 = parseFloat(opt("start", 0));
  const t1 = Math.min(parseFloat(opt("end", duration)), duration);
  if (info.errors.length) problems.push(...info.errors.map((e) => "runtime: " + e));

  fs.mkdirSync(path.dirname(out), { recursive: true });

  if (stillAt !== null) {
    await page.evaluate((t) => window.MDD.seek(t), parseFloat(stillAt));
    await page.screenshot({ path: out, type: out.endsWith(".jpg") ? "jpeg" : "png" });
    log(`✔ still at ${stillAt}s -> ${out}`);
  } else {
    const total = Math.round((t1 - t0) * fps);
    log(`rendering ${url}\n  ${W}x${H} @ ${fps}fps, ${t0}s→${t1}s = ${total} frames -> ${out}`);
    const ffArgs = ["-v", "error", "-y", "-f", "image2pipe", "-framerate", String(fps),
      "-c:v", frameFormat === "png" ? "png" : "mjpeg", "-i", "-"];
    if (audio) ffArgs.push("-i", path.resolve(audio));
    ffArgs.push("-c:v", "libx264", "-preset", preset, "-crf", crf, "-pix_fmt", "yuv420p",
      "-r", String(fps), "-movflags", "+faststart");
    if (audio) ffArgs.push("-c:a", "aac", "-b:a", "192k", "-shortest");
    ffArgs.push(out);
    const ff = spawn("ffmpeg", ffArgs, { stdio: ["pipe", "inherit", "inherit"] });
    const ffDone = new Promise((res, rej) => ff.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg exited " + c)))));

    const hashes = [];
    const started = Date.now();
    for (let i = 0; i < total; i++) {
      const t = t0 + i / fps;
      await page.evaluate((tt) => window.MDD.seek(tt), t);
      const buf = await page.screenshot({ type: frameFormat, quality: frameFormat === "jpeg" ? 95 : undefined, caret: "hide" });
      hashes.push(crypto.createHash("md5").update(buf).digest("hex"));
      if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
      if (i % Math.max(1, Math.round(fps)) === 0 || i === total - 1) {
        const el = (Date.now() - started) / 1000;
        process.stdout.write(`\r  frame ${i + 1}/${total}  ${el.toFixed(0)}s elapsed, ~${((el / (i + 1)) * (total - i - 1)).toFixed(0)}s left   `);
      }
    }
    ff.stdin.end();
    await ffDone;
    process.stdout.write("\n");

    // motion sanity: distinct frames and longest frozen run
    const unique = new Set(hashes).size;
    let run = 1, maxRun = 1;
    for (let i = 1; i < hashes.length; i++) { run = hashes[i] === hashes[i - 1] ? run + 1 : 1; maxRun = Math.max(maxRun, run); }
    log(`  distinct frames: ${unique}/${hashes.length}, longest identical run: ${maxRun} frames (${(maxRun / fps).toFixed(2)}s)`);
    if (unique < Math.max(2, hashes.length * 0.1)) problems.push(`animation looks static: only ${unique} distinct frames of ${hashes.length}`);

    if (verify) verifyVideo({ fps, duration: t1 - t0, total });
  }
} catch (e) {
  problems.push("fatal: " + e.message);
} finally {
  await cleanup();
}

if (problems.length) {
  console.error("\n⚠ problems detected:\n  - " + [...new Set(problems)].join("\n  - "));
  process.exit(2);
}
log("✔ done");

// ------------------------------------------------------------------ verification
function verifyVideo({ fps, duration, total }) {
  const probe = JSON.parse(execFileSync("ffprobe", ["-v", "error", "-count_packets", "-select_streams", "v:0",
    "-show_entries", "stream=codec_name,width,height,pix_fmt,r_frame_rate,nb_read_packets:format=duration,size,format_name",
    "-of", "json", out], { encoding: "utf8" }));
  const s = probe.streams?.[0] || {};
  const f = probe.format || {};
  const [n, d] = String(s.r_frame_rate || "0/1").split("/").map(Number);
  const rfps = n / (d || 1);
  const report = {
    file: out, container: f.format_name, codec: s.codec_name, pix_fmt: s.pix_fmt,
    width: s.width, height: s.height, fps: +rfps.toFixed(3), frames: +s.nb_read_packets,
    duration: +(+f.duration).toFixed(3), size_mb: +(f.size / 1048576).toFixed(2),
  };
  log("  ffprobe: " + JSON.stringify(report));
  if (!String(f.format_name).includes("mp4")) problems.push("output is not an MP4 container");
  if (s.codec_name !== "h264") problems.push("video codec is not h264");
  if (s.width !== W || s.height !== H) problems.push(`resolution ${s.width}x${s.height} != ${W}x${H}`);
  if (Math.abs(rfps - fps) > 0.01) problems.push(`fps ${rfps} != ${fps}`);
  if (Math.abs(+s.nb_read_packets - total) > 1) problems.push(`frame count ${s.nb_read_packets} != ${total}`);
  if (Math.abs(+f.duration - duration) > 2 / fps + 0.05) problems.push(`duration ${f.duration}s != ${duration}s`);

  // QA stills + contact sheet extracted from the encoded file itself
  const qa = path.join(path.dirname(out), "qa");
  fs.mkdirSync(qa, { recursive: true });
  const stills = String(opt("stills", "")).split(",").filter(Boolean).map(Number);
  const dur = +f.duration;
  const defaults = [0, dur * 0.25, dur * 0.5, dur * 0.75, Math.max(0, dur - 1 / fps)];
  for (const t of (stills.length ? stills : defaults)) {
    const p = path.join(qa, `frame_${t.toFixed(2)}s.png`);
    execFileSync("ffmpeg", ["-v", "error", "-y", "-ss", String(t), "-i", out, "-frames:v", "1", p]);
  }
  const cols = 4, rows = Math.ceil(sheetN / cols);
  const sheet = path.join(qa, "contact-sheet.png");
  execFileSync("ffmpeg", ["-v", "error", "-y", "-i", out, "-vf",
    `fps=${(sheetN / dur).toFixed(4)},scale=480:-2,tile=${cols}x${rows}:padding=6:color=0x222222`, "-frames:v", "1", sheet]);
  log(`  QA stills + contact sheet -> ${qa}`);
}
