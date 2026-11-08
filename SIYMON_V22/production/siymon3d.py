"""
SIYMON cinematic engine — a small, self-contained 3D renderer.

Pure numpy + PIL: perspective camera, z-buffer, per-vertex lighting, emissive
materials, additive glow sprites, projective phone-screen mapping and a film
grade (bloom, ACES tonemap, vignette, grain). No external 3D dependency.

Coordinate system: right-handed, +Y up, camera looks down its own -Z.
"""
from __future__ import annotations

import math
import numpy as np
from PIL import Image

F = np.float32

# --------------------------------------------------------------------------
# SIYMON brand palette (public/brand.css — single source of truth)
# --------------------------------------------------------------------------
BRAND = {
    "bg":        (0x0F, 0x0F, 0x0F),
    "surface":   (0x20, 0x20, 0x20),
    "green":     (0x5D, 0xD6, 0x2C),
    "green_dk":  (0x33, 0x74, 0x18),
    "text":      (0xF8, 0xF8, 0xF8),
    "muted":     (0xA8, 0xA8, 0xA8),
    "green_hov": (0x4D, 0xBF, 0x20),
}

GREEN = np.array([0x5D, 0xD6, 0x2C], dtype=F) / 255.0
BLACK = np.array([0x0F, 0x0F, 0x0F], dtype=F) / 255.0


# --------------------------------------------------------------------------
# small maths helpers
# --------------------------------------------------------------------------
def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = clamp(t)
    return t * t * (3.0 - 2.0 * t)


def ease_in_out(t):
    t = clamp(t)
    return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2


def ease_out(t):
    t = clamp(t)
    return 1 - pow(1 - t, 3)


def ease_in(t):
    t = clamp(t)
    return t * t * t


def ease_out_back(t, s=1.7):
    t = clamp(t)
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def ease_out_elastic(t):
    t = clamp(t)
    if t in (0.0, 1.0):
        return t
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * (2 * math.pi) / 3) + 1


def remap(t, a, b, lo=0.0, hi=1.0):
    """Map t from [a,b] into [lo,hi], clamped."""
    if b == a:
        return hi if t >= b else lo
    return lo + (hi - lo) * clamp((t - a) / (b - a))


def span(t, a, b):
    """0 before a, 1 after b, eased in between (raw, not eased)."""
    return clamp((t - a) / max(1e-6, b - a))


def pulse(t, a, b, c, d):
    """Rise over [a,b], hold, fall over [c,d]."""
    return smooth(span(t, a, b)) * smooth(1.0 - span(t, c, d))


def norm(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v


# --------------------------------------------------------------------------
# transforms
# --------------------------------------------------------------------------
def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], dtype=F)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], dtype=F)


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=F)


def trans(x, y, z):
    m = np.eye(4, dtype=F)
    m[0, 3], m[1, 3], m[2, 3] = x, y, z
    return m


def scale_m(sx, sy=None, sz=None):
    if sy is None:
        sy = sz = sx
    m = np.eye(4, dtype=F)
    m[0, 0], m[1, 1], m[2, 2] = sx, sy, sz
    return m


# --------------------------------------------------------------------------
# camera
# --------------------------------------------------------------------------

def _clip_near(pts, cols, near):
    """Clip a convex polygon (view space, keeping -z >= near) carrying colours."""
    out_p, out_c = [], []
    n = len(pts)
    for i in range(n):
        a = pts[i]
        b = pts[(i + 1) % n]
        ca = cols[i]
        cb = cols[(i + 1) % n]
        da = -a[2] - near
        db = -b[2] - near
        if da >= 0:
            out_p.append(a)
            out_c.append(ca)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            out_p.append(a + (b - a) * t)
            out_c.append(ca + (cb - ca) * t)
    if len(out_p) < 3:
        return [], []
    return out_p, out_c


def _project(poly, f, asp, W, H):
    out = []
    for p in poly:
        w = max(-p[2], 1e-4)
        sx = (f / asp) * p[0] / w
        sy = f * p[1] / w
        out.append(((sx * 0.5 + 0.5) * W, (0.5 - sy * 0.5) * H, p[2]))
    xs = [o[0] for o in out]
    ys = [o[1] for o in out]
    zs = [o[2] for o in out]
    return xs, ys, zs, out


