"""
SIYMON 3D props: the phone, the rider + scooter, the hex dispatch grid, the city.
All built from the engine primitives; palette follows public/brand.css.
"""
from __future__ import annotations

import math
import os
import numpy as np
from PIL import Image

from siymon3d import (F, Mesh, Obj, Scene, ScreenQuad, Sprite, box, cylinder, sphere,
                      quad, taper_box, rounded_plate, ribbon, norm, merge, trans,
                      rot_x, rot_y, rot_z, scale_m)

GREEN = np.array([0x5D, 0xD6, 0x2C], dtype=F) / 255.0
GREEN_DK = np.array([0x33, 0x74, 0x18], dtype=F) / 255.0
BLACKISH = np.array([0.085, 0.09, 0.095], dtype=F)
SURFACE = np.array([0.125, 0.125, 0.125], dtype=F)
METAL = np.array([0.30, 0.32, 0.33], dtype=F)
WHITE = np.array([0.93, 0.93, 0.91], dtype=F)


# --------------------------------------------------------------------------
def rounded_prism(w, h, d, r, color, seg=6, center=(0, 0, 0), **kw):
    """Rounded rectangle (XY) extruded along Z."""
    pts = []
    corners = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
               (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]
    for cx, cy, a0 in corners:
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append([cx + r * math.cos(a), cy + r * math.sin(a)])
    n = len(pts)
    v = []
    for z in (-d / 2, d / 2):
        for p in pts:
            v.append([p[0], p[1], z])
    faces = []
    # front / back caps (fan)
    cf = len(v); v.append([0, 0, -d / 2])
    cb = len(v); v.append([0, 0, d / 2])
    for i in range(n):
        j = (i + 1) % n
        faces.append((cf, j, i))
        faces.append((cb, n + i, n + j))
        faces.append((i, j, n + j, n + i))
    v = np.array(v, dtype=F) + np.array(center, dtype=F)
    return Mesh(v, faces, color, **kw)


def capsule(p0, p1, r0, r1=None, color=(0.5, 0.5, 0.5), seg=10, **kw):
    """Tapered cylinder between two 3D points."""
    p0 = np.array(p0, dtype=F)
    p1 = np.array(p1, dtype=F)
    r1 = r0 if r1 is None else r1
    d = p1 - p0
    L = float(np.linalg.norm(d))
    if L < 1e-6:
        return None
    z = d / L
    up = np.array([0, 1, 0], dtype=F) if abs(z[1]) < 0.95 else np.array([1, 0, 0], dtype=F)
    x = norm(np.cross(up, z))
    y = np.cross(z, x)
    v = []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        v.append(p0 + (x * math.cos(a) + y * math.sin(a)) * r0)
    for i in range(seg):
        a = 2 * math.pi * i / seg
        v.append(p1 + (x * math.cos(a) + y * math.sin(a)) * r1)
    faces = []
    for i in range(seg):
        j = (i + 1) % seg
        faces.append((i, seg + j, seg + i))
        faces.append((i, j, seg + j))
    c0 = len(v); v.append(p0)
    c1 = len(v); v.append(p1)
    for i in range(seg):
        j = (i + 1) % seg
        faces.append((c0, i, j))
        faces.append((c1, seg + j, seg + i))
    return Mesh(np.array(v, dtype=F), faces, color, **kw)


# --------------------------------------------------------------------------
# THE PHONE  (one shared model -> identical look in all three videos)
# --------------------------------------------------------------------------
PW, PH, PD = 1.0, 2.04, 0.075


