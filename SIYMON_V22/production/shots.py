"""
SIYMON-specific shots: dispatch hexes, live route, address pin, codes, earnings,
store preparation and hand-over. Built on scenes.py + props.py.
"""
from __future__ import annotations

import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from siymon3d import (F, Camera, Scene, Obj, Sprite, ScreenQuad, Mesh, lerp, clamp,
                      smooth, ease_in_out, ease_out, ease_in, span, norm, box, sphere,
                      cylinder, rot_y)
import props
import film
import scenes
from film import screen
from scenes import (GREEN, GREEN_DK, W, H, R, LOGO, comp, add, screen_blend, portrait,
                    phone_shot, moment_shot)
from film import radial_glow, black, load_plate


# --------------------------------------------------------------------------
def orbit(center, dist, height, azim_deg, tilt=0.0):
    """Camera position orbiting a centre point (degrees, azimuth 0 = +Z)."""
    a = math.radians(azim_deg)
    cx, cy, cz = center
    return (cx + math.sin(a) * dist, cy + height, cz + math.cos(a) * dist)


# --------------------------------------------------------------------------
# 3D city + dispatch hexes (aerial)
# --------------------------------------------------------------------------
def build_city(sc, extent=26, seed=7, density=0.62, block=2.6, skip_center=3.0):
    for m in props.make_holo_city(extent=extent, seed=seed, density=density, block=block,
                                  skip_center=skip_center):
        sc.add(Obj(m))
    sc.add(Obj(props.make_ground(extent * 5, (0.020, 0.024, 0.030))))


def hex_rings(sc, radius=3, size=1.7, y=0.04, fill_emis=0.18):
    """Returns [(fill_obj, outline_obj)] per ring."""
    return props.make_hex_field(radius=radius, size=size, y=y, fill_emis=fill_emis)


def marker(sc, pos, color=GREEN, h=1.6, width=0.16):
    """A vertical light pillar + ground disc marking a place."""
    o = Obj(name="marker")
    o.pos = np.array(pos, dtype=F)
    o.add(Obj(box(width * 0.45, h, width * 0.45, color, center=(0, h / 2, 0), emissive=0.55)))
    d = Obj(props.hex_plate(0, 0, width * 2.2, color, y=0.02, emissive=0.8))
    o.add(d)
    sc.add(o)
    sc.add_sprite(Sprite((pos[0], pos[1] + h * 0.5, pos[2]), 1.8, color, 0.20, 2.6))
    return o


def route_mesh(pts, color=GREEN, width=0.30, y=0.05, emissive=1.5):
    ms = []
    for i in range(len(pts) - 1):
        a = np.array(pts[i], dtype=F)
        b = np.array(pts[i + 1], dtype=F)
        d = b - a
        L = float(np.linalg.norm(d))
        if L < 1e-6:
            continue
        d = d / L
        n = np.array([-d[2], 0, d[0]], dtype=F) * width / 2
        v = [a - n, b - n, b + n, a + n]
        v = [np.array([p[0], y, p[2]], dtype=F) for p in v]
        ms.append(Mesh(np.array(v, dtype=F), [(0, 1, 2, 3)], color, double=True, emissive=emissive))
    return ms


def rider_dot(sc, pos, color=GREEN, r=0.55):
    o = Obj(name="dot")
    o.pos = np.array(pos, dtype=F)
    o.add(Obj(sphere(r, color, center=(0, r * 0.9, 0), seg=14, rings=10, emissive=1.3)))
    ring = Obj(props.hex_plate(0, 0, r * 3.2, color, y=0.02, emissive=0.35))
    o.add(ring)
    sc.add(o)
    sc.add_sprite(Sprite((pos[0], pos[1] + r, pos[2]), 2.4, color, 0.75, 2.2))
    return o