class Camera:
    def __init__(self, eye, target, up=(0, 1, 0), fov=42.0, roll=0.0):
        self.eye = np.array(eye, dtype=F)
        self.target = np.array(target, dtype=F)
        self.up = np.array(up, dtype=F)
        self.fov = fov
        self.roll = roll
        self._build()

    def _build(self):
        f = norm(self.target - self.eye)
        up = self.up
        if abs(float(np.dot(f, norm(up)))) > 0.999:
            up = np.array([0, 0, 1], dtype=F)
        s = norm(np.cross(f, up))
        u = np.cross(s, f)
        if self.roll:
            c, sn = math.cos(self.roll), math.sin(self.roll)
            s, u = s * c + u * sn, u * c - s * sn
        V = np.eye(4, dtype=F)
        V[0, :3], V[1, :3], V[2, :3] = s, u, -f
        V[:3, 3] = np.array([-np.dot(s, self.eye), -np.dot(u, self.eye), np.dot(f, self.eye)], dtype=F)
        self.V = V
        self.f = 1.0 / math.tan(math.radians(self.fov) * 0.5)

    def project(self, pts, W, H):
        """pts (N,3) world -> (screen_xy (N,2), view_z (N,), clip_w (N,))"""
        ph = np.concatenate([pts, np.ones((len(pts), 1), dtype=F)], axis=1)
        view = ph @ self.V.T
        z = view[:, 2]
        w = np.maximum(-z, 1e-4)
        sx = (self.f / (W / H)) * view[:, 0] / w
        sy = self.f * view[:, 1] / w
        return np.stack([(sx * 0.5 + 0.5) * W, (0.5 - sy * 0.5) * H], axis=1).astype(F), z, w


# --------------------------------------------------------------------------
# meshes
# --------------------------------------------------------------------------
class Mesh:
    """verts (N,3), faces list-of-tuples of indices, per-face or single colour."""

    def __init__(self, verts, faces, color=(0.8, 0.8, 0.8), emissive=0.0,
                 shade="smooth", double=False, glow=None, face_colors=None,
                 name=""):
        self.verts = np.asarray(verts, dtype=F)
        self.faces = [tuple(f) for f in faces]
        self.color = np.asarray(color, dtype=F)
        self.emissive = emissive
        self.shade = shade
        self.double = double
        self.glow = glow          # additive colour bled into bloom
        self.face_colors = face_colors
        self.name = name
        self._cache = None
        self._build()

    def _build(self):
        v = self.verts
        tris = []
        for face in self.faces:
            if len(face) == 3:
                tris.append(face)
            elif len(face) == 4:
                tris.append((face[0], face[1], face[2]))
                tris.append((face[0], face[2], face[3]))
            else:
                for k in range(1, len(face) - 1):
                    tris.append((face[0], face[k], face[k + 1]))
        self.tris = tris
        f = np.array(tris, dtype=np.int32)
        # face normals
        p0, p1, p2 = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        n = np.cross(p1 - p0, p2 - p0)
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        ln[ln < 1e-9] = 1.0
        self.fnorm = n / ln
        # vertex normals (area weighted)
        vn = np.zeros_like(v)
        for k in range(3):
            np.add.at(vn, f[:, k], n)
        lvn = np.linalg.norm(vn, axis=1, keepdims=True)
        lvn[lvn < 1e-9] = 1.0
        self.vnorm = vn / lvn
        self.fidx = f
        self.ntri = len(f)
        self.fcols = (np.asarray(self.face_colors, dtype=F) / 255.0
                      if self.face_colors is not None else None)


def merge(meshes):
    """Concatenate meshes into one (vertex colour/faceless-ish, keeps first's material)."""
    vs, fs, fc = [], [], []
    off = 0
    per_face_color = None
    for m in meshes:
        vs.append(m.verts)
        fs.extend([tuple(i + off for i in f) for f in m.faces])
        if m.face_colors is not None:
            per_face_color = (per_face_color or [])
            per_face_color.extend(np.asarray(m.face_colors).tolist())
        elif per_face_color is not None:
            per_face_color.extend([m.color * 255] * len(m.faces))
        off += len(m.verts)
    base = meshes[0]
    return Mesh(np.concatenate(vs), fs, base.color, base.emissive, base.shade,
                base.double, base.glow, per_face_color, base.name)


# ---- primitives ----------------------------------------------------------
def box(w, h, d, color, center=(0, 0, 0), face_colors=None, **kw):
    x, y, z = w / 2, h / 2, d / 2
    cx, cy, cz = center
    v = np.array([
        [-x, -y, -z], [x, -y, -z], [x, y, -z], [-x, y, -z],
        [-x, -y, z], [x, -y, z], [x, y, z], [-x, y, z],
    ], dtype=F) + np.array([cx, cy, cz], dtype=F)
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6),
         (1, 2, 6, 5), (0, 4, 7, 3)]
    return Mesh(v, f, color, **kw)


