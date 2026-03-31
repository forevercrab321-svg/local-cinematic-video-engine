#!/usr/bin/env python3
"""
debug.py — FFmpeg filter chain debugger

Tests FFmpeg commands in 4 progressive levels to isolate exactly
which filter or parameter causes failure.

Run standalone:
    python3 debug.py [--image PATH] [--preset NAME] [--out DIR]
"""

import argparse
import subprocess
import sys
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from preset import load_preset, Preset


# =============================================================================
# REPORT
# =============================================================================

class DebugReport:
    def __init__(self, shot_id: str, out_dir: Path):
        self.shot_id = shot_id
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.tests: list[dict] = []
        self.ffmpeg_version: str = ""

    def save_cmd(self, name: str, cmd: list) -> Path:
        """Save the full command to a .cmd.txt file."""
        path = self.out_dir / f"{self.shot_id}_{name}.cmd.txt"
        path.write_text(" ".join(cmd))
        return path

    def save_stderr(self, name: str, stderr: str) -> Path:
        """Save full stderr to a .stderr.log file."""
        path = self.out_dir / f"{self.shot_id}_{name}.stderr.log"
        path.write_text(stderr)
        return path

    def run_test(
        self,
        name: str,
        cmd: list,
        description: str = "",
    ) -> dict:
        """
        Run a single FFmpeg test.
        Returns dict with pass/fail, returncode, stderr excerpt, cmd path, stderr path.
        """
        cmd_path = self.save_cmd(name, cmd)
        stderr_path: Path = None

        print(f"\n  [{name}] {description}")
        print(f"  CMD: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        stderr_path = self.save_stderr(name, result.stderr)

        # Determine pass/fail
        passed = result.returncode == 0

        # Show return code + last meaningful lines of stderr (skip version header)
        stderr_lines = result.stderr.strip().split("\n")
        # Skip lines that are just version/config/library output
        skip_prefixes = (
            "ffmpeg version", "  built ", "  configuration:",
            "  libav", "  h264 ",
        )
        error_lines = [
            l for l in stderr_lines
            if l.strip() and not any(l.startswith(p) for p in skip_prefixes)
        ]
        last_30_meaningful = error_lines[-30:] if error_lines else stderr_lines[-30:]

        print(f"  RC: {result.returncode} | {'✅ PASS' if passed else '❌ FAIL'}")
        if not passed:
            n = len(error_lines)
            print(f"  STDERR ({len(stderr_lines)} total, {n} meaningful, showing last {len(last_30_meaningful)}):")
            for line in last_30_meaningful:
                print(f"    {line}")

        test_result = {
            "name": name,
            "description": description,
            "pass": passed,
            "returncode": result.returncode,
            "cmd_file": str(cmd_path),
            "stderr_file": str(stderr_path),
            "cmd": " ".join(cmd),
        }
        self.tests.append(test_result)
        return test_result

    def print_summary(self):
        print("\n" + "=" * 65)
        print(f"  DEBUG REPORT: {self.shot_id}")
        print("=" * 65)

        for t in self.tests:
            icon = "✅" if t["pass"] else "❌"
            print(f"  {icon} [{t['returncode']:3d}] {t['name']:30s} — {t['description']}")

        print("=" * 65)

        # Find first failure
        first_fail = next((t for t in self.tests if not t["pass"]), None)
        if first_fail:
            print(f"\n  🔍 FIRST FAILURE: {first_fail['name']}")
            print(f"     Command file: {first_fail['cmd_file']}")
            print(f"     Stderr file:  {first_fail['stderr_file']}")

            # Try to identify which argument failed
            stderr = Path(first_fail["stderr_file"]).read_text()
            lines = stderr.strip().split("\n")
            error_lines = [l for l in lines if any(
                k in l.lower() for k in ["error", "invalid", "no such", "failed", "cannot"]
            )]
            if error_lines:
                print(f"\n  Error lines from stderr:")
                for l in error_lines[:10]:
                    print(f"    {l}")

        print(f"\n  Log directory: {self.out_dir}")
        print("=" * 65)

        return first_fail


# =============================================================================
# DEBUG SCENE (run one shot through all levels)
# =============================================================================

def debug_shot(
    image_path: str,
    preset_name: str = None,
    shot_id: str = "debug",
    out_dir: str = None,
    duration: float = 4.0,
    fps: int = 24,
    width: int = 1080,
    height: int = 1920,
) -> DebugReport:
    """
    Run a 4-level progressive debug of a shot.

    Level A: Minimal — single image → 4s MP4, no filters
    Level B: + scale/fps — just aspect ratio fix
    Level C: + zoompan — the critical camera motion filter
    Level D: Full cinematic — zoompan + all effects
    """

    image_path = Path(image_path)
    if out_dir:
        out_dir = Path(out_dir)
    else:
        out_dir = SKILL_DIR / "demo_output"

    report = DebugReport(shot_id, out_dir)

    # Get FFmpeg version once
    ffmpeg = "/usr/local/bin/ffmpeg"
    r = subprocess.run([ffmpeg, "-version"], capture_output=True, text=True)
    report.ffmpeg_version = r.stdout.split("\n")[0]
    print(f"FFmpeg: {report.ffmpeg_version}")

    print(f"Image: {image_path}")
    print(f"Preset: {preset_name}")

    # Extract first frame if input is video (ffmpeg -loop only works on images)
    input_path = Path(image_path)
    is_video = input_path.suffix.lower() in (".mp4", ".mov", ".avi", ".mkv", ".webm")
    tmp_frame: Optional[Path] = None

    if is_video:
        tmp_frame = Path(tempfile.gettempdir()) / f"debug_frame_{os.getpid()}.jpg"
        extr = subprocess.run([
            ffmpeg, "-y", "-i", str(input_path),
            "-vframes", "1", "-q:v", "2", str(tmp_frame)
        ], capture_output=True, text=True, timeout=30)
        if extr.returncode != 0 or not tmp_frame.exists():
            print(f"❌ Frame extraction failed: {extr.stderr[-150:]}")
            return report
        actual_input = tmp_frame
        print(f"  Extracted first frame from {input_path.name} → {tmp_frame}")
    else:
        actual_input = input_path

    print()
    preset: Preset = None
    if preset_name:
        try:
            preset = load_preset(preset_name)
            print(f"✅ Preset loaded: {preset.name} | {preset.duration}s | {preset.fps}fps")
            print(f"   move: {preset.move()} | easing: {preset.easing()}")
            print(f"   zoom: {preset.zoom_start} → {preset.zoom_end}")
            print(f"   timing: hold_start={preset.hold_start_dur}s | move={preset.move_start}s→{preset.move_end}s | hold_end={preset.hold_end_dur}s")
            print(f"   motion: micro_shake={preset.micro_shake} | breath={preset.breathing}")
            duration = preset.duration
            fps = preset.fps
        except FileNotFoundError as e:
            print(f"❌ Preset load failed: {e}")
            from preset import list_presets
            print(f"   Available: {', '.join(list_presets())}")

    print()

    # === LEVEL A: Minimal baseline ===
    # Just copy image to 4s video, no filters at all
    out_a = out_dir / f"{shot_id}_A_minimal.mp4"
    cmd_a = [
        ffmpeg, "-y",
        "-loop", "1",
        "-i", str(actual_input),
        "-t", str(duration),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
        "-r", str(fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",
        str(out_a),
    ]
    report.run_test(
        "A_minimal",
        cmd_a,
        f"Baseline: scale+crop only, no zoompan, no motion",
    )

    # === LEVEL B: Add FPS + slightly more complex ===
    out_b = out_dir / f"{shot_id}_B_scale_fps.mp4"
    cmd_b = [
        ffmpeg, "-y",
        "-loop", "1",
        "-i", str(actual_input),
        "-t", str(duration),
        "-vf", (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"fps={fps}"
        ),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",
        str(out_b),
    ]
    report.run_test(
        "B_scale_fps",
        cmd_b,
        f"scale + crop + fps — verify aspect ratio and framerate",
    )

    # === LEVEL C: Add zoompan ===
    # zoompan needs pre-scaled input.
    # zoompan format: zoompan=z='expr':x='expr':y='expr':d=1:fps=N:s=WxH
    out_c = out_dir / f"{shot_id}_C_zoompan.mp4"
    pre_w = int(width * 1.35)
    pre_h = int(height * 1.35)

    cmd_c = [
        ffmpeg, "-y",
        "-loop", "1",
        "-i", str(actual_input),
        "-t", str(duration),
        "-vf", (
            f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
            f"crop={pre_w}:{pre_h},"
            f"zoompan="
            f"z='1.0':"
            f"x='iw/2-(iw/zoom)/2':"
            f"y='ih/2-(ih/zoom)/2':"
            f"d=1:"
            f"fps={fps}:"
            f"s={width}x{height}"
        ),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",
        str(out_c),
    ]
    report.run_test(
        "C_zoompan_static",
        cmd_c,
        f"zoompan with static z=1.0 — test zoompan filter chain",
    )

    # === LEVEL D: zoompan with dynamic z expression ===
    if preset and preset.zoom_end != 1.0:
        out_d = out_dir / f"{shot_id}_D_zoompan_dynamic.mp4"
        z_end = preset.zoom_end
        z_expr = f"if(lt(t,{duration-0.5}),1.0,{z_end})"

        cmd_d = [
            ffmpeg, "-y",
            "-loop", "1",
            "-i", str(actual_input),
            "-t", str(duration),
            "-vf", (
                f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
                f"crop={pre_w}:{pre_h},"
                f"zoompan="
                f"z='{z_expr}':"
                f"x='iw/2-(iw/zoom)/2':"
                f"y='ih/2-(ih/zoom)/2':"
                f"d=1:"
                f"fps={fps}:"
                f"s={width}x{height}"
            ),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "fast",
            "-crf", "18",
            str(out_d),
        ]
        report.run_test(
            "D_zoompan_dynamic",
            cmd_d,
            f"zoompan with dynamic z='{z_expr[:40]}...' — test time-based zoom",
        )

    # === LEVEL E: Full cinematic (PIL-based, using motion.py) ===
    # Test the actual pipeline
    out_e = out_dir / f"{shot_id}_E_cinematic.mp4"

    if preset:
        from motion import MotionRenderer
        renderer = MotionRenderer(ffmpeg_path=ffmpeg)

        # Run motion.py directly
        result = renderer.render(
            input_image_path=str(image_path),
            output_path=str(out_e),
            preset=preset,
            fps=fps,
            target_w=width,
            target_h=height,
            verbose=True,
        )

        # Record result as a test
        report.tests.append({
            "name": "E_cinematic_PIL",
            "description": f"PIL per-frame motion ({preset.name}) → FFmpeg encode",
            "pass": result["status"] == "success",
            "returncode": 0 if result["status"] == "success" else 1,
            "cmd_file": str(out_e),
            "stderr_file": str(out_e.with_suffix(".log")),
            "result": result,
        })

        if result["status"] == "success":
            print(f"\n  [E_cinematic_PIL] ✅ PASS — {result.get('file_size_mb')}MB | {result.get('render_time_sec')}s")
        else:
            print(f"\n  [E_cinematic_PIL] ❌ FAIL — {result.get('error', '?')}")

    # Cleanup
    if tmp_frame and tmp_frame.exists():
        try:
            tmp_frame.unlink()
        except Exception:
            pass

    return report


# =============================================================================
# ISOLATE BROKEN FILTER
# =============================================================================

def isolate_filter(
    image_path: str,
    filter_string: str,
    shot_id: str = "isolate",
    out_dir: str = None,
    duration: float = 3.0,
    fps: int = 24,
    width: int = 1080,
    height: int = 1920,
) -> dict:
    """
    Test a specific filter string and report exactly what fails.
    """
    ffmpeg = "/usr/local/bin/ffmpeg"
    out_dir = Path(out_dir) if out_dir else (SKILL_DIR / "demo_output")
    out_dir.mkdir(parents=True, exist_ok=True)

    output = out_dir / f"{shot_id}_isolate.mp4"
    cmd = [
        ffmpeg, "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-t", str(duration),
        "-vf", filter_string,
        "-r", str(fps),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",
        str(output),
    ]

    print(f"\n  Testing filter chain:")
    print(f"  {filter_string[:200]}")
    print(f"  CMD: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    # Save artifacts
    cmd_file = out_dir / f"{shot_id}_isolate.cmd.txt"
    stderr_file = out_dir / f"{shot_id}_isolate.stderr.log"
    cmd_file.write_text(" ".join(cmd))
    stderr_file.write_text(result.stderr)

    print(f"  RC: {result.returncode} | {'✅ PASS' if result.returncode == 0 else '❌ FAIL'}")
    if result.returncode != 0:
        print(f"  STDERR ({len(result.stderr.splitlines())} lines, last 20):")
        for line in result.stderr.strip().split("\n")[-20:]:
            print(f"    {line}")

    return {
        "returncode": result.returncode,
        "passed": result.returncode == 0,
        "cmd_file": str(cmd_file),
        "stderr_file": str(stderr_file),
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="FFmpeg filter chain debugger")
    parser.add_argument("--image", "-i", default="/tmp/test_frame.jpg",
                        help="Test image path")
    parser.add_argument("--preset", "-p", default=None,
                        help="Preset to debug")
    parser.add_argument("--shot", "-s", default="debug",
                        help="Shot ID for output files")
    parser.add_argument("--out", "-o", default=None,
                        help="Output directory")
    parser.add_argument("--duration", "-d", type=float, default=4.0)
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--filter", "-f", default=None,
                        help="Test a specific filter string")
    args = parser.parse_args()

    # Create test image if it doesn't exist
    if not Path(args.image).exists():
        print(f"Creating test image: {args.image}")
        from PIL import Image
        img = Image.new("RGB", (1080, 1920), color=(80, 80, 120))
        img.save(args.image)
        print(f"  Created {args.image}")

    if args.filter:
        # Single filter test
        result = isolate_filter(
            image_path=args.image,
            filter_string=args.filter,
            shot_id=args.shot,
            out_dir=args.out,
            duration=args.duration,
            fps=args.fps,
            width=args.width,
            height=args.height,
        )
        sys.exit(0 if result["passed"] else 1)

    # Full 4-level debug
    report = debug_shot(
        image_path=args.image,
        preset_name=args.preset,
        shot_id=args.shot,
        out_dir=args.out,
        duration=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height,
    )
    first_fail = report.print_summary()

    print()
    if not first_fail:
        print("🎉 All tests passed!")
    else:
        print(f"🔍 First failure: {first_fail['name']}")
        print(f"   Check: {first_fail['stderr_file']}")

    sys.exit(0 if not first_fail else 1)


if __name__ == "__main__":
    main()
