"""
SIYMON interface kit — app screens drawn to PIL images for the phone faces.

Layouts and colours follow the real markup (public/index.html, public/app.js,
public/restaurant/, public/store/, public/driver/, public/wallet/) and
public/brand.css. Copy is drawn as neutral skeleton bars: the brief forbids
readable on-screen words, so no text is ever rendered.
"""
from __future__ import annotations

import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

# brand tokens
BG = (15, 15, 15)
SURF = (32, 32, 32)
SURF2 = (26, 26, 26)
GREEN = (93, 214, 44)
GREEN_DK = (51, 116, 24)
TEXT = (248, 248, 248)
MUTED = (168, 168, 168)
BORDER = (44, 44, 44)
DIM = (74, 74, 74)

SW, SH = 540, 1170

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets") + "/"
try:
    _LOGO = Image.open(ASSETS + "logo.png").convert("RGBA")
    _BADGE = Image.open(ASSETS + "badge.png").convert("RGBA")
except Exception:  # pragma: no cover
    _LOGO = None
    _BADGE = None
S = 2.0  # draw at 2x


def _c(t, a=255):
    return (int(t[0]), int(t[1]), int(t[2]), int(a))


class Canvas:
    def __init__(self, w=SW, h=SH, bg=BG):
        self.w, self.h = int(w * S), int(h * S)
        self.img = Image.new("RGBA", (self.w, self.h), _c(bg))
        self.d = ImageDraw.Draw(self.img)

    def rr(self, x, y, w, h, r, fill=None, outline=None, ow=2, alpha=255):
        box = [x * S, y * S, (x + w) * S, (y + h) * S]
        r = r * S
        if fill is not None:
            self.d.rounded_rectangle(box, radius=r, fill=_c(fill, alpha))
        if outline is not None:
            self.d.rounded_rectangle(box, radius=r, outline=_c(outline, alpha), width=int(ow * S))

    def rect(self, x, y, w, h, fill, alpha=255):
        self.d.rectangle([x * S, y * S, (x + w) * S, (y + h) * S], fill=_c(fill, alpha))

    def circle(self, cx, cy, r, fill=None, outline=None, ow=2, alpha=255):
        box = [(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S]
        if fill is not None:
            self.d.ellipse(box, fill=_c(fill, alpha))
        if outline is not None:
            self.d.ellipse(box, outline=_c(outline, alpha), width=int(ow * S))

    def bar(self, x, y, w, h, alpha=90, color=TEXT, r=None):
        r = h / 2 if r is None else r
        if color is TEXT:
            alpha = int(alpha * 0.62)   # copy reads as text, never as a slab
        self.rr(x, y, w, h, r, fill=color, alpha=alpha)

    def line(self, pts, color, width=2, alpha=255):
        self.d.line([(p[0] * S, p[1] * S) for p in pts], fill=_c(color, alpha), width=int(width * S), joint="curve")

    def poly(self, pts, fill, alpha=255, outline=None):
        self.d.polygon([(p[0] * S, p[1] * S) for p in pts], fill=_c(fill, alpha),
                       outline=_c(outline) if outline else None)

    def glow(self, cx, cy, r, color, strength=1.0):
        """Additive soft glow (no hard edge)."""
        size = max(8, int(r * 2 * S))
        g = Image.new("L", (size, size), 0)
        gd = ImageDraw.Draw(g)
        steps = 26
        for i in range(steps):
            f = 1.0 - i / steps
            a = int(90 * (1 - f) ** 2.2 * strength)
            if a <= 0:
                continue
            rr = size * 0.5 * f
            gd.ellipse([size / 2 - rr, size / 2 - rr, size / 2 + rr, size / 2 + rr], fill=a)
        g = g.filter(ImageFilter.GaussianBlur(size * 0.10))
        layer = Image.new("RGBA", (size, size), _c(color, 0))
        layer.putalpha(g.point(lambda v: int(v * 0.55)))
        self.img.alpha_composite(layer, (int((cx - r) * S), int((cy - r) * S)))

    def paste_img(self, im, x, y, w, h, radius=None, mask_soft=0):
        im = im.convert("RGBA").resize((int(w * S), int(h * S)), Image.LANCZOS)
        if radius:
            m = Image.new("L", im.size, 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, im.size[0] - 1, im.size[1] - 1],
                                                radius=radius * S, fill=255)
            im.putalpha(m)
        self.img.alpha_composite(im, (int(x * S), int(y * S)))

    def out(self, w=SW, h=SH):
        return self.img.resize((w, h), Image.LANCZOS).convert("RGB")




# ---- photographic product thumbs -----------------------------------------
_FOOD_FILES = {
    "burger": "food/burger.jpg",
    "tagine": "food/tagine.jpg",
    "coffee": "food/coffee.jpg",
    "groceries": "food/groceries.jpg",
    "pharmacy": "food/pharmacy.jpg",
    "bag": "food/delivery-bag.jpg",
}
_FOOD_CACHE = {}
_FOOD_SRC = {}


def _food_src(kind):
    if kind not in _FOOD_SRC:
        _FOOD_SRC[kind] = Image.open(ASSETS + _FOOD_FILES[kind]).convert("RGB")
    return _FOOD_SRC[kind]


def food_img(kind, w, h, r=12, zoom=1.0, dim=1.0):
    """A cropped photographic still as a rounded tile."""
    key = (kind, int(w), int(h), int(r), round(zoom, 2), round(dim, 2))
    if key in _FOOD_CACHE:
        return _FOOD_CACHE[key]
    im = _food_src(kind)
    pw, ph = int(w * S), int(h * S)
    scale = max(pw / im.width, ph / im.height) * zoom
    nw, nh = max(pw, int(im.width * scale)), max(ph, int(im.height * scale))
    im2 = im.resize((nw, nh), Image.LANCZOS)
    ox, oy = (nw - pw) // 2, (nh - ph) // 2
    im2 = im2.crop((ox, oy, ox + pw, oy + ph))
    if dim != 1.0:
        arr = np.asarray(im2).astype(np.float32) * dim
        im2 = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    im2 = im2.convert("RGBA")
    if r:
        m = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=r * S, fill=255)
        im2.putalpha(m)
    if len(_FOOD_CACHE) > 120:
        _FOOD_CACHE.clear()
    out = im2.resize((int(w), int(h)), Image.LANCZOS)
    _FOOD_CACHE[key] = out
    return out

# --------------------------------------------------------------------------
# icons
# --------------------------------------------------------------------------
def icon_search(c, x, y, s=18, col=MUTED, w=2.4):
    c.circle(x + s * 0.42, y + s * 0.42, s * 0.32, outline=col, ow=w)
    c.line([(x + s * 0.66, y + s * 0.66), (x + s * 0.98, y + s * 0.98)], col, w)


def icon_pin(c, x, y, s=20, col=GREEN):
    c.circle(x + s / 2, y + s * 0.38, s * 0.34, fill=col)
    c.poly([(x + s * 0.18, y + s * 0.52), (x + s * 0.82, y + s * 0.52), (x + s * 0.5, y + s)], col)


def icon_cart(c, x, y, s=22, col=TEXT):
    c.line([(x, y + s * 0.1), (x + s * 0.2, y + s * 0.1), (x + s * 0.36, y + s * 0.62),
            (x + s * 0.86, y + s * 0.62)], col, 2.2)
    c.line([(x + s * 0.26, y + s * 0.28), (x + s * 0.94, y + s * 0.28), (x + s * 0.86, y + s * 0.62)], col, 2.2)
    c.circle(x + s * 0.4, y + s * 0.86, s * 0.1, fill=col)
    c.circle(x + s * 0.82, y + s * 0.86, s * 0.1, fill=col)


def icon_bell(c, x, y, s=22, col=TEXT):
    c.poly([(x + s * 0.5, y + s * 0.06),
            (x + s * 0.72, y + s * 0.26),
            (x + s * 0.78, y + s * 0.68),
            (x + s * 0.88, y + s * 0.80),
            (x + s * 0.12, y + s * 0.80),
            (x + s * 0.22, y + s * 0.68),
            (x + s * 0.28, y + s * 0.26)], col)
    c.circle(x + s * 0.5, y + s * 0.6, s * 0.2, fill=col)
    c.circle(x + s * 0.5, y + s * 0.9, s * 0.09, fill=col)


def icon_home(c, x, y, s=22, col=TEXT):
    c.poly([(x + s * 0.5, y + s * 0.08), (x + s * 0.96, y + s * 0.48), (x + s * 0.04, y + s * 0.48)], col)
    c.rr(x + s * 0.18, y + s * 0.42, s * 0.64, s * 0.5, 3, fill=col)


def icon_user(c, x, y, s=22, col=TEXT):
    c.circle(x + s * 0.5, y + s * 0.32, s * 0.2, fill=col)
    c.rr(x + s * 0.16, y + s * 0.58, s * 0.68, s * 0.36, s * 0.18, fill=col)