def rounded_plate(w, h, r, color, depth=0.0, seg=4, **kw):
    """Flat rounded rect in XY plane, normal +Z."""
    pts = []
    corners = [(w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90),
               (-w / 2 + r, -h / 2 + r, 180), (w / 2 - r, -h / 2 + r, 270)]
    for cx, cy, a0 in corners:
        for i in range(seg + 1):
            a = math.radians(a0 + 90 * i / seg)
            pts.append([cx + r * math.cos(a), cy + r * math.sin(a), depth])
    n = len(pts)
    faces = [(i, (i + 1) % n, -1) for i in range(n)]
    verts = pts + [[0, 0, depth]]
    faces = [tuple(i if i >= 0 else n for i in f) for f in faces]
    return Mesh(np.array(verts, dtype=F), faces, color, **kw)


def sphere(r, color, center=(0, 0, 0), seg=12, rings=8, **kw):
    v, f = [], []
    for j in range(rings + 1):
        phi = math.pi * j / rings
        for i in range(seg):
            th = 2 * math.pi * i / seg
            v.append([r * math.sin(phi) * math.cos(th),
                      r * math.cos(phi),
                      r * math.sin(phi) * math.sin(th)])
    for j in range(rings):
        for i in range(seg):
            a = j * seg + i
            b = j * seg + (i + 1) % seg
            c = (j + 1) * seg + i
            d = (j + 1) * seg + (i + 1) % seg
            f += [(a, c, d), (a, d, b)]
    v = np.array(v, dtype=F) + np.array(center, dtype=F)
    return Mesh(v, f, color, **kw)


def cylinder(r, h, color, center=(0, 0, 0), seg=14, r2=None, axis="y", caps=True, **kw):
    r2 = r if r2 is None else r2
    v, f = [], []
    for i in range(seg):
        a = 2 * math.pi * i / seg
        v.append([r * math.cos(a), -h / 2, r * math.sin(a)])
    for i in range(seg):
        a = 2 * math.pi * i / seg
        v.append([r2 * math.cos(a), h / 2, r2 * math.sin(a)])
    for i in range(seg):
        j = (i + 1) % seg
        f.append((i, j, seg + j))
        f.append((i, seg + j, seg + i))
    if caps:
        cb = len(v); v.append([0, -h / 2, 0])
        ct = len(v); v.append([0, h / 2, 0])
        for i in range(seg):
            j = (i + 1) % seg
            f.append((cb, j, i))
            f.append((ct, seg + i, seg + j))
    v = np.array(v, dtype=F)
    if axis == "x":
        v = v[:, [1, 0, 2]] * np.array([1, 1, -1], dtype=F)
    elif axis == "z":
        v = v[:, [0, 2, 1]] * np.array([1, 1, -1], dtype=F)
    v = v + np.array(center, dtype=F)
    return Mesh(v, f, color, **kw)


def quad(p0, p1, p2, p3, color, **kw):
    return Mesh(np.array([p0, p1, p2, p3], dtype=F), [(0, 1, 2), (0, 2, 3)], color, **kw)


def taper_box(w0, w1, h, d0, d1, color, center=(0, 0, 0), **kw):
    """Frustum-ish box: bottom w0/d0, top w1/d1."""
    v = np.array([
        [-w0 / 2, -h / 2, -d0 / 2], [w0 / 2, -h / 2, -d0 / 2],
        [w0 / 2, -h / 2, d0 / 2], [-w0 / 2, -h / 2, d0 / 2],
        [-w1 / 2, h / 2, -d1 / 2], [w1 / 2, h / 2, -d1 / 2],
        [w1 / 2, h / 2, d1 / 2], [-w1 / 2, h / 2, d1 / 2],
    ], dtype=F) + np.array(center, dtype=F)
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5),
         (2, 3, 7, 6), (3, 0, 4, 7)]
    return Mesh(v, f, color, **kw)


def ribbon(points, width, color, y=0.0, **kw):
    """Flat ground ribbon following a 2D polyline [(x,z), ...]."""
    pts = [np.array(p, dtype=F) for p in points]
    verts, faces = [], []
    for i, p in enumerate(pts):
        if i == 0:
            d = pts[1] - pts[0]
        elif i == len(pts) - 1:
            d = pts[-1] - pts[-2]
        else:
            d = pts[i + 1] - pts[i - 1]
        d = norm(d)
        n = np.array([-d[1], d[0]], dtype=F)
        a = p - n * width / 2
        b = p + n * width / 2
        verts += [[a[0], y, a[1]], [b[0], y, b[1]]]
    for i in range(len(pts) - 1):
        k = i * 2
        faces.append((k, k + 1, k + 3, k + 2))
    return Mesh(np.array(verts, dtype=F), faces, color, **kw)