# --------------------------------------------------------------------------
# shot: aerial dispatch field with rings expanding
# --------------------------------------------------------------------------
def dispatch_aerial(t, dur, cam_a=(8.5, 15.0, 12.0), cam_b=(5.0, 11.5, 15.5), look=(0, 0, 0.5),
                    rings_n=3, store=(0, 0, 0), rider_from=(6.0, 0.06, 8.0),
                    rider_to=(1.2, 0.06, 1.2), draw_routes=False, exposure=1.2,
                    glow=0.4, plate=None, dark=0.5, seed=7, skip_center=11.0):
    def build(sc, tt, dd):
        build_city(sc, seed=seed, skip_center=skip_center)
        rings = hex_rings(sc, radius=rings_n, size=1.7, fill_emis=0.10)
        # rings pulse outward
        for k, (f, o) in enumerate(rings):
            sc.add(f, o)
        marker(sc, store, h=2.0)
        p = ease_in_out(clamp(tt / max(dd, 1e-6)))
        rx = lerp(rider_from[0], rider_to[0], p)
        rz = lerp(rider_from[2], rider_to[2], p)
        rider_dot(sc, (rx, 0.06, rz))
    a = np.array(cam_a, dtype=F)
    b = np.array(cam_b, dtype=F)
    eye = lambda t2: tuple(a + (b - a) * ease_in_out(clamp(t2 / max(dur, 1e-6))))
    return scenes.scene_shot(plate, t, dur, build, eye, look, fov=42, exposure=exposure,
                             bloom=0.50, glow=glow, fog=False, dark=dark)


# --------------------------------------------------------------------------
# shot: the 500 m dispatch grid on its own — dark plane, glowing cells,
# three rings light up outward and the nearest rider is picked
# --------------------------------------------------------------------------
def hexgrid_shot(t, dur, radius=3, size=1.45, exposure=1.15, glow=0.35,
                 cam_a=(7.0, 11.5, 12.0), cam_b=(3.6, 8.0, 14.6), look=(0, 0, 0.3),
                 fov=40, plate=None, dark=0.45):
    rings = props.make_hex_field(radius=radius, size=size, y=0.02, fill_emis=0.07)

    def build(sc, tt, dd):
        p = clamp(tt / max(dd, 1e-6))
        # ground plane, so the field sits on something
        sc.add(Obj(Mesh(np.array([[-40, 0, -40], [40, 0, -40], [40, 0, 40], [-40, 0, 40]],
                                  dtype=F),
                        [(0, 1, 2, 3)], (0.030, 0.034, 0.040), double=True)))
        for k, (fill, outline) in enumerate(rings):
            # the whole field is there; a pulse of light travels outward
            a = clamp((p - 0.05 - k * 0.10) / 0.22)
            pulse = math.sin(math.pi * a) if 0 < a < 1 else 0.0
            fill.mesh.emissive = 0.045 + 0.075 * pulse
            outline.mesh.emissive = 0.55 + 0.55 * pulse
            sc.add(fill, outline)
        # the store at the centre, then the nearest rider's cell lights up
        marker(sc, (0, 0, 0), h=2.2, width=0.14)
        if p > 0.40:
            k = clamp((p - 0.40) / 0.30)
            q, r = -1, 2
            cx, cz = props.hex_center(q, r, size)
            sc.add(Obj(props.hex_plate(q, r, size, GREEN * 0.22, gap=0.93, y=0.05,
                                      emissive=0.02 + 0.05 * k)))
            sc.add(Obj(props.hex_outline_mesh(q, r, size, width=0.055 + 0.05 * k,
                                             y=0.06, emissive=0.7 + 0.7 * k)))
            if k > 0.45:
                g = clamp((k - 0.45) / 0.35)
                tr = route_mesh([(0, 0, 0), (cx * g, 0, cz * g)], width=0.14,
                                emissive=0.55 + 0.5 * g)
                if tr:
                    sc.add(Obj(props.merge(tr)))
            if k > 0.80:
                sc.add(Obj(sphere(0.30, GREEN, center=(cx, 0.34, cz), seg=14, rings=10,
                                  emissive=1.1)))
                sc.add_sprite(Sprite((cx, 0.34, cz), 1.5, GREEN, 0.22, 2.6))
        # a faint halo, not a hotspot
        sc.add_sprite(Sprite((0, 0.5, 0), 6.0, GREEN, 0.05, 2.2))
        # low, dim city silhouettes far out, purely for depth
        for k in range(26):
            ang = k * (2 * math.pi / 26) + 0.3
            dist = 26.0 + 3.0 * math.sin(k * 2.1)
            bx = math.sin(ang) * dist
            bz = math.cos(ang) * dist
            hh = 1.4 + 1.6 * abs(math.sin(k * 1.7))
            ww = 2.0 + 1.2 * abs(math.cos(k * 2.3))
            sc.add(Obj(box(ww, hh, ww, (0.022, 0.030, 0.026),
                           center=(bx, hh / 2, bz), emissive=0.02)))
            sc.add(Obj(box(ww * 1.01, 0.035, ww * 1.01, (0.10, 0.42, 0.16),
                           center=(bx, hh, bz), emissive=0.22)))

    def eye(tt):
        p = ease_in_out(clamp(tt / max(dur, 1e-6)))
        return tuple(np.array(cam_a, dtype=F) + (np.array(cam_b, dtype=F) - np.array(cam_a, dtype=F)) * p)

    return scenes.scene_shot(plate, t, dur, build, eye, look, fov=fov,
                             exposure=exposure, bloom=0.52, glow=glow, fog=False,
                             dark=dark, clear=(0.014, 0.018, 0.022),
                             vignette=0.46)


