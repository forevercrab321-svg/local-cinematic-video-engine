#!/usr/bin/env python3
"""
benchmark_paths.py — Benchmark three render modes:
  A. static_ffmpeg
  B. simple_zoompan_ffmpeg
  C. cinematic_pil

Produces comparison table and PRESET_ROUTING_LOCK.md.
"""
import subprocess, time, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from engine import CinematicShotEngine

INPUT = "/Users/monsterlee/.openclaw/media/inbound/file_3---5223086e-a136-4e3a-9c06-8c2363382b8b.jpg"
OUT = Path("/tmp/benchmark")
OUT.mkdir(exist_ok=True)
FFMPEG = "ffmpeg"
DUR = 5.0
FPS = 24

def probe(path):
    r = subprocess.run(
        [FFMPEG, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,r_frame_rate,duration,nb_frames",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True
    )
    if r.returncode != 0 or not r.stdout.strip():
        return {}
    parts = r.stdout.strip().split(",")
    return {
        "codec": parts[0] if len(parts) > 1 else "?",
        "w": int(parts[1]) if len(parts) > 1 else 0,
        "h": int(parts[2]) if len(parts) > 2 else 0,
        "fps": parts[3] if len(parts) > 3 else "?",
        "dur": float(parts[4]) if len(parts) > 4 else 0,
        "frames": int(parts[5]) if len(parts) > 5 else 0,
    }


def run_ffmpeg(cmd_list, out_path):
    """Run ffmpeg, return (returncode, wall_time)."""
    t0 = time.perf_counter()
    r = subprocess.run(cmd_list, capture_output=True, text=True)
    wall = time.perf_counter() - t0
    return r.returncode, wall, r.stderr


def build_scale_pad():
    return (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    )


defVf = build_scale_pad()

RESULTS = []


# ── A. static_ffmpeg ────────────────────────────────────────────────────────
print("=" * 60)
print("  A. static_ffmpeg")
out = OUT / "A_static.mp4"
cmd = [
    FFMPEG, "-y", "-loop", "1", "-i", INPUT,
    "-t", str(DUR), "-r", str(FPS),
    "-vf", defVf,
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    "-pix_fmt", "yuv420p",
    str(out)
]
rc, wall, err = run_ffmpeg(cmd, out)
info = probe(out)
sz = out.stat().st_size / 1024 / 1024 if out.exists() else 0
status = "✅" if rc == 0 else f"❌ RC={rc}"
print(f"  {status} {wall:.2f}s | {sz:.3f}MB | {info.get('w','?')}x{info.get('h','?')}")
RESULTS.append({
    "mode": "static_ffmpeg",
    "description": "Zero motion — pad + encode",
    "render_time_sec": round(wall, 2),
    "file_size_mb": round(sz, 3),
    "resolution": f"{info.get('w','?')}x{info.get('h','?')}",
    "frames": info.get("frames", "?"),
    "codec": info.get("codec", "?"),
    "rc": rc,
})


# ── B. simple_zoompan_ffmpeg (push-in) ─────────────────────────────────────
print("=" * 60)
print("  B. simple_zoompan_ffmpeg (push-in)")
out = OUT / "B_zoompan_push.mp4"
zoompan_vf = (
    "scale=1080:1920:force_original_aspect_ratio=decrease,"
    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
    "zoompan=z='min(zoom+0.001,1.12)':d=1:"
    "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',setsar=1"
)
cmd = [
    FFMPEG, "-y", "-loop", "1", "-i", INPUT,
    "-t", str(DUR), "-r", str(FPS),
    "-vf", zoompan_vf,
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    "-pix_fmt", "yuv420p",
    str(out)
]
rc, wall, err = run_ffmpeg(cmd, out)
info = probe(out)
sz = out.stat().st_size / 1024 / 1024 if out.exists() else 0
status = "✅" if rc == 0 else f"❌ RC={rc} {err[-80:]}"
print(f"  {status} {wall:.2f}s | {sz:.3f}MB | {info.get('w','?')}x{info.get('h','?')}")
RESULTS.append({
    "mode": "simple_zoompan_ffmpeg",
    "description": "Monotonic push-in using zoom recursive var",
    "render_time_sec": round(wall, 2),
    "file_size_mb": round(sz, 3),
    "resolution": f"{info.get('w','?')}x{info.get('h','?')}",
    "frames": info.get("frames", "?"),
    "codec": info.get("codec", "?"),
    "rc": rc,
    "variant": "push-in 1.0→1.12",
})


# ── B2. simple_zoompan_ffmpeg (pull-out) ────────────────────────────────────
print("=" * 60)
print("  B2. simple_zoompan_ffmpeg (pull-out)")
out = OUT / "B2_zoompan_pull.mp4"
zoompan_pull = (
    "scale=1080:1920:force_original_aspect_ratio=decrease,"
    "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
    "zoompan=z='max(zoom-0.001,0.90)':d=1:"
    "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',setsar=1"
)
cmd = [
    FFMPEG, "-y", "-loop", "1", "-i", INPUT,
    "-t", str(DUR), "-r", str(FPS),
    "-vf", zoompan_pull,
    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
    "-pix_fmt", "yuv420p",
    str(out)
]
rc, wall, err = run_ffmpeg(cmd, out)
info = probe(out)
sz = out.stat().st_size / 1024 / 1024 if out.exists() else 0
status = "✅" if rc == 0 else f"❌ RC={rc}"
print(f"  {status} {wall:.2f}s | {sz:.3f}MB | {info.get('w','?')}x{info.get('h','?')}")
RESULTS.append({
    "mode": "simple_zoompan_ffmpeg",
    "description": "Monotonic pull-out using zoom recursive var",
    "render_time_sec": round(wall, 2),
    "file_size_mb": round(sz, 3),
    "resolution": f"{info.get('w','?')}x{info.get('h','?')}",
    "frames": info.get("frames", "?"),
    "codec": info.get("codec", "?"),
    "rc": rc,
    "variant": "pull-out 1.0→0.90",
})


# ── C. cinematic_pil ─────────────────────────────────────────────────────────
print("=" * 60)
print("  C. cinematic_pil (suspense_push_r3_r6)")
out = OUT / "C_cinematic_pil.mp4"
t0 = time.perf_counter()
engine = CinematicShotEngine()
r_pil = engine.render(
    input_image=INPUT, output_path=str(out),
    preset_name="suspense_push_r3_r6",
    duration=DUR, fps=FPS, width=1080, height=1920
)
pil_wall = time.perf_counter() - t0
pil_info = probe(out)
pil_sz = out.stat().st_size / 1024 / 1024 if out.exists() else 0
print(f"  ✅ {pil_wall:.2f}s | {pil_sz:.3f}MB | {pil_info.get('w','?')}x{pil_info.get('h','?')}")
RESULTS.append({
    "mode": "cinematic_pil",
    "description": "PIL per-frame — hold + easing + effects + breathing",
    "render_time_sec": round(pil_wall, 2),
    "file_size_mb": round(pil_sz, 3),
    "resolution": f"{pil_info.get('w','?')}x{pil_info.get('h','?')}",
    "frames": pil_info.get("frames", "?"),
    "codec": pil_info.get("codec", "?"),
    "rc": 0,
})


# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=" * 65)
print("  BENCHMARK — THREE RENDER MODES")
print("=" * 65)
print(f"  {'MODE':28s} {'TIME':7s} {'SIZE':8s} {'RES':12s} {'FRAMES':7s}")
print(f"  {'-'*28:28s} {'-'*7:7s} {'-'*8:8s} {'-'*12:12s} {'-'*7:7s}")
for res in RESULTS:
    if res["rc"] == 0:
        print(f"  {res['mode']:28s} {res['render_time_sec']:.2f}s   "
              f"{res['file_size_mb']:.3f}MB "
              f"{res['resolution']:12s} {res['frames']}")
    else:
        print(f"  {res['mode']:28s}  FAIL")

# Time comparison
static_time = next((r["render_time_sec"] for r in RESULTS
                    if r["mode"] == "static_ffmpeg" and r["rc"] == 0), None)
zoompan_push = next((r["render_time_sec"] for r in RESULTS
                     if r["mode"] == "simple_zoompan_ffmpeg"
                     and r.get("variant") == "push-in 1.0→1.12" and r["rc"] == 0), None)
pil_time = next((r["render_time_sec"] for r in RESULTS
                 if r["mode"] == "cinematic_pil" and r["rc"] == 0), None)

print()
if all(v is not None for v in [static_time, zoompan_push, pil_time]):
    print(f"  Time ratio (zoompan vs PIL):   {zoompan_push/pil_time:.2f}x faster")
    print(f"  Time ratio (static vs PIL):   {static_time/pil_time:.2f}x faster")
    print(f"  PIL overhead vs zoompan:       {pil_time - zoompan_push:.2f}s extra")

with open(OUT / "benchmark_results.json", "w") as f:
    json.dump(RESULTS, f, indent=2)

print(f"\nSaved: {OUT/'benchmark_results.json'}")