def make_phone(screen_img=None, glow=1.0):
    root = Obj(name="phone")
    body = Obj(rounded_prism(PW, PH, PD, 0.15, BLACKISH, seg=8), parent=root, name="body")
    root.add(body)
    # metal frame ring (slightly larger, thin)
    frame = Obj(rounded_prism(PW + 0.018, PH + 0.018, PD * 0.55, 0.156, METAL, seg=8,
                              emissive=0.05), parent=root)
    frame.pos[2] = 0.0
    root.add(frame)
    # screen bezel: dark inset plate at +Z
    bez = Obj(rounded_prism(PW - 0.022, PH - 0.022, 0.004, 0.142, (0.02, 0.022, 0.024), seg=8),
              parent=root)
    bez.pos[2] = PD / 2 + 0.001
    root.add(bez)
    # side buttons
    for sy, ln in ((0.55, 0.16), (0.32, 0.24), (-0.30, 0.24)):
        b = Obj(box(0.012, ln, 0.03, METAL), parent=root)
        b.pos = np.array([PW / 2 + 0.004, sy, 0], dtype=F)
        root.add(b)
    if screen_img is not None:
        sw = PW - 0.048
        sh = PH - 0.048
        z = PD / 2 + 0.010
        corners = np.array([[-sw / 2, sh / 2, z], [sw / 2, sh / 2, z],
                            [sw / 2, -sh / 2, z], [-sw / 2, -sh / 2, z]], dtype=F)
        sq = ScreenQuad(corners, screen_img, brightness=1.12, radius=64, selflit=True)
        root.screens.append(sq)
        screen_obj = Obj(name="screen")
        root.add(screen_obj)
        screen_obj.screens.append(sq)
    return root


def phone_glow(root, color=GREEN, intensity=1.0):
    """Soft light spill around a phone."""
    s = []
    for d, r, it in ((0.55, 1.0, 0.22), (0.0, 0.55, 0.35)):
        sp = Sprite((0, 0, d), r * PW, color * 1.0, intensity * it, 2.6, parent=root)
        s.append(sp)
    return s


# --------------------------------------------------------------------------
# RIDER + SCOOTER
# --------------------------------------------------------------------------
def make_scooter():
    root = Obj(name="scooter")
    dark = np.array([0.10, 0.105, 0.11], dtype=F)
    # wheels
    for wz in (0.62, -0.62):
        w = Obj(cylinder(0.235, 0.10, (0.055, 0.055, 0.06), seg=18, axis="x"), parent=root)
        w.pos = np.array([0, 0.235, wz], dtype=F)
        root.add(w)
        rim = Obj(cylinder(0.135, 0.105, METAL, seg=14, axis="x"), parent=root)
        rim.pos = np.array([0, 0.235, wz], dtype=F)
        root.add(rim)
        hub = Obj(cylinder(0.05, 0.11, (0.2, 0.2, 0.21), seg=10, axis="x"), parent=root)
        hub.pos = np.array([0, 0.235, wz], dtype=F)
        root.add(hub)
    # body deck
    root.add(Obj(box(0.30, 0.10, 1.16, dark), pos=(0, 0.40, 0.02)))
    # front leg shield
    root.add(Obj(taper_box(0.30, 0.26, 0.62, 0.30, 0.16, dark, center=(0, 0.70, -0.52))))
    # seat
    root.add(Obj(rounded_prism(0.30, 0.60, 0.14, 0.06, (0.075, 0.075, 0.08)), pos=(0, 0.80, 0.20),
                 rot=(math.radians(90), 0, 0)))
    # rear body
    root.add(Obj(taper_box(0.28, 0.24, 0.34, 0.50, 0.34, dark, center=(0, 0.62, 0.52))))
    # handlebar column
    root.add(Obj(capsule((0, 0.62, -0.52), (0, 1.05, -0.60), 0.045, 0.04, METAL, seg=8), ))
    # handlebar
    root.add(Obj(capsule((-0.28, 1.06, -0.62), (0.28, 1.06, -0.62), 0.028, 0.028, (0.12, 0.12, 0.13), seg=8)))
    # windshield: small smoked screen above the bars
    ws = Obj(quad((-0.17, 1.10, -0.665), (0.17, 1.10, -0.665),
                  (0.20, 1.30, -0.72), (-0.20, 1.30, -0.72),
                  (0.085, 0.10, 0.105), double=True), parent=root)
    root.add(ws)
    # headlight
    hl = Obj(rounded_prism(0.15, 0.075, 0.04, 0.032, (0.80, 0.86, 0.80), seg=6, emissive=0.95),
             pos=(0, 0.88, -0.705))
    root.add(hl)
    # delivery box on the back (SIYMON green)
    root.add(Obj(rounded_prism(0.42, 0.44, 0.42, 0.05, GREEN_DK, seg=4), pos=(0, 0.98, 0.66)))
    root.add(Obj(box(0.34, 0.02, 0.26, GREEN, center=(0, 1.205, 0.66), emissive=0.03)))
    root.add(Obj(box(0.20, 0.10, 0.012, GREEN, center=(0, 1.02, 0.878), emissive=0.18)))
    # rear light
    root.add(Obj(box(0.13, 0.035, 0.025, (1.0, 0.16, 0.1), emissive=1.2), pos=(0, 0.74, 0.885)))
    # green accents
    root.add(Obj(box(0.02, 0.05, 0.44, GREEN, emissive=0.5), pos=(0.152, 0.50, -0.10)))
    root.add(Obj(box(0.02, 0.05, 0.44, GREEN, emissive=0.5), pos=(-0.152, 0.50, -0.10)))
    return root