# --------------------------------------------------------------------------
# shot: street-level route with a travelling rider + glowing path
# --------------------------------------------------------------------------
def route_street(t, dur, path=((0, 0, 12), (0, 0, 2), (2.6, 0, -5), (2.6, 0, -14)),
                 offset=(2.3, 2.5, 7.6), look_off=(-0.4, 1.0, -4.0), fov=34, exposure=1.2,
                 seed=5, show_rider=True, plate=None, width=0.32, follow=True,
                 street_w=5.6):
    """Tracking shot down a street canyon: the camera rides with the rider."""
    pts = [np.array(p, dtype=F) for p in path]

    def rider_at(p):
        seg = (len(pts) - 1) * clamp(p)
        i = min(int(seg), len(pts) - 2)
        f = seg - i
        return pts[i] + (pts[i + 1] - pts[i]) * f, i

    def build(sc, tt, dd):
        for m in props.make_street(w=street_w, length=60, seed=seed):
            sc.add(Obj(m))
        sc.add(Obj(props.make_ground(190, (0.028, 0.032, 0.038))))
        p = clamp(tt / max(dd, 1e-6))
        pos, i = rider_at(p)
        ms_all = route_mesh(pts, width=width * 0.6, emissive=0.45)
        if ms_all:
            sc.add(Obj(props.merge(ms_all)))
        done = [pts[k] for k in range(0, i + 1)] + [pos]
        if len(done) >= 2:
            ms = route_mesh(done, width=width, emissive=1.5)
            if ms:
                sc.add(Obj(props.merge(ms)))
        if show_rider:
            rb = props.make_rider_bike()
            rb.pos = pos
            d = pts[i + 1] - pts[i]
            rb.rot[1] = math.atan2(float(d[0]), float(d[2])) + math.pi
            sc.add(rb)
            sc.add_sprite(Sprite((float(pos[0]), 0.5, float(pos[2])), 1.0, GREEN, 0.16, 2.8))

    corridor = street_w / 2 - 0.85      # keep the camera off the facades

    def _cam_x(x):
        return max(-corridor, min(corridor, x))

    if follow:
        def eye(tt):
            p = clamp(tt / max(dur, 1e-6))
            pos, _ = rider_at(p)
            return (_cam_x(float(pos[0]) + offset[0]), offset[1],
                    float(pos[2]) + offset[2])
        def target(tt):
            p = clamp(tt / max(dur, 1e-6))
            pos, _ = rider_at(p)
            return (_cam_x(float(pos[0]) + look_off[0]), look_off[1],
                    float(pos[2]) + look_off[2])
    else:
        eye = (offset[0], offset[1], offset[2])
        target = look_off
    return scenes.scene_shot(plate, t, dur, build, eye, target, fov=fov,
                             exposure=exposure, bloom=0.7, fog=True, dark=0.3,
                             clear=(0.030, 0.036, 0.052), fog_density=0.020)