def icon_shop(c, x, y, s=22, col=TEXT):
    c.poly([(x + s * 0.06, y + s * 0.34), (x + s * 0.94, y + s * 0.34), (x + s * 0.82, y + s * 0.06),
            (x + s * 0.18, y + s * 0.06)], col)
    c.rr(x + s * 0.14, y + s * 0.38, s * 0.72, s * 0.56, 3, fill=col)


def icon_check(c, x, y, s=20, col=GREEN, w=3):
    c.line([(x + s * 0.08, y + s * 0.52), (x + s * 0.4, y + s * 0.84), (x + s * 0.94, y + s * 0.16)], col, w)


def icon_clock(c, x, y, s=18, col=MUTED):
    c.circle(x + s / 2, y + s / 2, s * 0.44, outline=col, ow=2)
    c.line([(x + s / 2, y + s * 0.22), (x + s / 2, y + s / 2), (x + s * 0.74, y + s * 0.62)], col, 2)


def icon_bank(c, x, y, s=24, col=GREEN):
    c.poly([(x + s * 0.5, y), (x + s, y + s * 0.34), (x, y + s * 0.34)], col)
    for i in range(3):
        c.rect(x + s * (0.12 + i * 0.3), y + s * 0.44, s * 0.14, s * 0.34, _c(col))
    c.rect(x, y + s * 0.84, s, s * 0.1, _c(col))


def icon_card(c, x, y, s=26, col=GREEN):
    c.rr(x, y + s * 0.18, s, s * 0.64, 4, outline=col, ow=2.2)
    c.rect(x, y + s * 0.34, s, s * 0.14, _c(col))
    c.rr(x + s * 0.62, y + s * 0.58, s * 0.26, s * 0.1, 2, fill=col)


def icon_cash(c, x, y, s=26, col=GREEN):
    c.rr(x, y + s * 0.2, s, s * 0.6, 4, outline=col, ow=2.2)
    c.circle(x + s / 2, y + s * 0.5, s * 0.18, outline=col, ow=2.2)


def icon_moto(c, x, y, s=30, col=GREEN):
    c.circle(x + s * 0.2, y + s * 0.78, s * 0.16, outline=col, ow=2.4)
    c.circle(x + s * 0.8, y + s * 0.78, s * 0.16, outline=col, ow=2.4)
    c.line([(x + s * 0.2, y + s * 0.78), (x + s * 0.42, y + s * 0.46), (x + s * 0.66, y + s * 0.46),
            (x + s * 0.8, y + s * 0.78)], col, 2.4)
    c.line([(x + s * 0.34, y + s * 0.46), (x + s * 0.62, y + s * 0.18)], col, 2.4)


def icon_arrow_r(c, x, y, s=20, col=TEXT, w=2.4):
    c.line([(x, y + s / 2), (x + s, y + s / 2)], col, w)
    c.line([(x + s * 0.58, y + s * 0.14), (x + s, y + s / 2), (x + s * 0.58, y + s * 0.86)], col, w)


def icon_warn(c, x, y, s=20, col=(230, 170, 60)):
    c.poly([(x + s * 0.5, y + s * 0.06), (x + s * 0.97, y + s * 0.92),
            (x + s * 0.03, y + s * 0.92)], col)
    c.rect(x + s * 0.455, y + s * 0.36, s * 0.09, s * 0.30, (20, 20, 20))
    c.circle(x + s * 0.5, y + s * 0.80, s * 0.055, fill=(20, 20, 20))


def icon_coins(c, x, y, s=20, col=GREEN):
    c.ellipse_coin = None
    c.circle(x + s * 0.34, y + s * 0.66, s * 0.30, fill=col)
    c.circle(x + s * 0.62, y + s * 0.38, s * 0.30, fill=col, alpha=170)
    c.circle(x + s * 0.34, y + s * 0.66, s * 0.13, fill=(15, 15, 15))


def icon_chev(c, x, y, s=14, col=MUTED, w=2.2):
    c.line([(x + s * 0.3, y), (x + s * 0.75, y + s * 0.5), (x + s * 0.3, y + s)], col, w)


# --------------------------------------------------------------------------
# food / product glyphs (flat, brand-consistent)
# --------------------------------------------------------------------------
def glyph_burger(c, cx, cy, s):
    c.rr(cx - s * 0.5, cy - s * 0.36, s, s * 0.3, s * 0.15, fill=(226, 160, 62))
    c.rect(cx - s * 0.48, cy - s * 0.05, s * 0.96, s * 0.1, _c((94, 168, 62)))
    c.rect(cx - s * 0.46, cy + s * 0.06, s * 0.92, s * 0.12, _c((110, 66, 40)))
    c.rr(cx - s * 0.48, cy + s * 0.18, s * 0.96, s * 0.18, s * 0.08, fill=(214, 148, 52))


def glyph_pizza(c, cx, cy, s):
    c.circle(cx, cy, s * 0.48, fill=(210, 120, 48))
    c.circle(cx, cy, s * 0.4, fill=(232, 176, 74))
    for a in (0.6, 2.2, 4.0):
        c.circle(cx + math.cos(a) * s * 0.18, cy + math.sin(a) * s * 0.18, s * 0.07, fill=(150, 52, 46))


def glyph_bowl(c, cx, cy, s):
    c.circle(cx, cy, s * 0.46, fill=(196, 92, 52))
    c.circle(cx, cy, s * 0.34, fill=(226, 150, 66))
    c.circle(cx - s * 0.12, cy - s * 0.1, s * 0.1, fill=(240, 206, 120))
    c.circle(cx + s * 0.14, cy + s * 0.06, s * 0.09, fill=(96, 156, 72))


def glyph_coffee(c, cx, cy, s):
    c.rr(cx - s * 0.34, cy - s * 0.24, s * 0.6, s * 0.56, s * 0.1, fill=(238, 234, 226))
    c.circle(cx + s * 0.28, cy, s * 0.16, outline=(238, 234, 226), ow=int(4 * s / 40) if s > 20 else 3)
    c.rect(cx - s * 0.3, cy - s * 0.02, s * 0.52, s * 0.1, _c((112, 72, 44)))


def glyph_bottle(c, cx, cy, s):
    c.rr(cx - s * 0.18, cy - s * 0.46, s * 0.36, s * 0.18, s * 0.05, fill=(60, 140, 200))
    c.rr(cx - s * 0.28, cy - s * 0.28, s * 0.56, s * 0.72, s * 0.14, fill=(72, 168, 216))


def glyph_bag(c, cx, cy, s):
    c.rr(cx - s * 0.4, cy - s * 0.2, s * 0.8, s * 0.66, s * 0.08, fill=(214, 176, 96))
    c.line([(cx - s * 0.22, cy - s * 0.2), (cx - s * 0.22, cy - s * 0.4), (cx + s * 0.22, cy - s * 0.4),
            (cx + s * 0.22, cy - s * 0.2)], (240, 220, 170), 3)


def glyph_cross(c, cx, cy, s):
    c.rr(cx - s * 0.14, cy - s * 0.44, s * 0.28, s * 0.88, s * 0.06, fill=(90, 220, 120))
    c.rr(cx - s * 0.44, cy - s * 0.14, s * 0.88, s * 0.28, s * 0.06, fill=(90, 220, 120))


def glyph_pill(c, cx, cy, s):
    c.rr(cx - s * 0.42, cy - s * 0.2, s * 0.84, s * 0.4, s * 0.2, fill=(236, 238, 240))
    c.rr(cx - s * 0.42, cy - s * 0.2, s * 0.42, s * 0.4, s * 0.2, fill=(96, 200, 120))


def glyph_leaf(c, cx, cy, s):
    c.poly([(cx, cy - s * 0.42), (cx + s * 0.36, cy + s * 0.06), (cx, cy + s * 0.42),
            (cx - s * 0.36, cy + s * 0.06)], (96, 186, 72))


GLYPHS = {
    "burger": glyph_burger, "pizza": glyph_pizza, "bowl": glyph_bowl, "coffee": glyph_coffee,
    "bottle": glyph_bottle, "bag": glyph_bag, "pharmacy": glyph_cross, "pill": glyph_pill,
    "leaf": glyph_leaf,
}


def food_card(kind, w=200, h=130, bg=(18, 15, 13), r=12, seed=0):
    """A product photo substitute: dark warm tile, soft top-left key light."""
    cw, ch = int(w * S), int(h * S)
    yy = np.linspace(0.0, 1.0, ch, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 1.0, cw, dtype=np.float32)[None, :]
    base = np.array(bg, dtype=np.float32).reshape(1, 1, 3)
    # vertical fall-off + diagonal key light
    grad = (1.30 - 0.75 * yy) * (1.25 - 0.55 * xx)
    spot = np.exp(-(((xx - 0.40) ** 2 / 0.11) + ((yy - 0.32) ** 2 / 0.16)))
    tint = np.array([46.0, 34.0, 20.0], dtype=np.float32)
    arr = base * grad[..., None] + tint[None, None, :] * spot[..., None]
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    im = Image.fromarray(arr, "RGB").convert("RGBA")
    c = Canvas.__new__(Canvas)
    c.img, c.d, c.w, c.h = im, ImageDraw.Draw(im), cw, ch
    GLYPHS[kind](c, w / 2, h / 2 + h * 0.02, min(w, h) * 0.60)
    m = Image.new("L", (cw, ch), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, cw - 1, ch - 1], radius=r * S, fill=255)
    im.putalpha(m)
    return im