def make_rider(helmet=True, seated=True):
    root = Obj(name="rider")
    jacket = np.array([0.105, 0.115, 0.11], dtype=F)
    pants = np.array([0.075, 0.08, 0.085], dtype=F)
    skin = np.array([0.62, 0.44, 0.33], dtype=F)
    hip_y = 0.86 if seated else 1.0
    # pelvis
    root.add(Obj(rounded_prism(0.29, 0.24, 0.30, 0.07, pants, seg=4), pos=(0, hip_y, 0.12)))
    # torso (leaning slightly forward)
    torso = Obj(taper_box(0.34, 0.44, 0.60, 0.24, 0.30, jacket, center=(0, 0, 0)), parent=root)
    torso.pos = np.array([0, hip_y + 0.30, 0.10], dtype=F)
    torso.rot[0] = math.radians(-13)
    root.add(torso)
    # jacket green zip line & shoulder accents
    torso.add(Obj(box(0.035, 0.52, 0.02, GREEN, emissive=0.35), pos=(0, 0.02, -0.152)))
    # shoulders
    sh_y = hip_y + 0.56
    # arms to handlebars
    for sx in (-1, 1):
        shoulder = (sx * 0.185, sh_y, 0.02)
        elbow = (sx * 0.255, sh_y - 0.20, -0.16)
        hand = (sx * 0.27, 1.06, -0.60)
        root.add(Obj(capsule(shoulder, elbow, 0.062, 0.052, jacket, seg=9)))
        root.add(Obj(capsule(elbow, hand, 0.052, 0.044, jacket, seg=9)))
        glove = Obj(sphere(0.052, (0.08, 0.08, 0.09), seg=8, rings=6), parent=root)
        glove.pos = np.array(hand, dtype=F)
        root.add(glove)
    # legs bent on the deck
    for sx in (-1, 1):
        hip = (sx * 0.10, hip_y - 0.04, 0.16)
        knee = (sx * 0.16, hip_y - 0.06, -0.30)
        foot = (sx * 0.16, 0.46, -0.24)
        root.add(Obj(capsule(hip, knee, 0.085, 0.07, pants, seg=9)))
        root.add(Obj(capsule(knee, foot, 0.07, 0.055, pants, seg=9)))
        shoe = Obj(rounded_prism(0.12, 0.24, 0.10, 0.03, (0.06, 0.06, 0.07), seg=3), parent=root)
        shoe.pos = np.array([sx * 0.16, 0.42, -0.30], dtype=F)
        shoe.rot[0] = math.radians(90)
        root.add(shoe)
    # neck + head
    neck_y = hip_y + 0.62
    root.add(Obj(capsule((0, neck_y, 0.02), (0, neck_y + 0.06, 0.0), 0.055, 0.05, skin, seg=8)))
    head = Obj(sphere(0.115, skin, seg=14, rings=10), parent=root)
    head.pos = np.array([0, neck_y + 0.16, 0.0], dtype=F)
    root.add(head)
    if helmet:
        hel = Obj(sphere(0.138, (0.075, 0.08, 0.085), seg=16, rings=11), parent=root)
        hel.pos = np.array([0, neck_y + 0.165, 0.005], dtype=F)
        hel.scale = np.array([1.0, 1.05, 1.08], dtype=F)
        root.add(hel)
        # smoked visor across the front (-Z) only
        vis = Obj(sphere(0.133, (0.035, 0.045, 0.055), seg=14, rings=7), parent=root)
        vis.pos = np.array([0, neck_y + 0.155, -0.012], dtype=F)
        vis.scale = np.array([0.96, 0.60, 1.02], dtype=F)
        root.add(vis)
        # slim green band across the crown
        st = Obj(rounded_prism(0.030, 0.20, 0.26, 0.014, GREEN, seg=3, emissive=0.20), parent=root)
        st.pos = np.array([0, neck_y + 0.255, 0.02], dtype=F)
        st.rot[0] = math.radians(70)
        root.add(st)
    # backpack-slim delivery satchel (green)
    bp = Obj(rounded_prism(0.30, 0.34, 0.14, 0.045, GREEN_DK, seg=4), parent=root)
    bp.pos = np.array([0, hip_y + 0.34, 0.28], dtype=F)
    root.add(bp)
    root.add(Obj(box(0.20, 0.03, 0.02, GREEN, emissive=0.55), pos=(0, hip_y + 0.42, 0.355)))
    return root


