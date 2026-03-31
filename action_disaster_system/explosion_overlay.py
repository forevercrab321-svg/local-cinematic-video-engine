"""
explosion_overlay.py — Procedural explosion effect overlaid on zoompan base.

Layers:
  1. Flash frame — white/orange flash at explosion
  2. Fire texture — procedural plasma fire
  3. Smoke cloud — rising dark smoke
  4. Screen shake — frame displacement
  5. Orange grade — warm cast
  6. Vignette — edge darkening
"""

import sys, json, math, random, tempfile, shutil
import numpy as np
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance

INPUT_IMAGE = "/Users/monsterlee/.openclaw/media/inbound/file_3---5223086e-a136-4e3a-9c06-8c2363382b8b.jpg"


def _fire_texture(W, H, intensity):
    """Generate procedural fire texture. Returns PIL RGB image."""
    fire_colors = np.array(
        [0,0,0, 80,10,0, 200,50,0, 255,120,0, 255,200,50, 255,255,200],
        dtype=np.uint8
    ).reshape(6, 3)
    xx, yy = np.meshgrid(
        np.linspace(0, 4*math.pi, W),
        np.linspace(0, 4*math.pi, H)
    )
    t = random.uniform(0, 2*math.pi)
    plasma = (
        np.sin(xx*1.5+t)*0.3 + np.sin(yy*1.2-t*0.7)*0.3 +
        np.sin((xx+yy)*1.0+t*0.5)*0.2 +
        np.sin(np.sqrt((xx-2)**2+(yy-2)**2)*0.2)*0.2
    )
    plasma = (plasma - plasma.min()) / (plasma.max() - plasma.min() + 1e-9)
    vert = np.linspace(1.0, 0.0, H)[:, None]
    plasma = plasma * vert * intensity
    idx = (plasma * 5).clip(0, 5).astype(int)
    arr = fire_colors[idx]
    return Image.fromarray(arr, mode="RGB")


def _smoke_texture(W, H, intensity):
    """Generate procedural smoke. Returns PIL RGBA image."""
    xx, yy = np.meshgrid(
        np.linspace(0, 3*math.pi, W),
        np.linspace(0, 3*math.pi, H)
    )
    t = random.uniform(0, 2*math.pi)
    smoke = (
        np.sin(xx*0.8+t*0.3)*0.4 + np.sin(yy*0.6-t*0.2)*0.4 +
        np.sin((xx*0.5+yy*0.5)+t*0.4)*0.2 + 0.5
    ).clip(0, 1) * intensity
    smoke_img = Image.fromarray((smoke*180).astype(np.uint8), mode="L")
    smoke_img = smoke_img.filter(ImageFilter.GaussianBlur(radius=6))
    smoke_arr = np.array(smoke_img)
    alpha = smoke_arr.astype(np.uint8)
    rgba = np.zeros((H, W, 4), dtype=np.uint8)
    rgba[:, :, 0] = 60
    rgba[:, :, 1] = 60
    rgba[:, :, 2] = 65
    rgba[:, :, 3] = alpha
    return Image.fromarray(rgba, mode="RGBA")


