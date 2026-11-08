"""
Shared shot vocabulary for the three SIYMON explainers.

Every shot is a function (t, dur) -> PIL frame, so the three videos stay
visually identical in phone, logo, palette, lens and transitions.
"""
from __future__ import annotations

import math
import os
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

from siymon3d import (F, Camera, Renderer, Scene, Obj, Sprite, ScreenQuad, Mesh,
                      lerp, clamp, smooth, ease_in_out, ease_out, ease_in, span, norm,
                      trans, rot_y, rot_x, rot_z, box, sphere, cylinder)
import siymon3d as S3
import props
import ui
import film
from film import screen
from film import W, H, load_plate, radial_glow, add, screen_blend, blend, black

GREEN = np.array([0x5D, 0xD6, 0x2C], dtype=F) / 255.0
GREEN_DK = np.array([0x33, 0x74, 0x18], dtype=F) / 255.0
WHITE = np.array([0.97, 0.97, 0.95], dtype=F)

R = Renderer(W, H, ss=1.0)
LOGO = Image.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/logo.png")).convert("RGBA")
BADGE = Image.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/badge.png")).convert("RGBA")

# food stills grouped by store type
FOOD = {
    "burger": "food/burger.jpg",
    "tagine": "food/tagine.jpg",
    "coffee": "food/coffee.jpg",
    "groceries": "food/groceries.jpg",
    "pharmacy": "food/pharmacy.jpg",
    "bag": "food/delivery-bag.jpg",
}


# --------------------------------------------------------------------------
def portrait(kind, w, h, r=26, dim=1.0, zoom=1.0):
    """A product still cropped into a rounded card."""
    im = Image.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets") + "/" + FOOD[kind]).convert("RGB")
    scale = max(w / im.width, h / im.height) * zoom
    nw, nh = max(w, int(im.width * scale)), max(h, int(im.height * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    ox = (nw - w) // 2
    oy = (nh - h) // 2
    im = im.crop((ox, oy, ox + w, oy + h))
    if dim != 1.0:
        a = np.asarray(im).astype(F) * dim
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    im = im.convert("RGBA")
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    im.putalpha(m)
    return im


def warm_glow(img, color=(0.20, 0.62, 0.16), strength=0.5, cx=0.5, cy=0.5, r=0.55):
    return add(img, radial_glow((W, H), color, cx, cy, r, 2.2, strength))


def streak(img, color=GREEN, weight=0.5, y=0.5, x0=0.1, x1=0.9, width=0.02, blur=26):
    """A thin horizontal light streak (lens flare)."""
    layer = Image.new("RGB", (W, H), (0, 0, 0))
    d = ImageDraw.Draw(layer)
    yy = int(y * H)
    d.rectangle([int(x0 * W), yy - int(width * H), int(x1 * W), yy + int(width * H)],
                fill=tuple(int(c * 255) for c in color))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return add(img, layer, weight)


def comp(base, rend, shadow=0.35):
    """Composite an RGBA-ish render (rgb + cov) over a plate with a soft shadow."""
    rgb, cov = rend
    a = np.asarray(cov).astype(F) / 255.0
    a = np.clip(a * 1.4, 0, 1)
    b = np.asarray(base).astype(F) / 255.0
    f = np.asarray(rgb).astype(F) / 255.0
    out = b * (1 - a[..., None]) + f
    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))


def shake(t, amp=1.0, seed=0):
    dx, dy, dz = film.hand_held(t, amp, seed)
    return dx, dy, dz