# --------------------------------------------------------------------------
# shared chrome
# --------------------------------------------------------------------------
def status_bar(c, w=SW):
    c.bar(28, 16, 34, 8, 120, TEXT, 4)
    c.bar(w - 90, 16, 26, 8, 120, TEXT, 4)
    c.rr(w - 58, 14, 30, 12, 4, outline=(120, 120, 120), ow=1.4)
    c.rect(w - 55, 17, 20, 6, _c(GREEN))


def bottom_nav(c, active=0, w=SW, h=SH, driver=False):
    y = h - 74
    c.rr(16, y, w - 32, 58, 28, fill=(24, 24, 24), outline=(46, 46, 46), ow=1.5)
    items = ["home", "cart", "shop", "bell", "user"] if not driver else ["home", "box", "clock", "user"]
    n = len(items)
    seg = (w - 32) / n
    for i, it in enumerate(items):
        cx = 16 + seg * (i + 0.5)
        isa = i == active
        if isa:
            c.rr(cx - seg * 0.42, y + 6, seg * 0.84, 46, 23, fill=GREEN)
        col = (15, 15, 15) if isa else (150, 150, 150)
        if it == "home":
            icon_home(c, cx - 11, y + 18, 22, col)
        elif it == "cart":
            icon_cart(c, cx - 11, y + 18, 22, col)
        elif it == "shop":
            icon_shop(c, cx - 11, y + 18, 22, col)
        elif it == "bell":
            icon_bell(c, cx - 11, y + 18, 22, col)
        elif it == "user":
            icon_user(c, cx - 11, y + 18, 22, col)
        elif it == "box":
            c.rr(cx - 10, y + 20, 20, 18, 3, outline=col, ow=2)
        elif it == "clock":
            icon_clock(c, cx - 10, y + 19, 20, col)


def logo_chip(c, x, y, s=30, rounded=True):
    """The real SIYMON app icon (vectorised from public/icons/icon-192.png)."""
    if _LOGO is None:
        c.rr(x, y, s, s, s * 0.29, fill=(72, 168, 28))
        return
    c.paste_img(_LOGO, x, y, s, s)


def badge(c, x, y, s=30):
    if _BADGE is None:
        c.circle(x + s / 2, y + s / 2, s / 2, fill=(20, 40, 18))
        return
    c.paste_img(_BADGE, x, y, s, s)


# --------------------------------------------------------------------------
# 1. customer home
# --------------------------------------------------------------------------
def screen_home(selected=0, cart=2, scroll=0.0, t=0.0, cats_shift=0.0):
    c = Canvas()
    status_bar(c)
    # header: wordmark block + real app icon
    logo_chip(c, 24, 44, 36)
    c.bar(74, 54, 74, 12, 175, r=4)
    c.bar(74, 72, 54, 8, 78, r=3)
    c.circle(SW - 44, 62, 21, fill=(28, 28, 28))
    icon_bell(c, SW - 55, 51, 22, TEXT)
    # location pill
    c.rr(24, 96, SW - 48, 56, 28, fill=SURF, outline=BORDER, ow=1.2)
    c.circle(SW - 56, 124, 17, fill=(24, 40, 20))
    icon_pin(c, SW - 66, 112, 22, GREEN)
    c.bar(SW - 300, 109, 150, 12, 165, r=4)
    c.bar(SW - 300, 127, 104, 8, 80, r=3)
    c.circle(52, 124, 16, fill=(38, 38, 38))
    c.d.line([(46 * S, 118 * S), (52 * S, 126 * S), (58 * S, 118 * S)], fill=_c(GREEN), width=int(2.2 * S))
    # search
    c.rr(24, 166, SW - 48, 54, 27, fill=SURF, outline=BORDER, ow=1.2)
    icon_search(c, 40, 182, 20, MUTED)
    c.bar(96, 187, 190, 12, 66, r=4)
    c.circle(SW - 54, 193, 19, fill=GREEN)
    icon_search(c, SW - 66, 181, 20, (15, 15, 15))
    # category chips
    cats = [("burger", True), ("pizza", False), ("bowl", False), ("coffee", False), ("pharmacy", False)]
    x = 24 - cats_shift
    cw = 96
    for g, active in cats:
        c.rr(x, 236, cw, 56, 28, fill=GREEN if active else SURF,
             outline=None if active else BORDER, ow=1.2)
        GLYPHS[g](c, x + cw / 2, 264, 31)
        x += cw + 12
    # section title
    c.bar(SW - 178, 322, 118, 14, 178, r=4)
    c.bar(24, 322, 54, 14, 60, r=4)
    # store cards
    stores = ["burger", "coffee", "groceries"]
    y = 352 - scroll
    for i, g in enumerate(stores):
        hgt = 200
        c.rr(24, y, SW - 48, hgt, 20, fill=(23, 23, 23), outline=BORDER, ow=1.2)
        c.paste_img(food_img(g, SW - 64, 124, 16, zoom=1.02, dim=0.92), 32, y + 8, SW - 64, 124)
        # open badge
        c.rr(SW - 124, y + 20, 56, 24, 12, fill=(246, 246, 246))
        c.circle(SW - 112, y + 32, 3.6, fill=(44, 170, 70))
        c.bar(SW - 102, y + 28, 26, 8, 150, (40, 40, 40), 3)
        # roundel
        badge(c, SW - 92, y + 106, 44)
        # name + meta
        c.bar(44, y + 144, 132, 14, 215, r=4)
        c.bar(44, y + 166, 76, 9, 84, r=3)
        icon_clock(c, SW - 190, y + 146, 15, MUTED)
        c.bar(SW - 170, y + 148, 46, 9, 84, r=3)
        c.bar(SW - 116, y + 148, 40, 9, 84, r=3)
        y += hgt + 14
    # cart bubble above nav
    c.circle(SW - 58, SH - 106, 21, fill=GREEN)
    icon_cart(c, SW - 69, SH - 118, 22, (15, 15, 15))
    c.circle(SW - 42, SH - 120, 10, fill=(15, 15, 15))
    c.bar(SW - 47, SH - 124, 10, 8, 200, TEXT, 2)
    bottom_nav(c, 0)
    return c.out()


# --------------------------------------------------------------------------
# 2. store detail + menu
# --------------------------------------------------------------------------
def screen_store(highlight=0, cart=0, t=0.0):
    c = Canvas()
    # cover
    cover = food_img("burger", SW, 300, 0, zoom=1.0, dim=1.0)
    c.paste_img(cover, 0, 0, SW, 300, radius=0)
    # gradient fade
    fade = Image.new("RGBA", (int(SW * S), int(300 * S)), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fade)
    for i in range(int(300 * S)):
        a = int(255 * max(0, (i / (300 * S) - 0.35)) / 0.65)
        fd.line([(0, i), (int(SW * S), i)], fill=_c(BG, a))
    c.img.alpha_composite(fade, (0, 0))
    status_bar(c)
    # back
    c.rr(24, 48, 44, 44, 22, fill=(20, 20, 20), alpha=220)
    icon_chev(c, 38, 62, 14, TEXT)
    c.d.line([(46 * S, 62 * S), (38 * S, 70 * S), (46 * S, 78 * S)], fill=_c(TEXT), width=int(2.4 * S))
    # store identity
    c.circle(64, 316, 34, fill=(24, 24, 24), outline=BORDER, ow=2)
    glyph_burger(c, 64, 316, 36)
    c.bar(SW - 250, 296, 170, 16, 220, r=4)
    c.bar(SW - 210, 322, 120, 9, 80)
    # tabs
    c.rr(24, 372, SW - 48, 48, 24, fill=SURF)
    c.rr(SW - 24 - (SW - 48) / 2, 378, (SW - 48) / 2 - 6, 36, 18, fill=GREEN)
    c.bar(SW - 168, 391, 70, 10, 160, (15, 15, 15))
    c.bar(78, 391, 70, 10, 90)
    # product grid
    items = ["burger", "tagine", "coffee", "groceries", "bag", "pharmacy"]
    cols, tw, th = 2, 236, 168
    x0 = 24
    for i, g in enumerate(items):
        r_, c_ = divmod(i, cols)
        x = x0 + c_ * (tw + 12)
        y = 440 + r_ * (th + 14)
        hl = i == highlight
        c.rr(x, y, tw, th, 18, fill=(26, 26, 26), outline=GREEN if hl else BORDER, ow=3 if hl else 1.2)
        c.paste_img(food_img(g, tw - 16, 104, 12, zoom=1.02, dim=0.95), x + 8, y + 8, tw - 16, 104)
        c.bar(x + 14, y + 122, 110, 10, 150, r=3)
        c.bar(x + 14, y + 140, 60, 9, 80, r=3)
        c.circle(x + tw - 26, y + th - 26, 14, fill=GREEN)
        c.d.line([(x + tw - 32, y + th - 26), (x + tw - 20, y + th - 26)], fill=_c((15, 15, 15)), width=int(2.6 * S))
        c.d.line([(x + tw - 26, y + th - 32), (x + tw - 26, y + th - 20)], fill=_c((15, 15, 15)), width=int(2.6 * S))
    bottom_nav(c, 2)
    return c.out()


