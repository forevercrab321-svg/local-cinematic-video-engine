#!/usr/bin/env python3
"""
Preset isolation debugger — suspense_push preset

Tests 4 progressive layers to isolate exactly which part of the
preset chain causes failure.

A. base camera only (zoom, no easing/motion)
B. base camera + motion (zoom + micro_shake/breathing)
C. base camera + motion + lighting (adds effects)
D. full preset with timing (hold windows, easing)

Each stage outputs:
  demo_output/suspense_{stage}_*.cmd.txt   — full ffmpeg command
  demo_output/suspense_{stage}_*.stderr.log — full stderr
  demo_output/suspense_{stage}_*.mp4      — output if pass
  RC: N | PASS/FAIL
"""

import subprocess
import shutil
import os
import math
import tempfile
import hashlib
from pathlib import Path
from PIL import Image

SKILL_DIR = Path(__file__).parent
DEMO = SKILL_DIR / "demo_output"
DEMO.mkdir(exist_ok=True)

FFMPEG = "/usr/local/bin/ffmpeg"
IMAGE = str(SKILL_DIR / "maya_keyframe.jpg")

DURATION = 5.0
FPS = 24
W, H = 1080, 1920
TOTAL_FRAMES = int(DURATION * FPS)


def save_cmd(stage: str, cmd: list) -> Path:
    p = DEMO / f"suspense_{stage}.cmd.txt"
    p.write_text(" ".join(cmd))
    return p

def save_stderr(stage: str, stderr: str) -> Path:
    p = DEMO / f"suspense_{stage}.stderr.log"
    p.write_text(stderr)
    return p

def run_stage(stage: str, cmd: list, desc: str) -> dict:
    print(f"\n  [{stage}] {desc}")
    print(f"  CMD: {' '.join(cmd[:8])}...")
    cmd_path = save_cmd(stage, cmd)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    stderr_path = save_stderr(stage, result.stderr)

    passed = result.returncode == 0
    output_path = DEMO / f"suspense_{stage}.mp4"

    # Filter meaningful stderr lines
    lines = result.stderr.strip().split("\n")
    skip = ("ffmpeg version", "  built ", "  configuration:",
            "  libav", "  h264 ", "  libsw")
    meaningful = [l for l in lines if l.strip() and not any(l.startswith(s) for s in skip)]
    last_20 = meaningful[-20:] if meaningful else lines[-20:]

    print(f"  RC: {result.returncode} | {'✅ PASS' if passed else '❌ FAIL'}")
    if not passed:
        print(f"  FAILING EXPRESSION (last 20 meaningful lines):")
        for l in last_20:
            print(f"    {l}")
        print(f"  Command: {cmd_path}")
        print(f"  Stderr:  {stderr_path}")

    return {
        "stage": stage, "desc": desc,
        "passed": passed, "rc": result.returncode,
        "cmd_file": str(cmd_path),
        "stderr_file": str(stderr_path),
        "output": str(output_path) if passed else None,
    }


# =============================================================================
# BUILD THE 4 STAGES
# =============================================================================

# Reference preset values (from suspense_push.json)
zoom_start = 1.0
zoom_end = 1.12
easing = "ease_in_out"
hold_start = 1.2
move_start = 1.2
move_end = 4.0
hold_end = 1.0
micro_shake = 0.006
breathing = 0.005
flicker = 0.02
vignette_pulse = 0.06
glow_drift = 0.03

# For PIL approach — generate a single frame with specific zoom applied
def pil_frame(frame_idx: int, zoom: float, shake_x: float, shake_y: float,
               target_w: int, target_h: int) -> Path:
    """Generate one frame with PIL."""
    img = Image.open(IMAGE).convert("RGB")
    src_w, src_h = img.size

    zoomed_w = src_w * zoom
    zoomed_h = src_h * zoom

    offset_x = shake_x
    offset_y = shake_y

    crop_x = (zoomed_w - target_w) / 2 - offset_x
    crop_y = (zoomed_h - target_h) / 2 - offset_y
    crop_x = max(0, min(crop_x, zoomed_w - target_w))
    crop_y = max(0, min(crop_y, zoomed_h - target_h))

    img_zoomed = img.resize((int(zoomed_w), int(zoomed_h)), Image.BICUBIC)
    frame = img_zoomed.crop((
        int(crop_x), int(crop_y),
        int(crop_x) + target_w, int(crop_y) + target_h
    ))
    out = Path(tempfile.gettempdir()) / f"iso_frame_{frame_idx:05d}.jpg"
    frame.save(out, "JPEG", quality=95)
    return out