# --------------------------------------------------------------------------
# scene graph
# --------------------------------------------------------------------------
class Obj:
    def __init__(self, mesh=None, pos=(0, 0, 0), rot=(0, 0, 0), scale=1.0,
                 parent=None, visible=True, screens=None, name=""):
        self.mesh = mesh
        self.pos = np.array(pos, dtype=F)
        self.rot = np.array(rot, dtype=F)      # euler XYZ, radians
        self.scale = np.array(scale, dtype=F) if hasattr(scale, "__len__") else np.array([scale] * 3, dtype=F)
        self.parent = parent
        self.visible = visible
        self.name = name
        self.screens = screens or []   # list of ScreenQuad in local space
        self.children = []

    def add(self, *objs):
        for o in objs:
            o.parent = self
            self.children.append(o)
        return objs[0] if len(objs) == 1 else objs

    def local(self):
        m = trans(*self.pos) @ rot_y(self.rot[1]) @ rot_x(self.rot[0]) @ rot_z(self.rot[2]) @ scale_m(*self.scale)
        return m

    def world(self):
        m = self.local()
        p = self.parent
        while p is not None:
            m = p.local() @ m
            p = p.parent
        return m


class ScreenQuad:
    """A flat app-screen surface (4 local corners, TL,TR,BR,BL) showing a PIL image."""

    def __init__(self, corners, image, brightness=1.35, radius=None, selflit=False):
        self.corners = np.array(corners, dtype=F)
        self.image = image
        self.brightness = brightness
        self.radius = radius
        self.selflit = selflit


class Sprite:
    """Additive soft radial glow in 3D."""

    def __init__(self, pos, radius, color, intensity=1.0, softness=2.2, parent=None):
        self.pos = np.array(pos, dtype=F)
        self.radius = radius
        self.color = np.asarray(color, dtype=F)
        self.intensity = intensity
        self.softness = softness
        self.parent = parent

    def world_pos(self):
        if self.parent is None:
            return self.pos
        m = self.parent.world()
        return (m @ np.array([*self.pos, 1.0], dtype=F))[:3]


class Scene:
    def __init__(self):
        self.objs = []
        self.sprites = []
        self.lights = []
        self.ambient = np.array([0.06, 0.07, 0.07], dtype=F)
        self.fog = None          # (color, density)
        self.clear = np.array([0.013, 0.014, 0.016], dtype=F)

    def add(self, *objs):
        for o in objs:
            self.objs.append(o)
        return objs[0] if len(objs) == 1 else objs

    def add_sprite(self, s):
        self.sprites.append(s)
        return s

    def light(self, direction, color, intensity=1.0):
        self.lights.append((norm(np.array(direction, dtype=F)), np.asarray(color, dtype=F), intensity))