def make_rider_bike():
    root = Obj(name="rider_bike")
    sc = make_scooter()
    rd = make_rider()
    root.add(sc, rd)
    return root


# --------------------------------------------------------------------------
# HEX DISPATCH GRID  (real 500 m cells, pointy-top, per lib/hexcell.js)
# --------------------------------------------------------------------------
SQ3 = math.sqrt(3.0)


def hex_center(q, r, size):
    x = size * SQ3 * (q + r / 2.0)
    z = size * 1.5 * r
    return x, z


def hex_plate(q, r, size, color, gap=0.965, y=0.0, **kw):
    cx, cz = hex_center(q, r, size)
    pts = []
    for i in range(6):
        a = math.radians(60 * i - 90)  # pointy-top
        pts.append((cx + size * gap * math.cos(a), cz + size * gap * math.sin(a)))
    v = [[p[0], y, p[1]] for p in pts]
    f = [(0, 1, 2, 3, 4, 5)]
    return Mesh(np.array(v, dtype=F), f, color, double=True, **kw)


def hex_ring(k):
    """All axial cells at cube-distance k from origin."""
    if k == 0:
        return [(0, 0)]
    out = []
    q, r = -k, k
    dirs = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
    for d in dirs:
        for _ in range(k):
            out.append((q, r))
            q += d[0]
            r += d[1]
    return out


def hex_outline_mesh(q, r, size, width=0.045, y=0.02, color=GREEN, emissive=1.6, gap=0.985):
    """A thin ribbon tracing one 500 m cell border."""
    cx, cz = hex_center(q, r, size)
    verts, faces = [], []
    for i in range(6):
        a0 = math.radians(60 * i - 90)
        a1 = math.radians(60 * (i + 1) - 90)
        p0 = np.array([cx + size * gap * math.cos(a0), y, cz + size * gap * math.sin(a0)], dtype=F)
        p1 = np.array([cx + size * gap * math.cos(a1), y, cz + size * gap * math.sin(a1)], dtype=F)
        d = p1 - p0
        L = float(np.linalg.norm(d))
        if L < 1e-6:
            continue
        d = d / L
        n = np.array([-d[2], 0, d[0]], dtype=F) * width / 2
        b = len(verts)
        verts += [p0 - n, p1 - n, p1 + n, p0 + n]
        faces.append((b, b + 1, b + 2, b + 3))
    return Mesh(np.array(verts, dtype=F), faces, color, double=True, emissive=emissive)


def make_hex_field(radius=4, size=1.0, y=0.0, outline=0.03, fill_emis=0.10,
                   fill_color=None):
    """Returns (fills, outlinemeshes) for a hex dispatch field, one Obj per ring."""
    fc = fill_color if fill_color is not None else np.array([0.018, 0.075, 0.024], dtype=F)
    rings = []
    for k in range(radius + 1):
        fills, outs = [], []
        for q, r in hex_ring(k):
            fills.append(hex_plate(q, r, size, fc, gap=0.93, y=y, emissive=fill_emis))
            outs.append(hex_outline_mesh(q, r, size, width=outline * size, y=y + 0.006))
        fo = Obj(merge(fills))
        oo = Obj(merge(outs))
        rings.append((fo, oo))
    return rings