# =============================================================================
# STAGE A: BASE CAMERA ONLY
# PIL: linear zoom from zoom_start to zoom_end over entire duration, NO easing
# =============================================================================

def stage_a():
    """Linear zoom only. No hold, no easing, no motion effects."""
    print("\n" + "="*60)
    print("STAGE A: BASE CAMERA ONLY")
    print("  - Linear zoom 1.0 → 1.12 over 5s")
    print("  - No hold, no easing, no micro_shake, no breathing")
    print("="*60)

    import math, tempfile
    tmp_dir = tempfile.mkdtemp(prefix="suspense_A_")

    # Linear zoom: delta/frame = (1.12 - 1.0) / (5*24) = 0.12/120 = 0.001
    delta = (zoom_end - zoom_start) / TOTAL_FRAMES
    current_zoom = zoom_start

    import hashlib
    for i in range(TOTAL_FRAMES):
        # Linear zoom (no easing, no motion)
        current_zoom = zoom_start + (zoom_end - zoom_start) * (i / TOTAL_FRAMES)
        # No shake, no breathing
        frame_path = pil_frame(i, current_zoom, 0.0, 0.0, W, H)
        shutil.move(str(frame_path), os.path.join(tmp_dir, f"frame_{i:05d}.jpg"))

    output = DEMO / "suspense_A.mp4"
    cmd = [
        FFMPEG, "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(tmp_dir, "frame_%05d.jpg"),
        "-t", str(DURATION),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "18", "-movflags", "+faststart",
        str(output),
    ]
    result = run_stage("A_base", cmd, "Linear zoom only, no easing/motion")

    shutil.rmtree(tmp_dir, ignore_errors=True)
    return result


# =============================================================================
# STAGE B: BASE CAMERA + MOTION (micro_shake + breathing)
# PIL: add micro_shake and breathing on top of linear zoom
# =============================================================================

def stage_b():
    """Linear zoom + micro_shake + breathing. No hold, no easing."""
    print("\n" + "="*60)
    print("STAGE B: BASE CAMERA + MOTION")
    print("  - Linear zoom 1.0 → 1.12")
    print("  + micro_shake=0.006")
    print("  + breathing=0.005 (sin wave)")
    print("  - No hold windows, no easing")
    print("="*60)

    import math, tempfile
    tmp_dir = tempfile.mkdtemp(prefix="suspense_B_")

    delta = (zoom_end - zoom_start) / TOTAL_FRAMES
    current_zoom = zoom_start
    time_sec = 0

    for i in range(TOTAL_FRAMES):
        time_sec = i / FPS
        # Linear zoom
        current_zoom = zoom_start + (zoom_end - zoom_start) * (i / TOTAL_FRAMES)
        # Breathing
        breath_zoom = breathing * math.sin(2 * math.pi * 0.35 * time_sec)
        # Micro shake (deterministic per frame)
        seed_x = int(hashlib.md5(f"{i}_x".encode()).hexdigest()[:8], 16)
        seed_y = int(hashlib.md5(f"{i}_y".encode()).hexdigest()[:8], 16)
        rng_x = ((seed_x % 1000) / 500.0) - 1.0
        rng_y = ((seed_y % 1000) / 500.0) - 1.0
        shake_x = rng_x * micro_shake * 1920
        shake_y = rng_y * micro_shake * 1920

        frame_path = pil_frame(i, current_zoom + breath_zoom, shake_x, shake_y, W, H)
        shutil.move(str(frame_path), os.path.join(tmp_dir, f"frame_{i:05d}.jpg"))

    output = DEMO / "suspense_B.mp4"
    cmd = [
        FFMPEG, "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(tmp_dir, "frame_%05d.jpg"),
        "-t", str(DURATION),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "18", "-movflags", "+faststart",
        str(output),
    ]
    result = run_stage("B_motion", cmd, "Linear zoom + micro_shake + breathing")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return result


# =============================================================================
# STAGE C: BASE CAMERA + MOTION + LIGHTING
# PIL: same as B + FFmpeg lighting effects (vignette_pulse, flicker, glow)
# =============================================================================

