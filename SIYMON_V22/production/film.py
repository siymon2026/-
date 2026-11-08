"""
Film layer: composes 3D renders with photographic depth plates into 9:16 frames.

- Plate: a cinematic still used as an out-of-focus background (Ken Burns +
  lens blur) so every scene has real photographic depth behind the 3D.
- Film: holds scenes on a timeline, cross-fades them, and writes the frame.
"""
from __future__ import annotations

import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from siymon3d import F, clamp, lerp, smooth, ease_in_out, ease_out, span
import ui

W, H = 1080, 1920
ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets") + "/"

_PLATE_CACHE = {}
_UI_CACHE = {}


# --------------------------------------------------------------------------
def load_plate(name, blur=18, zoom=1.0, cx=0.5, cy=0.5, dark=0.55, tint=None):
    """Photographic background plate, cropped to 9:16, lens-blurred and darkened."""
    key = (name, blur, round(zoom, 3), round(cx, 3), round(cy, 3), dark, tint)
    if key in _PLATE_CACHE:
        return _PLATE_CACHE[key]
    path = os.path.join(ASSETS, name)
    im = Image.open(path).convert("RGB")
    # cover-crop to 9:16
    tw, th = W, H
    scale = max(tw / im.width, th / im.height) * 1.24 * zoom
    nw, nh = int(im.width * scale), int(im.height * scale)
    im = im.resize((nw, nh), Image.LANCZOS)
    ox = int((nw - tw) * cx)
    oy = int((nh - th) * cy)
    im = im.crop((ox, oy, ox + tw, oy + th))
    if blur > 0:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im).astype(F) / 255.0
    if tint is not None:
        a = a * np.array(tint, dtype=F)[None, None, :]
    a = a * dark
    out = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    if len(_PLATE_CACHE) > 24:
        _PLATE_CACHE.clear()
    _PLATE_CACHE[key] = out
    return out


def screen(name, **kw):
    """Cached app-screen image."""
    key = (name, tuple(sorted((k, (round(v, 2) if isinstance(v, float) else v))
                              for k, v in kw.items())))
    if key not in _UI_CACHE:
        fn = getattr(ui, name)
        import inspect
        sig = inspect.signature(fn)
        clean = {k: v for k, v in kw.items() if k in sig.parameters}
        made = fn(**clean)
        if len(_UI_CACHE) > 60:
            _UI_CACHE.clear()
        _UI_CACHE[key] = made
        return made
    return _UI_CACHE[key]


# --------------------------------------------------------------------------
def plate_frame(name, t, dur, blur=18, zoom_from=1.0, zoom_to=1.10,
                pan=(0.5, 0.5), pan_to=None, dark=0.55, tint=None):
    """Ken-Burns plate for a shot."""
    p = ease_in_out(clamp(t / max(dur, 1e-6)))
    z = lerp(zoom_from, zoom_to, p)
    cx, cy = pan
    if pan_to:
        cx = lerp(pan[0], pan_to[0], p)
        cy = lerp(pan[1], pan_to[1], p)
    return load_plate(name, blur=blur, zoom=z, cx=cx, cy=cy, dark=dark, tint=tint)


# --------------------------------------------------------------------------
def blend(a, b, k):
    k = clamp(k)
    if k <= 0:
        return a
    if k >= 1:
        return b
    return Image.blend(a, b, k)


def add(img, layer, weight=1.0):
    """Additive composite of a float layer onto an image."""
    a = np.asarray(img).astype(F) / 255.0
    l = np.asarray(layer).astype(F) / 255.0
    return Image.fromarray((np.clip(a + l * weight, 0, 1) * 255).astype(np.uint8))


def screen_blend(img, layer, weight=1.0):
    a = np.asarray(img).astype(F) / 255.0
    l = np.asarray(layer).astype(F) / 255.0
    out = 1 - (1 - a) * (1 - l * weight)
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def radial_glow(size, color, cx=0.5, cy=0.5, r=0.6, power=2.0, strength=1.0):
    w, h = size
    yy = (np.arange(h, dtype=F) / h - cy)
    xx = (np.arange(w, dtype=F) / w - cx)
    d = np.sqrt((xx[None, :] * 1.0) ** 2 + (yy[:, None] * 0.8) ** 2) / r
    v = np.clip(1 - d, 0, 1) ** power * strength
    arr = v[..., None] * np.array(color, dtype=F)[None, None, :]
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))


def light_sweep(progress, angle=-18, width=0.22, color=(0.36, 0.85, 0.22)):
    """A soft diagonal band of light used for wipes / emphasis."""
    yy, xx = np.mgrid[0:H, 0:W].astype(F)
    x = xx / W
    y = yy / H
    ax = math.radians(angle)
    p = (x * math.cos(ax) + y * math.sin(ax))
    centre = lerp(-0.4, 1.4, progress)
    d = np.abs(p - centre) / width
    v = np.clip(1 - d, 0, 1) ** 2.2
    arr = v[..., None] * np.array(color, dtype=F)[None, None, :]
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8))


