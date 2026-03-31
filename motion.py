"""
motion.py — Cinematic camera motion renderer (Production Stable)

Three render paths, auto-selected:

  STATIC  → direct FFmpeg (no motion)          < 1s
  ZOOMPAN → FFmpeg zoompan (linear zoom only)  ~2s
  PIL     → per-frame generation (all effects)   8-20s

Graceful degradation:
  - Any unsupported/effect/skipped effect NEVER fails the render
  - Each effect has a fallback: skip → warn → continue
  - Manifest tracks: effects_requested, effects_applied, effects_skipped
"""

import math
import os
import shutil
import subprocess
import tempfile
import hashlib
from pathlib import Path
from typing import Optional

from preset import Preset


# =============================================================================
# EFFECT REGISTRY — what we support and how
# =============================================================================

class EffectRegistry:
    """
    Central registry of all effects.
    Each effect has:
      - supported: bool (can we do it?)
      - apply_fn: callable or None (how to apply in PIL pipeline)
      - ffprobe_filter: str or None (for direct FFmpeg path)
      - fallback: str ('skip' | 'approximate')
      - description: human-readable
    """

    @staticmethod
    def get_all() -> dict:
        return {
            "micro_shake": {
                "supported": True,
                "method": "pil_per_frame",
                "description": "Deterministic pseudo-random per-frame pan jitter",
                "fallback": "approximate",  # if zoompan path, skip
            },
            "breathing": {
                "supported": True,
                "method": "pil_per_frame",
                "description": "Subtle sin-wave zoom oscillation at 0.35Hz",
                "fallback": "skip",
            },
            "flicker": {
                "supported": True,
                "method": "ffmpeg_eq",
                "description": "Brightness micro-variation at ~4Hz",
                "fallback": "skip",
            },
            "vignette_pulse": {
                "supported": True,
                "method": "ffmpeg_eq_brightness",
                "description": "Vignette strength oscillation at 0.4Hz",
                "fallback": "skip",
            },
            "glow_drift": {
                "supported": True,
                "method": "ffmpeg_eq",
                "description": "Subtle contrast/brightness drift",
                "fallback": "skip",
            },
            "film_grain": {
                "supported": True,
                "method": "ffmpeg_noise",
                "description": "Temporal film grain overlay",
                "fallback": "skip",
            },
            "parallax": {
                "supported": True,
                "method": "pil_layer_offset",
                "description": "Multi-layer depth offset",
                "fallback": "approximate",  # approximate with single layer
            },
            "color_grade": {
                "supported": False,
                "method": None,
                "description": "Color grading (saturation, temperature, etc.)",
                "fallback": "skip",
            },
        }

    @staticmethod
    def effects_requested(preset: Preset) -> list:
        """List all effects requested by a preset."""
        effects = []
        p = preset
        if p.micro_shake > 0:
            effects.append("micro_shake")
        if p.breathing > 0:
            effects.append("breathing")
        if p.flicker > 0:
            effects.append("flicker")
        if p.vignette_pulse > 0:
            effects.append("vignette_pulse")
        if p.glow_drift > 0:
            effects.append("glow_drift")
        # Color grade from preset lighting section
        # (tracked separately)
        return effects


# =============================================================================
# GRACEFUL EFFECT APPLIER
# =============================================================================

