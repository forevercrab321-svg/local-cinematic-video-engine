#!/usr/bin/env python3
"""
batch.py — Batch scene renderer for local_cinematic_video_engine

Reads a scene_manifest.json and renders all shots automatically.
Outputs a render_ledger.json tracking every shot's status.

Usage:
    python3 batch.py scene_manifests/IN_THE_GROUP_CHAT.json
    python3 batch.py --manifest my_scene.json --out ./renders/
"""

import argparse
import json
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))


# =============================================================================
# RENDER LEDGER
# =============================================================================

class RenderLedger:
    """
    Tracks all shots in a batch render with structured status.
    Written after each shot completes (crash-safe).
    """

    def __init__(self, project_name: str, output_dir: Path):
        self.project_name = project_name
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = output_dir / "render_ledger.json"

        self.shots: list[dict] = []
        self.started_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None

    def add_shot(self, shot_data: dict):
        """Add or update a shot entry."""
        # Check if already exists
        for existing in self.shots:
            if existing["shot_id"] == shot_data["shot_id"]:
                existing.update(shot_data)
                self._save()
                return
        self.shots.append(shot_data)
        self._save()

    def update_shot(self, shot_id: str, **updates):
        """Update specific fields for a shot."""
        for shot in self.shots:
            if shot["shot_id"] == shot_id:
                shot.update(updates)
                self._save()
                return
        # If not found, add new
        self.add_shot({"shot_id": shot_id, **updates})

    def _save(self):
        """Write ledger to disk immediately (crash-safe)."""
        data = {
            "project": self.project_name,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_shots": len(self.shots),
            "success_count": sum(1 for s in self.shots if s.get("status") == "success"),
            "failed_count": sum(1 for s in self.shots if s.get("status") == "failed"),
            "in_progress": sum(1 for s in self.shots if s.get("status") == "rendering"),
            "pending_count": sum(1 for s in self.shots if s.get("status") in ("pending", None)),
            "shots": self.shots,
        }
        self.ledger_path.write_text(json.dumps(data, indent=2))

    def finalize(self):
        self.completed_at = datetime.now().isoformat()
        self._save()

    def print_summary(self):
        success = sum(1 for s in self.shots if s.get("status") == "success")
        failed = sum(1 for s in self.shots if s.get("status") == "failed")
        total = len(self.shots)

        print(f"\n{'='*55}")
        print(f"  RENDER LEDGER: {self.project_name}")
        print(f"{'='*55}")
        print(f"  {'SHOT':12s} {'STATUS':10s} {'DURATION':10s} {'SIZE':10s} {'PRESET':15s}")
        print(f"  {'-'*12:12s} {'-'*10:10s} {'-'*10:10s} {'-'*10:10s} {'-'*15:15s}")

        for s in self.shots:
            status_icon = {"success": "✅", "failed": "❌", "rendering": "⏳", "pending": "⏸"}.get(s.get("status", "?"), "?")
            dur = f"{s.get('duration', 0):.1f}s"
            size = f"{s.get('file_size_mb', 0):.1f}MB" if s.get("file_size_mb") else "—"
            preset = s.get("preset", "—")
            print(f"  {status_icon} {s.get('shot_id',''):11s} {s.get('status',''):10s} {dur:10s} {size:10s} {preset:15s}")

        print(f"{'='*55}")
        print(f"  Total: {total} | ✅ {success} | ❌ {failed}")
        elapsed = 0
        for s in self.shots:
            elapsed += s.get("render_time_sec", 0)
        print(f"  Total render time: {elapsed:.1f}s")
        print(f"{'='*55}")
        print(f"\n  Ledger: {self.ledger_path}")


# =============================================================================
# SCENE MANIFEST LOADER
# =============================================================================