def wipe(a, b, k, angle=-14, soft=0.10):
    """Diagonal soft wipe between two frames."""
    if k <= 0:
        return a
    if k >= 1:
        return b
    yy, xx = np.mgrid[0:a.size[1], 0:a.size[0]].astype(F)
    ax = math.radians(angle)
    p = (xx / a.size[0]) * math.cos(ax) + (yy / a.size[1]) * math.sin(ax)
    p = (p - p.min()) / (p.max() - p.min())
    m = np.clip((k * (1 + soft * 2) - p) / soft, 0, 1)[..., None]
    aa = np.asarray(a).astype(F) / 255.0
    bb = np.asarray(b).astype(F) / 255.0
    out = aa * (1 - m) + bb * m
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def fade_to_black(img, k):
    if k <= 0:
        return img
    return Image.blend(img, Image.new("RGB", img.size, (8, 9, 10)), clamp(k))


def black(w=W, h=H):
    return Image.new("RGB", (w, h), (8, 9, 10))


# --------------------------------------------------------------------------
def hand_held(t, amp=1.0, seed=0):
    """Subtle organic camera drift (radians / units)."""
    a = seed * 1.7
    dx = math.sin(t * 0.9 + a) * 0.010 * amp + math.sin(t * 2.3 + a * 2) * 0.004 * amp
    dy = math.cos(t * 0.7 + a) * 0.008 * amp + math.sin(t * 1.9 + a) * 0.003 * amp
    dz = math.sin(t * 0.5 + a) * 0.012 * amp
    return dx, dy, dz


class Film:
    """A scene list on a timeline with cross-fades."""

    def __init__(self, name, width=W, height=H):
        self.name = name
        self.scenes = []
        self.trans = {}          # scene name -> (kind, duration)
        self.W, self.H = width, height

    def add(self, name, dur, fn, start=None, xfade=0.45, trans="fade"):
        if start is None:
            start = (self.scenes[-1]["start"] + self.scenes[-1]["dur"] - xfade) if self.scenes else 0.0
        self.scenes.append(dict(name=name, dur=dur, fn=fn, start=start, xfade=xfade))
        self.trans[name] = (trans, xfade)
        return self

    @property
    def duration(self):
        s = self.scenes[-1]
        return s["start"] + s["dur"]

    def frame(self, t):
        active = []
        for s in self.scenes:
            if s["start"] - 1e-6 <= t <= s["start"] + s["dur"] + 1e-6:
                active.append(s)
        if not active:
            return black()
        if len(active) == 1:
            s = active[0]
            return s["fn"](clamp(t - s["start"], 0, s["dur"]), s["dur"])
        # two shots overlapping
        a, b = active[0], active[-1]
        k = smooth(span(t, b["start"], a["start"] + a["dur"]))
        ia = a["fn"](clamp(t - a["start"], 0, a["dur"]), a["dur"])
        ib = b["fn"](clamp(t - b["start"], 0, b["dur"]), b["dur"])
        kind = self.trans.get(b["name"], ("fade", 0.4))[0]
        if kind == "wipe":
            return wipe(ia, ib, k, angle=-14)
        if kind == "light":
            out = blend(ia, ib, k)
            out = screen_blend(out, light_sweep(k, angle=-12, width=0.16,
                                                color=(0.30, 0.85, 0.22)), 0.55)
            return out
        if kind == "flash":
            out = blend(ia, ib, k)
            fl = math.sin(k * math.pi) ** 3
            if fl > 0.01:
                out = add(out, Image.new("RGB", out.size,
                                         tuple(int(120 * fl) for _ in range(3))))
            return out
        return blend(ia, ib, k)


# --------------------------------------------------------------------------
def end_card(logo_img, t, dur, glow=1.0):
    """Closing brand frame: the real mark on black with a green bloom."""
    img = black()
    img = add(img, radial_glow((W, H), (0.16, 0.62, 0.09), 0.5, 0.47, 0.55,
                               power=2.4, strength=0.55 * glow))
    p = ease_out(clamp(t / min(1.1, dur * 0.5)))
    s = int(lerp(300, 470, p))
    lg = logo_img.resize((s, s), Image.LANCZOS)
    a = np.asarray(lg).astype(F) / 255.0
    alpha = a[..., 3:4] * p
    base = np.asarray(img).astype(F) / 255.0
    x0 = (W - s) // 2
    y0 = (H - s) // 2
    region = base[y0:y0 + s, x0:x0 + s]
    base[y0:y0 + s, x0:x0 + s] = region * (1 - alpha) + (a[..., :3] * 1.15) * alpha
    img = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8))
    # bloom halo
    halo = Image.new("RGB", (W, H))
    halo.paste(lg, (x0, y0), lg)
    halo = halo.filter(ImageFilter.GaussianBlur(28))
    img = screen_blend(img, halo, 0.55 * p)
    return img
