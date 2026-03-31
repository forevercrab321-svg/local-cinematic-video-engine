"""
engine.py — Cinematic shot render engine (Production Stable)

Auto-selects:
  STATIC → direct FFmpeg (no motion)  <1s
  ZOOMPAN → FFmpeg zoompan (linear)    ~2s
  PIL → per-frame (full effects)       8-20s

Graceful degradation:
  - Any unsupported effect → skipped, never fails render
  - Any expression error → fallback, never fails render

Manifest tracks: effects_requested, effects_applied, effects_skipped
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime

from preset import Preset, load_preset


# =============================================================================
# CINEMATIC ENGINE
# =============================================================================

class CinematicShotEngine:
    """
    Cinematic video renderer with graceful degradation.
    """

    def __init__(self, fps: int = 24, ffmpeg_path: str = None):
        self.fps = fps
        self.ffmpeg = ffmpeg_path or self._find_ffmpeg()
        self._log_entries: list[str] = []
        self._motion = None

    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {msg}"
        self._log_entries.append(entry)
        print(entry)

    def _find_ffmpeg(self) -> str:
        for p in ["/usr/local/bin/ffmpeg"]:
            if Path(p).exists():
                return p
        return "ffmpeg"

    @property
    def motion(self):
        if self._motion is None:
            from motion import MotionRenderer
            self._motion = MotionRenderer(ffmpeg_path=self.ffmpeg)
        return self._motion

    def render(
        self,
        input_image: str,
        output_path: str,
        preset_name: str = "none",
        camera_intensity: float = 1.0,
        duration: float = None,
        fps: int = 24,
        width: int = 1080,
        height: int = 1920,
        camera_override: str = None,
        additional_effects: list = None,
        frame_debug_path: str | None = None,
    ) -> dict:
        """Render a cinematic shot with graceful degradation."""
        import time
        start = time.perf_counter()
        self._log_entries = []
        temp_frame: Optional[Path] = None

        img_path = Path(input_image)
        if not img_path.exists():
            return {"status": "failed", "error": f"Image not found: {input_image}"}

        # ── INPUT TYPE VALIDATION ──────────────────────────────────────────
        # This engine is strictly image-to-video.
        # Video files are explicitly rejected with a clear error message.
        VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv"}
        IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

        ext = img_path.suffix.lower()
        if ext in VIDEO_EXTENSIONS:
            return {
                "status": "failed",
                "error": (
                    "local_cinematic_video_engine currently expects a keyframe image input, "
                    f"not a video file.\n"
                    f"  Received: {img_path.name} (video)\n"
                    f"  Supported input: single keyframe image (.jpg, .png, .webp)\n"
                    f"  Output: cinematic shot video (.mp4)\n"
                    f"  To convert video to images, use the local_video_ingest skill first."
                ),
                "input_type": "video_rejected",
                "input_file": str(img_path),
                "supported_input": "keyframe image",
            }

        if ext not in IMAGE_EXTENSIONS:
            return {
                "status": "failed",
                "error": (
                    f"Unsupported input file type: '{ext}'\n"
                    f"  Received: {img_path.name}\n"
                    f"  Supported input: keyframe image (.jpg, .jpeg, .png, .webp, .bmp)"
                ),
                "input_type": "unsupported",
                "input_file": str(img_path),
            }

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        # --- Load preset ---
        if preset_name and preset_name != "none":
            try:
                preset = load_preset(preset_name)
            except FileNotFoundError:
                return {
                    "status": "failed",
                    "error": f"Preset not found: {preset_name}",
                    "available_presets": self._list_presets(),
                }
        else:
            actual_dur = duration or 5.0
            actual_fps = fps or 24
            preset = Preset({
                "name": "custom",
                "duration_sec": actual_dur,
                "fps": actual_fps,
                "aspect_ratio": "9:16",
                "camera": {
                    "move": camera_override or "static",
                    "zoom_start": 1.0, "zoom_end": 1.0,
                    "x_start": 0.5, "x_end": 0.5,
                    "y_start": 0.5, "y_end": 0.5,
                    "rotation_start_deg": 0.0, "rotation_end_deg": 0.0,
                    "easing": "linear"
                },
                "motion": {"micro_shake": 0.0, "breathing": 0.0, "parallax_strength": 0.0},
                "lighting": {"flicker": 0.0, "vignette_pulse": 0.0, "glow_drift": 0.0},
                "timing": {
                    "hold_start_sec": 0.0,
                    "main_move_start_sec": 0.0,
                    "main_move_end_sec": actual_dur,
                    "hold_end_sec": 0.0
                },
                "output": {"codec": "h264", "pix_fmt": "yuv420p"}
            })

        actual_duration = duration if duration else preset.duration
        actual_fps = fps if fps else preset.fps
        actual_input = str(img_path)

        # --- Apply camera_override ---
        if camera_override and camera_override != "static":
            cam = dict(preset._d.get("camera", {}))
            cam["move"] = camera_override
            cam["zoom_start"] = 1.0
            cam["zoom_end"] = 1.0
            preset._d["camera"] = cam

        # --- Apply camera_intensity ---
        if camera_intensity != 1.0:
            cam = dict(preset._d.get("camera", {}))
            for key in ["zoom_start", "zoom_end"]:
                if key in cam:
                    cam[key] = cam[key] * camera_intensity
            preset._d["camera"] = cam

        if duration:
            preset._d["duration_sec"] = duration

        self._log(f"🎬 {img_path.name}")
        self._log(f"   Preset: {preset.name} | {width}×{height} | {preset.duration}s")

        # --- Render path selection ---
        # (video already rejected above; input is always a keyframe image)
        has_motion = (
            preset.zoom_start != preset.zoom_end
            or preset.x_start != preset.x_end
            or preset.y_start != preset.y_end
            or preset.rot_start != preset.rot_end
            or preset.micro_shake > 0
            or preset.breathing > 0
        )

        effects_requested = self._effects_requested(preset)
        effects_applied = []
        effects_skipped = []

        if not has_motion:
            # === PATH 1: STATIC ===
            self._log(f"  Mode: static (direct FFmpeg)")

            vf_parts = []

            if preset.flicker > 0:
                vf_parts.append(f"eq=brightness={preset.flicker}*sin(t*25):contrast=1.0")
                effects_applied.append(f"flicker({preset.flicker})")
            else:
                effects_skipped.append("flicker(intensity=0)")

            if preset.glow_drift > 0:
                vf_parts.append(f"eq=contrast={1+preset.glow_drift}:brightness={preset.glow_drift*0.5}")
                effects_applied.append(f"glow_drift({preset.glow_drift})")
            else:
                effects_skipped.append("glow_drift(intensity=0)")

            if preset.vignette_pulse > 0:
                freq = 0.4
                vf_parts.append(
                    f"eq=brightness={preset.vignette_pulse}*sin(t*{freq}*{2*3.14159}):contrast=1.0"
                )
                effects_applied.append(f"vignette_pulse({preset.vignette_pulse})")
            else:
                effects_skipped.append("vignette_pulse(intensity=0)")

            scale_crop = (
                "scale=1080:1920:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=24"
            )

            if vf_parts:
                vf = scale_crop.replace("fps=24", "") + "," + ",".join(vf_parts) + ",fps=24"
            else:
                vf = scale_crop

            cmd = [
                self.ffmpeg, "-y",
                "-loop", "1", "-i", actual_input,
                "-t", str(actual_duration),
                "-vf", vf,
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "fast", "-crf", "18",
                "-movflags", "+faststart",
                str(out_path),
            ]

            self._log(f"  Effects: applied={effects_applied} skipped={effects_skipped}")

            cmd_file = out_path.with_suffix(".ffmpeg.cmd.txt")
            cmd_file.write_text(" ".join(cmd))

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            elapsed = time.perf_counter() - start
            stderr_file = out_path.with_suffix(".ffmpeg.stderr.log")
            stderr_file.write_text(result.stderr)

            manifest_base = {
                "preset_name": preset.name,
                "schema_version": "v1",
                "timeline_applied": {
                    "hold_start_sec": preset.hold_start_dur,
                    "main_move_start_sec": preset.move_start,
                    "main_move_end_sec": preset.move_end,
                    "hold_end_sec": preset.hold_end_dur,
                },
                "camera_params_applied": {
                    "move": preset.move(),
                    "zoom_start": preset.zoom_start,
                    "zoom_end": preset.zoom_end,
                    "x_start": preset.x_start,
                    "x_end": preset.x_end,
                    "y_start": preset.y_start,
                    "y_end": preset.y_end,
                    "rotation_start_deg": preset.rot_start,
                    "rotation_end_deg": preset.rot_end,
                    "easing": preset.easing(),
                },
                "effects_requested": effects_requested,
                "effects_applied": effects_applied,
                "effects_skipped": effects_skipped,
            }

            if result.returncode == 0 and out_path.exists():
                size_mb = out_path.stat().st_size / (1024 * 1024)
                self._log(f"  ✅ {out_path.name} — {size_mb:.2f}MB | {elapsed:.1f}s")
                final_result = {
                    **manifest_base,
                    "status": "success",
                    "output_path": str(out_path),
                    "file_size_mb": round(size_mb, 2),
                    "duration": actual_duration,
                    "render_time_sec": round(elapsed, 1),
                    "camera_intensity": camera_intensity,
                    "resolution": f"{width}×{height}",
                    "fps": actual_fps,
                    "method": "static_ffmpeg",
                    "lighting_vf": ",".join(vf_parts) if vf_parts else None,
                    "render_log": self._log_entries,
                }
            else:
                self._log(f"  ❌ RC={result.returncode}")
                final_result = {
                    **manifest_base,
                    "status": "failed",
                    "error": f"FFmpeg RC={result.returncode}: {result.stderr[-200:]}",
                    "render_time_sec": round(elapsed, 1),
                    "method": "static_ffmpeg",
                    "render_log": self._log_entries,
                }

        elif self.motion._can_use_zoompan(preset):
            # === PATH 2: ZOOMPAN ===
            cmd, desc = self.motion._build_zoompan_command(
                actual_input, str(out_path), preset, actual_fps, width, height
            )
            self._log(f"  Mode: zoompan (linear motion)")

            cmd_file = out_path.with_suffix(".ffmpeg.cmd.txt")
            cmd_file.write_text(" ".join(cmd))

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            elapsed = time.perf_counter() - start
            stderr_file = out_path.with_suffix(".ffmpeg.stderr.log")
            stderr_file.write_text(result.stderr)

            manifest_base = {
                "preset_name": preset.name,
                "schema_version": "v1",
                "timeline_applied": {
                    "hold_start_sec": preset.hold_start_dur,
                    "main_move_start_sec": preset.move_start,
                    "main_move_end_sec": preset.move_end,
                    "hold_end_sec": preset.hold_end_dur,
                },
                "camera_params_applied": {
                    "move": preset.move(),
                    "zoom_start": preset.zoom_start,
                    "zoom_end": preset.zoom_end,
                    "x_start": preset.x_start,
                    "x_end": preset.x_end,
                    "y_start": preset.y_start,
                    "y_end": preset.y_end,
                    "rotation_start_deg": preset.rot_start,
                    "rotation_end_deg": preset.rot_end,
                    "easing": preset.easing(),
                },
                "effects_requested": effects_requested,
                "effects_skipped": ["breathing", "micro_shake", "flicker", "glow_drift", "vignette_pulse"],
            }

            if result.returncode == 0 and out_path.exists():
                size_mb = out_path.stat().st_size / (1024 * 1024)
                self._log(f"  ✅ {out_path.name} — {size_mb:.2f}MB | {elapsed:.1f}s [zoompan]")
                final_result = {
                    **manifest_base,
                    "status": "success",
                    "output_path": str(out_path),
                    "file_size_mb": round(size_mb, 2),
                    "duration": actual_duration,
                    "render_time_sec": round(elapsed, 1),
                    "fps": actual_fps,
                    "resolution": f"{width}×{height}",
                    "method": "zoompan",
                    "effects_applied": [],
                    "render_log": self._log_entries,
                }
            else:
                self._log(f"  ⚠️  zoompan failed RC={result.returncode}, falling back to PIL")
                result = self.motion.render(
                    input_image_path=actual_input,
                    output_path=str(out_path),
                    preset=preset,
                    fps=actual_fps,
                    target_w=width,
                    target_h=height,
                    verbose=False,
                    frame_debug_path=frame_debug_path,
                )
                elapsed = time.perf_counter() - start
                result["render_time_sec"] = round(elapsed, 1)
                result["preset"] = preset.name
                result["render_log"] = self._log_entries
                return result

        else:
            # === PATH 3: PIL PER-FRAME ===
            self._log(f"  Mode: cinematic motion (PIL per-frame)")
            result = self.motion.render(
                input_image_path=actual_input,
                output_path=str(out_path),
                preset=preset,
                fps=actual_fps,
                target_w=width,
                target_h=height,
                verbose=False,
                frame_debug_path=frame_debug_path,
            )
            elapsed = time.perf_counter() - start
            effects_applied = result.get("effects_applied", [])
            effects_skipped = result.get("effects_skipped", [])
            manifest_base = {
                "preset_name": preset.name,
                "schema_version": "v1",
                "timeline_applied": {
                    "hold_start_sec": preset.hold_start_dur,
                    "main_move_start_sec": preset.move_start,
                    "main_move_end_sec": preset.move_end,
                    "hold_end_sec": preset.hold_end_dur,
                },
                "camera_params_applied": {
                    "move": preset.move(),
                    "zoom_start": preset.zoom_start,
                    "zoom_end": preset.zoom_end,
                    "x_start": preset.x_start,
                    "x_end": preset.x_end,
                    "y_start": preset.y_start,
                    "y_end": preset.y_end,
                    "rotation_start_deg": preset.rot_start,
                    "rotation_end_deg": preset.rot_end,
                    "easing": preset.easing(),
                },
                "effects_requested": effects_requested,
                "effects_applied": effects_applied,
                "effects_skipped": effects_skipped,
            }
            final_result = {
                **manifest_base,
                **result,
                "status": result.get("status", "failed"),
                "fps": actual_fps,
                "resolution": f"{width}×{height}",
                "render_time_sec": round(elapsed, 1),
                "render_log": self._log_entries,
            }

        return final_result

    def _effects_requested(self, preset: Preset) -> list:
        effects = []
        if preset.zoom_start != preset.zoom_end or preset.x_start != preset.x_end:
            effects.append("camera_move")
        if preset.micro_shake > 0:
            effects.append("micro_shake")
        if preset.breathing > 0:
            effects.append("breathing")
        if preset.flicker > 0:
            effects.append("flicker")
        if preset.vignette_pulse > 0:
            effects.append("vignette_pulse")
        if preset.glow_drift > 0:
            effects.append("glow_drift")
        if preset.parallax > 0:
            effects.append("parallax")
        return effects


    def _list_presets(self) -> list:
        from preset import list_presets
        return list_presets()


# =============================================================================
# STANDALONE
# =============================================================================

def render_shot(
    input_image: str,
    output_path: str,
    preset: str = "none",
    camera_intensity: float = 1.0,
    duration: float = 5.0,
    fps: int = 24,
    aspect_ratio: str = "9:16",
    quality: str = "high",
    camera_override: str = None,
) -> dict:
    """Single-shot render entry point."""
    ratio_wh = {
        "9:16": (1080, 1920), "16:9": (1920, 1080),
        "1:1": (1080, 1080), "4:3": (1440, 1080), "3:4": (1080, 1440),
    }
    w, h = ratio_wh.get(aspect_ratio, (1080, 1920))
    scale = {"ultra": 1.0, "high": 1.0, "medium": 0.667, "low": 0.5}.get(quality, 1.0)
    width, height = int(w * scale), int(h * scale)

    engine = CinematicShotEngine(fps=fps)
    return engine.render(
        input_image=input_image, output_path=output_path,
        preset_name=preset, camera_intensity=camera_intensity,
        duration=duration, fps=fps, width=width, height=height,
        camera_override=camera_override,
    )