class SceneManifestLoader:
    """Load and validate a scene manifest JSON."""

    REQUIRED_FIELDS = ["project", "shots"]
    SHOT_REQUIRED = ["shot_id", "input_image", "output_file", "duration", "preset"]

    def __init__(self, manifest_path: str):
        self.path = Path(manifest_path)
        self.data = self._load()
        self._validate()

    def _load(self) -> dict:
        if not self.path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.path}")
        return json.loads(self.path.read_text())

    def _validate(self):
        for field in self.REQUIRED_FIELDS:
            if field not in self.data:
                raise ValueError(f"Manifest missing required field: {field}")
        for i, shot in enumerate(self.data.get("shots", [])):
            for field in self.SHOT_REQUIRED:
                if field not in shot:
                    raise ValueError(f"Shot {i} missing required field: {field}")

    @property
    def project_name(self) -> str:
        return self.data["project"]

    @property
    def shots(self) -> list[dict]:
        return self.data["shots"]

    @property
    def render_config(self) -> dict:
        return self.data.get("render_config", {})

    def resolve_image_path(self, shot: dict, manifest_dir: Path) -> Path:
        """Resolve shot image path relative to manifest."""
        img_path = Path(shot["input_image"])
        if img_path.is_absolute():
            return img_path
        # Resolve relative to manifest
        return (manifest_dir.parent / img_path).resolve()


# =============================================================================
# SHOT RENDERER (single shot)
# =============================================================================

def render_single_shot(
    shot: dict,
    output_dir: Path,
    render_config: dict,
    verbose: bool = False,
) -> dict:
    """
    Render a single shot using the cinematic engine.

    Returns a dict with status, output, timing info.
    """
    import subprocess

    shot_id = shot["shot_id"]
    image_path = shot["input_image"]
    duration = shot.get("duration", 5.0)
    fps = shot.get("fps", 24)
    preset = shot.get("preset", "none")
    intensity = shot.get("camera_intensity", 1.0)
    camera_override = shot.get("camera_override")
    aspect_ratio = render_config.get("aspect_ratio", "9:16")
    quality = render_config.get("quality", "high")

    output_file = output_dir / shot.get("output_file", f"{shot_id}.mp4")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build CLI command
    cmd = [
        sys.executable,
        str(SKILL_DIR / "run_shot.py"),
        "--image", str(image_path),
        "--preset", preset,
        "--duration", str(duration),
        "--fps", str(fps),
        "--ratio", aspect_ratio,
        "--quality", quality,
        "--shot", shot_id,
        "--out", str(output_dir),
    ]

    if camera_override:
        cmd.extend(["--camera", camera_override])
    else:
        cmd.extend(["--camera", "static"])

    cmd.extend(["--intensity", str(intensity)])

    # Run
    start = time.perf_counter()

    if verbose:
        print(f"  🎬 {shot_id} | preset={preset} | intensity={intensity} | {duration}s")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=duration * 10 + 60,
        )
        elapsed = time.perf_counter() - start

        if result.returncode == 0 and output_file.exists():
            file_size_mb = output_file.stat().st_size / (1024 * 1024)
            return {
                "shot_id": shot_id,
                "status": "success",
                "output_file": str(output_file),
                "file_size_mb": round(file_size_mb, 2),
                "duration": duration,
                "render_time_sec": round(elapsed, 1),
                "preset": preset,
                "camera": camera_override or preset,
                "intensity": intensity,
                "error": None,
            }
        else:
            # Try to parse error
            err = result.stderr[-300:] if result.stderr else "Unknown error"
            return {
                "shot_id": shot_id,
                "status": "failed",
                "output_file": None,
                "file_size_mb": None,
                "duration": duration,
                "render_time_sec": round(elapsed, 1),
                "preset": preset,
                "camera": camera_override or preset,
                "intensity": intensity,
                "error": err.strip(),
            }

    except subprocess.TimeoutExpired:
        return {
            "shot_id": shot_id,
            "status": "failed",
            "error": "Render timeout",
            "render_time_sec": time.perf_counter() - start,
            **shot,
        }
    except Exception as e:
        return {
            "shot_id": shot_id,
            "status": "failed",
            "error": str(e),
            "render_time_sec": time.perf_counter() - start,
            **shot,
        }