# --------------------------------------------------------------------------
# 3. cart
# --------------------------------------------------------------------------
def screen_cart(n=3):
    c = Canvas()
    status_bar(c)
    c.rr(24, 48, 44, 44, 22, fill=(26, 26, 26))
    c.d.line([(46 * S, 62 * S), (38 * S, 70 * S), (46 * S, 78 * S)], fill=_c(TEXT), width=int(2.4 * S))
    c.bar(SW - 190, 58, 130, 16, 200, r=4)
    # store strip
    c.rr(24, 108, SW - 48, 68, 18, fill=SURF)
    glyph_burger(c, 66, 142, 38)
    c.bar(SW - 230, 126, 130, 11, 160)
    c.bar(SW - 200, 146, 90, 8, 70)
    y = 196
    items = [("burger", 2), ("coffee", 1), ("bag", 1)][:n]
    for i, (g, q) in enumerate(items):
        c.rr(24, y, SW - 48, 88, 16, fill=(24, 24, 24))
        c.paste_img(food_img(g, 72, 68, 12, dim=0.95), 34, y + 10, 72, 68)
        c.bar(SW - 220, y + 22, 116, 10, 150, r=3)
        c.bar(SW - 190, y + 42, 74, 8, 70, r=3)
        # stepper
        sx, sy_ = 132, y + 50
        c.rr(sx, sy_, 112, 30, 15, fill=(40, 40, 40))
        c.d.line([(sx + 20, sy_ + 15), (sx + 34, sy_ + 15)], fill=_c(GREEN), width=int(2.6 * S))
        c.d.line([(sx + 82, sy_ + 15), (sx + 96, sy_ + 15)], fill=_c(GREEN), width=int(2.6 * S))
        c.d.line([(sx + 89, sy_ + 8), (sx + 89, sy_ + 22)], fill=_c(GREEN), width=int(2.6 * S))
        c.bar(sx + 50, sy_ + 11, 12, 8, 210)
        y += 98
    # totals block
    ty = 500
    c.rr(24, ty, SW - 48, 176, 20, fill=(22, 22, 22), outline=BORDER, ow=1.2)
    rows = [3, 4, 5]
    for i, rlen in enumerate([92, 74, 108]):
        ry = ty + 22 + i * 34
        c.bar(SW - 40 - rlen, ry, rlen, 10, 70, r=3)
        c.bar(44, ry, 56, 10, 110, r=3)
    c.line([(44, ty + 118), (SW - 44, ty + 118)], BORDER, 1.4)
    c.bar(44, ty + 136, 70, 14, 200, r=4)
    c.bar(44, ty + 136, 70, 0, 0)
    c.bar(SW - 152, ty + 132, 108, 20, 240, r=5)
    # payment + delivery summary cards fill the lower page
    sy2 = ty + 194
    c.rr(24, sy2, SW - 48, 84, 16, fill=(23, 23, 23))
    c.rr(38, sy2 + 20, 44, 44, 12, fill=(28, 40, 24))
    icon_pin(c, 46, sy2 + 28, 26, GREEN)
    c.bar(SW - 220, sy2 + 26, 120, 10, 150, r=3)
    c.bar(SW - 190, sy2 + 44, 90, 8, 70, r=3)

    sy3 = sy2 + 96
    c.rr(24, sy3, SW - 48, 84, 16, fill=(23, 23, 23))
    c.rr(38, sy3 + 20, 44, 44, 12, fill=(28, 40, 24))
    icon_cash(c, 46, sy3 + 28, 26, GREEN)
    c.bar(SW - 220, sy3 + 26, 110, 10, 150, r=3)
    c.bar(SW - 190, sy3 + 44, 80, 8, 70, r=3)
    # CTA
    c.rr(24, SH - 196, SW - 48, 62, 31, fill=GREEN)
    c.bar(SW - 250, SH - 176, 150, 13, 120, (15, 15, 15), 4)
    c.circle(SW - 74, SH - 165, 20, fill=(15, 15, 15), alpha=40)
    icon_arrow_r(c, SW - 82, SH - 174, 18, (15, 15, 15))
    bottom_nav(c, 1)
    return c.out()


# --------------------------------------------------------------------------
# 4. checkout / payment  (only real methods: COD, TPE, transfer)
# --------------------------------------------------------------------------
def screen_pay(selected=0, pressed=0.0):
    c = Canvas()
    status_bar(c)
    c.bar(SW - 200, 54, 140, 16, 200, r=4)
    # total hero
    c.rr(24, 100, SW - 48, 96, 20, fill=(22, 34, 20), outline=(44, 92, 32), ow=1.6)
    c.bar(SW - 190, 122, 90, 10, 90, r=3)
    c.bar(SW - 210, 144, 170, 22, 240, r=6)
    methods = [("cash", False), ("card", True), ("bank", False)]
    y = 222
    for i, (g, off) in enumerate(methods):
        sel = i == selected
        c.rr(24, y, SW - 48, 78, 18, fill=(26, 26, 26) if sel else (21, 21, 21),
             outline=GREEN if sel else BORDER, ow=3 if sel else 1.2)
        c.rr(40, y + 17, 44, 44, 12, fill=(34, 42, 30) if sel else (32, 32, 32))
        if g == "cash":
            icon_cash(c, 50, y + 26, 24, GREEN if sel else MUTED)
        elif g == "card":
            icon_card(c, 50, y + 26, 24, GREEN if sel else MUTED)
        else:
            icon_bank(c, 50, y + 26, 24, GREEN if sel else MUTED)
        c.bar(SW - 230, y + 26, 130, 11, 160 if sel else 110, r=3)
        c.bar(SW - 190, y + 46, 90, 8, 70, r=3)
        if off:
            c.rr(SW - 150, y + 50, 44, 18, 9, fill=(58, 48, 26))
            c.bar(SW - 144, y + 55, 30, 7, 150, (214, 168, 60), 3)
        # radio
        c.circle(66, y + 39, 12, outline=GREEN if sel else (70, 70, 70), ow=2.4)
        if sel:
            c.circle(66, y + 39, 6, fill=GREEN)
        y += 88
    # note strip
    c.rr(24, 494, SW - 48, 54, 14, fill=(24, 28, 24))
    icon_clock(c, 42, 512, 18, MUTED)
    c.bar(SW - 240, 512, 170, 9, 70, r=3)
    # order summary
    sy2 = 560
    c.rr(24, sy2, SW - 48, 128, 18, fill=(23, 23, 23))
    for i in range(3):
        yy = sy2 + 18 + i * 30
        c.bar(SW - 40 - (90 - i * 14), yy, 90 - i * 14, 9, 70, r=3)
        c.bar(44, yy, 52 - i * 6, 9, 110, r=3)
    c.line([(44, sy2 + 104), (SW - 44, sy2 + 104)], BORDER, 1.2)
    icon_coins(c, 44, sy2 + 116, 18, GREEN)
    c.bar(70, sy2 + 118, 44, 9, 90, r=3)
    # card terminal at the door (TPE) quick service
    qy = sy2 + 140
    c.rr(24, qy, SW - 48, 66, 16, fill=(22, 26, 22), outline=BORDER, ow=1.2)
    icon_card(c, 40, qy + 20, 26, MUTED)
    c.bar(SW - 240, qy + 24, 120, 9, 140, r=3)
    c.bar(SW - 210, qy + 42, 80, 7, 60, r=3)
    c.rr(SW - 100, qy + 20, 60, 26, 13, fill=(30, 44, 26))
    c.bar(SW - 88, qy + 28, 36, 9, 150, GREEN, 3)
    # 3-D Secure / transfer verification note
    ny = qy + 80
    c.rr(24, ny, SW - 48, 56, 14, fill=(34, 30, 20), outline=(70, 58, 30), ow=1.2)
    icon_warn(c, 40, ny + 16, 22, (226, 168, 58))
    c.bar(SW - 250, ny + 20, 150, 9, 120, (226, 190, 130), 3)
    # confirm button
    press = pressed
    y0 = ny + 80 + press * 4
    if press > 0.01:
        c.glow(SW / 2, y0 + 34, 190, GREEN, press * 1.2)
    c.rr(24, y0, SW - 48, 68, 34, fill=GREEN if press < 0.6 else (255, 255, 255))
    icon_check(c, SW / 2 - 60, y0 + 24, 20, (15, 15, 15), 3.2)
    c.bar(SW / 2 - 30, y0 + 27, 96, 13, 140, (15, 15, 15), 4)
    return c.out()


