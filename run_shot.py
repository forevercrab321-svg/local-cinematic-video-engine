#!/usr/bin/env python3
"""
run_shot.py — CLI for CinematicShotEngine

Usage:
    python3 run_shot.py --image KEYFRAME.png --preset suspense_push
    python3 run_shot.py --image KEYFRAME.png --preset comedy_snap --duration 3.5
    python3 run_shot.py --batch scene_manifests/IN_THE_GROUP_CHAT.json
    python3 run_shot.py --list-presets
    python3 run_shot.py --check
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from engine import CinematicShotEngine
from preset import load_preset, Preset


# =============================================================================
# SYSTEM CHECK
# =============================================================================

def system_check():
    """Verify ffmpeg + dependencies and display input contract."""
    print("🎬 CinematicShotEngine — System Check")
    print("=" * 40)
    print()
    print("  INPUT CONTRACT (strict):")
    print("  ✅ Supported:  .jpg .jpeg .png .webp (keyframe images)")
    print("  ❌ Rejected:   .mp4 .mov .mkv .avi (video files)")
    print()
    print("  OUTPUT: cinematic shot video (.mp4, H.264, 24fps, 9:16)")
    print()
    print("=" * 40)

    # ffmpeg
    for path in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
        if Path(path).exists():
            r = subprocess.run([path, "-version"], capture_output=True, text=True)
            version = r.stdout.split("\n")[0]
            print(f"  ✅ ffmpeg: {path}")
            print(f"         {version}")
            # Check libx264
            r2 = subprocess.run([path, "-encoders"], capture_output=True, text=True)
            has_libx264 = "libx264" in r2.stdout
            print(f"  {'✅' if has_libx264 else '❌'} libx264: {'available' if has_libx264 else 'MISSING'}")
            break
    else:
        print("  ❌ ffmpeg: NOT FOUND")
        return False

    # Python
    print(f"  ✅ Python: {sys.version.split()[0]}")

    # Presets
    preset_dir = SKILL_DIR / "presets"
    presets = list(preset_dir.glob("*.json"))
    preset_names = sorted(p.stem for p in presets if p.stem != "PRESET_SPEC")
    print(f"  ✅ Presets: {', '.join(preset_names)}")

    # Test engine import
    try:
        from engine import CinematicShotEngine
        print(f"  ✅ engine.py: loadable")
    except Exception as e:
        print(f"  ❌ engine.py: {e}")
        return False

    return True


# =============================================================================
# PRESET LIST
# =============================================================================

def list_presets():
    """List all available presets with descriptions."""
    print("\n📋 Available Presets")
    print("=" * 55)
    preset_dir = SKILL_DIR / "presets"
    for path in sorted(preset_dir.glob("*.json")):
        if path.stem == "PRESET_SPEC":
            continue
        try:
            d = json.loads(path.read_text())
            desc = d.get("description", "—")
            dur = d.get("duration_sec", "?")
            move = d.get("camera", {}).get("move", "?")
            print(f"  {path.stem:25s} {dur}s | {move:12s} | {desc}")
        except Exception as e:
            print(f"  {path.stem}: ERROR — {e}")
    print()


# =============================================================================
# RENDER SINGLE SHOT
# =============================================================================

def render(
    image: str,
    preset_name: str,
    output: str = None,
    duration: float = None,
    fps: int = 24,
    ratio: str = "9:16",
    quality: str = "high",
    camera: str = None,
    intensity: float = 1.0,
    shot_id: str = "shot",
):
    """Render a single shot."""

    # Resolve image
    img_path = Path(image)
    if not img_path.exists():
        print(f"❌ Image not found: {image}")
        return None

    # Determine output path
    if output:
        out_path = Path(output)
        if out_path.is_dir():
            out_path.mkdir(exist_ok=True)
            out_path = out_path / f"{shot_id}_{preset_name}.mp4"
    else:
        out_dir = img_path.parent / "cinematic_renders"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"{shot_id}_{preset_name}.mp4"

    # Load preset for duration if not specified
    if duration is None:
        try:
            p = load_preset(preset_name)
            duration = p.duration
        except:
            duration = 5.0

    # Resolution
    ratio_wh = {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:3": (1440, 1080),
        "3:4": (1080, 1440),
    }
    w, h = ratio_wh.get(ratio, (1080, 1920))
    scale_map = {"ultra": 1.0, "high": 1.0, "medium": 0.667, "low": 0.5}
    scale = scale_map.get(quality, 1.0)
    width, height = int(w * scale), int(h * scale)

    print(f"\n🎬 Rendering: {img_path.name}")
    print(f"   Preset: {preset_name} | {width}×{height} | {duration}s")
    if camera:
        print(f"   Camera override: {camera} (intensity={intensity})")

    engine = CinematicShotEngine(fps=fps)
    result = engine.render(
        input_image=str(img_path),
        output_path=str(out_path),
        preset_name=preset_name,
        camera_intensity=intensity,
        duration=duration,
        fps=fps,
        width=width,
        height=height,
        camera_override=camera,
    )

    # Write manifest
    if result["status"] == "success":
        manifest_path = out_path.with_suffix(".shot_manifest.json")
        manifest = {
            "shot_id": shot_id,
            "preset": preset_name,
            "camera_override": camera,
            "camera_intensity": intensity,
            "duration": result["duration"],
            "fps": result.get("fps", fps),
            "resolution": result.get("resolution", f"{width}×{height}"),
            "file_size_mb": result["file_size_mb"],
            "render_time_sec": result["render_time_sec"],
            "output_file": str(out_path),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))

        print(f"\n✅ Output: {out_path}")
        print(f"   Manifest: {manifest_path}")
    else:
        print(f"\n❌ Failed: {result.get('error', 'unknown')}")

    return result


# =============================================================================
# BATCH RENDER
# =============================================================================

def batch_render(manifest_path: str, output_dir: str = None, stop_on_error: bool = False):
    """Run batch.py on a scene manifest."""
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {manifest_path}")
        return

    # Import batch renderer
    batch_path = SKILL_DIR / "batch.py"
    if not batch_path.exists():
        print(f"❌ batch.py not found")
        return

    import subprocess
    cmd = [sys.executable, str(batch_path), str(manifest_path)]
    if output_dir:
        cmd.extend(["--out", output_dir])
    if stop_on_error:
        cmd.append("--stop-on-error")

    result = subprocess.run(cmd)
    sys.exit(result.returncode)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Cinematic shot video renderer")
    parser.add_argument("--image", "-i", help="Keyframe image path")
    parser.add_argument("--preset", "-p", default="suspense_push",
                        help="Shot preset name (default: suspense_push)")
    parser.add_argument("--output", "-o", help="Output MP4 path")
    parser.add_argument("--duration", "-d", type=float, help="Duration in seconds")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--ratio", default="9:16",
                        help="Aspect ratio: 9:16, 16:9, 1:1, 4:3, 3:4")
    parser.add_argument("--quality", "-q", default="high",
                        choices=["ultra", "high", "medium", "low"])
    parser.add_argument("--camera", "-c", help="Camera override (push_in, shake, static, etc.)")
    parser.add_argument("--intensity", type=float, default=1.0)
    parser.add_argument("--shot", help="Shot ID for manifest")
    parser.add_argument("--batch", help="Batch render a scene manifest")
    parser.add_argument("--list-presets", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.list_presets:
        list_presets()
        return

    if args.check:
        ok = system_check()
        sys.exit(0 if ok else 1)
        return

    if args.batch:
        batch_render(args.batch, args.output)
        return

    if not args.image:
        print("❌ --image required. Use --check for system info, --list-presets to see available.")
        sys.exit(1)

    shot_id = args.shot or Path(args.image).stem

    result = render(
        image=args.image,
        preset_name=args.preset,
        output=args.output,
        duration=args.duration,
        fps=args.fps,
        ratio=args.ratio,
        quality=args.quality,
        camera=args.camera,
        intensity=args.intensity,
        shot_id=shot_id,
    )

    # Handle video rejection
    if result.get("status") == "failed" and result.get("input_type") == "video_rejected":
        print(f"\n❌ INPUT ERROR: Video file rejected.")
        print(f"   {result['error']}")
        print(f"\n   Hint: local_cinematic_video_engine is an IMAGE-TO-VIDEO engine.")
        print(f"   Supported input: keyframe image (.jpg, .png, .webp)")
        print(f"   To convert video to images, use local_video_ingest skill first.")
        return

    # Print debug command files if available
    from pathlib import Path
    out = Path(args.output or (Path(args.image).parent / "cinematic_renders"))
    if out.is_dir():
        cmd_files = list(out.glob(f"{shot_id}*.cmd.txt"))
        if cmd_files:
            print(f"\n  FFmpeg commands saved to:")
            for f in cmd_files:
                print(f"    {f}")


if __name__ == "__main__":
    main()
