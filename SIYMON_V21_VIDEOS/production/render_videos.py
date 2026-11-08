#!/usr/bin/env python3
"""Build SIYMON V21 vertical silent ads from repository screenshots and still visuals.

Requires ImageMagick's `convert`, `identify`, and an FFmpeg build with libx264 + zoompan.
Intermediate frames and scene clips are written under /tmp, not the repository.
"""
from pathlib import Path
import glob, os, shutil, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'assets'
SOURCES = ASSETS / 'source-interfaces'
OUT = ROOT / 'final'
PREVIEWS = ROOT / 'previews' / 'video-previews'
W, H, FPS = 1080, 1920, 30
SCENE_SECS = 2.5
TRANSITION_FRAMES = 12  # 0.4 seconds at 30 fps

FFMPEG = os.environ.get('FFMPEG') or shutil.which('ffmpeg') or '/tmp/siymon-video-tool/node_modules/@ffmpeg-installer/linux-x64/ffmpeg'
CONVERT = shutil.which('convert') or '/usr/bin/convert'

source = {p.name: p for p in SOURCES.glob('*.jpg')}
def src(prefix):
    hits = [p for n,p in source.items() if n.startswith(prefix)]
    if len(hits) != 1:
        raise RuntimeError(f'Expected one screenshot beginning {prefix}; got {hits}')
    return hits[0]
CUSTOMER_HOME = src('Screenshot_2026-11-08-14-14-42')
CUSTOMER_SHOPS = src('Screenshot_2026-11-08-14-14-56')
CUSTOMER_NOTIFICATIONS = src('Screenshot_2026-11-08-14-15-01')
DRIVER_DASH = src('Screenshot_2026-11-08-14-15-17')
DRIVER_PROFILE = src('Screenshot_2026-11-08-14-15-27')
DRIVER_MAP = src('Screenshot_2026-11-08-14-16-18')


def run(args):
    subprocess.run([str(x) for x in args], check=True, stdout=subprocess.DEVNULL)

def base(bg, target):
    run([CONVERT, bg, '-resize', f'{W}x{H}^', '-gravity', 'center', '-extent', f'{W}x{H}',
         '-modulate', '96,94,100', '-brightness-contrast', '-2x4', target])

def rounded_screen(image, w, h, out, radius=32):
    tmp = tempfile.mktemp(suffix='.png')
    run([CONVERT, image, '-resize', f'{w}x{h}!', tmp])
    mask = tempfile.mktemp(suffix='.png')
    run([CONVERT, '-size', f'{w}x{h}', 'xc:black', '-fill', 'white', '-draw',
         f'roundrectangle 0,0 {w-1},{h-1} {radius},{radius}', mask])
    run([CONVERT, tmp, mask, '-alpha', 'off', '-compose', 'CopyOpacity', '-composite', out])
    os.unlink(tmp); os.unlink(mask)

def device(image, out, w=660):
    # A restrained unbranded black handset surround; the displayed pixels remain the real app screenshot.
    h = round(w * 2400 / 1080)
    frame_w, frame_h = w + 44, h + 76
    screen = tempfile.mktemp(suffix='.png')
    rounded_screen(image, w, h, screen, 34)
    frame = tempfile.mktemp(suffix='.png')
    run([CONVERT, '-size', f'{frame_w}x{frame_h}', 'xc:none', '-fill', '#101312',
         '-draw', f'roundrectangle 0,0 {frame_w-1},{frame_h-1} 58,58',
         '-stroke', '#48514b', '-strokewidth', '2', '-fill', 'none',
         '-draw', f'roundrectangle 1,1 {frame_w-2},{frame_h-2} 58,58',
         screen, '-geometry', '+22+38', '-composite', frame])
    # Slightly softened shadow on transparent background.
    shadow = tempfile.mktemp(suffix='.png')
    run([CONVERT, frame, '-background', 'none', '-shadow', '0x22+0+14', shadow])
    # Rebuild canvas, shadow, handset; trim shadow padding to the designed device bounds.
    # ImageMagick shadow expands bounds, so use the simple handset frame for predictable placement.
    os.replace(frame, out)
    os.unlink(screen); os.unlink(shadow)

