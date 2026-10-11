#!/usr/bin/env python3
"""Brand/product image analysis + safe preparation for motion-design-director.

  inspect_assets.py inspect <img|dir>...          -> JSON per image: size, orientation, alpha,
                                                     background type/colour, dominant palette,
                                                     subject bbox, cutout recommendation
  inspect_assets.py cutout <img> -o out.png       -> remove a near-uniform background (flood fill
                    [--tol 28] [--feather 1.5]       from the borders only, so interior pixels of the
                                                     same colour are kept), trim to subject, PNG+alpha
  inspect_assets.py fit <img> -o out.png --max 2400  -> downscale huge images (never upscales)

Never alters proportions. Always writes new files; originals are untouched.
Requires Pillow + numpy.
"""
import argparse
import json
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageFilter, ImageOps
except ImportError:  # pragma: no cover
    sys.exit("needs Pillow and numpy: pip install pillow numpy")

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".bmp", ".tif", ".tiff", ".gif"}


def load(path):
    im = Image.open(path)
    im = ImageOps.exif_transpose(im)  # respect camera orientation
    return im


def hexc(rgb):
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb[:3])


def luminance(rgb):
    r, g, b = [v / 255 for v in rgb[:3]]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def palette(im, n=6, exclude=None):
    rgb = im.convert("RGBA")
    a = np.asarray(rgb)
    mask = a[..., 3] > 200
    if exclude is not None:
        mask &= ~exclude
    px = a[..., :3][mask]
    if len(px) == 0:
        return []
    if len(px) > 60000:
        px = px[np.random.default_rng(0).choice(len(px), 60000, replace=False)]
    small = Image.fromarray(px.reshape(-1, 1, 3).astype("uint8"))
    q = small.quantize(colors=n * 2, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    out, kept = [], []
    for cnt, idx in counts:
        c = np.array(pal[idx * 3: idx * 3 + 3], float)
        share = cnt / len(px)
        near = next((k for k in kept if np.sqrt(((k[0] - c) ** 2).sum()) < 24), None)
        if near is not None:  # merge visually identical swatches
            near[1] += share
            continue
        kept.append([c, share])
    for c, share in sorted(kept, key=lambda k: -k[1])[:n]:
        out.append({"hex": hexc(c), "share": round(share, 3), "lum": round(luminance(c), 2)})
    return out


def border_stats(arr):
    h, w = arr.shape[:2]
    k = max(2, min(h, w) // 50)
    border = np.concatenate([arr[:k].reshape(-1, arr.shape[2]), arr[-k:].reshape(-1, arr.shape[2]),
                             arr[:, :k].reshape(-1, arr.shape[2]), arr[:, -k:].reshape(-1, arr.shape[2])])
    rgb = border[:, :3].astype(float)
    med = np.median(rgb, axis=0)
    dev = np.sqrt(((rgb - med) ** 2).sum(1))
    return med, float(np.mean(dev < 30)), float(dev.std())


def bg_mask(arr, tol):
    """Background = pixels within tol of the border median colour that are CONNECTED to the border.

    Uses PIL's C flood fill on a 1px-padded candidate map, so it is fast on large photos and
    keeps interior pixels that merely share the background colour (e.g. white labels).
    """
    from PIL import ImageDraw
    med, _, _ = border_stats(arr)
    diff = np.sqrt(((arr[..., :3].astype(float) - med) ** 2).sum(-1))
    cand = diff < tol
    if arr.shape[2] == 4:
        cand |= arr[..., 3] < 10
    h, w = cand.shape
    pad = np.full((h + 2, w + 2), 255, "uint8")
    pad[1:-1, 1:-1] = np.where(cand, 255, 0)
    img = Image.fromarray(pad).copy()  # copy: floodfill is a no-op on array-backed images
    ImageDraw.floodfill(img, (0, 0), 128, thresh=0)
    return np.asarray(img)[1:-1, 1:-1] == 128, med


def analyze(path):
    im = load(path)
    w, h = im.size
    info = {"file": str(path), "width": w, "height": h, "mode": im.mode,
            "aspect": round(w / h, 3),
            "orientation": "landscape" if w / h > 1.15 else "portrait" if w / h < 0.87 else "square",
            "megapixels": round(w * h / 1e6, 2)}
    rgba = im.convert("RGBA")
    arr = np.asarray(rgba)
    alpha = arr[..., 3]
    transparent = float(np.mean(alpha < 10))
    info["has_alpha"] = bool(transparent > 0.005)
    info["transparent_share"] = round(transparent, 3)
    work = arr
    if max(w, h) > 900:  # analyse a downscaled copy for speed
        s = 900 / max(w, h)
        work = np.asarray(rgba.resize((max(1, int(w * s)), max(1, int(h * s))), Image.BILINEAR))
    med, uniform, _ = border_stats(work)
    info["border_color"] = hexc(med)
    info["border_uniformity"] = round(uniform, 2)
    if info["has_alpha"]:
        bg = "transparent"
    elif uniform > 0.9:
        bg = "uniform-light" if luminance(med) > 0.8 else "uniform-dark" if luminance(med) < 0.2 else "uniform-colour"
    elif uniform > 0.6:
        bg = "mostly-uniform (gradient/shadow)"
    else:
        bg = "complex/photographic"
    info["background"] = bg
    # subject bbox
    mask = None
    if info["has_alpha"]:
        ys, xs = np.where(work[..., 3] > 10)
    else:
        if uniform > 0.6:
            mask, _ = bg_mask(work, 28)
            info["background_share"] = round(float(mask.mean()), 3)
            ys, xs = np.where(~mask)
        else:
            ys, xs = np.where(np.ones(work.shape[:2], bool))
    if len(xs):
        sy, sx = h / work.shape[0], w / work.shape[1]
        x0, x1, y0, y1 = xs.min() * sx, (xs.max() + 1) * sx, ys.min() * sy, (ys.max() + 1) * sy
        info["subject_bbox"] = [int(x0), int(y0), int(x1), int(y1)]
        info["subject_fill"] = round(((x1 - x0) * (y1 - y0)) / (w * h), 3)
    info["palette_subject"] = palette(Image.fromarray(work), exclude=mask)
    rec = []
    if bg.startswith("uniform") or bg.startswith("mostly"):
        rec.append("cutout candidate: run `cutout` to isolate the subject on transparency (check edges after)")
    if bg == "complex/photographic":
        rec.append("photographic background: use full-frame (mask/wipe/parallax/Ken Burns) rather than cutting out")
    if info["has_alpha"]:
        rec.append("already transparent: can float over any background; add a soft contact shadow")
    if max(w, h) < 1200:
        rec.append("low resolution for 1080p: avoid scaling past ~100%, keep it smaller in frame")
    if max(w, h) > 4000:
        rec.append("very large: run `fit --max 2400` to speed up loading/rendering")
    if w * h and info.get("subject_fill", 1) < 0.25:
        rec.append("subject is small in the frame: crop/trim before using as hero")
    info["recommendations"] = rec
    return info


def cmd_inspect(a):
    files = []
    for p in a.paths:
        p = Path(p)
        if p.is_dir():
            files += sorted(f for f in p.rglob("*") if f.suffix.lower() in EXTS)
        else:
            files.append(p)
    res = []
    for f in files:
        try:
            res.append(analyze(f))
        except Exception as e:
            res.append({"file": str(f), "error": str(e)})
    print(json.dumps(res, indent=1))


def cmd_cutout(a):
    im = load(a.image).convert("RGBA")
    arr = np.asarray(im)
    mask, med = bg_mask(arr, a.tol)
    alpha = np.where(mask, 0, arr[..., 3]).astype("uint8")
    am = Image.fromarray(alpha)
    if a.feather > 0:
        am = am.filter(ImageFilter.GaussianBlur(a.feather))
        # keep interior fully opaque, soften only the rim
        am = Image.fromarray(np.minimum(np.asarray(am).astype(int) * 2, 255).astype("uint8"))
        am = Image.fromarray(np.minimum(np.asarray(am), arr[..., 3]).astype("uint8"))
    out = im.copy()
    out.putalpha(am)
    removed = float(np.mean(mask))
    if not a.no_trim:
        bbox = out.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
        if bbox:
            pad = a.pad
            bbox = (max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(out.width, bbox[2] + pad), min(out.height, bbox[3] + pad))
            out = out.crop(bbox)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    out.save(a.output)
    warn = []
    if removed < 0.05:
        warn.append("almost nothing removed - background probably not uniform; use the original")
    if removed > 0.92:
        warn.append("removed >92% - subject may have been eaten; lower --tol")
    print(json.dumps({"output": a.output, "size": out.size, "background_color": hexc(med),
                      "removed_share": round(removed, 3), "warnings": warn}, indent=1))


def cmd_fit(a):
    im = load(a.image)
    if max(im.size) > a.max:
        s = a.max / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    im.save(a.output, quality=92) if a.output.lower().endswith((".jpg", ".jpeg")) else im.save(a.output)
    print(json.dumps({"output": a.output, "size": im.size}))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("inspect")
    i.add_argument("paths", nargs="+")
    i.set_defaults(fn=cmd_inspect)
    c = sub.add_parser("cutout")
    c.add_argument("image")
    c.add_argument("-o", "--output", required=True)
    c.add_argument("--tol", type=float, default=28)
    c.add_argument("--feather", type=float, default=1.2)
    c.add_argument("--pad", type=int, default=8)
    c.add_argument("--no-trim", action="store_true")
    c.set_defaults(fn=cmd_cutout)
    f = sub.add_parser("fit")
    f.add_argument("image")
    f.add_argument("-o", "--output", required=True)
    f.add_argument("--max", type=int, default=2400)
    f.set_defaults(fn=cmd_fit)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