def stage_c():
    """Zoom + motion + lighting effects. No hold, no easing."""
    print("\n" + "="*60)
    print("STAGE C: BASE CAMERA + MOTION + LIGHTING")
    print("  - Linear zoom 1.0 → 1.12")
    print("  + micro_shake=0.006 + breathing=0.005")
    print("  + flicker=0.02, vignette_pulse=0.06, glow_drift=0.03")
    print("  - No hold windows, no easing")
    print("="*60)

    import math, tempfile
    tmp_dir = tempfile.mkdtemp(prefix="suspense_C_")

    delta = (zoom_end - zoom_start) / TOTAL_FRAMES
    time_sec = 0

    for i in range(TOTAL_FRAMES):
        time_sec = i / FPS
        current_zoom = zoom_start + (zoom_end - zoom_start) * (i / TOTAL_FRAMES)
        breath_zoom = breathing * math.sin(2 * math.pi * 0.35 * time_sec)

        seed_x = int(hashlib.md5(f"{i}_x".encode()).hexdigest()[:8], 16)
        seed_y = int(hashlib.md5(f"{i}_y".encode()).hexdigest()[:8], 16)
        rng_x = ((seed_x % 1000) / 500.0) - 1.0
        rng_y = ((seed_y % 1000) / 500.0) - 1.0
        shake_x = rng_x * micro_shake * 1920
        shake_y = rng_y * micro_shake * 1920

        frame_path = pil_frame(i, current_zoom + breath_zoom, shake_x, shake_y, W, H)
        shutil.move(str(frame_path), os.path.join(tmp_dir, f"frame_{i:05d}.jpg"))

    output = DEMO / "suspense_C.mp4"

    # Lighting effects chain
    # vignette_pulse: eq brightness modulation
    # flicker: eq brightness micro-variation
    # glow_drift: eq contrast boost
    vf_parts = []

    # Flicker: brightness oscillates at ~4Hz
    if flicker > 0:
        vf_parts.append(f"eq=brightness={flicker}*sin(t*25):contrast=1.0")

    # Glow drift: subtle contrast boost
    if glow_drift > 0:
        vf_parts.append(f"eq=contrast={1+glow_drift}:brightness={glow_drift*0.5}")

    # Vignette pulse: vignette filter with variable strength
    # Using lenscorrection or curves for vignette
    # FFmpeg vignette: vignette=angle=PI/3:mode=forward
    # Pulsing vignette via lut filter... complex.
    # Simplify: apply fixed vignette + brightness pulse separately
    if vignette_pulse > 0:
        # Fixed vignette + brightness pulse
        freq_v = 0.4
        # eq for brightness pulse
        vf_parts.append(
            f"eq=brightness={vignette_pulse}*sin(t*{freq_v}*{2*3.14159}):contrast=1.0"
        )

    vf = ",".join(vf_parts) if vf_parts else None

    cmd = [
        FFMPEG, "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(tmp_dir, "frame_%05d.jpg"),
    ]
    if vf:
        cmd += ["-vf", vf]
    cmd += [
        "-t", str(DURATION),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "18", "-movflags", "+faststart",
        str(output),
    ]

    full_cmd = cmd[:]
    if vf:
        full_cmd = cmd[:cmd.index("-vf")] + ["-vf", vf] + cmd[cmd.index("-vf")+2:]
    # Rebuild cleanly
    cmd_clean = [
        FFMPEG, "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(tmp_dir, "frame_%05d.jpg"),
    ]
    if vf:
        cmd_clean += ["-vf", vf]
    cmd_clean += [
        "-t", str(DURATION),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "18", "-movflags", "+faststart",
        str(output),
    ]

    result = run_stage("C_lighting", cmd_clean,
                        f"Linear zoom + motion + lighting ({vf_parts})")
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return result


# =============================================================================
# STAGE D: FULL PRESET — with timing (hold windows + easing)
# PIL: easing curve + hold windows + motion effects
# =============================================================================