# --------------------------------------------------------------------------
# 5. tracking map
# --------------------------------------------------------------------------
def _map_base(c, x, y, w, h, seed=3):
    """Dark 3D-ish city map: blocks, streets, park."""
    rng = np.random.default_rng(seed)
    c.rr(x, y, w, h, 20, fill=(20, 24, 26))
    # street grid
    for i in range(1, 6):
        gx = x + w * i / 6
        c.line([(gx, y + 8), (gx, y + h - 8)], (40, 46, 50), 7)
    for i in range(1, 8):
        gy = y + h * i / 8
        c.line([(x + 8, gy), (x + w - 8, gy)], (40, 46, 50), 7)
    # blocks
    for i in range(6):
        for j in range(8):
            if rng.random() < 0.22:
                continue
            bx = x + w * (i + 0.18) / 6
            by = y + h * (j + 0.16) / 8
            bw = w * 0.64 / 6
            bh = h * 0.68 / 8
            shade = int(30 + rng.random() * 14)
            c.rr(bx, by, bw, bh, 3, fill=(shade, shade + 3, shade + 5))
    # park
    c.rr(x + w * 0.06, y + h * 0.5, w * 0.26, h * 0.2, 6, fill=(24, 44, 30))


def screen_track(progress=0.0, steps=2):
    c = Canvas()
    c.rr(0, 0, SW, SH, 0, fill=(17, 20, 22))
    # real 3D city map still as the map surface
    try:
        mp = Image.open(ASSETS + "scenes/map.jpg").convert("RGB")
        mp = mp.resize((int(SW * S), int(SH * 0.62 * S)), Image.LANCZOS)
        arr = np.asarray(mp).astype(np.float32) * 0.72
        c.img.paste(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)),
                    (0, 0))
    except Exception:
        _map_base(c, -20, -20, SW + 40, SH * 0.62, 5)
    # route
    pts = [(88, 560), (150, 470), (150, 350), (250, 300), (250, 200), (360, 200), (420, 130)]
    c.line(pts, (255, 255, 255), 13, 90)
    c.line(pts, GREEN, 8)
    # traveled portion
    # destination pin
    dx, dy = pts[-1]
    c.circle(dx, dy, 15, fill=(255, 255, 255))
    c.circle(dx, dy, 9, fill=GREEN)
    # driver marker at progress
    idx = progress * (len(pts) - 1)
    i0 = min(int(idx), len(pts) - 2)
    f = idx - i0
    mx = pts[i0][0] + (pts[i0 + 1][0] - pts[i0][0]) * f
    my = pts[i0][1] + (pts[i0 + 1][1] - pts[i0][1]) * f
    c.glow(mx, my, 46, GREEN, 1.0)
    c.circle(mx, my, 19, fill=(18, 22, 18), outline=GREEN, ow=3)
    icon_moto(c, mx - 12, my - 12, 24, GREEN)
    # top status pill
    c.rr(24, 96, SW - 48, 76, 20, fill=(20, 26, 20), outline=(46, 84, 36), ow=1.4)
    c.rr(40, 112, 44, 44, 14, fill=GREEN)
    icon_moto(c, 49, 118, 26, (15, 15, 15))
    c.bar(SW - 240, 112, 130, 12, 190, r=4)
    c.bar(SW - 210, 132, 90, 8, 80, r=3)
    c.bar(SW - 104, 118, 48, 16, 220, r=5)
    # sheet
    sy = SH * 0.55
    c.rr(0, sy, SW, SH - sy, 30, fill=(18, 18, 18), outline=(38, 38, 38), ow=1.5)
    c.rr(SW / 2 - 26, sy + 12, 52, 5, 3, fill=(70, 70, 70))
    icon_moto(c, SW - 70, sy + 34, 30, GREEN)
    c.bar(SW - 230, sy + 42, 130, 14, 210, r=4)
    c.bar(SW - 180, sy + 66, 82, 9, 80, r=3)
    # ETA pill
    c.rr(36, sy + 36, 96, 34, 17, fill=(28, 44, 24), outline=(52, 100, 38), ow=1.2)
    c.bar(50, sy + 48, 26, 11, 200, r=3)
    c.bar(84, sy + 50, 32, 8, 90, r=3)
    # progress steps
    labels = ["✓", "✓", "", ""]
    y = sy + 96
    for i in range(4):
        sx = 60
        py = y + i * 54
        done = i < steps
        c.circle(sx, py, 11, fill=GREEN if done else (44, 44, 44), outline=GREEN if done else (60, 60, 60), ow=2)
        if done:
            c.d.line([(sx - 5 * S, py * S), (sx - 1 * S, (py + 4) * S), (sx + 6 * S, (py - 4) * S)],
                     fill=_c((15, 15, 15)), width=int(2.4 * S))
        if i < 3:
            c.line([(sx, py + 12), (sx, py + 42)], (44, 60, 40) if done else (40, 40, 40), 2.4)
        c.bar(88, py - 6, 150 - i * 18, 10, 150 if done else 70, r=3)
    bottom_nav(c, 0)
    return c.out()


# --------------------------------------------------------------------------
# 6. merchant: orders
# --------------------------------------------------------------------------
def screen_merchant_orders(state=0, t=0.0, pulse=0.0):
    """state 0 = incoming, 1 = reviewing, 2 = accepted/ready"""
    c = Canvas()
    c.rr(0, 0, SW, SH, 0, fill=(16, 16, 16))
    status_bar(c)
    logo_chip(c, SW - 78, 44, 34)
    c.bar(SW - 190, 50, 92, 13, 190)
    c.bar(SW - 170, 70, 70, 8, 70)
    # tabs
    c.rr(24, 98, SW - 48, 46, 23, fill=SURF)
    c.rr(SW - 24 - (SW - 48) / 2, 103, (SW - 48) / 2 - 5, 36, 18, fill=GREEN)
    c.bar(SW - 170, 116, 60, 10, 150, (15, 15, 15))
    c.bar(80, 116, 60, 10, 90)
    # KPI strip
    kp = 160
    for i in range(3):
        kx = 24 + i * ((SW - 48 - 24) / 3 + 12)
        kw = (SW - 48 - 24) / 3
        c.rr(kx, kp, kw, 76, 14, fill=(24, 24, 24) if i else (24, 38, 22),
             outline=BORDER if i else (46, 88, 36), ow=1.2)
        c.bar(kx + 14, kp + 16, 40, 8, 70, r=3)
        c.bar(kx + 14, kp + 34, 34, 18, 220 if i == 0 else 170, r=4)
        c.circle(kx + kw - 24, kp + 26, 10, fill=(30, 44, 26) if i == 0 else (34, 34, 34))
        GLYPHS[["bag", "coffee", "burger"][i]](c, kx + kw - 24, kp + 26, 13)
    # rows
    y = 258
    rows = [
        (True, 1.0),
        (False, 0.55),
        (False, 0.4),
        (False, 0.3),
        (False, 0.25),
    ]
    for i, (isnew, alpha) in enumerate(rows):
        hgt = 104
        hl = i == 0 and state >= 0
        if pulse > 0.02 and i == 0:
            c.glow(SW / 2, y + hgt / 2, 180, GREEN, pulse * 0.8)
        c.rr(24, y, SW - 48, hgt, 16, fill=(26, 30, 24) if hl else (23, 23, 23),
             outline=GREEN if (hl and pulse > 0.05) else BORDER, ow=2.4 if hl else 1.2)
        # order id block
        c.rr(38, y + 16, 44, 44, 10, fill=(30, 34, 28) if hl else (32, 32, 32))
        icon_cart(c, 48, y + 26, 24, GREEN if hl else MUTED)
        c.bar(SW - 190, y + 22, 96, 10, 160, r=3)
        c.bar(SW - 230, y + 42, 136, 8, 70, r=3)
        # status pill
        if hl:
            c.rr(38, y + 68, 86, 18, 9, fill=GREEN)
            c.bar(48, y + 72, 44, 7, 170, (15, 15, 15), 3)
        else:
            c.rr(38, y + 68, 86, 18, 9, fill=(38, 38, 38))
            c.bar(48, y + 72, 44, 7, 80, r=3)
        c.bar(38, y + 26, 0.1, 0.1, 0)
        y += hgt + 12
    # footer status strip
    fy = SH - 150
    c.rr(24, fy, SW - 48, 96, 18, fill=(23, 23, 23))
    c.circle(58, fy + 34, 16, fill=(30, 46, 26))
    icon_clock(c, 47, fy + 23, 22, GREEN)
    c.bar(SW - 220, fy + 24, 120, 10, 150, r=3)
    c.bar(SW - 190, fy + 42, 84, 8, 70, r=3)
    for i in range(5):
        c.rr(44 + i * 30, fy + 64, 22, 22, 6, fill=(34, 50, 30), outline=(52, 96, 40), ow=1.2)
        c.circle(55 + i * 30, fy + 75, 3.4, fill=GREEN)
    # detail sheet (state >= 1)
    if state >= 1:
        sy = 470
        c.rr(0, sy, SW, SH - sy, 28, fill=(22, 22, 22), outline=(40, 40, 40), ow=1.5)
        c.rr(SW / 2 - 26, sy + 12, 52, 5, 3, fill=(70, 70, 70))
        c.bar(SW - 210, sy + 34, 150, 14, 210, r=4)
        # line items
        ly = sy + 66
        for i in range(3):
            c.rr(24, ly, SW - 48, 52, 12, fill=(28, 28, 28))
            c.paste_img(food_img(["burger", "coffee", "bag"][i], 40, 40, 9, dim=0.95), 36, ly + 6, 40, 40)
            c.bar(SW - 220, ly + 15, 110, 9, 150, r=3)
            c.bar(SW - 180, ly + 31, 70, 7, 70, r=3)
            c.bar(40, ly + 20, 22, 11, 170, r=3)
            ly += 60
        c.line([(24, ly + 4), (SW - 24, ly + 4)], BORDER, 1.4)
        c.bar(24, ly + 18, 60, 9, 80, r=3)
        c.bar(24, ly + 18, 60, 0, 0)
        c.bar(SW - 130, ly + 14, 106, 16, 230, r=4)
        # accept CTA
        cy = ly + 52
        if state == 1:
            c.glow(SW / 2, cy + 32, 170, GREEN, 0.55)
            c.rr(24, cy, SW - 48, 64, 32, fill=GREEN)
            icon_check(c, SW / 2 - 46, cy + 22, 20, (15, 15, 15), 3.2)
            c.bar(SW / 2 - 16, cy + 25, 78, 12, 150, (15, 15, 15), 4)
        else:
            c.rr(24, cy, SW - 48, 64, 32, fill=(28, 40, 24), outline=GREEN, ow=2)
            icon_check(c, SW / 2 - 40, cy + 22, 20, GREEN, 3.2)
            c.bar(SW / 2 - 10, cy + 25, 70, 12, 170, GREEN, 4)
            # preparation checklist + hand-over slot
            cy2 = cy + 84
            for i in range(3):
                yy = cy2 + i * 46
                done = i < 2
                c.circle(48, yy + 14, 11, fill=GREEN if done else (40, 40, 40),
                         outline=GREEN if done else (62, 62, 62), ow=2)
                if done:
                    c.d.line([(43 * S, (yy + 14) * S), (47 * S, (yy + 18) * S), (54 * S, (yy + 9) * S)],
                             fill=_c((15, 15, 15)), width=int(2.4 * S))
                c.bar(74, yy + 9, 150 - i * 20, 10, 130 if done else 66, r=3)
            # pickup code row
            ry = cy2 + 3 * 46 + 10
            c.rr(24, ry, SW - 48, 78, 16, fill=(26, 34, 24), outline=(46, 88, 36), ow=1.4)
            c.bar(SW - 170, ry + 20, 110, 9, 80, r=3)
            for k in range(6):
                c.rr(SW - 240 + k * 34, ry + 38, 26, 28, 7, fill=(34, 50, 30), outline=GREEN, ow=1.2)
                c.circle(SW - 227 + k * 34, ry + 52, 4, fill=GREEN)
            c.circle(58, ry + 39, 20, fill=(28, 44, 24))
            icon_check(c, 46, ry + 27, 24, GREEN, 2.6)
    return c.out()