# --------------------------------------------------------------------------
# shot: phone hero against a photographic plate
# --------------------------------------------------------------------------
def phone_shot(plate, t, dur, screen_img, eye=(0.0, 0.02, 5.0), target=(0, 0, 0),
               rot_y_deg=0.0, rot_x_deg=0.0, fov=30, exposure=1.25, bloom=0.55,
               dark=0.5, blur=20, glow=1.0, drift=1.0, seed=0, glow_color=GREEN,
               screen_brightness=1.12, shadow=True):
    bg = film.plate_frame(plate, t, dur, blur=blur, dark=dark) if plate else black()
    ph = props.make_phone(screen_img)
    ph.rot[1] = math.radians(rot_y_deg)
    ph.rot[0] = math.radians(rot_x_deg)
    dx, dy, dz = shake(t, drift, seed)
    ph.pos = np.array([dx * 1.2, dy * 1.2, 0], dtype=F)
    sc = Scene()
    sc.ambient = np.array([0.055, 0.058, 0.062], dtype=F)
    sc.light((-0.55, -0.55, -0.62), (0.85, 0.90, 1.0), 0.95)
    sc.light((0.75, -0.05, -0.35), (0.35, 1.0, 0.45), 0.55)
    sc.light((0.0, 0.9, -0.2), (0.5, 0.9, 0.55), 0.35)
    sc.add(ph)
    if glow > 0:
        for d, r, it in ((0.62, 0.95, 0.16), (0.0, 0.62, 0.10)):
            sc.add_sprite(Sprite((0, 0, d), r, glow_color, it * glow, 2.4, parent=ph))
    cam = Camera(eye, target, fov=fov)
    rgb, cov = R.render(sc, cam, exposure=exposure, bloom=bloom, return_alpha=True,
                        vignette=0.34, grain=0.014)
    out = comp(bg, (rgb, cov))
    # light spill on the backdrop
    if glow > 0:
        out = add(out, radial_glow((W, H), tuple(glow_color * 0.55), 0.5, 0.42, 0.62, 2.6, 0.16 * glow))
    return out


# --------------------------------------------------------------------------
# shot: logo reveal
# --------------------------------------------------------------------------
def logo_shot(t, dur, plate=None, scale_from=0.2, scale_to=1.0, glow=1.0,
              y=0.0, rot_from=0.0, rot_to=0.0, dark=0.62, blur=26, bloom=1.1,
              rise=0.0):
    if plate:
        bg = film.plate_frame(plate, t, dur, blur=blur, dark=dark)
    else:
        bg = black()
        bg = add(bg, radial_glow((W, H), (0.16, 0.60, 0.09), 0.5, 0.48, 0.62, 2.4, 0.5 * glow))
    p = ease_out(clamp(t / max(0.9, dur * 0.55)))
    s = lerp(scale_from, scale_to, p)
    rot = lerp(rot_from, rot_to, ease_out(clamp(t / max(1.2, dur * 0.6))))
    size = 520
    lg = LOGO.resize((int(size * s), int(size * s)), Image.LANCZOS)
    if abs(rot) > 0.2:
        lg = lg.rotate(rot, resample=Image.BICUBIC, expand=True)
    x0 = (W - lg.width) // 2
    y0 = int((H - lg.height) // 2 + y * H + (1 - p) * rise * H)
    # bloom halo
    halo = Image.new("RGB", (W, H))
    halo.paste(lg, (x0, y0), lg)
    halo = halo.filter(ImageFilter.GaussianBlur(20))
    bg = screen_blend(bg, halo, 0.42 * bloom * p)
    base = np.asarray(bg).astype(F) / 255.0
    a = np.asarray(lg).astype(F) / 255.0
    alpha = a[..., 3:4] * p
    h0, w0 = lg.height, lg.width
    region = base[y0:y0 + h0, x0:x0 + w0]
    base[y0:y0 + h0, x0:x0 + w0] = region * (1 - alpha) + np.clip(a[..., :3] * 1.12, 0, 1) * alpha
    out = Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8))
    return out


# --------------------------------------------------------------------------
# shot: full-bleed interface with a slow push-in
# --------------------------------------------------------------------------
def screen_shot(img, t, dur, plate=None, push=0.045, drift=1.0, seed=0, radius=0):
    """Full-bleed app screen, slightly over-sized so the camera can push in."""
    if plate:
        bg = film.plate_frame(plate, t, dur, blur=24, dark=0.42)
    else:
        bg = black()
    p = ease_in_out(clamp(t / dur))
    sx = 0.86 + push * p
    sh = int(H * sx)
    sw = int(sh * img.width / img.height)
    im = img.resize((sw, sh), Image.LANCZOS)
    dx, dy, _ = shake(t, drift, seed)
    ox = (W - sw) // 2 + int(dx * 40)
    oy = (H - sh) // 2 + int(dy * 40 - (sh - H) * 0.35 * p)
    canvas = bg.copy()
    if radius:
        m = Image.new("L", (sw, sh), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, sw - 1, sh - 1], radius=radius, fill=255)
        canvas.paste(im, (ox, oy), m)
    else:
        canvas.paste(im, (ox, oy))
    return canvas