def composite_explosion_frame(base: Image.Image, frame_idx: int,
                               total_frames: int,
                               start_pct: float = 0.0,
                               peak_pct: float = 0.3,
                               fire_int: float = 0.8,
                               smoke_int: float = 0.6) -> Image.Image:
    """Overlay explosion on one base frame. Returns RGB PIL image."""
    W, H = base.size
    t = frame_idx / max(1, total_frames - 1)

    if t < start_pct:
        intensity = 0.0
    elif t < peak_pct:
        intensity = ((t - start_pct) / (peak_pct - start_pct)) ** 0.5
    else:
        intensity = math.exp(-3 * (t - peak_pct) / (1.0 - peak_pct + 1e-9))

    if intensity < 0.01:
        return base.convert("RGB")

    frame = base.convert("RGBA")
    result = frame

    # 1. Orange color wash
    if intensity > 0.1:
        ov = Image.new("RGBA", (W, H), (255, 100, 0, int(60*intensity)))
        result = Image.alpha_composite(result, ov)

    # 2. Fire at bottom-center
    if intensity > 0.2:
        fW, fH = int(W*0.8), int(H*0.6)
        fire = _fire_texture(fW, fH, intensity * fire_int)
        fx = (W - fW)//2 + random.randint(-W//8, W//8)
        fy = H - fH + int(H*0.1*intensity)
        fire_rgba = fire.copy()
        fa = np.array(fire_rgba)
        fa[:, :, 3] = (fa[:,:,:3].mean(axis=2) * 0.7 * 255 / 255).clip(0,255).astype(np.uint8)
        fire_rgba = Image.fromarray(fa, mode="RGBA")
        result = Image.alpha_composite(result, fire_rgba)

    # 3. Smoke rising
    if intensity > 0.15:
        sW, sH = W, int(H*0.65)
        smoke = _smoke_texture(sW, sH, intensity * smoke_int)
        sy = H - sH
        sx = random.randint(-W//10, W//10)
        smoke_np = np.array(smoke).astype(float)
        frame_np = np.array(result).astype(float)
        a = (smoke_np[:,:,3] / 255.0 * intensity).clip(0,1)
        for c in range(3):
            frame_np[:,:,c] = (frame_np[:,:,c]*(1-a) + smoke_np[:,:,c]*a).clip(0,255)
        result = Image.fromarray(frame_np.astype(np.uint8), mode="RGBA")

    # 4. Screen shake at high intensity
    if intensity > 0.4:
        shk = int(8*intensity)
        dx = random.randint(-shk, shk)
        dy = random.randint(-shk, shk)
        result = result.transform((W, H), Image.EXTENT,
                                  (dx, dy, W+dx, H+dy), Image.BICUBIC)

    # 5. Brightness flash at peak
    if intensity > 0.6:
        flash_str = (intensity - 0.6) / 0.4
        flash = Image.new("RGBA", (W, H), (255, 255, 200, int(100*flash_str)))
        result = Image.alpha_composite(result, flash)

    # 6. Vignette
    vig = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(vig)
    iW = int(W*(1 - 0.3*intensity))
    iH = int(H*(1 - 0.3*intensity))
    d.ellipse([(W-iW)//2, (H-iH)//2, (W+iW)//2, (H+iH)//2], fill=0)
    vnp = np.array(vig) / 255.0
    rnp = np.array(result.convert("RGB")).astype(float)
    rnp = (rnp * vnp[:,:,None]).clip(0,255).astype(np.uint8)
    return Image.fromarray(rnp, mode="RGB")


def apply_overlay(input_video: str, output_video: str,
                  start_pct: float = 0.0, peak_pct: float = 0.3,
                  fire_int: float = 0.8, smoke_int: float = 0.6) -> dict:
    """Apply explosion overlay to a video. Returns status dict."""
    tmp = Path(tempfile.mkdtemp(prefix="expl_"))
    fr_dir = tmp / "frames"; fr_dir.mkdir()
    out_fr = tmp / "out_frames"; out_fr.mkdir()

    try:
        # Probe video
        info = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "stream=width,height,r_frame_rate,nb_frames", "-of", "json", input_video
        ], capture_output=True, text=True, timeout=10)
        st = json.loads(info.stdout)["streams"][0]
        W, H = st["width"], st["height"]
        fps = eval(st["r_frame_rate"])
        nb = int(st.get("nb_frames", 0) or fps*6)

        # Extract frames
        subprocess.run([
            "ffmpeg", "-y", "-i", input_video,
            "-q:v", "2", str(fr_dir/"f%04d.png")
        ], capture_output=True, timeout=60)

        frames = sorted(fr_dir.glob("f*.png"))
        for i, fp in enumerate(frames):
            base = Image.open(fp).convert("RGBA")
            proc = composite_explosion_frame(
                base, i, nb, start_pct, peak_pct, fire_int, smoke_int
            )
            proc.save(out_fr / f"p{fp.name}", "PNG")

        # Encode
        rc = subprocess.run([
            "ffmpeg", "-y", "-framerate", str(fps),
            "-i", str(out_fr/"pframe_%04d.png"),
            "-vf", f"scale={W}:{H}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", "-crf", "18",
            output_video,
        ], capture_output=True, timeout=60).returncode == 0

        return {"status": "success" if rc else "failed",
                "frames": nb, "output": output_video}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        inp = sys.argv[1]
        out = sys.argv[2] if len(sys.argv) > 2 else inp.replace(".mp4", "_expl.mp4")
        r = apply_overlay(inp, out)
        print(f"Done: {r}")
