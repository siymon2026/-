"""
The three SIYMON cinematic explainers (9:16, silent, no on-screen text).

Video 1 — Customer experience
Video 2 — Restaurant & store experience
Video 3 — Driver experience

Every beat maps to a verified feature of the project (see PROJECT-AUDIT.md):
the real status machine, the pickup/delivery 6-digit codes, COD / TPE /
manual-transfer payment options only, the 500 m hex dispatch grid and the
driver earnings model.
"""
from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import film
import scenes
import shots
from scenes import GREEN, W, H, add, screen_blend, moment_shot, phone_shot, logo_shot
from film import radial_glow, black, screen


# ==========================================================================
#  shared building blocks
# ==========================================================================
def title_none(*a, **k):  # placeholder guard: the brief forbids titles
    raise RuntimeError("no titles allowed")


def endcard(t, dur):
    """Closing brand frame shared by all three films."""
    img = logo_shot(t, dur, plate=None, scale_from=0.30, scale_to=0.92, glow=1.0,
                    bloom=1.15, rise=0.02)
    k = film.span(t, 0, dur * 0.55)
    img = film.fade_to_black(img, 1.0 - film.smooth(k))
    return img


def black_out(t, dur, hold=0.12):
    return black()


def phone_customer(t, dur, name, plate="env/street.jpg", **kw):
    return phone_shot(plate, t, dur, screen(name, **kw), rot_y_deg=-10, fov=29,
                      exposure=1.3, dark=0.55, glow=0.9)


# ==========================================================================
#  VIDEO 1 — CUSTOMER
# ==========================================================================
def build_customer():
    f = film.Film("01-customer")

    # 1. brand opens on black, green light
    f.add("brand-open", 3.0, lambda t, d: logo_shot(t, d, plate=None, scale_from=0.18,
                                                    scale_to=0.86, glow=1.0, bloom=1.0),
          start=0.0, xfade=0.5)

    # 2. the phone appears out of the light, camera pushes into the screen
    def s2(t, d):
        img = phone_shot("env/street.jpg", t, d, screen("screen_home"),
                         eye=(0.0, 0.06, 5.4), target=(0, 0.02, 0), rot_y_deg=-14,
                         fov=30, exposure=1.3, dark=0.5, glow=0.8)
        return img
    f.add("phone-arrive", 3.4, s2, xfade=0.5, trans="light")

    # 3. inside the app: discover restaurants, stores, pharmacy
    f.add("discover", 4.6, lambda t, d: shots.scroll_shot(t, d, "screen_home",
                                                          scroll_from=0, scroll_to=170,
                                                          push=0.06,
                                                          tap=(0.5, 0.30,
                                                               film.span(t, d * 0.55, d * 0.7))),
          xfade=0.55, trans="wipe")

    # 4. store menu + choosing products, flying into the cart
    f.add("choose", 4.8, lambda t, d: shots.add_to_cart_shot(t, d, plate="env/store.jpg",
                                                             dark=0.58), xfade=0.5,
          trans="light")

    # 5. cart, then the address pin on the city
    f.add("cart", 3.4, lambda t, d: shots.scroll_shot(t, d, "screen_cart", push=0.05),
          xfade=0.5)
    f.add("address", 3.8, lambda t, d: shots.pin_shot(t, d), xfade=0.55, trans="light")

    # 6. payment: only the methods the project really offers
    def s6(t, d):
        press = film.smooth(film.span(t, d * 0.62, d * 0.80))
        return phone_shot("env/door.jpg", t, d,
                          screen("screen_pay", selected=0, pressed=press),
                          rot_y_deg=-9, fov=28, exposure=1.28, dark=0.62, glow=0.9)
    f.add("pay", 4.6, s6, xfade=0.5)

    # 7. the order lands on the store's screen
    f.add("to-store", 3.8, lambda t, d: shots.order_travel_shot(t, d, plate="env/kitchen.jpg"),
          xfade=0.5, trans="flash")

    # 8. the store prepares it
    f.add("prepare", 3.4, lambda t, d: moment_shot("env/kitchen.jpg", t, d, dark=0.80,
                                                   zoom=(1.03, 1.14), glow=0.30,
                                                   glow_cy=0.45, glow_r=0.5),
          xfade=0.5)

    # 9. live tracking: status ladder + the map + the rider on the street
    f.add("track-app", 3.2, lambda t, d: shots.track_shot(t, d, plate="env/street.jpg",
                                                          dark=0.72), xfade=0.5)
    f.add("track-3d", 4.2, lambda t, d: shots.route_street(
        t, d, street_w=5.6, offset=(0.8, 2.4, 7.4), look_off=(-0.2, 1.05, -4.0),
        fov=36), xfade=0.55, trans="light")

    # 10. hand-over and the brand close
    f.add("handover", 3.6, lambda t, d: shots.handoff_shot(t, d, dark=0.90), xfade=0.5)
    f.add("end", 3.6, endcard, xfade=0.6, trans="flash")
    return f