# --------------------------------------------------------------------------
# shot: floating interface card in 3D over a plate (parallax)
# --------------------------------------------------------------------------
def card_shot(plate, t, dur, img, w=0.86, tilt=0.0, y=0.0,
              dark=0.55, blur=20, glow=0.8, exposure=1.3, fov=34, max_h=1.45):
    """A floating interface card in 3D over a photographic plate."""
    bg = film.plate_frame(plate, t, dur, blur=blur, dark=dark) if plate else black()
    sc = Scene()
    sc.ambient = np.array([0.05, 0.05, 0.055], dtype=F)
    sc.light((-0.5, -0.6, -0.6), (0.9, 0.95, 1.0), 0.9)
    sc.light((0.7, -0.1, -0.4), (0.35, 1.0, 0.45), 0.5)
    p = ease_in_out(clamp(t / dur))
    A = img.height / img.width
    w = min(w, max_h / A)
    h = w * A
    obj = Obj(name="card")
    obj.add(Obj(props.rounded_prism(w, h, 0.05, 0.055, (0.055, 0.058, 0.062), seg=6)))
    z = 0.030
    corners = np.array([[-w / 2, h / 2, z], [w / 2, h / 2, z],
                        [w / 2, -h / 2, z], [-w / 2, -h / 2, z]], dtype=F)
    obj.screens.append(ScreenQuad(corners, img, brightness=1.14,
                                  radius=int(94 * (w / 0.9)), selflit=True))
    obj.rot[1] = math.radians(tilt)
    obj.rot[0] = math.radians(-3.0 * (1 - p))
    dx, dy, dz = shake(t, 0.6, 3)
    obj.pos = np.array([dx, y + dy - 0.06 * (1 - p), 0], dtype=F)
    sc.add(obj)
    if glow > 0:
        sc.add_sprite(Sprite((0, 0, 0.30), w * 0.95, GREEN, 0.10 * glow, 2.5, parent=obj))
    cam = Camera((0, 0, 3.1), (0, 0, 0), fov=fov)
    rgb, cov = R.render(sc, cam, exposure=exposure, bloom=0.5, return_alpha=True,
                        vignette=0.3, grain=0.013)
    out = comp(bg, (rgb, cov))
    if glow > 0:
        out = add(out, radial_glow((W, H), tuple(GREEN * 0.5), 0.5, 0.5, 0.55, 2.4, 0.10 * glow))
    return out


# --------------------------------------------------------------------------
# shot: 3D sequence (city / hex / rider) with its own scene builder
# --------------------------------------------------------------------------
def scene_shot(plate, t, dur, build, eye, target, fov=42, dark=0.35, blur=18,
               exposure=1.15, bloom=0.6, glow=0.0, vignette=0.4, fog=True, clear=None,
               fog_density=0.014):
    bg = film.plate_frame(plate, t, dur, blur=blur, dark=dark) if plate else black()
    sc = Scene()
    sc.clear = (np.array(clear, dtype=F) if clear is not None
                else np.array([0.02, 0.023, 0.026], dtype=F))
    sc.ambient = np.array([0.07, 0.075, 0.085], dtype=F)
    sc.light((-0.30, -0.80, -0.52), (1.0, 0.92, 0.80), 0.95)
    sc.light((0.75, -0.15, 0.35), (0.35, 1.0, 0.50), 0.75)
    sc.light((0.1, 0.9, -0.3), (0.30, 0.55, 0.95), 0.30)
    if fog:
        sc.fog = (np.array([0.03, 0.035, 0.04], dtype=F), fog_density)
    build(sc, t, dur)
    cam = Camera(eye(t) if callable(eye) else eye,
                 target(t) if callable(target) else target, fov=fov)
    rgb, cov = R.render(sc, cam, exposure=exposure, bloom=bloom, return_alpha=True,
                        vignette=vignette, grain=0.013)
    out = comp(bg, (rgb, cov))
    if glow > 0:
        out = add(out, radial_glow((W, H), tuple(GREEN * 0.5), 0.5, 0.55, 0.5, 2.4, glow))
    return out


