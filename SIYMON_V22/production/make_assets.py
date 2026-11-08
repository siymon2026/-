"""
Derive SIYMON brand assets from the authentic app icon.

The "S" of public/icons/icon-192.png is traced to smooth polygons (4x upscale,
threshold, morphological clean, contour approx) so it can be redrawn crisply at
any size instead of being blurred up from a 106 px source. The squircle body
keeps the original green gradient sampled from the icon.

No new mark is invented: this is the project's own icon, vectorised.
"""
from __future__ import annotations

import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFilter

SRC = "assets/siymon-logo-icon.png"
OUT = "assets/"
UP = 4


def trace_s():
    a = np.asarray(Image.open(SRC).convert("RGB"))
    big = cv2.resize(a, None, fx=UP, fy=UP, interpolation=cv2.INTER_CUBIC)
    g = cv2.cvtColor(big, cv2.COLOR_RGB2GRAY)
    mask = (g > 148).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    h, w = mask.shape
    polys = []
    for c in cnts:
        if cv2.contourArea(c) < 400:
            continue
        c = cv2.approxPolyDP(c, 1.2, True).reshape(-1, 2).astype(np.float64)
        # normalise to 0..1 of the icon box
        c[:, 0] /= w
        c[:, 1] /= h
        polys.append(c)
    polys.sort(key=lambda p: -cv2.contourArea(p.astype(np.float32)))
    return polys


def _densify(poly, step=0.004):
    """Resample a closed polygon evenly so it can be smoothed."""
    pts = np.vstack([poly, poly[:1]])
    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    total = seg.sum()
    n = max(12, int(total / step))
    cum = np.concatenate([[0], np.cumsum(seg)])
    out = []
    for i in range(n):
        d = total * i / n
        j = min(np.searchsorted(cum, d) - 1, len(seg) - 1)
        j = max(j, 0)
        f = (d - cum[j]) / max(seg[j], 1e-9)
        out.append(pts[j] + (pts[j + 1] - pts[j]) * f)
    return np.array(out)


def _smooth(poly, iters=3):
    p = _densify(poly)
    for _ in range(iters):
        p = 0.25 * np.roll(p, 1, axis=0) + 0.5 * p + 0.25 * np.roll(p, -1, axis=0)
    return p


def build_logo(size=1024):
    polys = [_smooth(p) for p in trace_s()]
    SS = 2  # supersample
    W = H = size * SS
    pad = int(W * 0.015)

    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    top, bot = np.array([150, 232, 60]), np.array([44, 128, 18])
    gr = np.zeros((H, W, 4), dtype=np.uint8)
    for y in range(H):
        t = (y / H) ** 0.92
        c = (top + (bot - top) * t).astype(np.uint8)
        gr[y, :, :3] = c
        gr[y, :, 3] = 255
    body = Image.fromarray(gr, "RGBA")
    smask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(smask).rounded_rectangle([pad, pad, W - pad - 1, H - pad - 1],
                                            radius=int(W * 0.285), fill=255)
    body.putalpha(smask)

    # rim light on the top-left edge, shade on the bottom
    rim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rim)
    for i in range(int(W * 0.05)):
        a = int(46 * (1 - i / (W * 0.05)) ** 1.6)
        rd.rounded_rectangle([pad + i * 0.5, pad + i * 0.5, W - pad - i * 0.5, H - pad - i * 0.5],
                             radius=int(W * 0.285), outline=(220, 255, 170, a), width=SS)
    rim.putalpha(Image.composite(rim.getchannel("A"), Image.new("L", (W, H), 0), smask))
    body = Image.alpha_composite(body, rim)

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    img.alpha_composite(body)

    # ---- S layer
    smask_s = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(smask_s)
    for p in polys:
        pts = [(pad + x * (W - 2 * pad), pad + y * (H - 2 * pad)) for x, y in p]
        sd.polygon(pts, fill=255)

    # colour: light lime with a soft vertical fall-off like the original
    sc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sg = np.zeros((H, W, 4), dtype=np.uint8)
    c0, c1 = np.array([214, 252, 120]), np.array([150, 226, 58])
    for y in range(H):
        t = np.clip((y / H - 0.1) / 0.9, 0, 1)
        c = (c0 + (c1 - c0) * t).astype(np.uint8)
        sg[y, :, :3] = c
        sg[y, :, 3] = 255
    sc = Image.fromarray(sg, "RGBA")
    sc.putalpha(smask_s)

    # shadow of the S cast onto the body
    sh = smask_s.filter(ImageFilter.GaussianBlur(W * 0.012)).point(lambda v: int(v * 0.42))
    shadow = Image.new("RGBA", (W, H), (18, 62, 8, 255))
    shadow.putalpha(sh)
    img.alpha_composite(shadow, (int(W * 0.008), int(H * 0.016)))
    img.alpha_composite(sc)

    img = img.resize((size, size), Image.LANCZOS)
    return img


def build_badge(size=512):
    """Circular SIYMON roundel used on restaurant cards in the app."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=(11, 22, 10, 255),
              outline=(93, 214, 44, 255), width=max(2, int(size * 0.028)))
    logo = build_logo(int(size * 0.60))
    img.alpha_composite(logo, (int(size * 0.20), int(size * 0.20)))
    return img


if __name__ == "__main__":
    lg = build_logo(1024)
    lg.save(OUT + "logo.png")
    b = build_badge(620)
    b.save(OUT + "badge.png")
    prev = Image.new("RGB", (1300, 460), (9, 9, 9))
    prev.paste(lg.resize((400, 400), Image.LANCZOS), (40, 30), lg.resize((400, 400), Image.LANCZOS))
    prev.paste(b.resize((300, 300), Image.LANCZOS), (500, 80), b.resize((300, 300), Image.LANCZOS))
    prev.paste(lg.resize((120, 120), Image.LANCZOS), (860, 60), lg.resize((120, 120), Image.LANCZOS))
    prev.paste(b.resize((90, 90), Image.LANCZOS), (1010, 70), b.resize((90, 90), Image.LANCZOS))
    prev.paste(lg.resize((56, 56), Image.LANCZOS), (860, 250), lg.resize((56, 56), Image.LANCZOS))
    prev.save("/tmp/logo_prev.png")
    print("done")