# ==========================================================================
#  VIDEO 2 — RESTAURANT & STORE
# ==========================================================================
def build_merchant():
    f = film.Film("02-stores")

    # 1. the shop at night, then its SIYMON panel lights up
    f.add("store-open", 4.6, lambda t, d: moment_shot("env/store.jpg", t, d, dark=0.78,
                                                      zoom=(1.02, 1.12), glow=0.35,
                                                      glow_cy=0.5), start=0.0, xfade=0.5)
    def panel_shot(t, d):
        img = screen("screen_merchant_products", toggle=1.0, add=0.0)
        return scenes.card_shot("env/store.jpg", t, d, img, tilt=5.0, dark=0.66, glow=0.7)
    f.add("panel", 3.9, panel_shot, xfade=0.5, trans="light")

    # 2. product management: add one, switch another off
    f.add("products", 6.2, lambda t, d: shots.products_shot(t, d, plate="env/store.jpg",
                                                           dark=0.62), xfade=0.55)

    # 3. a new order arrives (notification) and is reviewed
    f.add("new-order", 5.2, lambda t, d: shots.order_arrives_shot(t, d,
                                                                  plate="env/kitchen.jpg",
                                                                  dark=0.72), xfade=0.5)

    # 4. preparation: the order moves down the rail as it is cooked/packed
    f.add("prep-rail", 4.4, lambda t, d: shots.status_rail(t, d, plate="env/kitchen.jpg",
                                                           dark=0.62), xfade=0.5)
    f.add("packing", 4.4, lambda t, d: moment_shot("env/store.jpg", t, d, dark=0.82,
                                                   zoom=(1.05, 1.16), pan=(0.45, 0.5),
                                                   pan_to=(0.5, 0.5), glow=0.28,
                                                   glow_cy=0.55), xfade=0.5)

    # 5. the driver appears on the 3D map and arrives at the pickup point
    f.add("driver-map", 5.0, lambda t, d: shots.hexgrid_shot(t, d, radius=3, glow=0.30,
                                                            cam_a=(10, 17, 16),
                                                            cam_b=(6.5, 12.5, 19),
                                                            look=(0, 0, 0.8)),
          xfade=0.55)

    # 6. hand-over to the rider with the pickup code check
    f.add("handoff", 4.8, lambda t, d: shots.code_shot(t, d, plate="people/handoff.jpg",
                                                       entered_max=6, ok_at=0.55,
                                                       dark=0.86, blur=14), xfade=0.5)

    # 7. brand close on the shop
    f.add("end", 3.9, lambda t, d: endcard(t, d), xfade=0.6)
    return f