# --------------------------------------------------------------------------
# shot: address pin drop on the city, then route to the store
# --------------------------------------------------------------------------
def pin_shot(t, dur, cam=(14, 11, 17), look=(0, 0.6, 0), plate=None, exposure=1.2):
    def build(sc, tt, dd):
        build_city(sc, seed=11, density=0.50)
        p = ease_out(clamp(tt / (dd * 0.42)))
        y = lerp(11.0, 0.0, p)
        pin = Obj(name="pin")
        pin.pos = np.array([0.6, y, 0.4], dtype=F)
        pin.add(Obj(sphere(0.55, GREEN, center=(0, 2.2, 0), seg=14, rings=10, emissive=0.9)))
        pin.add(Obj(box(0.20, 2.2, 0.20, GREEN, center=(0, 1.0, 0), emissive=1.1)))
        pin.add(Obj(props.hex_plate(0, 0, 1.5, GREEN, y=0.05, emissive=0.6)))
        sc.add(pin)
        if p > 0.55:
            k = clamp((p - 0.55) / 0.3)
            rp = [(0.6, 0, 0.4), (0.6, 0, -4.2), (-3.6, 0, -4.2), (-3.6, 0, -8.4)]
            n = max(2, int(lerp(2, 4, k)))
            ms = route_mesh(rp[:n], width=0.34)
            if ms:
                sc.add(Obj(props.merge(ms)))
            marker(sc, (-3.6, 0, -8.4), h=2.4)
        sc.add_sprite(Sprite((0.6, 2.2, 0.4), 3.4, GREEN, 0.30, 2.4))
    return scenes.scene_shot(plate, t, dur, build, cam, look, fov=40, exposure=exposure,
                             bloom=0.7, glow=0.22, fog=False)


# --------------------------------------------------------------------------
# 2D: floating product tiles flying into a SIYMON bag over a plate
# --------------------------------------------------------------------------
def fly_to_bag(t, dur, plate="env/store.jpg", kinds=("burger", "coffee", "groceries"),
               dark=0.62, blur=0, title=None):
    bg = film.plate_frame(plate, t, dur, blur=blur, zoom_from=1.02, zoom_to=1.10, dark=dark)
    p = clamp(t / max(dur, 1e-6))
    # bag sits lower-right
    bx, by, bw, bh = W * 0.52, H * 0.52, W * 0.34, W * 0.42
    bag = Image.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets") + "/food/delivery-bag.jpg").convert("RGB")
    bag = bag.resize((int(bw), int(bh)), Image.LANCZOS)
    m = Image.new("L", bag.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, bag.width - 1, bag.height - 1], radius=40, fill=255)
    canvas = bg.copy()
    canvas.paste(bag, (int(bx), int(by)), m)
    # glowing rim around bag
    glow = Image.new("RGB", canvas.size, (0, 0, 0))
    gm = Image.new("L", canvas.size, 0)
    gm.paste(m, (int(bx), int(by)))
    glow.paste(Image.new("RGB", canvas.size, (60, 200, 40)), (0, 0), gm)
    canvas = screen_blend(canvas, glow.filter(ImageFilter.GaussianBlur(26)), 0.30)
    # tiles fly in one by one
    for i, k in enumerate(kinds):
        s0 = 0.16 + i * 0.20
        s1 = s0 + 0.34
        q = clamp((p - s0) / (s1 - s0))
        if q <= 0 or q >= 1:
            continue
        e = ease_in_out(q)
        tw = int(W * lerp(0.40, 0.16, e))
        th = int(tw * 0.66)
        tile = portrait(k, tw, th, r=int(tw * 0.16), zoom=1.05)
        x = lerp(W * 0.50 - tw / 2 + (i - 1) * W * 0.10, bx + bw * 0.5 - tw / 2, e)
        y = lerp(H * 0.20 + (i % 2) * H * 0.10, by + bh * 0.42, e)
        canvas.paste(tile, (int(x), int(y)), tile)
    return canvas