def panel_scene(bg, screen, out, x=None, y=175, width=660):
    canvas = tempfile.mktemp(suffix='.jpg')
    base(bg, canvas)
    handset = tempfile.mktemp(suffix='.png')
    device(screen, handset, width)
    iw, ih = map(int, subprocess.check_output([shutil.which('identify') or '/usr/bin/identify', '-format', '%w %h', handset]).decode().split())
    if x is None: x = (W-iw)//2
    # soft grounding shadow behind the phone, then composite exact supplied screenshot in the device.
    shadow = tempfile.mktemp(suffix='.png')
    run([CONVERT, '-size', f'{iw+100}x{ih+100}', 'xc:none', '-fill', '#00000099',
         '-draw', f'roundrectangle 50,50 {iw+49},{ih+49} 70,70', '-blur', '0x24', shadow])
    run([CONVERT, canvas, shadow, '-geometry', f'+{x-50}+{y-28}', '-composite', handset,
         '-geometry', f'+{x}+{y}', '-composite', out])
    for p in (canvas, handset, shadow):
        if os.path.exists(p): os.unlink(p)

def studio_phone(out, screen=CUSTOMER_HOME):
    # The supplied screen is fitted over the blank screen of the generated studio phone.
    canvas = tempfile.mktemp(suffix='.jpg')
    base(ASSETS/'studio-atmosphere.jpg', canvas)
    scr = tempfile.mktemp(suffix='.png')
    rounded_screen(screen, 420, 933, scr, 28)
    run([CONVERT, canvas, scr, '-geometry', '+330+510', '-composite', out])
    os.unlink(canvas); os.unlink(scr)

def end_card(out):
    # A clean dark brand finish: no slogan, added copy, or invented wordmark.
    # The only mark is the original green SIYMON app icon cropped from the supplied UI.
    basefile, glowfile, litfile, iconfile = [tempfile.mktemp(suffix='.png') for _ in range(4)]
    run([CONVERT, '-size', f'{W}x{H}', 'xc:#020403', basefile])
    run([CONVERT, '-size', f'{W}x{H}', 'xc:none', '-fill', '#12400d',
         '-draw', f'circle {W//2},{H//2} {W//2},{H//2-280}', '-blur', '0x150', glowfile])
    run([CONVERT, basefile, glowfile, '-composite', litfile])
    run([CONVERT, ASSETS/'siymon-logo-icon.png', '-filter', 'Lanczos', '-resize', '250x250', iconfile])
    run([shutil.which('composite') or '/usr/bin/composite', '-gravity', 'center', iconfile, litfile, out])
    for p in (basefile, glowfile, litfile, iconfile): os.unlink(p)

def build_scenes():
    tmp = Path(tempfile.mkdtemp(prefix='siymon-scenes-'))
    specs = {
      '01-discover-siymon.mp4': [
        ('studio', None), ('restaurant-kitchen.jpg', 'shops'), ('moroccan-home.jpg', 'home'), ('delivery-rider.jpg', 'map'), ('end', None)],
      '02-customer-experience.mp4': [
        ('moroccan-home.jpg', None), ('moroccan-home.jpg', 'home'), ('restaurant-kitchen.jpg', 'shops'), ('moroccan-home.jpg', 'notifications'), ('end', None)],
      '03-siymon-stores.mp4': [
        ('restaurant-kitchen.jpg', None), ('restaurant-kitchen.jpg', 'shops'), ('studio', 'shops'), ('delivery-rider.jpg', 'home'), ('end', None)],
      '04-siymon-driver.mp4': [
        ('delivery-rider.jpg', None), ('delivery-rider.jpg', 'dashboard'), ('delivery-rider.jpg', 'profile'), ('delivery-rider.jpg', 'map'), ('end', None)],
    }
    screens = {'home': CUSTOMER_HOME, 'shops': CUSTOMER_SHOPS, 'notifications': CUSTOMER_NOTIFICATIONS,
               'dashboard': DRIVER_DASH, 'profile': DRIVER_PROFILE, 'map': DRIVER_MAP}
    for name, seq in specs.items():
        frames=[]
        for i,(background,screen_name) in enumerate(seq):
            p=tmp/f'{name[:-4]}-scene-{i+1:02d}.jpg'
            if background == 'end': end_card(p)
            elif background == 'studio' and screen_name is None: studio_phone(p)
            elif background == 'studio': panel_scene(ASSETS/'studio-atmosphere.jpg', screens[screen_name], p, y=170)
            elif screen_name is None: base(ASSETS/background, p)
            else: panel_scene(ASSETS/background, screens[screen_name], p, y=180)
            frames.append(p)
        yield name, frames, tmp