# --------------------------------------------------------------------------
# shot: a photographic moment with a cinematic push (kitchen, street, handoff)
# --------------------------------------------------------------------------
def moment_shot(plate, t, dur, blur=0, zoom=(1.02, 1.14), pan=(0.5, 0.5),
                pan_to=None, dark=0.78, tint=None, glow=0.0, glow_cy=0.5,
                glow_r=0.5, flash=0.0):
    out = film.plate_frame(plate, t, dur, blur=blur, zoom_from=zoom[0], zoom_to=zoom[1],
                           pan=pan, pan_to=pan_to, dark=dark, tint=tint)
    if glow > 0:
        p = ease_in_out(clamp(t / dur))
        out = add(out, radial_glow((W, H), tuple(GREEN * 0.55), 0.5, glow_cy, glow_r, 2.2,
                                   glow * (0.6 + 0.4 * p)))
    if flash > 0:
        k = math.exp(-((t - dur * 0.42) ** 2) / (2 * (dur * 0.09) ** 2)) * flash
        out = add(out, Image.new("RGB", (W, H), tuple(int(230 * k) for _ in range(3))))
    return out


# --------------------------------------------------------------------------
# shot: icon symbol animation (no text) e.g. checkmark, hex, spark
# --------------------------------------------------------------------------
def symbol_shot(t, dur, plate=None, kind="check", dark=0.6, blur=24, color=GREEN,
                cx=0.5, cy=0.47, size=0.30):
    bg = film.plate_frame(plate, t, dur, blur=blur, dark=dark) if plate else black()
    bg = add(bg, radial_glow((W, H), tuple(color * 0.5), cx, cy, 0.62, 2.4, 0.34))
    p = ease_out(clamp(t / max(0.5, dur * 0.45)))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    s = size * W * lerp(0.6, 1.0, p)
    x0, y0 = cx * W, cy * H
    if kind == "check":
        # ring
        rr = s * 0.86
        d.ellipse([x0 - rr, y0 - rr, x0 + rr, y0 + rr],
                  outline=tuple(int(c * 255) for c in color) + (255,), width=int(10 * p + 2))
        pts = [(x0 - s * 0.42, y0 + s * 0.02), (x0 - s * 0.10, y0 + s * 0.34), (x0 + s * 0.48, y0 - s * 0.30)]
        # draw the tick progressively
        prog = clamp((t / max(0.6, dur * 0.5)) * 1.6)
        seg1 = [pts[0], pts[1]]
        seg2 = [pts[1], pts[2]]
        wdt = int(14 + 10 * p)
        if prog > 0:
            k = clamp(prog * 2)
            d.line([seg1[0], (lerp(seg1[0][0], seg1[1][0], k), lerp(seg1[0][1], seg1[1][1], k))],
                   fill=tuple(int(c * 255) for c in color) + (255,), width=wdt, joint="curve")
        if prog > 0.5:
            k = clamp((prog - 0.5) * 2)
            d.line([seg1[1], (lerp(seg2[0][0], seg2[1][0], k), lerp(seg2[0][1], seg2[1][1], k))],
                   fill=tuple(int(c * 255) for c in color) + (255,), width=wdt, joint="curve")
    elif kind == "hex":
        pts = []
        for i in range(6):
            a = math.radians(60 * i - 90)
            pts.append((x0 + s * 0.8 * math.cos(a), y0 + s * 0.8 * math.sin(a)))
        d.polygon(pts, outline=tuple(int(c * 255) for c in color) + (255,),
                  width=max(2, int(10 * p)))
    halo = layer.filter(ImageFilter.GaussianBlur(24))
    bg = screen_blend(bg, halo.convert("RGB"), 0.6)
    base = np.asarray(bg).astype(F) / 255.0
    a = np.asarray(layer).astype(F) / 255.0
    base = base * (1 - a[..., 3:4]) + a[..., :3] * a[..., 3:4]
    return Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8))