# --------------------------------------------------------------------------
# renderer
# --------------------------------------------------------------------------
class Renderer:
    def __init__(self, W=1080, H=1920, ss=1.4):
        self.W, self.H = W, H
        self.ss = ss
        self.RW, self.RH = int(W * ss), int(H * ss)

    @property
    def ss(self):
        return self._ss

    @ss.setter
    def ss(self, v):
        self._ss = v
        self.RW, self.RH = int(self.W * v), int(self.H * v)

    # ---- main entry ----
    def render(self, scene, camera, exposure=1.0, bloom=0.5, bloom_thresh=0.72,
               grain=0.018, vignette=0.42, grade=1.0, ca=0.0, return_alpha=False):
        W, H = self.RW, self.RH
        self._cov = np.zeros((H, W), dtype=F)
        buf = np.empty((H, W, 3), dtype=F)
        buf[:] = scene.clear
        zbuf = np.full((H, W), -1e9, dtype=F)

        amb = scene.ambient
        lights = [(d, c, i) for d, c, i in scene.lights]

        for o in scene.objs:
            if not o.visible:
                continue
            self._draw_obj(o, camera, buf, zbuf, W, H, amb, lights, scene)

        for s in scene.sprites:
            self._draw_sprite(s, camera, buf, zbuf, W, H, scene)

        out = self._post(buf, exposure, bloom, bloom_thresh, grain, vignette, grade, ca)
        if return_alpha:
            cov = Image.fromarray((np.clip(self._cov, 0, 1) * 255).astype(np.uint8))
            if self.ss != 1.0:
                cov = cov.resize((self.W, self.H), Image.LANCZOS)
            return out, cov
        return out

    # ---- geometry ----
    def _draw_obj(self, o, cam, buf, zbuf, W, H, amb, lights, scene):
        M = o.world()
        if o.mesh is not None:
            self._draw_mesh(o.mesh, M, cam, buf, zbuf, W, H, amb, lights, scene)
        for sq in o.screens:
            self._draw_screen(sq, M, cam, buf, zbuf, W, H)
        for c in o.children:
            if c.visible:
                self._draw_obj(c, cam, buf, zbuf, W, H, amb, lights, scene)

    def _draw_mesh(self, mesh, M, cam, buf, zbuf, W, H, amb, lights, scene):
        Rm = M[:3, :3]
        vw = mesh.verts @ Rm.T + M[:3, 3]
        # world -> view
        view = (vw @ cam.V[:3, :3].T) + cam.V[:3, 3]
        z = view[:, 2]

        # vertex normals in world
        nv = mesh.vnorm @ Rm.T
        tocam = cam.eye[None, :] - vw
        tl = np.linalg.norm(tocam, axis=1, keepdims=True)
        tl[tl < 1e-9] = 1
        vdir = tocam / tl

        # per-vertex lighting
        shade = np.empty_like(vw)
        shade[:] = scene.ambient
        for d, lc, inten in lights:
            nd = np.clip(nv @ d, 0, 1)
            shade += (nd * inten)[:, None] * lc[None, :]
            ndv = np.clip(np.sum(nv * vdir, axis=1), 0, 1)
            rim = (1.0 - ndv) ** 3
            shade += (rim * 0.50)[:, None] * np.array([0.28, 0.95, 0.42], dtype=F)[None, :]
        if mesh.fcols is not None:
            # flat per-face colour: average the three corners' lighting
            fc = mesh.fcols[mesh.fidx].mean(axis=1)
            vcols_face = fc[:, None, :] * (shade[mesh.fidx].mean(axis=1)[:, None, :] + mesh.emissive)
        else:
            vcols_face = None
        vcols = mesh.color[None, :] * (shade + mesh.emissive)

        if scene.fog is not None:
            fogc, fd = scene.fog
            dist = np.linalg.norm(vw - cam.eye, axis=1)
            fv = (1.0 - np.exp(-dist * fd))[:, None]
            vcols = vcols * (1 - fv) + np.asarray(fogc, dtype=F)[None, :] * fv

        f = mesh.fidx
        fz = z[f]
        # cheap reject: fully behind the near plane
        behind = (fz > -0.04).all(axis=1)
        keep = ~behind
        if not mesh.double:
            # backface in view space
            p0 = view[f[:, 0]]; p1 = view[f[:, 1]]; p2 = view[f[:, 2]]
            nrm = np.cross(p1 - p0, p2 - p0)
            cen = (p0 + p1 + p2) / 3.0
            keep &= (np.sum(nrm * cen, axis=1) > 0)
        idx = np.nonzero(keep)[0]
        if len(idx) == 0:
            return
        order = idx[np.argsort(fz[idx].mean(axis=1))]

        f_ = cam.f
        asp = W / H
        NEAR = 0.06
        for i in order:
            tri = f[i]
            pv = view[tri]
            cv = vcols[tri]
            if vcols_face is not None:
                cv = np.repeat(vcols_face[i][None, :, :], 3, axis=0)
            # clip against the near plane (keep -z >= NEAR)
            poly, cpoly = _clip_near(pv, cv, NEAR)
            if len(poly) < 3:
                continue
            sx, sy, sz, cw = _project(poly, f_, asp, W, H)
            # fan rasterise
            for k in range(1, len(poly) - 1):
                self._tri(sx[0], sy[0], sz[0], cpoly[0],
                          sx[k], sy[k], sz[k], cpoly[k],
                          sx[k + 1], sy[k + 1], sz[k + 1], cpoly[k + 1],
                          buf, zbuf, W, H)

    def _tri(self, ax, ay, az, ca, bx, by, bz, cb, cx, cy, cz, cc, buf, zbuf, W, H):
        minx = int(math.floor(min(ax, bx, cx)))
        maxx = int(math.ceil(max(ax, bx, cx)))
        miny = int(math.floor(min(ay, by, cy)))
        maxy = int(math.ceil(max(ay, by, cy)))
        if minx < 0:
            minx = 0
        if miny < 0:
            miny = 0
        if maxx > W - 1:
            maxx = W - 1
        if maxy > H - 1:
            maxy = H - 1
        if maxx - minx < 2 or maxy - miny < 2:
            return
        if (maxx - minx) * (maxy - miny) > 6.0 * W * H:
            return
        xs = np.arange(minx, maxx + 1, dtype=F) + 0.5
        ys = np.arange(miny, maxy + 1, dtype=F) + 0.5
        X = xs[None, :]
        Y = ys[:, None]
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-9:
            return
        w0 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / d
        w1 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / d
        w2 = 1.0 - w0 - w1
        mask = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not mask.any():
            return
        zz = w0 * az + w1 * bz + w2 * cz
        subz = zbuf[miny:maxy + 1, minx:maxx + 1]
        m = mask & (zz > subz)
        if not m.any():
            return
        sub = buf[miny:maxy + 1, minx:maxx + 1]
        r = w0 * ca[0] + w1 * cb[0] + w2 * cc[0]
        g = w0 * ca[1] + w1 * cb[1] + w2 * cc[1]
        b = w0 * ca[2] + w1 * cb[2] + w2 * cc[2]
        cov = self._cov[miny:maxy + 1, minx:maxx + 1]
        cov[...] = np.where(m, 1.0, cov)
        sub[..., 0] = np.where(m, r, sub[..., 0])
        sub[..., 1] = np.where(m, g, sub[..., 1])
        sub[..., 2] = np.where(m, b, sub[..., 2])
        subz[...] = np.where(m, zz, subz)

    # ---- sprites ----
    def _draw_sprite(self, sp, cam, buf, zbuf, W, H, scene):
        p = sp.world_pos()
        clip = cam.V[:3, :3] @ p + cam.V[:3, 3]
        if clip[2] > -0.05:
            return
        w = -clip[2]
        sx = (cam.f / (W / H)) * clip[0] / w
        sy = cam.f * clip[1] / w
        cxp = (sx * 0.5 + 0.5) * W
        cyp = (0.5 - sy * 0.5) * H
        # radius in pixels from a point offset by radius in view-right
        rpx = sp.radius * (cam.f * W / (2 * w * (W / H)))
        rpx = max(2.0, rpx)
        x0 = max(0, int(cxp - rpx)); x1 = min(W - 1, int(cxp + rpx))
        y0 = max(0, int(cyp - rpx)); y1 = min(H - 1, int(cyp + rpx))
        if x0 >= x1 or y0 >= y1:
            return
        if (x1 - x0) * (y1 - y0) > 0.6 * W * H:
            return
        xs = np.arange(x0, x1 + 1, dtype=F) + 0.5
        ys = np.arange(y0, y1 + 1, dtype=F) + 0.5
        dx = (xs[None, :] - cxp) / rpx
        dy = (ys[:, None] - cyp) / rpx
        r2 = dx * dx + dy * dy
        fall = np.clip(1.0 - r2, 0, 1) ** sp.softness
        m = fall > 0.0035
        zc = clip[2] * 0.999
        subz = zbuf[y0:y1 + 1, x0:x1 + 1]
        m = m & (zc >= subz - 1e-3)
        if not m.any():
            return
        sub = buf[y0:y1 + 1, x0:x1 + 1]
        covr = self._cov[y0:y1 + 1, x0:x1 + 1]
        covr[...] = np.where(m, np.maximum(covr, fall * min(1.0, sp.intensity)), covr)
        add = (fall * sp.intensity)[..., None] * sp.color[None, None, :]
        sub[...] = np.where(m[..., None], sub + add, sub)

    # ---- phone screens ----
    def _draw_screen(self, sq, M, cam, buf, zbuf, W, H):
        cw = sq.corners @ M[:3, :3].T + M[:3, 3]
        px, z = cam.project(cw, W, H)[:2]
        # homography: source rect -> projected quad
        sw, sh = sq.image.size
        src = np.array([[0, 0], [sw, 0], [sw, sh], [0, sh]], dtype=np.float64)
        dst = px.astype(np.float64)
        Hm = _homography(src, dst)
        if Hm is None:
            return
        try:
            inv = np.linalg.inv(Hm)
        except np.linalg.LinAlgError:
            return
        x0 = max(0, int(math.floor(dst[:, 0].min())))
        x1 = min(W - 1, int(math.ceil(dst[:, 0].max())))
        y0 = max(0, int(math.floor(dst[:, 1].min())))
        y1 = min(H - 1, int(math.ceil(dst[:, 1].max())))
        if x0 >= x1 or y0 >= y1:
            return
        if (x1 - x0) * (y1 - y0) > 0.75 * W * H:
            return
        xs = np.arange(x0, x1 + 1, dtype=np.float64) + 0.5
        ys = np.arange(y0, y1 + 1, dtype=np.float64) + 0.5
        X = np.broadcast_to(xs[None, :], (len(ys), len(xs)))
        Y = np.broadcast_to(ys[:, None], (len(ys), len(xs)))
        den = inv[2, 0] * X + inv[2, 1] * Y + inv[2, 2]
        den = np.where(np.abs(den) < 1e-12, 1e-12, den)
        u = (inv[0, 0] * X + inv[0, 1] * Y + inv[0, 2]) / den
        v = (inv[1, 0] * X + inv[1, 1] * Y + inv[1, 2]) / den
        # containment: inside the projected convex quad (robust to the sign of
        # the homography's scale factor)
        inside = np.ones(X.shape, dtype=bool)
        sgn = 0
        for e in range(4):
            ax, ay = dst[e]
            bx, by = dst[(e + 1) % 4]
            cr = (bx - ax) * (Y - ay) - (by - ay) * (X - ax)
            if e == 0:
                sgn = 1.0 if cr.mean() >= 0 else -1.0
            inside &= (cr * sgn) >= -1.0
        mask = (u >= 0) & (u <= sw - 1) & (v >= 0) & (v <= sh - 1) & inside
        if not mask.any():
            return
        # rounded corner rejection
        if sq.radius:
            cu = np.clip(u, sq.radius, sw - 1 - sq.radius)
            cv = np.clip(v, sq.radius, sh - 1 - sq.radius)
            dd = (u - cu) ** 2 + (v - cv) ** 2
            mask &= dd <= sq.radius ** 2
        img = np.asarray(sq.image.convert("RGB"), dtype=F) / 255.0
        ui = np.clip(u.astype(np.int32), 0, sw - 1)
        vi = np.clip(v.astype(np.int32), 0, sh - 1)
        smp = img[vi, ui] * sq.brightness

        # planar depth from corner view-z (bilinear in quad space)
        zs = z.astype(np.float64)
        zu = np.clip(u / sw, 0, 1); zv = np.clip(v / sh, 0, 1)
        zz = ((1 - zu) * (1 - zv) * zs[0] + zu * (1 - zv) * zs[1]
              + zu * zv * zs[2] + (1 - zu) * zv * zs[3]).astype(F)
        subz = zbuf[y0:y1 + 1, x0:x1 + 1]
        ok = mask & (zz >= subz - 2e-3)
        if not ok.any():
            return
        sub = buf[y0:y1 + 1, x0:x1 + 1]
        sub[...] = np.where(ok[..., None], smp, sub)
        subz[...] = np.where(ok, zz, subz)
        self._cov[y0:y1 + 1, x0:x1 + 1][...] = np.where(
            ok, 1.0, self._cov[y0:y1 + 1, x0:x1 + 1])

    # ---- post ----
    def _post(self, buf, exposure, bloom, bloom_thresh, grain, vignette, grade, ca):
        W, H = self.RW, self.RH
        img = buf * exposure

        if bloom > 0:
            lum = img.max(axis=2)
            bright = np.clip(lum - bloom_thresh, 0, None) / (1.0 + np.clip(lum - bloom_thresh, 0, None))
            b = img * bright[..., None]
            k = 4
            h4, w4 = H // k, W // k
            bh, bw = h4 * k, w4 * k
            small = b[:bh, :bw].reshape(h4, k, w4, k, 3).mean(axis=(1, 3))
            small = _blur(_blur(_blur(small, 1.6), 2.6), 1.6)
            up = _upscale_fast(small, bw, bh)
            up2 = np.zeros((H, W, 3), dtype=F)
            up2[:bh, :bw] = up
            if bh < H:
                up2[bh:, :] = up2[bh - 1:bh, :]
            if bw < W:
                up2[:, bw:] = up2[:, bw - 1:bw]
            img = img + up2 * bloom

        # Soft highlight roll-off only: mids keep their exact brand value,
        # values above 1 (bloom/emissive) compress instead of clipping hard.
        knee = 0.80
        over = np.clip(img - knee, 0, None)
        img = np.where(img > knee, knee + over / (1.0 + over * 2.2), img)

        # grade: a touch of cool in the shadows, warmth in the highlights
        if grade:
            lum = (img @ np.array([0.299, 0.587, 0.114], dtype=F))[..., None]
            sh = np.clip(1.0 - lum * 3.2, 0, 1) ** 2
            img = img + sh * np.array([-0.006, 0.002, 0.012], dtype=F) * grade
            hi = np.clip((lum - 0.55) * 2.2, 0, 1) ** 2
            img = img + hi * np.array([0.010, 0.008, 0.002], dtype=F) * grade
            img = np.where(np.abs(lum - lum) > -1, img, img)
            g = lum
            img = g + (img - g) * (1.0 + 0.05 * grade)

        # vignette (built at 1/8 res then upscaled: it is a smooth field)
        if vignette:
            k = 8
            hh, ww = (H + k - 1) // k, (W + k - 1) // k
            yy = (np.arange(hh, dtype=F) / hh - 0.5)[:, None]
            xx = (np.arange(ww, dtype=F) / ww - 0.5)[None, :]
            r = np.sqrt(xx * xx * 1.15 + yy * yy * 1.05)
            vm = np.clip(1.0 - vignette * (r * 1.55) ** 2.3, 0, 1)[..., None]
            vm = np.repeat(np.repeat(vm, k, axis=0), k, axis=1)[:H, :W]
            img = img * vm

        img = np.clip(img, 0, 1)

        if grain:
            rng = np.random.default_rng(7)
            n = rng.standard_normal((H, W, 1)).astype(F) * grain
            img = np.clip(img + n, 0, 1)

        out = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
        if self.ss != 1.0:
            out = out.resize((self.W, self.H), Image.LANCZOS)
        return out



