# SIYMON V21 — silent vertical video collection

Four rendered MP4 ads are in [`final/`](final/). Each is an independent, silent, 9:16 H.264 video at 1080 × 1920 and 30 fps. The videos use subtle Ken Burns camera motion and short image dissolves; they are not AI-generated moving footage.

## Videos

| Deliverable | Duration | Preview |
|---|---:|---|
| [01 — Discover SIYMON](final/01-discover-siymon.mp4) | 14.10 s | [JPG](previews/video-previews/01-discover-siymon.jpg) |
| [02 — Customer Experience](final/02-customer-experience.mp4) | 14.10 s | [JPG](previews/video-previews/02-customer-experience.jpg) |
| [03 — SIYMON Stores](final/03-siymon-stores.mp4) | 14.10 s | [JPG](previews/video-previews/03-siymon-stores.jpg) |
| [04 — SIYMON Driver & Smart Delivery](final/04-siymon-driver.mp4) | 14.10 s | [JPG](previews/video-previews/04-siymon-driver.jpg) |

## Production

- The supplied customer and driver screens are shown as provided, not recreated. The final SIYMON mark is a crop of the original green app icon from the customer interface.
- Generated photorealistic stills add the studio, home, kitchen and rider environments. The app screenshots and all production resources are kept in [`assets/`](assets/).
- Shot intent and exact source mapping: [`production/video-production-script.md`](production/video-production-script.md) and [`production/asset-inventory.md`](production/asset-inventory.md).
- Build and quality-control notes: [`production/production-notes.md`](production/production-notes.md).
- Re-render with Python 3, ImageMagick, and FFmpeg (`libx264`, `zoompan` filter):

  ```bash
  python3 production/render_videos.py
  ```

  `FFMPEG=/path/to/ffmpeg` may be set if FFmpeg is not on `PATH`.

## Important source limitations

The repository supplied customer-web and driver-app screenshots, but no separate SIYMON Store manager UI, customer checkout/confirmation screen, standalone map asset, or live action footage. Accordingly, Video 03 presents the genuine customer-facing restaurant listing alongside the kitchen visual rather than inventing a store dashboard. The route/map and driver screens in Video 04 are the genuine supplied driver screenshots. Restaurant food, home and rider scenes are generated stills, not footage of actual SIYMON merchants, employees, customers, routes, or deliveries. See the production notes for the complete scope and QC record.

All four deliverables are video-only MP4s with no audio stream. No title cards, captions, subtitles, added copy or watermark are present; text visible within an original supplied application screen is part of that authentic interface.