def render(name, scenes, tmp):
    clips=[]
    for i,im in enumerate(scenes):
        clip=tmp/f'{name[:-4]}-clip-{i:02d}.mp4'
        run([FFMPEG, '-y', '-loglevel','error', '-loop','1','-framerate',str(FPS),'-i',im,
             '-vf', "zoompan=z='min(zoom+0.00034,1.025)':d=75:s=1080x1920:fps=30,format=yuv420p",
             '-frames:v','75','-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p',
             '-r',str(FPS),'-t',str(SCENE_SECS),clip])
        clips.append(clip)
    # Twelve-frame image dissolves, based on actual last/first rendered camera frames.
    for i in range(len(clips)-1):
        a=tmp/f'trans-{i}-a.png'; b=tmp/f'trans-{i}-b.png'
        run([FFMPEG,'-y','-loglevel','error','-sseof','-0.04','-i',clips[i],'-frames:v','1',a])
        run([FFMPEG,'-y','-loglevel','error','-i',clips[i+1],'-frames:v','1',b])
        tdir=tmp/f'transition-{i}'; tdir.mkdir(exist_ok=True)
        for n in range(TRANSITION_FRAMES):
            pct=round(n*100/(TRANSITION_FRAMES-1),2)
            run([CONVERT,a,b,'-define',f'compose:args={100-pct},{pct}','-compose','blend','-composite',tdir/f'{n:03d}.jpg'])
        trans=tmp/f'{name[:-4]}-transition-{i:02d}.mp4'
        run([FFMPEG,'-y','-loglevel','error','-framerate',str(FPS),'-i',tdir/'%03d.jpg','-frames:v',str(TRANSITION_FRAMES),
             '-an','-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-r',str(FPS),trans])
        # Insert transition between consecutive scene clips.
        clips.insert(i*2+1,trans)
    listfile=tmp/f'{name[:-4]}-concat.txt'
    listfile.write_text(''.join(f"file '{c.as_posix()}'\n" for c in clips))
    dest=OUT/name
    run([FFMPEG,'-y','-loglevel','error','-f','concat','-safe','0','-i',listfile,
         '-an','-c:v','libx264','-preset','slow','-crf','20','-pix_fmt','yuv420p','-r',str(FPS),
         '-movflags','+faststart','-video_track_timescale','30000',dest])
    # A representative preview frame, never a montage.
    preview=PREVIEWS/(name.replace('.mp4','.jpg'))
    run([FFMPEG,'-y','-loglevel','error','-ss','4.0','-i',dest,'-frames:v','1','-q:v','2',preview])
    print(f'RENDERED {dest} ({dest.stat().st_size:,} bytes)')

def main():
    OUT.mkdir(parents=True,exist_ok=True); PREVIEWS.mkdir(parents=True,exist_ok=True)
    for name,scenes,tmp in build_scenes():
        render(name,scenes,tmp)
    print('Done. All outputs intentionally contain video only; no audio stream is added.')

if __name__=='__main__': main()