# --------------------------------------------------------------------------
# 2D: verification code being entered on a phone screen, in 3D
# --------------------------------------------------------------------------
def code_shot(t, dur, plate=None, entered_max=6, ok_at=0.72, dark=0.72, blur=10):
    """The 6-digit verification stage, full-bleed so the code reads clearly."""
    p = clamp(t / dur)
    n = int(round(lerp(1, entered_max, clamp(p / ok_at))))
    ok = clamp((p - ok_at) / 0.16)
    img = screen("screen_code", entered=max(0, min(n, 6)), ok=ok)
    out = scenes.screen_shot(img, t, dur, plate=plate, push=0.03, drift=0.6)
    if ok > 0.02:
        out = add(out, radial_glow((W, H), tuple(GREEN * 0.85), 0.5, 0.55, 0.5, 2.2, 0.22 * ok))
    return out


# --------------------------------------------------------------------------
# 2D: earnings / wallet rise
# --------------------------------------------------------------------------
def earnings_shot(t, dur, plate="env/street.jpg", dark=0.72, blur=12):
    p = clamp(t / dur)
    glow = smooth(clamp((p - 0.25) / 0.5))
    img = screen("wallet_screen", balance_glow=glow, entries=4)
    out = scenes.card_shot(plate, t, dur, img, w=0.92, tilt=-3.0, dark=dark, blur=blur,
                           glow=0.7)
    if glow > 0:
        out = add(out, radial_glow((W, H), tuple(GREEN * 0.8), 0.5, 0.33, 0.42, 2.4,
                                   0.16 * glow))
    return out


# --------------------------------------------------------------------------
# 2D: a store/product panel with a new product appearing and stock toggling
# --------------------------------------------------------------------------
def products_shot(t, dur, plate="env/store.jpg", dark=0.66):
    p = clamp(t / dur)
    toggle = 1.0 - smooth(clamp((p - 0.45) / 0.2))
    add_p = ease_out(clamp((p - 0.12) / 0.25))
    img = screen("screen_merchant_products", toggle=toggle, add=add_p,
                        scroll=0.0)
    out = scenes.card_shot(plate, t, dur, img, tilt=5.0, dark=dark, glow=0.7)
    if add_p > 0:
        out = add(out, radial_glow((W, H), tuple(GREEN * 0.7), 0.80, 0.34, 0.22, 2.2,
                                   0.12 * add_p))
    return out


# --------------------------------------------------------------------------
# 2D: merchant order arrives (notification) then accept
# --------------------------------------------------------------------------
def order_arrives_shot(t, dur, plate="env/kitchen.jpg", dark=0.70):
    p = clamp(t / dur)
    state = 0 if p < 0.42 else (1 if p < 0.72 else 2)
    pulse = math.exp(-((p - 0.30) ** 2) / (2 * 0.045 ** 2))
    img = screen("screen_merchant_orders", state=state, pulse=pulse)
    out = scenes.card_shot(plate, t, dur, img, tilt=-4.0, dark=dark, glow=0.9)
    if pulse > 0.05:
        out = add(out, radial_glow((W, H), tuple(GREEN * 0.9), 0.5, 0.34, 0.42, 2.2,
                                   0.18 * pulse))
    return out


# --------------------------------------------------------------------------
# 2D: driver offer arriving then accepted
# --------------------------------------------------------------------------
def offer_shot(t, dur, plate="env/street.jpg", dark=0.72):
    p = clamp(t / dur)
    accept = ease_in(clamp((p - 0.40) / 0.22))
    img = screen("screen_driver_offer", accept=accept)
    out = scenes.card_shot(plate, t, dur, img, tilt=4.0, dark=dark, glow=0.9)
    if accept > 0.4:
        out = add(out, radial_glow((W, H), tuple(GREEN * 0.9), 0.5, 0.55, 0.4, 2.2,
                                   0.16 * accept))
    return out


