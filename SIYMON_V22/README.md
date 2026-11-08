# SIYMON V22 — three official cinematic explainer videos

Three separate, silent, 9:16 vertical films (1080 × 1920, 30 fps, H.264 + AAC)
built from the real SIYMON application, not from a generic delivery template.

| # | Film | Story | Length | Size |
|---|---|---|---|---|
| 1 | [`final/01-customer-experience.mp4`](final/01-customer-experience.mp4) | discover → choose → address → pay → store prepares → live tracking → hand-over | 43.2 s | 25.4 MB |
| 2 | [`final/02-restaurants-and-stores.mp4`](final/02-restaurants-and-stores.mp4) | shop → product & stock management → new order → accept → prepare → pick-up code → rider takes it | 38.2 s | 23.8 MB |
| 3 | [`final/03-driver-experience.mp4`](final/03-driver-experience.mp4) | rider → online → 500 m hex dispatch → offer → accept → ride → pickup code → ride → delivery code → earnings → close | 42.1 s | 33.6 MB |

All three: 1080 × 1920, 30 fps, H.264 High, AAC 44.1 kHz stereo (≈191 kb/s).
Contact sheets and stills: [`previews/stills/`](previews/stills/).

**No speech, no voice-over, no dialogue, no on-screen text, no titles, no
captions.** Copy inside the recreated app screens is drawn as neutral skeleton
bars, exactly so that nothing can be read. Meaning is carried by 3D motion,
iconography, colour and sound design only.

---

## Why these films look like SIYMON

Every screen, label position, icon, flow and constraint was read from the
project in `siymon_v19_driver_docs_toggle.zip` before a single frame was drawn —
see [`production/PROJECT-AUDIT.md`](production/PROJECT-AUDIT.md).

* **Brand**: palette taken verbatim from `public/brand.css`
  (`#0F0F0F`, `#202020`, `#5DD62C`, `#337418`, `#F8F8F8`, `#A8A8A8`).
* **Logo**: not redrawn. The real `public/icons/icon-192.png` is vectorised
  (4× upscale → threshold → contour → smoothing) and re-rendered at any size, so
  the mark is identical to the app icon and stays razor-sharp.
* **App surfaces**: `public/index.html`, `public/app.js`, `public/orders/`,
  `public/restaurant/`, `public/store/`, `public/driver/`, `public/wallet/` and
  the supplied device screenshots all inform the recreated UI: dark home with
  store covers and category chips, green pill CTA, bottom nav, merchant
  Orders/Products tabs with availability switches, driver online toggle and
  earnings cards, wallet balance hero with a ledger.

## Honesty constraints taken from the code

| Reality in the project | What the films show |
|---|---|
| `lib/payment-methods.js`: Stripe **not integrated** | never shown; card payment appears only as a **TPE terminal at hand-over** |
| COD + TPE + manual transfer (verified by a supervisor) | cash-on-delivery selected by default; the TPE row carries an "at delivery" badge; the transfer row carries a *pending verification* warning |
| `lib/order-state.js`: `new → admin_accepted → restaurant_ready → accepted → picked_up → on_the_way → delivered → done` | the whole arc, in this order, nothing skipped |
| `lib/verify-codes.js`: 6-digit **pickup** stage for the store, **delivery** stage for the customer, driver never receives either | two code screens, each typed on the driver's phone |
| `lib/hexcell.js` + `lib/dispatch-service.js`: real **500 m** hex cells, 3 rings ≈ 1.3 km around the pickup | the aerial dispatch field is built from genuine pointy-top hex geometry |
| `lib/driver-earnings.js`: earning = delivery fee or base + road-km | wallet balance rises after the delivery is confirmed, never before |

Nothing that the system does not do is shown as done.

---

## How it is made

A small purpose-built renderer (`production/siymon3d.py`, numpy + PIL) gives the
films one coherent 3D language instead of a pile of stock footage:

* real perspective cameras with orbit/tracking moves, near-plane clipping,
  z-buffer, per-vertex lighting, emissive materials, additive glow and a film
  grade (bloom, highlight roll-off, vignette, grain);
* the same phone model, logo, palette, lens and transition set in all three
  films, so they read as one campaign;
* photographic plates (product, kitchen, store, street, doorway, rider) sit
  behind the 3D so every frame has real depth, while the app UI is rendered
  through a projective screen quad on the phone itself — not pasted on.

Audio is an original synthesized electronic score (104 BPM, A minor:
sub-bass, detuned pads, arpeggio, kick/hats) with UI sound design — whooshes on
cuts, impacts on reveals, a two-note chime for each verification and a shimmer
when the wallet balance rises. It is generated in `production/score.py`, so it is
royalty-free and timed exactly to the picture.

### Rebuild

```bash
python3 -m venv .venv && .venv/bin/pip install pillow numpy opencv-python-headless imageio-ffmpeg
cd production
python3 make_assets.py          # vectorise the logo from the real app icon
python3 render.py               # all three films -> ../final/
python3 render.py customer      # one film
N=12 python3 render.py driver --preview   # contact sheet frames
```

Rendering is CPU-only and parallel; expect roughly 8–12 minutes per film on two
cores (≈1–1.5 frames/s). Frames are written to `/tmp/siymon_frames/<film>/` and
the run is resumable: existing PNGs are skipped, so an interrupted film restarts
where it stopped. `WORKERS` (default 2) sets the frame-worker count.