# --------------------------------------------------------------------------
# CITY  (holographic low-poly night city for the 3D dispatch map)
# --------------------------------------------------------------------------
def make_holo_city(extent=26, seed=7, density=0.72, height=(0.8, 3.4), block=2.6,
                   skip_center=3.0, edge_glow=True):
    """Dark glass blocks with luminous tops; reads as a 3D city map at any scale."""
    rng = np.random.default_rng(seed)
    bodies, edges, dots = [], [], []
    n = int(extent / block)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            if math.hypot(i, j) * block < skip_center:
                continue
            if rng.random() > density:
                continue
            h = float(rng.uniform(*height)) * (1.0 + 0.10 * math.exp(-math.hypot(i, j) * 0.06))
            w = block * float(rng.uniform(0.55, 0.86))
            d = block * float(rng.uniform(0.55, 0.86))
            x = i * block + float(rng.uniform(-0.22, 0.22))
            z = j * block + float(rng.uniform(-0.22, 0.22))
            shade = float(rng.uniform(0.085, 0.155))
            bodies.append(box(w, h, d, (shade * 0.92, shade, shade * 1.12), center=(x, h / 2, z)))
            if edge_glow:
                # thin luminous rim along the roof perimeter (not a filled cap)
                g = float(rng.uniform(0.25, 0.75))
                rimc = (0.16 * g, 0.62 * g, 0.22 * g)
                rem = 0.5 + 0.45 * g
                t = 0.045
                for sx, sz, bw, bd in ((0, 1, w * 1.004, t), (0, -1, w * 1.004, t),
                                       (1, 0, t, d * 1.004), (-1, 0, t, d * 1.004)):
                    edges.append(box(bw, 0.028, bd, rimc,
                                     center=(x + sx * (w / 2), h - 0.014,
                                             z + sz * (d / 2)),
                                     emissive=rem))
            # a couple of lit windows on the top half
            for _ in range(int(rng.integers(0, 3))):
                wy = float(rng.uniform(0.45, 0.9)) * h
                side = int(rng.integers(0, 4))
                if side < 2:
                    cx = x + float(rng.uniform(-w * 0.3, w * 0.3))
                    cz = z + (d / 2 + 0.012) * (1 if side == 0 else -1)
                    dots.append(box(0.16, 0.20, 0.02, (1.0, 0.82, 0.48),
                                    center=(cx, wy, cz), emissive=0.9))
                else:
                    cz = z + float(rng.uniform(-d * 0.3, d * 0.3))
                    cx = x + (w / 2 + 0.012) * (1 if side == 2 else -1)
                    dots.append(box(0.02, 0.20, 0.16, (1.0, 0.82, 0.48),
                                    center=(cx, wy, cz), emissive=0.9))
    out = [merge(bodies)]
    if edges:
        out.append(merge(edges))
    if dots:
        out.append(merge(dots))
    return out