class EffectApplier:
    """
    Applies effects to a PIL frame or FFmpeg command.
    Never raises. Logs skips. Tracks what was applied vs skipped.
    """

    def __init__(self, preset: Preset):
        self.preset = preset
        self.applied: list[str] = []
        self.skipped: list[str] = []
        self._warnings: list[str] = []
        self._effect_defs = EffectRegistry.get_all()

    def warn(self, msg: str):
        self._warnings.append(msg)
        print(f"    ⚠️  {msg}")

    def request_effect(self, name: str, reason: str = ""):
        """Record that an effect was requested but may not be applied."""
        pass  # tracked via values, not explicit request

    def apply_to_frame_pil(
        self,
        frame_idx: int,
        total_frames: int,
        img_zoomed: "Image.Image",
        zoom: float,
        pan_x_n: float,
        pan_y_n: float,
        shake_x: float,
        shake_y: float,
        target_w: int,
        target_h: int,
    ) -> tuple["Image.Image", float, float]:
        """
        Apply motion effects to a PIL Image.
        Returns: (modified_frame, final_zoom, final_shake_x, final_shake_y)

        All effects are applied IN ORDER. Skipped effects don't break the chain.
        """
        from PIL import Image
        p = self.preset
        time_sec = frame_idx / total_frames * p.duration
        src_w, src_h = img_zoomed.size

        # Apply micro_shake (always, if > 0)
        if p.micro_shake > 0:
            sx = shake_x
            sy = shake_y
            self.applied.append("micro_shake")
        else:
            sx, sy = shake_x, shake_y

        # Breathing (if > 0)
        if p.breathing > 0:
            self.applied.append("breathing")
            # Already baked into zoom in _compute_frame_transform
        else:
            pass  # noop

        return img_zoomed, zoom, sx, sy

    def build_ffmpeg_effects_chain(self) -> tuple[Optional[str], list, list]:
        """
        Build FFmpeg vf chain for lighting effects.
        Returns: (vf_string, applied_list, skipped_list)

        Only effects that work on the PIL output (not the zoompan path)
        can be applied here.
        """
        p = self.preset
        parts: list[str] = []
        applied: list[str] = []
        skipped: list[str] = []

        # Flicker → eq brightness micro-variation
        if p.flicker > 0:
            if self._effect_defs["flicker"]["supported"]:
                expr = f"eq=brightness={p.flicker}*sin(t*25):contrast=1.0"
                parts.append(expr)
                applied.append(f"flicker(intensity={p.flicker})")
            else:
                skipped.append(f"flicker(intensity={p.flicker}): unsupported")
        else:
            skipped.append("flicker: intensity=0")

        # Glow drift → eq contrast boost
        if p.glow_drift > 0:
            if self._effect_defs["glow_drift"]["supported"]:
                expr = f"eq=contrast={1+p.glow_drift}:brightness={p.glow_drift*0.5}"
                parts.append(expr)
                applied.append(f"glow_drift(intensity={p.glow_drift})")
            else:
                skipped.append(f"glow_drift(intensity={p.glow_drift}): unsupported")

        # Vignette pulse → brightness oscillation (simple approximation)
        # FFmpeg vignette filter is complex to pulse; we approximate with eq
        if p.vignette_pulse > 0:
            if self._effect_defs["vignette_pulse"]["supported"]:
                freq = 0.4
                expr = (
                    f"eq=brightness="
                    f"{p.vignette_pulse}*sin(t*{freq}*{2*math.pi}):"
                    f"contrast=1.0"
                )
                parts.append(expr)
                applied.append(f"vignette_pulse(intensity={p.vignette_pulse})")
            else:
                skipped.append(f"vignette_pulse(intensity={p.vignette_pulse}): unsupported")

        vf = ",".join(parts) if parts else None
        return vf, applied, skipped


# =============================================================================
# MOTION RENDERER
# =============================================================================