# =============================================================================
# BATCH RENDERER
# =============================================================================

def render_scene(
    manifest_path: str,
    output_dir: Optional[str] = None,
    verbose: bool = False,
    continue_on_error: bool = True,
) -> RenderLedger:
    """
    Render all shots in a scene manifest.

    Args:
        manifest_path: Path to scene_manifest.json
        output_dir: Override output directory
        verbose: Print per-shot status
        continue_on_error: Keep rendering if a shot fails

    Returns:
        RenderLedger with all shot statuses
    """
    # Load manifest
    manifest = SceneManifestLoader(manifest_path)
    manifest_dir = Path(manifest_path).parent.resolve()

    # Determine output directory
    if output_dir:
        out_dir = Path(output_dir)
    else:
        out_dir = manifest_dir.parent / manifest.render_config.get("output_dir", "renders")

    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Create ledger
    ledger = RenderLedger(manifest.project_name, out_dir)

    # Pre-populate ledger with pending shots
    for shot in manifest.shots:
        ledger.add_shot({
            "shot_id": shot["shot_id"],
            "status": "pending",
            "preset": shot.get("preset", "none"),
            "duration": shot.get("duration", 5.0),
            "input_image": str(manifest.resolve_image_path(shot, manifest_dir)),
        })

    # Resolve image paths and check
    valid_shots = []
    for shot in manifest.shots:
        img_path = manifest.resolve_image_path(shot, manifest_dir)
        if not img_path.exists():
            print(f"⚠️  {shot['shot_id']}: Image not found: {img_path}")
            if not continue_on_error:
                continue
            ledger.update_shot(shot["shot_id"], status="failed", error=f"Image not found: {img_path}")
        else:
            shot["_resolved_image"] = str(img_path)
            valid_shots.append(shot)

    if not valid_shots:
        print("❌ No valid shots to render")
        return ledger

    # Render each shot
    total = len(valid_shots)
    print(f"\n📦 {manifest.project_name}")
    print(f"   Shots: {total} | Output: {out_dir}")
    print(f"   Config: {manifest.render_config}")
    print()

    for i, shot in enumerate(valid_shots):
        shot_id = shot["shot_id"]
        img_path = shot["_resolved_image"]

        print(f"[{i+1}/{total}] {shot_id}... ", end="", flush=True)

        ledger.update_shot(shot_id, status="rendering")

        # Override image path with resolved
        shot["input_image"] = img_path

        result = render_single_shot(
            shot=shot,
            output_dir=out_dir,
            render_config=manifest.render_config,
            verbose=verbose,
        )

        # Update ledger
        ledger.update_shot(shot_id, **result)

        if result["status"] == "success":
            print(f"✅ {result['render_time_sec']}s | {result['file_size_mb']}MB")
        else:
            print(f"❌ {result.get('error', 'unknown error')[:60]}")

        # Check if should continue
        if result["status"] == "failed" and not continue_on_error:
            print(f"\n⚠️  Stopping due to render failure (continue_on_error=False)")
            break

    ledger.finalize()
    return ledger


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Batch render a scene from manifest"
    )
    parser.add_argument("manifest", help="Path to scene_manifest.json")
    parser.add_argument("--out", "-o", help="Output directory override")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--stop-on-error", action="store_true", default=False,
                        help="Stop batch on first failure")
    args = parser.parse_args()

    ledger = render_scene(
        manifest_path=args.manifest,
        output_dir=args.out,
        verbose=args.verbose,
        continue_on_error=not args.stop_on_error,
    )

    ledger.print_summary()

    failed = sum(1 for s in ledger.shots if s.get("status") == "failed")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