def make_street(w=7.0, length=40.0, seed=11, sides=(-1, 1)):
    """A street canyon: facades with warm windows, shop fronts, asphalt, kerbs.

    Meshes are grouped by material colour — merge() keeps only its first mesh's
    colour, so every differently-coloured part needs its own group.
    """
    rng = np.random.default_rng(seed)
    bodies, windows, shops, kerbs, road, dashes = [], [], [], [], [], []
    z = -length / 2
    while z < length / 2:
        depth = float(rng.uniform(2.4, 4.2))
        for side in sides:
            h = float(rng.uniform(3.0, 6.5))
            x = side * (w / 2 + depth / 2)
            shade = float(rng.uniform(0.05, 0.10))
            bodies.append(box(depth, h, depth * 0.92, (shade, shade * 1.02, shade * 1.10),
                              center=(x, h / 2, z)))
            # windows facing the street
            rows = int(h / 1.1)
            cols = int(depth * 0.92 / 0.9)
            for r_ in range(rows):
                for c_ in range(cols):
                    if rng.random() < 0.42:
                        continue
                    wy = 0.8 + r_ * 1.05
                    if wy > h - 0.5:
                        continue
                    wz = z - depth * 0.46 + 0.5 + c_ * 0.9
                    warm = float(rng.uniform(0.55, 1.0))
                    windows.append(box(0.03, 0.22, 0.26, (1.0 * warm, 0.74 * warm, 0.40 * warm),
                                       center=(x - side * (depth / 2 + 0.016), wy, wz),
                                       emissive=float(rng.uniform(0.30, 0.80))))
            # ground-floor shop front
            if rng.random() < 0.66:
                shop_h = float(rng.uniform(0.95, 1.35))
                shop_w = depth * float(rng.uniform(0.48, 0.70))
                shop_c = float(rng.uniform(0.45, 0.90))
                shops.append(box(0.035, shop_h, shop_w,
                                 (1.0 * shop_c, 0.78 * shop_c, 0.48 * shop_c),
                                 center=(x - side * (depth / 2 + 0.02), 0.12 + shop_h / 2,
                                         z + float(rng.uniform(-0.2, 0.2))),
                                 emissive=float(rng.uniform(0.26, 0.52))))
        z += depth + float(rng.uniform(0.1, 0.5))
    # kerbs and pavement slabs
    for side in sides:
        kerbs.append(box(0.16, 0.12, length, (0.115, 0.12, 0.125),
                         center=(side * (w / 2 - 0.08), 0.06, 0), emissive=0.03))
        kerbs.append(box(1.5, 0.02, length, (0.055, 0.058, 0.062),
                         center=(side * (w / 2 + 0.78), 0.010, 0)))
    # asphalt, in short strips so per-vertex lighting stays local
    seg = 3.0
    sz = -length / 2
    while sz < length / 2 - 1e-6:
        sz2 = min(sz + seg, length / 2)
        road.append(Mesh(np.array([[-w / 2 + 0.02, 0.0, sz], [w / 2 - 0.02, 0.0, sz],
                                   [w / 2 - 0.02, 0.0, sz2], [-w / 2 + 0.02, 0.0, sz2]],
                                  dtype=F),
                         [(0, 1, 2, 3)], (0.062, 0.066, 0.073), double=True,
                         emissive=0.012))
        sz = sz2
    dz = -length / 2 + 1.2
    while dz < length / 2:
        dashes.append(box(0.11, 0.008, 1.5, (0.26, 0.27, 0.25),
                          center=(0, 0.008, dz), emissive=0.03))
        dz += 3.0
    ms = [merge(bodies)]
    if windows:
        ms.append(merge(windows))
    if shops:
        ms.append(merge(shops))
    ms += [merge(road), merge(kerbs), merge(dashes)]
    return ms


def make_ground(size=90, color=(0.045, 0.05, 0.055)):
    return Mesh(np.array([[-size, 0, -size], [size, 0, -size], [size, 0, size], [-size, 0, size]], dtype=F),
                [(0, 1, 2, 3)], color, double=True)


def make_roads(paths, width=1.5, color=(0.075, 0.08, 0.088)):
    ms = []
    for p in paths:
        ms.append(ribbon(p, width, color, y=0.012))
    return merge(ms)


def make_building_block(w, h, d, color=(0.14, 0.15, 0.16), center=(0, 0, 0), windows=True, seed=1):
    rng = np.random.default_rng(seed)
    ms = [box(w, h, d, color, center=(center[0], h / 2, center[2]))]
    if windows:
        rows = max(1, int(h / 1.1))
        cols = max(2, int(w / 0.9))
        for r_ in range(rows):
            for c_ in range(cols):
                if rng.random() < 0.35:
                    continue
                wy = 0.7 + r_ * 1.05
                if wy > h - 0.4:
                    continue
                wx = -w / 2 + 0.55 + c_ * (w - 1.1) / max(1, cols - 1)
                warm = float(rng.uniform(0.6, 1.0))
                ms.append(box(0.42, 0.34, 0.03, (1.0 * warm, 0.8 * warm, 0.45 * warm),
                              center=(center[0] + wx, wy, center[2] + d / 2 + 0.016),
                              emissive=float(rng.uniform(0.4, 0.9))))
    return merge(ms)