# ==========================================================================
#  VIDEO 3 — DRIVER
# ==========================================================================
def build_driver():
    f = film.Film("03-driver")

    def accept_shot(t, d):
        """The accepted task moves into the active list."""
        p = film.clamp(t / max(d, 1e-6))
        img = screen("screen_driver_home", online=1.0, offers=1,
                     pulse=0.0 if p < 0.35 else 0.9 * (1 - p))
        return scenes.card_shot("env/street.jpg", t, d, img, tilt=-3.0, dark=0.74, glow=0.8)


    # 1. the rider, then the app
    f.add("rider-hero", 3.2, lambda t, d: moment_shot("people/rider.jpg", t, d, dark=0.92,
                                                      zoom=(1.03, 1.14), glow=0.45,
                                                      glow_cy=0.42, glow_r=0.5),
          start=0.0, xfade=0.5, trans="light")

    # the rider opens the driver app and goes online
    def s1(t, d):
        on = film.smooth(film.span(t, d * 0.42, d * 0.62))
        return phone_shot("env/street.jpg", t, d,
                          screen("screen_driver_home", online=on, offers=1, pulse=0.0),
                          rot_y_deg=-11, fov=29, exposure=1.3, dark=0.68, glow=0.9)
    f.add("go-online", 4.4, s1, xfade=0.5, trans="light")

    # 2. position + the 500 m hex cells that find the nearest rider
    f.add("hex-field", 4.2, lambda t, d: shots.hexgrid_shot(t, d, radius=3, glow=0.38,
                                                           cam_a=(11, 18, 15),
                                                           cam_b=(6.0, 12.0, 20),
                                                           look=(0, 0, 0.8)),
          xfade=0.55, trans="wipe")

    # 3. an offer appears: pickup, drop-off, distance, payout
    f.add("offer", 4.0, lambda t, d: shots.offer_shot(t, d, dark=0.74), xfade=0.5, trans="light")

    # 4. accept -> the task moves to the active list
    f.add("accept", 2.6, accept_shot, xfade=0.45, trans="flash")

    # 5. ride to the store
    f.add("to-store", 4.6, lambda t, d: shots.route_street(
        t, d, path=((0, 0, 9), (0, 0, 1), (2.4, 0, -6), (2.4, 0, -14)),
        offset=(0.6, 2.5, 7.4), look_off=(0.0, 1.05, -4.0), street_w=5.6,
        fov=36), xfade=0.55)

    # 6. pickup verified with the store's code
    f.add("pickup", 4.2, lambda t, d: shots.code_shot(t, d, plate="people/handoff.jpg",
                                                      entered_max=6, ok_at=0.60,
                                                      dark=0.88, blur=12), xfade=0.5)

    # 7. to the customer
    f.add("to-customer", 4.8, lambda t, d: shots.route_street(
        t, d, path=((0, 0, 8), (2.2, 0, 1), (2.2, 0, -7), (0, 0, -14)),
        offset=(-1.3, 2.5, 7.0), look_off=(0.1, 1.05, -3.8), seed=9,
        street_w=5.6, fov=36), xfade=0.55)

    # 8. delivery confirmed with the customer's code
    def s8(t, d):
        img = shots.code_shot(t, d, plate="env/door.jpg", entered_max=6, ok_at=0.58,
                              dark=0.86, blur=10)
        return img
    f.add("delivery", 4.2, s8, xfade=0.5)

    # 9. earnings land in the wallet
    f.add("earnings", 4.6, lambda t, d: shots.earnings_shot(t, d, dark=0.70), xfade=0.55)

    # 10. ride away into the city, brand close
    f.add("ride-away", 3.4, lambda t, d: shots.route_street(
        t, d, path=((0, 0, 6), (1.6, 0, -2), (1.6, 0, -12)),
        offset=(1.2, 2.4, 6.6), look_off=(-0.1, 1.1, -4.4), seed=13,
        street_w=5.6, fov=36, show_rider=True), xfade=0.5)
    f.add("end", 3.6, endcard, xfade=0.6)
    return f


BUILDERS = {
    "customer": build_customer,
    "merchant": build_merchant,
    "driver": build_driver,
}
