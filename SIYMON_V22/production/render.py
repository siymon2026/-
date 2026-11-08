"""
Render the three SIYMON explainers and mux the score.

  python3 render.py              # all three
  python3 render.py customer     # one film
  python3 render.py customer --preview   # 12 still previews per film
"""
from __future__ import annotations

import os
import sys
import math
import time
import subprocess
import multiprocessing as mp

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FPS = 30
W, H = 1080, 1920
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "final")
TMP = "/tmp/siymon_frames"


# --------------------------------------------------------------------------
def _render_worker(key, fps, worker_id, nworkers, chunk):
    """Render every n-th block of frames; skips blocks already on disk (resumable)."""
    import films
    film = films.BUILDERS[key]()
    n = int(math.ceil(film.duration * fps))
    blocks = list(range(0, n, chunk))
    mine = blocks[worker_id::nworkers]
    outdir = f"{TMP}/{key}"
    os.makedirs(outdir, exist_ok=True)
    t0 = time.time()
    done = 0
    for b0 in mine:
        todo = [i for i in range(b0, min(b0 + chunk, n))
                if not os.path.exists(f"{outdir}/{i:05d}.png")]
        if not todo:
            continue
        for i in todo:
            t = i / fps
            try:
                img = film.frame(min(t, film.duration - 1e-3))
            except Exception as e:  # keep the pipeline alive, report loudly
                print(f"[{key} frame {i}] ERROR {type(e).__name__} {e}", flush=True)
                img = Image.new("RGB", (W, H), (8, 9, 10))
            img.save(f"{outdir}/{i:05d}.png", compress_level=1)
            done += 1
        el = time.time() - t0
        print(f"  {key}[{worker_id}]: {done} new frames, {el:.0f}s "
              f"({done / max(el, 1e-6):.2f} f/s)", flush=True)


def render_film_procs(key, workers=2, chunk=24, fps=FPS):
    import films
    film = films.BUILDERS[key]()
    n = int(math.ceil(film.duration * fps))
    os.makedirs(f"{TMP}/{key}", exist_ok=True)
    procs = [mp.Process(target=_render_worker, args=(key, fps, w, workers, chunk))
             for w in range(workers)]
    t0 = time.time()
    for p in procs:
        p.start()
    for p in procs:
        p.join()
    have = len([f for f in os.listdir(f"{TMP}/{key}") if f.endswith(".png")])
    print(f"  {key}: {have}/{n} frames in {time.time()-t0:.0f}s", flush=True)
    return n, film.duration


def render_film(key, workers=4, chunk=45, fps=FPS):
    import films
    film = films.BUILDERS[key]()
    dur = film.duration
    n = int(math.ceil(dur * fps))
    os.makedirs(f"{TMP}/{key}", exist_ok=True)
    idxs = list(range(n))
    jobs = [(key, idxs[i:i + chunk], fps) for i in range(0, n, chunk)]
    t0 = time.time()
    done = 0
    with mp.get_context("fork").Pool(workers) as pool:
        for ridx, imgs in pool.imap_unordered(_render_chunk, jobs):
            for i, im in zip(ridx, imgs):
                im.save(f"{TMP}/{key}/{i:05d}.png", compress_level=1)
            done += len(ridx)
            el = time.time() - t0
            print(f"  {key}: {done}/{n} frames  {el:.0f}s  ({done/max(el,1e-6):.2f} f/s)",
                  flush=True)
    return n, dur


def encode(key, fps=FPS):
    import films
    film = films.BUILDERS[key]()
    dur = film.duration
    silent = f"{TMP}/{key}-video.mp4"
    cmd = [
        FFMPEG, "-y", "-framerate", str(fps), "-i", f"{TMP}/{key}/%05d.png",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.2",
        "-movflags", "+faststart", "-an", silent,
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return silent


def mux(key, silent, out_path, fps=FPS):
    import films, score
    film = films.BUILDERS[key]()
    wav = f"{TMP}/{key}-score.wav"
    score.build(key, film, wav)
    if score.SILENT:
        subprocess.run([FFMPEG, "-y", "-i", silent, "-c", "copy", "-an", out_path],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    subprocess.run([FFMPEG, "-y", "-i", silent, "-i", wav,
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", out_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def previews(key, n=12):
    import films
    film = films.BUILDERS[key]()
    os.makedirs("previews", exist_ok=True)
    for i in range(n):
        t = film.duration * (i / (n - 1)) * 0.985
        img = film.frame(t)
        img.resize((270, 480), Image.LANCZOS).save(f"previews/{key}-{i:02d}.jpg", quality=88)


try:
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG = "ffmpeg"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    want = args[0] if args else None
    keys = [want] if want else ["customer", "merchant", "driver"]
    names = {"customer": "01-customer-experience", "merchant": "02-restaurants-and-stores",
             "driver": "03-driver-experience"}
    if "--preview" in sys.argv:
        for k in keys:
            previews(k, int(os.environ.get("N", "12")))
            print("previews", k)
        sys.exit(0)
    os.makedirs(OUT, exist_ok=True)
    for k in keys:
        print(f"=== {k} ===", flush=True)
        t0 = time.time()
        n, dur = render_film_procs(k, workers=int(os.environ.get("WORKERS", "2")))
        silent = encode(k)
        out = f"{OUT}/{names[k]}.mp4"
        mux(k, silent, out)
        print(f"{out}  {dur:.2f}s  {os.path.getsize(out)/1e6:.1f} MB  "
              f"({time.time()-t0:.0f}s)", flush=True)