def _upscale_fast(a, w, h):
    """Nearest + box smoothing upscale, much cheaper than bilinear for bloom."""
    oh, ow = a.shape[:2]
    if oh == h and ow == w:
        return a
    ry = max(1, h // oh)
    rx = max(1, w // ow)
    big = np.repeat(np.repeat(a, ry, axis=0), rx, axis=1)
    # trim / pad to the exact size
    out = np.empty((h, w, 3), dtype=F)
    bh, bw = big.shape[:2]
    out[:min(h, bh), :min(w, bw)] = big[:min(h, bh), :min(w, bw)]
    if bh < h:
        out[bh:, :] = out[bh - 1:bh, :]
    if bw < w:
        out[:, bw:] = out[:, bw - 1:bw]
    return out * 2.2


def _resize_bilinear(a, w, h):
    """Bilinear resize of an (H,W,3) float array."""
    oh, ow = a.shape[:2]
    if oh == h and ow == w:
        return a
    ys = (np.arange(h, dtype=F) + 0.5) * (oh / h) - 0.5
    xs = (np.arange(w, dtype=F) + 0.5) * (ow / w) - 0.5
    y0 = np.clip(np.floor(ys).astype(np.int32), 0, oh - 1)
    x0 = np.clip(np.floor(xs).astype(np.int32), 0, ow - 1)
    y1 = np.clip(y0 + 1, 0, oh - 1)
    x1 = np.clip(x0 + 1, 0, ow - 1)
    fy = np.clip(ys - y0, 0, 1)[:, None, None]
    fx = np.clip(xs - x0, 0, 1)[None, :, None]
    top = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    return (top * (1 - fy) + bot * fy).astype(F)


def _blur(img, sigma):
    r = max(1, int(sigma * 1.8))
    xs = np.arange(-r, r + 1, dtype=F)
    k = np.exp(-(xs ** 2) / (2 * sigma * sigma))
    k /= k.sum()
    out = img
    pad = np.pad(out, ((0, 0), (r, r), (0, 0)), mode="edge")
    tmp = np.zeros_like(out)
    for i, w in enumerate(k):
        tmp += pad[:, i:i + out.shape[1], :] * w
    out = tmp
    pad = np.pad(out, ((r, r), (0, 0), (0, 0)), mode="edge")
    tmp = np.zeros_like(out)
    for i, w in enumerate(k):
        tmp += pad[i:i + out.shape[0], :, :] * w
    return tmp


def _homography(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    A = np.array(A, dtype=np.float64)
    try:
        _, _, vt = np.linalg.svd(A)
    except np.linalg.LinAlgError:
        return None
    Hm = vt[-1].reshape(3, 3)
    if abs(Hm[2, 2]) < 1e-12:
        return None
    return Hm / Hm[2, 2]