# --------------------------------------------------------------------------
# 2D: live tracking map on the phone
# --------------------------------------------------------------------------
def track_shot(t, dur, plate=None, dark=0.62, steps=None):
    p = clamp(t / dur)
    prog = ease_in_out(p)
    st = 1 if p < 0.45 else 2
    img = screen("screen_track", progress=prog, steps=st)
    return scenes.card_shot(plate, t, dur, img, w=0.98, tilt=0.0, dark=dark, blur=16, glow=0.8)


# --------------------------------------------------------------------------
# 2D: hand-over close-up with a success tick
# --------------------------------------------------------------------------
def handoff_shot(t, dur, plate="people/handoff.jpg", dark=0.86, ok_at=0.55):
    out = moment_shot(plate, t, dur, blur=0, zoom=(1.04, 1.16), dark=dark, glow=0.30,
                      glow_cy=0.55, glow_r=0.45)
    p = clamp((t / dur - ok_at) / 0.22)
    if p > 0:
        out = scenes.symbol_shot.__globals__["add"](out, radial_glow((W, H), tuple(GREEN * 0.9),
                                                                    0.5, 0.5, 0.34, 2.4,
                                                                    0.30 * p))
    return out


# --------------------------------------------------------------------------
# 2D: scrolling app UI, full bleed with a push and a tap highlight
# --------------------------------------------------------------------------
def scroll_shot(t, dur, screen_name, plate=None, scroll_from=0.0, scroll_to=140.0,
                tap=None, push=0.05, dark=0.5):
    p = ease_in_out(clamp(t / max(dur, 1e-6)))
    scroll = round(lerp(scroll_from, scroll_to, p) / 8) * 8
    img = screen(screen_name, scroll=scroll)
    out = scenes.screen_shot(img, t, dur, plate=plate, push=push, drift=0.8)
    if tap is not None:
        tx, ty, ta = tap
        if ta > 0:
            out = add(out, radial_glow((W, H), tuple(GREEN * 0.55), tx, ty, 0.13, 2.2, 0.55 * ta))
    return out


