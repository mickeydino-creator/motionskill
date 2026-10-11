#!/usr/bin/env python3
"""Motion Prompts (motionprompts.dev) catalog client for the motion-design-director skill.

Uses only the documented, public, key-free surfaces (verified against
https://motionprompts.dev/developers/):
  REST  /api/v1/components.json, /api/v1/motion-systems.json,
        /api/v1/composition-rules.json, /prompts/<slug>.md
  MCP   https://motionprompts.dev/mcp  (Streamable HTTP, stateless JSON-RPC, no auth)

Catalog JSON is cached locally (default ~/.cache/motion-design-director, TTL 7 days)
and searched offline when the network is unavailable. Every result carries a
`source` field ("mcp", "local-cache") so the caller never confuses a real library
hit with something invented.

Stdlib only. Run `mp_catalog.py -h` for commands.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SITE = "https://motionprompts.dev"
MCP_URL = SITE + "/mcp"
CATALOG_FILES = {
    "components": "/api/v1/components.json",
    "systems": "/api/v1/motion-systems.json",
    "rules": "/api/v1/composition-rules.json",
}
CACHE_DIR = Path(os.environ.get("MDD_CACHE_DIR", Path.home() / ".cache" / "motion-design-director"))
TTL = int(os.environ.get("MDD_CACHE_TTL", 7 * 24 * 3600))
UA = "motion-design-director-skill/1.0 (+Claude Code)"
LICENSE_NOTE = ("motionprompts components/prompts are PolyForm Noncommercial 1.0.0 + mandatory "
                "attribution. Commercial use needs a separate license from motionprompts.dev.")


# ---------------------------------------------------------------- network
def http_get(path_or_url, accept="application/json", timeout=30, retries=3):
    url = path_or_url if path_or_url.startswith("http") else SITE + path_or_url
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(e.headers.get("Retry-After", 2)))
                last = e
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


_rpc_id = 0


def mcp_call(tool, arguments, timeout=45):
    """Call a tool on the hosted MCP server via a single stateless JSON-RPC POST."""
    global _rpc_id
    _rpc_id += 1
    body = json.dumps({"jsonrpc": "2.0", "id": _rpc_id, "method": "tools/call",
                       "params": {"name": tool, "arguments": arguments}}).encode()
    req = urllib.request.Request(MCP_URL, data=body, method="POST", headers={
        "User-Agent": UA, "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
    if raw.lstrip().startswith("event:") or raw.lstrip().startswith("data:"):
        datas = [l[5:].strip() for l in raw.splitlines() if l.startswith("data:")]
        raw = datas[-1] if datas else "{}"
    msg = json.loads(raw)
    if "error" in msg:
        raise RuntimeError(f"MCP error: {msg['error']}")
    res = msg.get("result", {})
    if res.get("isError"):
        raise RuntimeError("MCP tool error: " + " ".join(c.get("text", "") for c in res.get("content", [])))
    texts = [c.get("text", "") for c in res.get("content", []) if c.get("type") == "text"]
    joined = "\n".join(texts)
    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        return joined


# ---------------------------------------------------------------- cache
def cache_path(name):
    return CACHE_DIR / f"{name}.json"


def load_catalog(name, force=False, allow_stale=True):
    p = cache_path(name)
    fresh = p.exists() and (time.time() - p.stat().st_mtime) < TTL
    if fresh and not force:
        return json.loads(p.read_text())
    try:
        data = http_get(CATALOG_FILES[name])
        json.loads(data)  # validate before writing
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return json.loads(data)
    except Exception as e:
        if p.exists() and allow_stale:
            print(f"[warn] could not refresh {name} ({e}); using stale cache from "
                  f"{time.ctime(p.stat().st_mtime)}", file=sys.stderr)
            return json.loads(p.read_text())
        raise RuntimeError(f"catalog '{name}' unavailable: network failed ({e}) and no cache at {p}")


def components_by_slug():
    return {c["slug"]: c for c in load_catalog("components")["components"]}


# ---------------------------------------------------------------- search
WORD = re.compile(r"[a-z0-9áéíóúñü]+")
STOP = set("a an the and or of for with to in on by de la el y con para un una los las del que en "
           "video ad advert advertisement premium professional".split())


def tokens(s):
    return [w for w in WORD.findall((s or "").lower()) if w not in STOP and len(w) > 1]


def local_search(query, limit=12, category=None, trigger=None):
    comps = load_catalog("components")["components"]
    q = tokens(query)
    out = []
    for c in comps:
        m = c.get("motion") or {}
        if category and c.get("category") not in category:
            continue
        if trigger and m.get("trigger") not in trigger:
            continue
        fields = {
            "title": (c.get("title", ""), 4.0),
            "slug": (c.get("slug", "").replace("-", " "), 3.0),
            "category": (c.get("category", ""), 2.5),
            "description": (c.get("description", ""), 1.0),
            "signature": (m.get("motion_signature", "") or "", 1.0),
            "libs": (" ".join(m.get("libs") or []) + " " + (m.get("engine") or ""), 1.5),
            "cluster": ((m.get("cluster") or "").replace("-", " "), 1.5),
        }
        score, why = 0.0, []
        for name, (text, w) in fields.items():
            tt = set(tokens(text))
            hits = [t for t in q if t in tt or any(x.startswith(t) for x in tt if len(t) > 3)]
            if hits:
                score += w * len(set(hits))
                why.append(f"{name}: {', '.join(sorted(set(hits)))}")
        if score > 0 or not q:
            out.append((score, c, why))
    out.sort(key=lambda x: -x[0])
    return [summarize(c, score=round(s, 1), why=why, source="local-cache") for s, c, why in out[:limit]]


def summarize(c, **extra):
    m = c.get("motion") or {}
    d = {
        "slug": c["slug"], "title": c.get("title"), "category": c.get("category"),
        "trigger": m.get("trigger"), "engine": m.get("engine"), "libs": m.get("libs"),
        "complexity": m.get("complexity"), "native_system": m.get("native_system"),
        "ease_family": m.get("ease_family"), "duration_range": m.get("duration_range"),
        "assets_required": (m.get("assets_required") or {}).get("count"),
        "page": c.get("page"), "prompt": c.get("prompt"), "demo": c.get("demo"),
        "thumb": c.get("thumb"), "preview": c.get("preview"),
    }
    d.update(extra)
    return d


def mcp_search(args):
    a = {"query": args.query, "limit": args.limit}
    for k, v in (("mood", args.mood), ("useCase", args.use_case), ("category", args.category),
                 ("level", args.level), ("deps", args.deps)):
        if v:
            a[k] = v
    if args.max_perf:
        a["maxPerfCost"] = args.max_perf
    res = mcp_call("search_components", a)
    try:
        cat = components_by_slug()
    except Exception:
        cat = {}
    out = []
    for r in res.get("results", []):
        base = cat.get(r["slug"])
        s = summarize(base) if base else {"slug": r["slug"], "title": r.get("title")}
        s.update({k: r.get(k) for k in ("useWhen", "mood", "useCase", "level", "perfCost",
                                        "mobileSafe", "deps", "score", "why") if k in r})
        s["source"] = "mcp"
        out.append(s)
    return out


# ---------------------------------------------------------------- commands
def cmd_refresh(args):
    for name in CATALOG_FILES:
        d = load_catalog(name, force=True, allow_stale=False)
        n = d.get("count") or len(d.get("components") or d.get("systems") or d.get("hard_rules") or [])
        print(f"cached {name}: {n} entries -> {cache_path(name)}")


def cmd_status(args):
    for name in CATALOG_FILES:
        p = cache_path(name)
        if p.exists():
            age = (time.time() - p.stat().st_mtime) / 3600
            print(f"{name}: cached {age:.1f}h ago ({'fresh' if age * 3600 < TTL else 'stale'}) {p}")
        else:
            print(f"{name}: not cached")
    for label, fn in (("REST", lambda: http_get(CATALOG_FILES["systems"], timeout=10, retries=1)),
                      ("MCP", lambda: mcp_call("list_facets", {}, timeout=15))):
        try:
            fn()
            print(f"{label}: reachable")
        except Exception as e:
            print(f"{label}: UNREACHABLE ({e})")


def cmd_search(args):
    results, mode, err = [], None, None
    if not args.local:
        try:
            results, mode = mcp_search(args), "mcp"
        except Exception as e:
            err = e
            print(f"[warn] MCP search failed ({e}); falling back to local catalog search", file=sys.stderr)
    if mode is None:
        results, mode = local_search(args.query, args.limit, args.category, args.trigger), "local-cache"
    if args.trigger and mode == "mcp":
        results = [r for r in results if r.get("trigger") in args.trigger]
    if not args.full:
        keep = ("slug", "title", "category", "trigger", "engine", "libs", "complexity", "native_system",
                "useWhen", "mood", "useCase", "perfCost", "score", "why", "source")
        results = [{k: r[k] for k in keep if r.get(k) not in (None, [], "")} for r in results]
    out = {"query": args.query, "search_mode": mode, "count": len(results),
           "urls": SITE + "/component/<slug>/  |  /prompts/<slug>.md  |  /previews/<slug>.webm",
           "results": results}
    if err:
        out["mcp_error"] = str(err)
    print(json.dumps(out, indent=1, ensure_ascii=False))


def cmd_get(args):
    out_dir = Path(args.out) / args.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    cat = components_by_slug()
    if args.slug not in cat:
        sys.exit(f"unknown slug '{args.slug}'. Use `search` - never guess slugs.")
    meta = {"catalog": cat[args.slug], "retrieved": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "license": LICENSE_NOTE}
    written = []
    # build prompt (canonical REST markdown)
    try:
        md = http_get(f"/prompts/{args.slug}.md", accept="text/markdown").decode("utf-8")
        (out_dir / "prompt.md").write_text(md)
        written.append("prompt.md")
    except Exception as e:
        print(f"[warn] prompt fetch failed: {e}", file=sys.stderr)
    # enriched meta + optional real source via MCP
    include = ["meta"] + (["source"] if args.source else [])
    try:
        r = mcp_call("get_component", {"slug": args.slug, "include": include})
        if isinstance(r, dict):
            meta["enriched"] = r.get("meta")
            src = (r.get("source") or {})
            if src.get("files"):
                sdir = out_dir / "source"
                sdir.mkdir(exist_ok=True)
                for f in src["files"]:
                    name = Path(f["file"]).name  # never allow path traversal
                    (sdir / name).write_text(f.get("content", ""))
                    written.append(f"source/{name}")
                for k in ("integration", "integration_note", "note"):
                    if src.get(k):
                        meta["integration_note"] = src[k]
    except Exception as e:
        print(f"[warn] MCP get_component failed: {e}", file=sys.stderr)
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False))
    written.append("meta.json")
    print(json.dumps({"slug": args.slug, "dir": str(out_dir), "files": written,
                      "page": cat[args.slug].get("page"), "license": LICENSE_NOTE}, indent=1))


def cmd_preview(args):
    """Download thumbnail + preview video and build a contact sheet PNG to look at."""
    cat = components_by_slug()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for slug in args.slugs:
        c = cat.get(slug)
        if not c:
            print(f"{slug}: unknown slug", file=sys.stderr)
            continue
        made = []
        if c.get("preview"):
            webm = out / f"{slug}.webm"
            try:
                webm.write_bytes(http_get(c["preview"], accept="*/*", timeout=60))
                sheet = out / f"{slug}-sheet.png"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(webm), "-vf",
                                "fps=1.5,scale=480:-2,tile=3x2:padding=4:color=white", "-frames:v", "1",
                                str(sheet)], check=True)
                made.append(str(sheet))
            except Exception as e:
                print(f"{slug}: preview failed ({e})", file=sys.stderr)
        if not made and c.get("thumb"):
            try:
                p = out / f"{slug}-thumb.webp"
                p.write_bytes(http_get(c["thumb"], accept="*/*"))
                png = out / f"{slug}-thumb.png"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(p), str(png)], check=True)
                made.append(str(png))
            except Exception as e:
                print(f"{slug}: thumb failed ({e})", file=sys.stderr)
        print(json.dumps({"slug": slug, "images": made}))


def cmd_systems(args):
    data = load_catalog("systems")
    if args.name:
        s = next((x for x in data["systems"] if x["name"] == args.name), None)
        if not s:
            sys.exit(f"unknown system; choose from {[x['name'] for x in data['systems']]}")
        s = {k: v for k, v in s.items() if k != "_evidence"}
        print(json.dumps(s, indent=1, ensure_ascii=False))
    else:
        for s in data["systems"]:
            print(f"{s['name']:<22} members={s['members']:<3} ease={s['ease']} "
                  f"duration={s['duration']} stagger={s['stagger']}")


def cmd_mcp(args):
    """Escape hatch: call any MCP tool verified via tools/list, e.g. plan_imagery."""
    print(json.dumps(mcp_call(args.tool, json.loads(args.json)), indent=1, ensure_ascii=False))


def cmd_credit(args):
    cat = components_by_slug()
    c = cat.get(args.slug)
    if not c:
        sys.exit(f"unknown slug '{args.slug}' - refusing to record a credit for a component that does not exist")
    proj = Path(args.project)
    jf = proj / "library-credits.json"
    data = json.loads(jf.read_text()) if jf.exists() else {"library": SITE, "license": LICENSE_NOTE, "used": []}
    data["used"] = [u for u in data["used"] if u["slug"] != args.slug]
    data["used"].append({"slug": args.slug, "title": c.get("title"), "page": c.get("page"),
                         "prompt": c.get("prompt"), "how_used": args.how, "usage": args.usage})
    jf.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    lines = ["# Credits", "", f"Motion references from [motionprompts.dev]({SITE}) - {LICENSE_NOTE}", ""]
    for u in data["used"]:
        lines.append(f"- **{u['title']}** (`{u['slug']}`) - {u['page']}  \n  usage: {u['usage']} - {u['how_used']}")
    lines += ["", "Everything not listed above is custom code written for this project."]
    (proj / "CREDITS.md").write_text("\n".join(lines) + "\n")
    print(f"recorded {args.slug} in {jf} and CREDITS.md")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh", help="force-refresh cached catalog JSON").set_defaults(fn=cmd_refresh)
    sub.add_parser("status", help="show cache age and REST/MCP reachability").set_defaults(fn=cmd_status)

    s = sub.add_parser("search", help="search components (MCP first, local cache fallback)")
    s.add_argument("query")
    s.add_argument("--mood", nargs="*", help="minimal elegant luxury editorial bold playful corporate retro "
                                             "futuristic experimental cinematic brutalist organic technical")
    s.add_argument("--use-case", nargs="*", help="hero preloader page-transition gallery slider card-deck "
                                                 "scroll-story image-reveal text-reveal logo background "
                                                 "product-showcase marquee cta ...")
    s.add_argument("--category", nargs="*")
    s.add_argument("--level", nargs="*", choices=["page", "section", "widget"])
    s.add_argument("--deps", nargs="*")
    s.add_argument("--trigger", nargs="*", help="post-filter: scroll load click pointer hover wheel drag")
    s.add_argument("--max-perf", choices=["light", "medium", "heavy"])
    s.add_argument("--limit", type=int, default=12)
    s.add_argument("--local", action="store_true", help="skip MCP, search cached catalog only")
    s.add_argument("--full", action="store_true", help="include all URLs and metadata per result")
    s.set_defaults(fn=cmd_search)

    g = sub.add_parser("get", help="download build prompt (+ real source) for one slug")
    g.add_argument("slug")
    g.add_argument("--source", action="store_true", help="also fetch the real index.html/styles.css/script.js")
    g.add_argument("--out", default="./mp-refs")
    g.set_defaults(fn=cmd_get)

    p = sub.add_parser("preview", help="download preview video -> contact-sheet PNG for visual evaluation")
    p.add_argument("slugs", nargs="+")
    p.add_argument("--out", default="./mp-refs/previews")
    p.set_defaults(fn=cmd_preview)

    y = sub.add_parser("systems", help="list motion systems or show one system's tokens")
    y.add_argument("name", nargs="?")
    y.set_defaults(fn=cmd_systems)

    m = sub.add_parser("mcp", help="call any MCP tool directly with JSON arguments")
    m.add_argument("tool")
    m.add_argument("json", nargs="?", default="{}")
    m.set_defaults(fn=cmd_mcp)

    c = sub.add_parser("credit", help="record a used component in <project>/CREDITS.md")
    c.add_argument("slug")
    c.add_argument("--project", required=True)
    c.add_argument("--usage", choices=["mechanic-reference", "adapted-source", "verbatim-source"],
                   default="mechanic-reference")
    c.add_argument("--how", default="", help="one line: which technique was taken and how it was adapted")
    c.set_defaults(fn=cmd_credit)

    args = ap.parse_args()
    try:
        args.fn(args)
    except RuntimeError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