# --------------------------------------------------------------------------
# 7. merchant: products
# --------------------------------------------------------------------------
def screen_merchant_products(toggle=1.0, add=0.0, scroll=0.0):
    c = Canvas()
    status_bar(c)
    logo_chip(c, SW - 78, 44, 34)
    c.bar(SW - 190, 50, 100, 13, 190)
    c.rr(24, 98, SW - 48, 46, 23, fill=SURF)
    c.rr(24 + 5, 103, (SW - 48) / 2 - 5, 36, 18, fill=GREEN)
    c.bar(80, 116, 60, 10, 150, (15, 15, 15))
    c.bar(SW - 170, 116, 60, 10, 90)
    # "new product" row
    if add > 0.02:
        c.glow(SW - 80, 192, 150, GREEN, add * 0.9)
    c.rr(24, 160, SW - 48, 78, 16, fill=(26, 40, 22) if add > 0.3 else (22, 22, 22),
         outline=GREEN if add > 0.3 else (52, 96, 40), ow=2)
    c.rr(38, 174, 50, 50, 14, fill=GREEN if add > 0.3 else (30, 44, 26))
    col = (15, 15, 15) if add > 0.3 else GREEN
    c.d.line([(51 * S, 199 * S), (75 * S, 199 * S)], fill=_c(col), width=int(3 * S))
    c.d.line([(63 * S, 187 * S), (63 * S, 211 * S)], fill=_c(col), width=int(3 * S))
    c.bar(SW - 240, 180, 130, 10, 170 if add > 0.3 else 110, r=3)
    c.bar(SW - 210, 200, 100, 8, 60, r=3)
    # product rows
    items = ["burger", "tagine", "coffee", "groceries", "pharmacy", "bag"]
    y = 254 - scroll
    for i, g in enumerate(items):
        c.rr(24, y, SW - 48, 96, 16, fill=(24, 24, 24), outline=BORDER, ow=1.2)
        c.paste_img(food_img(g, 74, 74, 10, dim=0.95), 32, y + 11, 74, 74)
        c.bar(SW - 226, y + 22, 116, 10, 150, r=3)
        c.bar(SW - 200, y + 42, 90, 8, 70, r=3)
        # availability toggle
        on = 1.0 if i != 2 else 0.0
        if i == 2:
            on = toggle
        tx, ty = SW - 104, y + 30
        c.rr(tx, ty, 52, 26, 13, fill=GREEN if on > 0.5 else (52, 52, 52))
        kx = tx + 26 + (on - 0.5) * 20
        c.circle(kx, ty + 13, 10, fill=(250, 250, 250))
        y += 106
    # footer: stock sync note
    fy = SH - 112
    c.rr(24, fy, SW - 48, 74, 16, fill=(23, 23, 23))
    glyph_leaf(c, 42, fy + 26, 26)
    c.bar(SW - 250, fy + 20, 130, 10, 150, r=3)
    c.bar(SW - 210, fy + 40, 90, 8, 70, r=3)
    c.rr(SW - 106, fy + 24, 58, 26, 13, fill=(30, 44, 26), outline=GREEN, ow=1.3)
    icon_check(c, SW - 96, fy + 29, 16, GREEN, 2.2)
    return c.out()


# --------------------------------------------------------------------------
# 8. driver home
# --------------------------------------------------------------------------
def screen_driver_home(online=1.0, earn=0.0, offers=0, pulse=0.0):
    c = Canvas()
    status_bar(c)
    c.circle(64, 66, 22, fill=(30, 30, 30))
    icon_bell(c, 52, 54, 24, TEXT)
    c.circle(SW - 60, 66, 26, fill=(30, 46, 26), outline=GREEN, ow=2)
    icon_moto(c, SW - 74, 52, 28, GREEN)
    c.bar(SW - 176, 54, 62, 10, 150, r=3)
    c.bar(SW - 190, 72, 76, 8, 80, r=3)
    # online card
    c.rr(24, 108, SW - 48, 128, 22, fill=(20, 34, 18) if online > 0.5 else (26, 26, 26),
         outline=(48, 96, 36) if online > 0.5 else BORDER, ow=1.6)
    c.circle(64, 140, 12, fill=GREEN if online > 0.5 else (90, 90, 90))
    if online > 0.5:
        c.glow(64, 140, 34, GREEN, 0.9)
    c.bar(SW - 200, 130, 110, 13, 200, r=4)
    c.bar(SW - 240, 152, 150, 8, 70, r=3)
    # toggle
    tx, ty = SW - 152, 168
    c.rr(tx, ty, 92, 40, 20, fill=(40, 40, 40))
    c.rr(tx, ty, 92 * max(0.15, online), 40, 20, fill=GREEN)
    kx = tx + 20 + (92 - 40) * online
    c.circle(kx, ty + 20, 15, fill=(250, 250, 250))
    # earnings card
    c.rr(24, 252, SW - 48, 152, 22, fill=(30, 30, 30))
    c.bar(SW - 170, 274, 100, 10, 90, r=3)
    c.bar(SW - 230, 296, 160, 28, 240, r=7)
    c.bar(SW - 150, 334, 80, 9, 70, r=3)
    c.line([(40, 360), (SW - 40, 360)], (48, 48, 48), 1.4)
    c.bar(SW - 120, 372, 66, 9, 80, r=3)
    c.bar(40, 372, 66, 9, 80, r=3)
    c.bar(SW - 110, 392, 50, 12, 170, r=3)
    c.bar(40, 392, 50, 12, 170, r=3)
    # offers section
    c.bar(SW - 210, 428, 120, 13, 180, r=4)
    c.rr(SW - 108, 422, 44, 26, 13, fill=GREEN)
    c.bar(SW - 96, 431, 22, 8, 150, (15, 15, 15), 3)
    # offer cards
    y = 472
    for i in range(max(1, offers)):
        if pulse > 0 and i == 0:
            c.glow(SW / 2, y + 100, 200, GREEN, pulse * 1.1)
        c.rr(24, y, SW - 48, 196, 20, fill=(24, 30, 22) if i == 0 else (23, 23, 23),
             outline=GREEN if (i == 0 and pulse > 0.05) else BORDER, ow=3 if i == 0 else 1.2)
        # riding thumb + route diagram
        try:
            rd = Image.open(ASSETS + "scenes/ride.jpg").convert("RGB")
            rd = rd.crop((0, int(rd.height * 0.18), rd.width, int(rd.height * 0.82)))
            c.paste_img(rd, 36, y + 14, 112, 96, radius=12)
        except Exception:
            pass
        c.circle(168, y + 34, 9, fill=GREEN)
        c.circle(168, y + 86, 9, fill=(250, 250, 250))
        c.line([(168, y + 44), (168, y + 76)], (90, 120, 80), 2.4)
        c.bar(SW - 200, y + 28, 110, 10, 160, r=3)
        c.bar(SW - 180, y + 80, 90, 10, 160, r=3)
        c.bar(SW - 260, y + 46, 60, 7, 60, r=3)
        c.bar(SW - 240, y + 98, 70, 7, 60, r=3)
        c.line([(40, y + 126), (SW - 40, y + 126)], (44, 44, 44), 1.3)
        # metrics
        c.bar(SW - 130, y + 138, 44, 9, 70, r=3)
        c.bar(SW - 120, y + 154, 54, 14, 200, r=3)
        icon_arrow_r(c, 42, y + 146, 18, GREEN)
        c.bar(70, y + 148, 60, 10, 120, r=3)
        c.bar(70, y + 148, 0, 0, 0)
        y += 208
    # recent deliveries fill the rest of the panel
    hy = max(y + 10, 690)
    c.bar(SW - 190, hy, 110, 12, 150, r=4)
    c.bar(24, hy, 60, 12, 70, r=4)
    hy += 26
    for i, amt in enumerate((86, 64)):
        c.rr(24, hy, SW - 48, 66, 14, fill=(23, 23, 23))
        c.circle(58, hy + 33, 17, fill=(30, 46, 26))
        icon_check(c, 48, hy + 23, 20, GREEN, 2.6)
        c.bar(SW - 230, hy + 18, 120 - i * 16, 9, 130, r=3)
        c.bar(SW - 200, hy + 36, 80 - i * 10, 7, 62, r=3)
        c.bar(SW - 120, hy + 24, 46 + amt * 0.2, 11, 190, r=3)
        c.bar(SW - 66, hy + 24, 0.1, 0.1, 0)
        hy += 74
    bottom_nav(c, 0, driver=True)
    return c.out()