# --------------------------------------------------------------------------
# 2D: product tiles being added to the cart
# --------------------------------------------------------------------------
def add_to_cart_shot(t, dur, plate="env/store.jpg", kinds=("burger", "coffee", "groceries"),
                     dark=0.60):
    bg = film.plate_frame(plate, t, dur, blur=0, zoom_from=1.02, zoom_to=1.10, dark=dark)
    p = clamp(t / max(dur, 1e-6))
    canvas = bg.copy()
    # the product sheet appears
    sheet = scenes.screen("screen_store", highlight=0)
    sh = int(H * 0.80)
    sw = int(sh * sheet.width / sheet.height)
    sc_im = sheet.resize((sw, sh), Image.LANCZOS)
    appear = ease_out(clamp(p / 0.22))
    oy = int((H - sh) + (1 - appear) * H * 0.12)
    m = Image.new("L", sc_im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, sw - 1, sh - 1], radius=54, fill=255)
    canvas.paste(sc_im, ((W - sw) // 2, oy), m)
    # tiles fly from the sheet to the cart chip
    cart_x, cart_y = W * 0.86, H * 0.055
    for i, k in enumerate(kinds):
        s0 = 0.34 + i * 0.16
        s1 = s0 + 0.26
        q = clamp((p - s0) / (s1 - s0))
        if q <= 0 or q >= 1:
            continue
        e = ease_in_out(q)
        tw = int(W * lerp(0.26, 0.10, e))
        th = int(tw * 0.66)
        tile = portrait(k, tw, th, r=int(max(6, tw * 0.18)), zoom=1.05)
        x = lerp(W * 0.30 + (i % 2) * W * 0.22, cart_x - tw / 2, e)
        y = lerp(oy + sh * 0.42 + (i % 2) * H * 0.10, cart_y - th / 2, e)
        canvas.paste(tile, (int(x), int(y)), tile)
    # cart chip in the top corner
    cw_ = int(W * 0.15)
    chip = Image.new("RGBA", (cw_, cw_), (0, 0, 0, 0))
    d = ImageDraw.Draw(chip)
    d.ellipse([0, 0, cw_ - 1, cw_ - 1], fill=(93, 214, 44, 255))
    d.line([(cw_ * 0.28, cw_ * 0.30), (cw_ * 0.36, cw_ * 0.30), (cw_ * 0.44, cw_ * 0.62),
            (cw_ * 0.74, cw_ * 0.62)], fill=(15, 15, 15, 255), width=max(2, int(cw_ * 0.045)))
    d.line([(cw_ * 0.40, cw_ * 0.40), (cw_ * 0.80, cw_ * 0.40), (cw_ * 0.74, cw_ * 0.62)],
           fill=(15, 15, 15, 255), width=max(2, int(cw_ * 0.045)))
    for cxp in (0.46, 0.72):
        d.ellipse([cw_ * cxp - cw_ * 0.045, cw_ * 0.74 - cw_ * 0.045,
                   cw_ * cxp + cw_ * 0.045, cw_ * 0.74 + cw_ * 0.045], fill=(15, 15, 15, 255))
    chip = chip.resize((cw_, cw_), Image.LANCZOS)
    canvas.paste(chip, (int(W * 0.80), int(H * 0.04)), chip)
    return canvas


# --------------------------------------------------------------------------
# 2D: an order card travelling from one phone to another (3D transition)
# --------------------------------------------------------------------------
def order_travel_shot(t, dur, plate="env/kitchen.jpg", dark=0.72):
    bg = film.plate_frame(plate, t, dur, blur=8, zoom_from=1.0, zoom_to=1.06, dark=dark)
    p = clamp(t / max(dur, 1e-6))
    card = screen("screen_merchant_orders", state=1, pulse=0.0)
    ch = int(H * 0.46)
    cwd = int(ch * card.width / card.height)
    cim = card.resize((cwd, ch), Image.LANCZOS)
    m = Image.new("L", cim.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, cwd - 1, ch - 1], radius=44, fill=255)
    # travels up from below into place
    e = ease_out(clamp(p / 0.55))
    y = int(lerp(H * 0.86, H * 0.30, e))
    x = int(W * 0.5 - cwd / 2 + math.sin(p * math.pi) * W * 0.02)
    canvas = bg.copy()
    # motion trail
    if 0.05 < p < 0.8:
        trail = Image.new("RGB", canvas.size, (0, 0, 0))
        tm = Image.new("L", canvas.size, 0)
        tm.paste(m, (x, min(y + 90, H - ch)))
        trail.paste(Image.new("RGB", canvas.size, (40, 140, 30)), (0, 0), tm)
        canvas = screen_blend(canvas, trail.filter(ImageFilter.GaussianBlur(30)), 0.35)
    canvas.paste(cim, (x, y), m)
    rim = Image.new("RGB", canvas.size, (0, 0, 0))
    rm = Image.new("L", canvas.size, 0)
    rm.paste(m, (x, y))
    rim.paste(Image.new("RGB", canvas.size, (70, 220, 50)), (0, 0), rm)
    canvas = screen_blend(canvas, rim.filter(ImageFilter.GaussianBlur(22)), 0.28)
    return canvas


# --------------------------------------------------------------------------
# 2D: status ladder (order progresses) drawn as a glowing rail
# --------------------------------------------------------------------------
def status_rail(t, dur, plate=None, steps=4, dark=0.62):
    bg = film.plate_frame(plate, t, dur, blur=18, dark=dark) if plate else black()
    p = clamp(t / max(dur, 1e-6))
    filled = p * steps
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x = W * 0.32
    y0, y1 = H * 0.24, H * 0.76
    d.rounded_rectangle([x - 3, y0, x + 3, y1], radius=3, fill=(40, 44, 40, 255))
    hh = (y1 - y0) * clamp(filled / steps)
    d.rounded_rectangle([x - 3, y0, x + 3, y0 + hh], radius=3, fill=(93, 214, 44, 255))
    for i in range(steps):
        yy = y0 + (y1 - y0) * i / (steps - 1)
        on = filled >= i + 0.35
        r = 15
        if on:
            d.ellipse([x - r, yy - r, x + r, yy + r], fill=(93, 214, 44, 255))
            d.line([(x - 6, yy), (x - 1, yy + 5), (x + 7, yy - 5)],
                   fill=(15, 15, 15, 255), width=4, joint="curve")
        else:
            d.ellipse([x - r + 2, yy - r + 2, x + r - 2, yy + r - 2],
                      outline=(86, 90, 86, 255), width=3)
        d.rounded_rectangle([x + 46, yy - 7, x + 46 + 150 - i * 22, yy + 7],
                            radius=7, fill=(210, 210, 210, 120 if on else 48))
    halo = layer.filter(ImageFilter.GaussianBlur(20))
    bg = screen_blend(bg, halo.convert("RGB"), 0.5)
    base = np.asarray(bg).astype(F) / 255.0
    a = np.asarray(layer).astype(F) / 255.0
    base = base * (1 - a[..., 3:4]) + a[..., :3] * a[..., 3:4]
    return Image.fromarray((np.clip(base, 0, 1) * 255).astype(np.uint8))


# --------------------------------------------------------------------------
# cached photographic stills of the 3D sets (used as cards in the app UI)
# --------------------------------------------------------------------------
STILLS = {
    "map": "scenes/map.jpg",
    "ride": "scenes/ride.jpg",
}


def _still_map():
    def build(sc, tt, dd):
        build_city(sc, extent=30, seed=7, density=0.62, skip_center=8.0)
        rings = hex_rings(sc, radius=2, size=1.8, fill_emis=0.10)
        for f, o in rings:
            sc.add(f, o)
        marker(sc, (0, 0, 0), h=2.0)
    sc = Scene()
    sc.clear = np.array([0.015, 0.019, 0.024], dtype=F)
    sc.ambient = np.array([0.08, 0.085, 0.095], dtype=F)
    sc.light((-0.30, -0.80, -0.52), (1.0, 0.92, 0.80), 0.95)
    sc.light((0.75, -0.15, 0.35), (0.35, 1.0, 0.50), 0.7)
    build(sc, 0, 1)
    cam = Camera((7.5, 8.5, 13.5), (0, 0.4, 0.6), fov=40)
    rgb, cov = R.render(sc, cam, exposure=1.12, bloom=0.55, return_alpha=True,
                        vignette=0.38, grain=0.010)
    return rgb.convert("RGB")


def _still_ride():
    def build(sc, tt, dd):
        for m in props.make_street(w=9.0, length=60, seed=5):
            sc.add(Obj(m))
        sc.add(Obj(props.make_ground(190, (0.028, 0.032, 0.038))))
        pts = [(0, 0, 10), (0, 0, 0), (2.6, 0, -8)]
        ms = route_mesh(pts, width=0.34)
        if ms:
            sc.add(Obj(props.merge(ms)))
        rb = props.make_rider_bike()
        rb.pos = (0, 0, 1)
        rb.rot[1] = math.radians(200)
        sc.add(rb)
        sc.add_sprite(Sprite((0, 0.5, 1), 1.2, GREEN, 0.18, 2.8))
    sc = Scene()
    sc.clear = np.array([0.02, 0.024, 0.030], dtype=F)
    sc.ambient = np.array([0.075, 0.08, 0.09], dtype=F)
    sc.light((-0.30, -0.80, -0.52), (1.0, 0.92, 0.80), 0.95)
    sc.light((0.75, -0.15, 0.35), (0.35, 1.0, 0.50), 0.7)
    sc.fog = (np.array([0.03, 0.035, 0.04], dtype=F), 0.014)
    build(sc, 0, 1)
    cam = Camera((2.6, 2.2, 7.4), (0.2, 1.0, -1.6), fov=36)
    rgb, cov = R.render(sc, cam, exposure=1.15, bloom=0.6, return_alpha=True,
                        vignette=0.35, grain=0.010)
    return rgb.convert("RGB")


def ensure_stills():
    """Render the set stills once, so UI cards can show real scenes."""
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
    made = {}
    for key, fn in (("map", _still_map), ("ride", _still_ride)):
        path = os.path.join(root, STILLS[key])
        if not os.path.exists(path):
            img = fn()
            img.save(path, quality=92)
        made[key] = path
    return made