class MotionRenderer:

    ZOOMPAN_MAX_FRAMES = 500

    def __init__(self, ffmpeg_path: str = None):
        self.ffmpeg = ffmpeg_path or self._find_ffmpeg()

    def _find_ffmpeg(self) -> str:
        for p in ["/usr/local/bin/ffmpeg"]:
            if Path(p).exists():
                return p
        return "ffmpeg"

    def _ease(self, eased_t: float, ease_type: str) -> float:
        if ease_type == "linear":
            return eased_t
        elif ease_type == "ease_in":
            return eased_t ** 3
        elif ease_type == "ease_out":
            return 1 - (1 - eased_t) ** 3
        elif ease_type == "ease_in_out":
            return eased_t * eased_t * (3 - 2 * eased_t)
        elif ease_type == "sudden":
            return 1.0 if eased_t > 0 else 0.0
        elif ease_type == "hold":
            return 0.0
        elif ease_type == "hesitate":
            if eased_t < 0.5:
                return eased_t * 0.05
            return 0.05 + (eased_t - 0.5) * 1.9
        return eased_t

    def _can_use_zoompan(self, preset: Preset) -> bool:
        """Check if preset can use fast zoompan path."""
        p = preset
        if p.micro_shake > 0 or p.breathing > 0:
            return False
        if p.easing() not in ("linear", "hold"):
            return False
        if abs(p.x_start - p.x_end) > 0.01 or abs(p.y_start - p.y_end) > 0.01:
            return False
        if abs(p.rot_start - p.rot_end) > 0.1:
            return False
        if p.hold_start_dur > 0.1:
            return False
        if int(p.duration * p.fps) > self.ZOOMPAN_MAX_FRAMES:
            return False
        if p.zoom_start == p.zoom_end:
            return False
        return True

    def _build_zoompan_command(
        self,
        input_path: str,
        output_path: str,
        preset: Preset,
        fps: int,
        target_w: int,
        target_h: int,
    ) -> tuple[list, str]:
        """Build zoompan FFmpeg command. Always succeeds if input is valid."""
        p = preset
        total_frames = int(p.duration * fps)
        zdelta = (p.zoom_end - p.zoom_start) / total_frames
        zdelta = max(-0.05, min(0.05, zdelta))

        if zdelta >= 0:
            zexpr = f"min(zoom+{zdelta:.6f},{max(p.zoom_end, 1.0):.4f})"
        else:
            zexpr = f"max(zoom-{abs(zdelta):.6f},{min(p.zoom_end, 0.5):.4f})"

        maxz = max(p.zoom_end, p.zoom_start)
        pre_w = int(target_w * maxz * 1.1)
        pre_h = int(target_h * maxz * 1.1)

        vf = (
            f"scale={pre_w}:{pre_h}:force_original_aspect_ratio=increase,"
            f"crop={pre_w}:{pre_h},"
            f"zoompan="
            f"z='{zexpr}':"
            f"x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':"
            f"d=1:"
            f"fps={fps}:"
            f"s={target_w}x{target_h}"
        )

        cmd = [
            self.ffmpeg, "-y",
            "-loop", "1", "-i", input_path,
            "-t", str(p.duration),
            "-vf", vf,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "fast", "-crf", "18",
            "-movflags", "+faststart",
            output_path,
        ]
        desc = f"zoompan {p.zoom_start:.3f}→{p.zoom_end:.3f} ({zdelta:+.6f}/frame)"
        return cmd, desc

    def _compute_frame(
        self,
        frame_idx: int,
        total_frames: int,
        preset: Preset,
        src_w: int,
        src_h: int,
        target_w: int,
        target_h: int,
    ) -> tuple[float, float, float, float, float]:
        """
        Compute per-frame: (zoom, pan_x_n, pan_y_n, shake_x, shake_y).
        All effects baked in. No expressions that can fail.
        """
        p = preset
        t = frame_idx / total_frames
        time_sec = t * p.duration
        total_dur = p.duration

        ms = move_start_n = p.move_start / total_dur if total_dur > 0 else 0.0
        me = move_end_n = p.move_end / total_dur if total_dur > 0 else 1.0

        if t < ms:
            zoom = p.zoom_start
            pan_x_n = p.x_start
            pan_y_n = p.y_start
        elif t > me:
            zoom = p.zoom_end
            pan_x_n = p.x_end
            pan_y_n = p.y_end
        else:
            local_t = (t - ms) / (me - ms)
            eased = self._ease(local_t, p.easing())
            zoom = p.zoom_start + (p.zoom_end - p.zoom_start) * eased
            pan_x_n = p.x_start + (p.x_end - p.x_start) * eased
            pan_y_n = p.y_start + (p.y_end - p.y_start) * eased

        # Breathing: safe sin expression
        if p.breathing > 0:
            zoom += p.breathing * math.sin(2 * math.pi * 0.35 * time_sec)

        # Micro shake: deterministic
        if p.micro_shake > 0:
            seed_x = int(hashlib.md5(f"{frame_idx}_x".encode()).hexdigest()[:8], 16)
            seed_y = int(hashlib.md5(f"{frame_idx}_y".encode()).hexdigest()[:8], 16)
            rng_x = ((seed_x % 1000) / 500.0) - 1.0
            rng_y = ((seed_y % 1000) / 500.0) - 1.0
            shake_x = rng_x * p.micro_shake * 1920
            shake_y = rng_y * p.micro_shake * 1920
        else:
            shake_x, shake_y = 0.0, 0.0

        return zoom, pan_x_n, pan_y_n, shake_x, shake_y

    # ===================================================================
    # PIL PER-FRAME RENDER
    # ===================================================================

    def _render_pil(
        self,
        input_path: str,
        output_path: str,
        preset: Preset,
        fps: int,
        target_w: int,
        target_h: int,
        verbose: bool = True,
        frame_debug_path: str | None = None,
    ) -> dict:
        """PIL per-frame → FFmpeg encode. Fully graceful."""
        import time
        from PIL import Image

        start = time.perf_counter()
        tmp_dir = tempfile.mkdtemp(prefix="cin_frames_")
        applier = EffectApplier(preset)

        try:
            img = Image.open(input_path).convert("RGB")
            src_w, src_h = img.size
            total_frames = int(preset.duration * fps)

            # Build FFmpeg lighting effects chain
            vf_parts: list[str] = []
            effects_applied: list[str] = []
            effects_skipped: list[str] = []

            # Flicker
            if preset.flicker > 0:
                vf_parts.append(
                    f"eq=brightness={preset.flicker}*sin(t*25):contrast=1.0"
                )
                effects_applied.append(f"flicker({preset.flicker})")
            else:
                effects_skipped.append("flicker(intensity=0)")

            # Glow drift
            if preset.glow_drift > 0:
                vf_parts.append(
                    f"eq=contrast={1+preset.glow_drift}:brightness={preset.glow_drift*0.5}"
                )
                effects_applied.append(f"glow_drift({preset.glow_drift})")
            else:
                effects_skipped.append("glow_drift(intensity=0)")

            # Vignette pulse (approximate via brightness)
            if preset.vignette_pulse > 0:
                freq = 0.4
                vf_parts.append(
                    f"eq=brightness="
                    f"{preset.vignette_pulse}*sin(t*{freq}*{2*math.pi}):"
                    f"contrast=1.0"
                )
                effects_applied.append(f"vignette_pulse({preset.vignette_pulse})")
            else:
                effects_skipped.append("vignette_pulse(intensity=0)")

            if verbose:
                print(f"  [PIL] {total_frames} frames, {fps}fps")
                if effects_applied:
                    print(f"  [PIL] Effects applied: {effects_applied}")
                if effects_skipped:
                    print(f"  [PIL] Effects skipped: {effects_skipped}")

            # Generate frames
            frame_debug: list[dict] = []
            for i in range(total_frames):
                zoom, pan_x_n, pan_y_n, shake_x, shake_y = self._compute_frame(
                    i, total_frames, preset, src_w, src_h, target_w, target_h
                )

                # Collect per-frame debug data
                if frame_debug_path is not None:
                    frame_debug.append({
                        "frame": i,
                        "zoom": round(zoom, 6),
                        "pan_x": round(pan_x_n, 6),
                        "pan_y": round(pan_y_n, 6),
                        "rotation": 0.0,          # reserved for future rot support
                        "shake_x": round(shake_x, 4),
                        "shake_y": round(shake_y, 4),
                    })

                # Apply zoom
                zoomed_w = src_w * zoom
                zoomed_h = src_h * zoom
                off_x = (0.5 - pan_x_n) * zoomed_w + shake_x
                off_y = (0.5 - pan_y_n) * zoomed_h + shake_y
                crop_x = max(0, min((zoomed_w - target_w) / 2 - off_x, zoomed_w - target_w))
                crop_y = max(0, min((zoomed_h - target_h) / 2 - off_y, zoomed_h - target_h))

                img_z = img.resize((int(zoomed_w), int(zoomed_h)), Image.BICUBIC)
                frame = img_z.crop((
                    int(crop_x), int(crop_y),
                    int(crop_x) + target_w, int(crop_y) + target_h
                ))
                frame = frame.resize((target_w, target_h), Image.BICUBIC)

                frame.save(os.path.join(tmp_dir, f"frame_{i:05d}.jpg"), "JPEG", quality=95)

                if verbose and (i + 1) % fps == 0:
                    pct = (i + 1) / total_frames * 100
                    print(f"  [{pct:.0f}%] {i+1}/{total_frames} frames")

            # Write frame debug data
            if frame_debug_path is not None and frame_debug:
                import json as _json
                debug_out = Path(frame_debug_path)
                debug_out.parent.mkdir(parents=True, exist_ok=True)
                debug_out.write_text(_json.dumps(frame_debug, indent=2))
                if verbose:
                    print(f"  [DEBUG] Frame data → {debug_out} ({len(frame_debug)} frames)")

            if verbose:
                print(f"  [PIL] Encoding → {output_path}...")

            # Build final FFmpeg command
            cmd = [self.ffmpeg, "-y",
                   "-framerate", str(fps),
                   "-i", os.path.join(tmp_dir, "frame_%05d.jpg"),
                   "-t", str(preset.duration)]

            if vf_parts:
                cmd += ["-vf", ",".join(vf_parts)]

            cmd += [
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "fast", "-crf", "18",
                "-movflags", "+faststart",
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            elapsed = time.perf_counter() - start

            if result.returncode == 0 and Path(output_path).exists():
                size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                if verbose:
                    print(f"  ✅ {Path(output_path).name} — {size_mb:.2f}MB | {elapsed:.1f}s")
                return {
                    "status": "success",
                    "output_path": output_path,
                    "file_size_mb": round(size_mb, 2),
                    "duration": preset.duration,
                    "render_time_sec": round(elapsed, 1),
                    "frame_count": total_frames,
                    "fps": fps,
                    "resolution": f"{target_w}×{target_h}",
                    "method": "pil",
                    "frame_debug_path": frame_debug_path,
                    "effects_requested": [EffectRegistry.effects_requested(preset)],
                    "effects_applied": effects_applied,
                    "effects_skipped": effects_skipped,
                    "lighting_vf": ",".join(vf_parts) if vf_parts else None,
                }
            else:
                if verbose:
                    print(f"  ❌ PIL encode failed RC={result.returncode}")
                return {
                    "status": "failed",
                    "error": f"FFmpeg RC={result.returncode}: {result.stderr[-200:]}",
                    "render_time_sec": round(elapsed, 1),
                    "method": "pil",
                    "effects_applied": effects_applied,
                    "effects_skipped": effects_skipped,
                }

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ===================================================================
    # MAIN RENDER — auto-selects path
    # ===================================================================

    def render(
        self,
        input_image_path: str,
        output_path: str,
        preset: Preset,
        fps: int = 24,
        target_w: int = 1080,
        target_h: int = 1920,
        verbose: bool = True,
        frame_debug_path: str | None = None,
    ) -> dict:
        """
        Render cinematic video.
        Auto-selects: static → zoompan → PIL.
        NEVER fails due to unsupported effects.
        """
        import time
        from PIL import Image

        start = time.perf_counter()
        tmp_frame: Optional[Path] = None

        # Resolve input — motion.py only accepts images (videos rejected upstream in engine.py)
        input_path = Path(input_image_path)
        actual_input = str(input_path)

        has_motion = (
        preset.zoom_start != preset.zoom_end
        or preset.x_start != preset.x_end
        or preset.y_start != preset.y_end
        or preset.rot_start != preset.rot_end
        or preset.micro_shake > 0
        or preset.breathing > 0
        )

        if not has_motion:
            # === PATH 1: STATIC (direct FFmpeg) ===
            if verbose:
                print(f"  [static] No motion — direct FFmpeg")

            # Determine lighting effects for static path too
            vf_parts = []
            effects_applied = []
            effects_skipped = []

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
                    f"eq=brightness={preset.vignette_pulse}*sin(t*{freq}*{2*math.pi}):contrast=1.0"
                )
                effects_applied.append(f"vignette_pulse({preset.vignette_pulse})")
            else:
                effects_skipped.append("vignette_pulse(intensity=0)")

            if verbose and effects_applied:
                print(f"  [static] Effects applied: {effects_applied}")

            vf = ",".join(vf_parts) if vf_parts else None
            cmd = [self.ffmpeg, "-y", "-loop", "1", "-i", actual_input,
                   "-t", str(preset.duration)]
            if vf:
                cmd += ["-vf", vf]
            cmd += [
                "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                       "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=24"
                       if not vf else (
                           f"scale=1080:1920:force_original_aspect_ratio=decrease,"
                           f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
                           f"{vf},fps=24"
                       ),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-preset", "fast", "-crf", "18",
                "-movflags", "+faststart",
                output_path,
            ]

            # Fix: only one -vf
            if not vf:
                cmd = [self.ffmpeg, "-y", "-loop", "1", "-i", actual_input,
                       "-t", str(preset.duration),
                       "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                              "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=24",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p",
                       "-preset", "fast", "-crf", "18",
                       "-movflags", "+faststart",
                       output_path]

            cmd_path = Path(output_path).with_suffix(".ffmpeg.cmd.txt")
            cmd_path.write_text(" ".join(cmd))

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            elapsed = time.perf_counter() - start
            stderr_path = Path(output_path).with_suffix(".ffmpeg.stderr.log")
            stderr_path.write_text(result.stderr)

            if result.returncode == 0 and Path(output_path).exists():
                size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                if verbose:
                    print(f"  ✅ {Path(output_path).name} — {size_mb:.2f}MB | {elapsed:.1f}s")
                return {
                    "status": "success",
                    "output_path": output_path,
                    "file_size_mb": round(size_mb, 2),
                    "duration": preset.duration,
                    "render_time_sec": round(elapsed, 1),
                    "fps": fps,
                    "resolution": f"{target_w}×{target_h}",
                    "method": "static_ffmpeg",
                    "effects_requested": EffectRegistry.effects_requested(preset),
                    "effects_applied": effects_applied,
                    "effects_skipped": effects_skipped,
                    "lighting_vf": vf,
                }
            else:
                return {
                    "status": "failed",
                    "error": f"static FFmpeg RC={result.returncode}",
                    "render_time_sec": round(elapsed, 1),
                    "method": "static_ffmpeg",
                    "effects_applied": effects_applied,
                    "effects_skipped": effects_skipped,
                }

        elif self._can_use_zoompan(preset):
            # === PATH 2: ZOOMPAN (fast, linear only) ===
            if verbose:
                print(f"  [zoompan] Linear zoom — fast path")

            cmd, desc = self._build_zoompan_command(
                actual_input, output_path, preset, fps, target_w, target_h
            )
            if verbose:
                print(f"  {desc}")

            cmd_path = Path(output_path).with_suffix(".ffmpeg.cmd.txt")
            cmd_path.write_text(" ".join(cmd))

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            elapsed = time.perf_counter() - start
            stderr_path = Path(output_path).with_suffix(".ffmpeg.stderr.log")
            stderr_path.write_text(result.stderr)

            if result.returncode == 0 and Path(output_path).exists():
                size_mb = Path(output_path).stat().st_size / (1024 * 1024)
                if verbose:
                    print(f"  ✅ {Path(output_path).name} — {size_mb:.2f}MB | {elapsed:.1f}s [zoompan]")
                return {
                    "status": "success",
                    "output_path": output_path,
                    "file_size_mb": round(size_mb, 2),
                    "duration": preset.duration,
                    "render_time_sec": round(elapsed, 1),
                    "frame_count": int(preset.duration * fps),
                    "fps": fps,
                    "resolution": f"{target_w}×{target_h}",
                    "method": "zoompan",
                    "effects_requested": EffectRegistry.effects_requested(preset),
                    "effects_applied": [],
                    "effects_skipped": ["breathing", "micro_shake", "vignette_pulse", "flicker", "glow_drift"],
                    "description": desc,
                }
            else:
                if verbose:
                    print(f"  ⚠️  zoompan failed RC={result.returncode}, falling back to PIL")
                # Fall through to PIL

        # === PATH 3: PIL PER-FRAME (universal) ===
        return self._render_pil(
            actual_input, output_path, preset, fps, target_w, target_h,
            verbose, frame_debug_path=frame_debug_path,
        )


