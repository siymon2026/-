# Production and quality-control notes

## Pipeline and creative treatment

- Initial environment check found no configured AI video-generation service/API and no FFmpeg executable. No credentials, payment, or external generation service were assumed.
- Four original photorealistic still environments were generated for studio, Moroccan home, restaurant kitchen, and rider/street scenes. These are single images, not video footage.
- The supplied customer/driver screenshots are presented as image pixels in modest black handset frames; the screens themselves were not redesigned or relabelled. App colors are preserved. Grade is restrained: darker charcoal shadows and controlled saturation, with the existing SIYMON green as the accent.
- Rendered locally with ImageMagick and an FFmpeg 4.x build (H.264/libx264, `zoompan`, 30 fps). Cross-dissolves are pre-rendered as 12-frame image blends because the available FFmpeg build did not include the `xfade` filter. Outputs contain no audio stream.
- `production/render_videos.py` is the repeatable render script. Its temporary scene clips and transition images are created outside this package. The FFmpeg binary was installed into a temporary environment and is not bundled or committed.

## QC performed

- Confirmed all four MP4s decode through to end without FFmpeg errors.
- Confirmed each file reports one H.264 video stream only; no audio/subtitle/data stream is present.
- Confirmed each output is 1080 × 1920, square pixels, 9:16 display aspect, 30 fps and 14.10 s.
- Confirmed four preview JPEGs exist in `previews/video-previews/`.
- Visually reviewed the representative frames and final icon card. No added captions, titles, watermarks, or new type overlays are used. The only visible interface text is baked into the real supplied screenshots.
- All four outputs use the same phone-frame treatment, green accent, dark grade, gentle push-ins and dissolve cadence.

## Material production limitations

The repository does not contain a separate SIYMON Store manager interface, checkout/confirmation screen, standalone map asset, or actual live-action footage. Consequently:

- Video 03 uses a genuine **customer-facing store listing**, not a Store employee/admin app. No manager UI was invented.
- The order-progress beat uses the supplied customer notifications/status screen, not a checkout/confirmation screen.
- The route/map view is the authentic map embedded in the driver app screenshot.
- The requested restaurant preparation, human-use, motorcycle, streets, and delivery scenes are represented by generated stills with subtle animated camera movement. There is no actual moving camera footage, animated riding, nor a real handover scene. Images do not depict verified SIYMON staff, customers, merchants, or routes.
- The repository contained a SIYMON icon within the supplied customer UI, but no separate logo file; the ending mark is cropped from that source.

These limitations are disclosed rather than simulated with invented product interfaces or presented as live footage. The delivered files are actual rendered MP4 video files, but their movement is an editorial still-image treatment rather than native AI-generated motion video.