def stage_d():
    """Full suspense_push preset with timing (hold windows + easing)."""
    print("\n" + "="*60)
    print("STAGE D: FULL PRESET WITH TIMING")
    print("  - Timing: hold 1.2s → move 1.2-4.0s → hold 1.0s")
    print("  - Easing: ease_in_out")
    print("  - Zoom: 1.0 → 1.12 (at ease_in_out)")
    print("  + micro_shake + breathing")
    print("  + lighting effects")
    print("="*60)

    import math, tempfile
    tmp_dir = tempfile.mkdtemp(prefix="suspense_D_")

    def ease_in_out(t):
        return t * t * (3 - 2 * t)

    def get_zoom_and_motion(frame_idx: int):
        t = frame_idx / TOTAL_FRAMES
        time_sec = t * DURATION

        # Hold window
        if t < hold_start / DURATION:
            zoom = zoom_start
            pan_x_n, pan_y_n = 0.5, 0.5
        elif t > move_end / DURATION:
            zoom = zoom_end
            pan_x_n, pan_y_n = 0.5, 0.5
        else:
            # During move: ease_in_out
            local_t = (t - hold_start/DURATION) / ((move_end - hold_start) / DURATION)
            eased = ease_in_out(local_t)
            zoom = zoom_start + (zoom_end - zoom_start) * eased
            pan_x_n, pan_y_n = 0.5, 0.5

        # Breathing
        if breathing > 0:
            zoom += breathing * math.sin(2 * math.pi * 0.35 * time_sec)

        # Micro shake
        if micro_shake > 0:
            seed_x = int(hashlib.md5(f"{frame_idx}_x".encode()).hexdigest()[:8], 16)
            seed_y = int(hashlib.md5(f"{frame_idx}_y".encode()).hexdigest()[:8], 16)
            rng_x = ((seed_x % 1000) / 500.0) - 1.0
            rng_y = ((seed_y % 1000) / 500.0) - 1.0
            shake_x = rng_x * micro_shake * 1920
            shake_y = rng_y * micro_shake * 1920
        else:
            shake_x, shake_y = 0.0, 0.0

        return zoom, pan_x_n, pan_y_n, shake_x, shake_y

    # Generate frames with hold + easing
    for i in range(TOTAL_FRAMES):
        zoom, pan_x_n, pan_y_n, shake_x, shake_y = get_zoom_and_motion(i)
        frame_path = pil_frame(i, zoom, shake_x, shake_y, W, H)
        shutil.move(str(frame_path), os.path.join(tmp_dir, f"frame_{i:05d}.jpg"))

    output = DEMO / "suspense_D.mp4"

    # Lighting effects
    vf_parts = []
    if flicker > 0:
        vf_parts.append(f"eq=brightness={flicker}*sin(t*25):contrast=1.0")
    if glow_drift > 0:
        vf_parts.append(f"eq=contrast={1+glow_drift}:brightness={glow_drift*0.5}")
    if vignette_pulse > 0:
        freq_v = 0.4
        vf_parts.append(
            f"eq=brightness={vignette_pulse}*sin(t*{freq_v}*{2*3.14159}):contrast=1.0"
        )
    vf = ",".join(vf_parts) if vf_parts else None

    cmd = [
        FFMPEG, "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(tmp_dir, "frame_%05d.jpg"),
    ]
    if vf:
        cmd += ["-vf", vf]
    cmd += [
        "-t", str(DURATION),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-preset", "fast", "-crf", "18", "-movflags", "+faststart",
        str(output),
    ]

    desc = f"Full preset + timing ({'hold/ease' if True else 'linear'})"
    if vf_parts:
        desc += f" + lighting({len(vf_parts)} effects)"
    result = run_stage("D_full", cmd, desc)
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return result


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("="*60)
    print("PRESET ISOLATION DEBUGGER — suspense_push")
    print("="*60)
    print(f"  FFmpeg: {FFMPEG}")
    print(f"  Image:  {IMAGE}")
    print(f"  Output: {DEMO}")
    print(f"  Duration: {DURATION}s @ {FPS}fps = {TOTAL_FRAMES} frames")
    print()

    results = []

    # Stage A
    r_a = stage_a()
    results.append(r_a)
    if not r_a["passed"]:
        print("\n" + "="*60)
        print("🔍 STAGE A FAILED — stopping further tests")
        print("="*60)
        return results

    # Stage B
    r_b = stage_b()
    results.append(r_b)
    if not r_b["passed"]:
        print("\n" + "="*60)
        print("🔍 STAGE B FAILED — motion layer broken")
        print("="*60)
        return results

    # Stage C
    r_c = stage_c()
    results.append(r_c)
    if not r_c["passed"]:
        print("\n" + "="*60)
        print("🔍 STAGE C FAILED — lighting layer broken")
        print("="*60)
        return results

    # Stage D
    r_d = stage_d()
    results.append(r_d)

    # Final report
    print("\n" + "="*60)
    print("FINAL REPORT — STAGE RESULTS")
    print("="*60)
    for r in results:
        icon = "✅" if r["passed"] else "❌"
        print(f"  {icon} Stage {r['stage']:4s} | RC={r['rc']:3d} | {r['desc']}")
    print("="*60)

    return results


if __name__ == "__main__":
    main()