# --------------------------------------------------------------------------
# BAGS / PACKAGING
# --------------------------------------------------------------------------
def make_paper_bag(w=0.36, h=0.46, d=0.22, color=(0.55, 0.44, 0.28)):
    root = Obj(name="bag")
    root.add(Obj(taper_box(w, w * 1.04, h, d, d * 1.04, color, center=(0, h / 2, 0))))
    # fold at the top
    root.add(Obj(box(w * 1.06, 0.03, d * 1.06, np.array(color, dtype=F) * 0.72, center=(0, h, 0))))
    # SIYMON green sticker
    root.add(Obj(rounded_prism(0.16, 0.11, 0.006, 0.02, GREEN, seg=4, emissive=0.25),
                 pos=(0, h * 0.62, -d / 2 - 0.004), rot=(0, math.radians(90), 0)))
    # handles
    for sx in (-1, 1):
        p0 = (sx * w * 0.3, h, -d * 0.2)
        p1 = (sx * w * 0.3, h + 0.12, -d * 0.2)
        root.add(Obj(capsule(p0, p1, 0.008, 0.008, (0.42, 0.34, 0.22), seg=5)))
    return root


def make_delivery_box(color=GREEN_DK, size=0.9):
    root = Obj(name="delivery_box")
    w = size
    root.add(Obj(rounded_prism(w, w, w * 0.8, 0.05, color, seg=4)))
    root.add(Obj(rounded_prism(w * 0.86, 0.03, w * 0.66, 0.02, nan, seg=3, emissive=0.1)
                 if False else rounded_prism(w * 0.86, 0.03, w * 0.66, 0.02, GREEN, seg=3, emissive=0.10),
                 pos=(0, w * 0.5 + 0.01, 0)))
    return root


def make_food_boxes():
    ms = []
    ms.append(box(0.30, 0.10, 0.22, (0.13, 0.13, 0.14), center=(0, 0.05, 0)))
    ms.append(box(0.30, 0.02, 0.22, (0.78, 0.78, 0.76), center=(0, 0.11, 0)))
    return merge(ms)


def make_counter(w=3.0, h=1.0, d=0.8, color=(0.17, 0.17, 0.18)):
    ms = [box(w, h, d, color, center=(0, h / 2, 0))]
    ms.append(box(w * 1.02, 0.05, d * 1.05, (0.5, 0.52, 0.52), center=(0, h, 0)))
    return merge(ms)


def make_shelf(w=2.4, h=2.0, d=0.5, color=(0.14, 0.14, 0.15), items=9, seed=2):
    """Store shelving with product blocks."""
    rng = np.random.default_rng(seed)
    ms = [box(0.06, h, d, color, center=(-w / 2, h / 2, 0)),
          box(0.06, h, d, color, center=(w / 2, h / 2, 0)),
          box(w, h, 0.05, color, center=(0, h / 2, -d / 2))]
    levels = 4
    for i in range(levels + 1):
        y = 0.15 + i * (h - 0.3) / levels
        ms.append(box(w, 0.04, d, (0.20, 0.20, 0.21), center=(0, y, 0)))
        if i == levels:
            continue
        x = -w / 2 + 0.18
        while x < w / 2 - 0.22:
            bw = float(rng.uniform(0.09, 0.17))
            bh = float(rng.uniform(0.14, 0.26))
            hue = rng.random()
            if hue < 0.34:
                col = (0.62, 0.34, 0.20)
            elif hue < 0.62:
                col = (0.68, 0.66, 0.62)
            elif hue < 0.82:
                col = (0.30, 0.48, 0.26)
            else:
                col = (0.55, 0.42, 0.16)
            ms.append(box(bw, bh, d * 0.55, col, center=(x + bw / 2, y + 0.02 + bh / 2, 0.02)))
            x += bw + 0.03
    return merge(ms)


# --------------------------------------------------------------------------
# LOGO OBJECT (billboard plane with the real traced mark)
# --------------------------------------------------------------------------
def make_logo_plane(img, w=1.0, h=None, emissive_boost=1.0):
    """A flat emissive panel showing the SIYMON icon."""
    h = w if h is None else h
    corners = np.array([[-w / 2, h / 2, 0], [w / 2, h / 2, 0],
                        [w / 2, -h / 2, 0], [-w / 2, -h / 2, 0]], dtype=F)
    o = Obj(name="logo")
    o.screens.append(ScreenQuad(corners, img, brightness=1.55))
    return o