# --------------------------------------------------------------------------
# 9. driver offer detail
# --------------------------------------------------------------------------
def screen_driver_offer(accept=0.0):
    c = Canvas()
    c.rr(0, 0, SW, SH, 0, fill=(17, 17, 17))
    _map_base(c, -20, -20, SW + 40, 520, 9)
    c.rr(0, 0, SW, SH, 0, fill=(15, 15, 15), alpha=90)
    status_bar(c)
    # route on mini map
    pts = [(110, 380), (110, 300), (200, 260), (200, 170), (330, 170), (380, 110)]
    c.line(pts, (255, 255, 255), 12, 70)
    c.line(pts, GREEN, 7)
    c.circle(pts[0][0], pts[0][1], 12, fill=GREEN, outline=(255, 255, 255), ow=3)
    c.circle(pts[-1][0], pts[-1][1], 12, fill=(255, 255, 255), outline=GREEN, ow=3)
    # sheet
    sy = 420
    c.rr(0, sy, SW, SH - sy, 30, fill=(20, 20, 20), outline=(40, 40, 40), ow=1.5)
    c.rr(SW / 2 - 26, sy + 12, 52, 5, 3, fill=(70, 70, 70))
    # payout hero
    c.rr(24, sy + 34, SW - 48, 92, 20, fill=(22, 36, 20), outline=(48, 96, 36), ow=1.5)
    c.bar(SW - 160, sy + 52, 90, 9, 90, r=3)
    c.bar(SW - 230, sy + 74, 170, 26, 245, r=6)
    # pickup / dropoff
    ry = sy + 146
    c.circle(50, ry + 12, 8, fill=GREEN)
    c.circle(50, ry + 60, 8, fill=(250, 250, 250))
    c.line([(50, ry + 22), (50, ry + 50)], (80, 110, 70), 2.4)
    c.bar(SW - 200, ry + 6, 110, 10, 170, r=3)
    c.bar(SW - 230, ry + 22, 140, 8, 70, r=3)
    c.bar(SW - 200, ry + 54, 110, 10, 170, r=3)
    c.bar(SW - 240, ry + 70, 150, 8, 70, r=3)
    # distance + time metrics
    my = ry + 108
    for i in range(3):
        mx = 44 + i * 152
        c.rr(mx, my, 136, 66, 14, fill=(30, 30, 30))
        c.bar(mx + 16, my + 16, 44, 8, 70, r=3)
        c.bar(mx + 16, my + 34, 66, 14, 200, r=3)
    # accept / decline
    ay = my + 92
    if accept > 0.02:
        c.glow(SW / 2, ay + 36, 200, GREEN, accept * 1.3)
    c.rr(24, ay, SW - 48, 72, 36, fill=GREEN if accept < 0.85 else (250, 250, 250))
    icon_check(c, SW / 2 - 56, ay + 26, 22, (15, 15, 15), 3.4)
    c.bar(SW / 2 - 24, ay + 29, 84, 13, 150, (15, 15, 15), 4)
    # decline
    c.rr(24, ay + 88, SW - 48, 58, 29, fill=(28, 28, 28), outline=(58, 58, 58), ow=1.4)
    c.d.line([(SW / 2 - 66 * S, (ay + 117) * S), (SW / 2 - 50 * S, (ay + 117) * S)],
             fill=_c((200, 200, 200)), width=int(2.6 * S))
    c.d.line([(SW / 2 - 58 * S, (ay + 109) * S), (SW / 2 - 66 * S, (ay + 117) * S),
              (SW / 2 - 58 * S, (ay + 125) * S)], fill=_c((200, 200, 200)), width=int(2.6 * S))
    c.bar(SW / 2 - 32, ay + 112, 78, 11, 90, r=3)
    # footnote strip
    c.rr(24, ay + 164, SW - 48, 52, 14, fill=(23, 26, 23))
    icon_clock(c, 42, ay + 180, 18, MUTED)
    c.bar(SW - 250, ay + 181, 120, 9, 66, r=3)
    c.bar(SW - 120, ay + 181, 60, 9, 90, r=3)
    return c.out()


# --------------------------------------------------------------------------
# 10. driver navigation
# --------------------------------------------------------------------------
def nav_map(progress=0.0, phase=0):
    """Full-screen 3D-ish navigation view."""
    c = Canvas()
    c.rr(0, 0, SW, SH, 0, fill=(18, 22, 24))
    _map_base(c, -30, -30, SW + 60, SH + 120, 11 if phase == 0 else 13)
    pts = [(70, 900), (70, 720), (200, 680), (200, 480), (360, 480), (360, 300), (470, 260)]
    c.line(pts, (255, 255, 255), 20, 60)
    c.line(pts, (36, 42, 46), 14)
    c.line(pts, GREEN, 9)
    # remaining (dim)
    idx = progress * (len(pts) - 1)
    i0 = min(int(idx), len(pts) - 2)
    f = idx - i0
    mx = pts[i0][0] + (pts[i0 + 1][0] - pts[i0][0]) * f
    my = pts[i0][1] + (pts[i0 + 1][1] - pts[i0][1]) * f
    # travelled fade
    c.glow(mx, my, 70, GREEN, 0.9)
    c.circle(mx, my, 25, fill=(16, 20, 16), outline=GREEN, ow=4)
    icon_moto(c, mx - 16, my - 16, 32, GREEN)
    # top instruction card
    c.rr(24, 96, SW - 48, 96, 22, fill=(20, 24, 20), outline=(46, 60, 42), ow=1.5)
    c.rr(40, 112, 64, 64, 18, fill=GREEN)
    c.d.line([(56 * S, 150 * S), (72 * S, 130 * S), (88 * S, 150 * S)], fill=_c((15, 15, 15)), width=int(5 * S))
    c.bar(SW - 240, 118, 150, 16, 210, r=4)
    c.bar(SW - 200, 146, 100, 10, 90, r=3)
    # bottom bar
    c.rr(24, SH - 150, SW - 48, 96, 24, fill=(20, 20, 20), outline=(44, 44, 44), ow=1.4)
    c.bar(SW - 220, SH - 128, 130, 14, 200, r=4)
    c.bar(SW - 180, SH - 106, 90, 9, 80, r=3)
    c.circle(SW - 76, SH - 102, 26, fill=(24, 34, 22))
    icon_bell(c, SW - 88, SH - 114, 24, GREEN)
    return c.out()


# --------------------------------------------------------------------------
# 11. verification code pad
# --------------------------------------------------------------------------
def screen_code(entered=3, ok=0.0):
    c = Canvas()
    c.rr(0, 0, SW, SH, 0, fill=(14, 14, 14))
    status_bar(c)
    # sheet
    c.rr(0, 118, SW, SH - 118, 30, fill=(20, 20, 20), outline=(40, 40, 40), ow=1.5)
    c.rr(SW / 2 - 26, 132, 52, 5, 3, fill=(70, 70, 70))
    # lock glyph
    c.circle(SW / 2, 206, 30, fill=(28, 42, 24))
    c.rr(SW / 2 - 12, 196, 24, 20, 4, outline=GREEN, ow=2.4)
    c.d.arc([(SW / 2 - 9) * S, 182 * S, (SW / 2 + 9) * S, 206 * S], 180, 360, fill=_c(GREEN), width=int(2.4 * S))
    c.bar(SW / 2 - 90, 258, 180, 12, 170, r=4)
    c.bar(SW / 2 - 60, 280, 120, 8, 70, r=3)
    # code boxes
    n = 6
    bw, gap = 46, 12
    total = n * bw + (n - 1) * gap
    x0 = (SW - total) / 2
    for i in range(n):
        x = x0 + i * (bw + gap)
        filled = i < entered
        c.rr(x, 318, bw, 56, 12, fill=(30, 30, 30) if not filled else (34, 52, 28),
             outline=GREEN if (filled or i == entered) else (56, 56, 56), ow=2)
        if filled:
            c.circle(x + bw / 2, 346, 7, fill=GREEN)
        elif i == entered:
            c.rr(x + bw / 2 - 1.2, 330, 2.4, 32, 1.2, fill=GREEN)
    # keypad
    keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "del"]
    kw, kh = 84, 62
    gx, gy = 22, 22
    total_w = 3 * kw + 2 * gx
    kx0 = (SW - total_w) / 2
    for i, k in enumerate(keys):
        r_, c_ = divmod(i, 3)
        x = kx0 + c_ * (kw + gx)
        y = 386 + r_ * (kh + gy)
        if k == "":
            continue
        c.rr(x, y, kw, kh, 18, fill=(30, 30, 30))
        if k == "del":
            c.rr(x + 24, y + 22, 36, 18, 4, outline=(200, 200, 200), ow=2)
            c.line([(x + 34, y + 31), (x + 44, y + 31)], (200, 200, 200), 2)
            c.line([(x + 46, y + 22), (x + 34, y + 31), (x + 46, y + 40)], (200, 200, 200), 2)
        else:
            # digit as dot pattern (no readable numerals -> abstract keypad dots)
            val = int(k)
            dots = [(x + kw / 2, y + kh / 2)]
            if val == 0:
                c.circle(x + kw / 2, y + kh / 2, 13, outline=(190, 190, 190), ow=2.6)
            else:
                cnt = val
                cols = 3
                for d in range(cnt):
                    dx = (d % cols - 1) * 13
                    dy = (d // cols - (cnt // cols) / 2) * 13
                    c.circle(x + kw / 2 + dx, y + kh / 2 + dy, 4.4, fill=(220, 220, 220))
    # footer: what is being confirmed + CTA
    fy = 866
    c.rr(24, fy, SW - 48, 96, 18, fill=(26, 30, 26), outline=(46, 84, 36), ow=1.4)
    c.circle(62, fy + 34, 18, fill=GREEN)
    icon_bell(c, 50, fy + 22, 24, (15, 15, 15))
    c.bar(SW - 240, fy + 22, 120, 11, 190, r=4)
    c.bar(SW - 210, fy + 42, 90, 8, 80, r=3)
    c.line([(44, fy + 66), (SW - 44, fy + 66)], (44, 60, 40), 1.2)
    icon_moto(c, 44, fy + 70, 20, GREEN)
    c.bar(SW - 250, fy + 74, 110, 8, 70, r=3)
    c.bar(SW - 150, fy + 74, 44, 8, 110, r=3)
    if ok > 0.02:
        c.glow(SW / 2, fy + 152, 200, GREEN, ok * 1.3)
        c.rr(24, fy + 110, SW - 48, 72, 36, fill=GREEN)
        icon_check(c, SW / 2 - 52, fy + 134, 22, (15, 15, 15), 3.4)
        c.bar(SW / 2 - 20, fy + 138, 72, 12, 150, (15, 15, 15), 4)
    else:
        c.rr(24, fy + 110, SW - 48, 72, 36, fill=(34, 34, 34))
        c.bar(SW / 2 - 56, fy + 137, 112, 12, 70, r=4)
    return c.out()


# --------------------------------------------------------------------------
# 12. driver wallet / earnings
# --------------------------------------------------------------------------
def wallet_screen(balance_glow=0.0, entries=3):
    c = Canvas()
    c.rr(0, 0, SW, SH, 0, fill=(16, 16, 16))
    status_bar(c)
    c.bar(SW - 190, 52, 90, 14, 190, r=4)
    # hero
    if balance_glow > 0.02:
        c.glow(SW / 2, 250, 260, GREEN, balance_glow * 1.1)
    c.rr(24, 100, SW - 48, 190, 26, fill=(20, 34, 18), outline=(46, 92, 34), ow=1.6)
    c.bar(SW - 160, 126, 70, 9, 90, r=3)
    c.bar(SW - 260, 152, 200, 34, 248, r=8)
    c.bar(SW - 170, 200, 110, 9, 90, r=3)
    c.line([(44, 226), (SW - 44, 226)], (44, 74, 36), 1.4)
    c.bar(44, 240, 60, 8, 80, r=3)
    c.bar(44, 256, 44, 12, 170, r=3)
    c.bar(SW - 104, 240, 60, 8, 80, r=3)
    c.bar(SW - 104, 256, 44, 12, 170, r=3)
    # topup button
    c.rr(40, 322, 140, 44, 22, fill=GREEN)
    c.bar(70, 336, 60, 10, 150, (15, 15, 15), 3)
    c.rr(SW - 96, 302, 72, 62, 20, fill=(30, 46, 26))
    icon_bank(c, SW - 78, 320, 36, GREEN)
    # ledger
    c.bar(SW - 190, 406, 100, 12, 170, r=3)
    y = 440
    rows = [("+", GREEN), ("-", (220, 220, 220)), ("+", GREEN), ("-", (220, 220, 220))]
    for i in range(entries):
        sign, col = rows[i % 4]
        c.rr(24, y, SW - 48, 72, 14, fill=(23, 23, 23))
        c.circle(62, y + 36, 19, fill=(30, 44, 26) if sign == "+" else (36, 36, 36))
        if sign == "+":
            icon_check(c, 52, y + 26, 20, GREEN, 2.8)
        else:
            c.line([(54, y + 36), (70, y + 36)], (200, 200, 200), 2.6)
        c.bar(SW - 210, y + 22, 120, 10, 150, r=3)
        c.bar(SW - 170, y + 42, 80, 8, 60, r=3)
        c.bar(96, y + 26, 0.1, 0.1, 0)
        c.bar(SW - 120, y + 26, 56, 12, 200 if sign == "+" else 130, r=3)
        y += 82
    bottom_nav(c, 3, driver=True)
    return c.out()


# --------------------------------------------------------------------------
# small components for 3D overlays
# --------------------------------------------------------------------------
def notification_bar(icon="bell"):
    c = Canvas(540, 132, bg=(0, 0, 0))
    c.img = Image.new("RGBA", (c.w, c.h), (0, 0, 0, 0))
    c.d = ImageDraw.Draw(c.img)
    c.rr(10, 10, 520, 112, 30, fill=(28, 30, 28), outline=(70, 120, 56), ow=1.6)
    c.rr(30, 30, 72, 72, 22, fill=GREEN)
    if icon == "bell":
        icon_bell(c, 50, 50, 32, (15, 15, 15))
    else:
        icon_moto(c, 50, 46, 34, (15, 15, 15))
    c.bar(122, 42, 210, 16, 210, r=4)
    c.bar(122, 70, 300, 11, 90, r=3)
    c.bar(122, 90, 170, 11, 70, r=3)
    c.circle(480, 52, 8, fill=GREEN)
    return c.img.resize((540, 132), Image.LANCZOS)


def pill_track(text_len=0, w=260, color=GREEN):
    c = Canvas(w, 64, bg=(0, 0, 0))
    c.img = Image.new("RGBA", (c.w, c.h), (0, 0, 0, 0))
    c.d = ImageDraw.Draw(c.img)
    c.rr(0, 6, w, 52, 26, fill=(20, 26, 20), outline=color, ow=1.5)
    c.circle(26, 32, 10, fill=color)
    c.bar(46, 26, w - 90, 12, 160, r=4)
    return c.img.resize((w, 64), Image.LANCZOS)


def toast_ok(w=300, h=90):
    c = Canvas(w, h, bg=(0, 0, 0))
    c.img = Image.new("RGBA", (c.w, c.h), (0, 0, 0, 0))
    c.d = ImageDraw.Draw(c.img)
    c.rr(0, 0, w, h, 24, fill=(24, 42, 20), outline=GREEN, ow=2)
    c.circle(48, h / 2, 26, fill=GREEN)
    icon_check(c, 34, h / 2 - 14, 28, (15, 15, 15), 4)
    c.bar(92, h / 2 - 12, w - 130, 11, 160, r=4)
    c.bar(92, h / 2 + 6, w - 170, 9, 80, r=3)
    return c.img.resize((w, h), Image.LANCZOS)
