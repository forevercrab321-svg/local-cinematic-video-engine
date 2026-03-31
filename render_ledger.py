"""
render_ledger.py — Scene render ledger

Tracks the complete state of a batch scene render:
  - Every shot: pending → rendering → success | failed
  - Per-shot: exact preset, camera params, effects applied, timing
  - Scene-level: progress, total time, success/fail counts
  - Written after each shot (crash-safe)

Output: scene_render_ledger.json

Usage:
    ledger = RenderLedger("IN_THE_GROUP_CHAT", output_dir=Path("./renders"))
    ledger.add_scene(scene_manifest)
    ledger.render_all()
    ledger.print_summary()
"""

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from datetime import datetime
from typing import Optional
from threading import Lock


# =============================================================================
# SHOT STATUS
# =============================================================================

class ShotStatus:
    PENDING    = "pending"
    RENDERING  = "rendering"
    SUCCESS    = "success"
    FAILED     = "failed"
    SKIPPED    = "skipped"


# =============================================================================
# SHOT LEDGER ENTRY
# =============================================================================

@dataclass
class ShotLedgerEntry:
    """Single shot's ledger entry."""
    shot_id: str
    scene_index: int
    preset: str
    duration_sec: float
    fps: int
    aspect_ratio: str
    input_image: str
    output_file: str
    caption_text: Optional[str] = None
    dialogue: Optional[str] = None
    note: Optional[str] = None
    risk_level: str = "safe"
    shot_type: str = "medium"
    camera_override: Optional[str] = None
    camera_intensity: float = 1.0

    # Render result
    status: str = ShotStatus.PENDING
    method: Optional[str] = None       # "PIL" | "zoompan" | "static_ffmpeg"
    engine_mode: Optional[str] = None   # same as method (alias)
    file_size_mb: Optional[float] = None
    render_time_sec: Optional[float] = None
    wall_clock_start: Optional[str] = None
    wall_clock_end: Optional[str] = None

    # Effects tracking
    timeline_applied: dict = field(default_factory=dict)
    camera_params_applied: dict = field(default_factory=dict)
    effects_requested: list = field(default_factory=list)
    effects_applied: list = field(default_factory=list)
    effects_skipped: list = field(default_factory=list)

    # Error
    error: Optional[str] = None

    # Frame count
    frame_count: Optional[int] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Remove None values for cleanliness
        return {k: v for k, v in d.items() if v is not None}


# =============================================================================
# SCENE LEDGER
# =============================================================================

@dataclass
class SceneLedger:
    """Ledger for an entire scene render."""
    project: str
    output_dir: Path
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())
    total_shots: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    in_progress_count: int = 0
    pending_count: int = 0
    total_render_time_sec: float = 0.0
    total_wall_clock_sec: float = 0.0
    shots: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


# =============================================================================
# RENDER LEDGER
# =============================================================================

class RenderLedger:
    """
    Crash-safe render ledger for a scene.

    Writes to scene_render_ledger.json after EVERY shot.
    Can be resumed if interrupted.

    Usage:
        ledger = RenderLedger("IN_THE_GROUP_CHAT", output_dir)
        ledger.add_scene(scene_manifest)
        ledger.render_all(verbose=True)
        ledger.print_summary()
    """

    LEDGER_FILENAME = "scene_render_ledger.json"

    def __init__(self, project_name: str, output_dir: str | Path):
        self.project_name = project_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.ledger_path = self.output_dir / self.LEDGER_FILENAME
        self._lock = Lock()

        # Load existing ledger if present (resume support)
        self.scene: Optional[SceneLedger] = None
        if self.ledger_path.exists():
            try:
                data = json.loads(self.ledger_path.read_text())
                self.scene = SceneLedger(**data)
            except Exception:
                pass  # Start fresh

        if self.scene is None:
            self.scene = SceneLedger(project=project_name, output_dir=str(self.output_dir))

    # -------------------------------------------------------------------------
    # Population
    # -------------------------------------------------------------------------

    def add_scene(self, scene_manifest) -> "RenderLedger":
        """
        Add all shots from a SceneManifest to the ledger.
        Returns self for chaining.
        """
        if self.scene.shots:
            raise RuntimeError("Scene already added. Create a new ledger.")

        self.scene.project = scene_manifest.project
        self.scene.total_shots = len(scene_manifest.shots)
        self.scene.pending_count = len(scene_manifest.shots)
        self.scene.started_at = datetime.now().isoformat()
        self.scene.completed_at = None

        for i, shot in enumerate(scene_manifest.shots):
            entry = ShotLedgerEntry(
                shot_id=shot.shot_id,
                scene_index=i,
                preset=shot.preset,
                duration_sec=shot.duration_sec,
                fps=shot.fps,
                aspect_ratio=shot.aspect_ratio,
                input_image=str(shot.resolved_input),
                output_file=str(shot.resolved_output),
                caption_text=shot.caption_text,
                dialogue=shot.dialogue,
                note=shot.note,
                risk_level=shot.risk_level,
                shot_type=shot.shot_type,
                camera_override=shot.camera_override,
                camera_intensity=shot.camera_intensity,
                status=ShotStatus.PENDING,
            )
            self.scene.shots.append(entry)

        self._save()
        return self

    # -------------------------------------------------------------------------
    # State transitions
    # -------------------------------------------------------------------------

    def start_shot(self, shot_id: str):
        """Mark a shot as rendering."""
        with self._lock:
            entry = self._get_entry(shot_id)
            if entry is None:
                raise ValueError(f"Unknown shot_id: {shot_id}")
            entry.status = ShotStatus.RENDERING
            entry.wall_clock_start = datetime.now().isoformat()
            self.scene.in_progress_count += 1
            self.scene.pending_count -= 1
            self._save()

    def complete_shot(self, shot_id: str, result: dict):
        """
        Record a shot's render result.

        result: the full manifest dict from engine.render()
        """
        with self._lock:
            entry = self._get_entry(shot_id)
            if entry is None:
                return

            entry.status = result.get("status", ShotStatus.SUCCESS)
            entry.method = result.get("method")
            entry.engine_mode = result.get("method")  # alias
            entry.file_size_mb = result.get("file_size_mb")
            entry.render_time_sec = result.get("render_time_sec")
            entry.wall_clock_end = datetime.now().isoformat()
            entry.error = result.get("error")
            entry.frame_count = result.get("frame_count")
            entry.timeline_applied = result.get("timeline_applied", {})
            entry.camera_params_applied = result.get("camera_params_applied", {})
            entry.effects_requested = result.get("effects_requested", [])
            entry.effects_applied = result.get("effects_applied", [])
            entry.effects_skipped = result.get("effects_skipped", [])

            self.scene.in_progress_count -= 1
            if result.get("status") == "success":
                self.scene.success_count += 1
                self.scene.total_render_time_sec += result.get("render_time_sec", 0)
            else:
                self.scene.failed_count += 1

            self._save()

    def skip_shot(self, shot_id: str, reason: str):
        """Mark a shot as skipped (e.g. input not found)."""
        with self._lock:
            entry = self._get_entry(shot_id)
            if entry is None:
                return
            entry.status = ShotStatus.SKIPPED
            entry.error = reason
            entry.wall_clock_end = datetime.now().isoformat()
            self.scene.in_progress_count -= 1
            self.scene.skipped_count += 1
            self.scene.pending_count -= 1
            self._save()

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def render_all(self, scene_manifest, verbose: bool = True,
                   continue_on_error: bool = True):
        """
        Render all shots in the ledger.

        Uses engine.render() for each shot.
        Stops on first failure unless continue_on_error=True.
        """
        from engine import CinematicShotEngine

        engine = CinematicShotEngine()
        total = len(self.scene.shots)

        for i, entry in enumerate(self.scene.shots):
            print(f"\n[{i+1}/{total}] {entry.shot_id}...", end=" ", flush=True)
            self.start_shot(entry.shot_id)

            # Check input exists
            if entry.status == ShotStatus.PENDING:
                if not Path(entry.input_image).exists():
                    self.skip_shot(entry.shot_id, f"Input not found: {entry.input_image}")
                    print(f"⏭️  SKIPPED (input not found)")
                    continue

            # Render — convert aspect_ratio to (width, height)
            ratio_wh = {
                "9:16": (1080, 1920),
                "16:9": (1920, 1080),
                "1:1": (1080, 1080),
                "4:3": (1440, 1080),
                "3:4": (1080, 1440),
            }
            w, h = ratio_wh.get(entry.aspect_ratio, (1080, 1920))

            # Ensure output dir exists
            out_path = Path(entry.output_file)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            wall_start = time.perf_counter()
            try:
                result = engine.render(
                    input_image=entry.input_image,
                    output_path=entry.output_file,
                    preset_name=entry.preset,
                    duration=entry.duration_sec,
                    fps=entry.fps,
                    width=w,
                    height=h,
                    camera_override=entry.camera_override,
                )
            except Exception as e:
                result = {
                    "status": "failed",
                    "error": f"Exception: {e}",
                    "method": None,
                }

            wall_end = time.perf_counter()
            result["render_time_sec"] = wall_end - wall_start
            self.complete_shot(entry.shot_id, result)

            if result.get("status") == "success":
                size = result.get("file_size_mb", "?")
                time_s = result.get("render_time_sec", "?")
                method = result.get("method", "?")
                print(f"✅ {method} | {time_s:.1f}s | {size}MB")
            else:
                err = result.get("error", "?")
                print(f"❌ {err[:60]}")
                if not continue_on_error:
                    break

        self.scene.completed_at = datetime.now().isoformat()
        self._save()

    # -------------------------------------------------------------------------
    # Output
    # -------------------------------------------------------------------------

    def _save(self):
        """Write ledger to disk atomically."""
        import tempfile
        tmp = self.ledger_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self.scene), indent=2))
        tmp.replace(self.ledger_path)

    def _get_entry(self, shot_id: str) -> Optional[ShotLedgerEntry]:
        for e in self.scene.shots:
            if e.shot_id == shot_id:
                return e
        return None

    def print_summary(self):
        """Print a human-readable summary."""
        s = self.scene
        print()
        print("=" * 60)
        print(f"  SCENE RENDER LEDGER: {s.project}")
        print("=" * 60)
        print(f"  {'SHOT ID':12s} {'STATUS':10s} {'PRESET':18s} {'TIME':8s} {'SIZE':8s} {'METHOD':10s}")
        print(f"  {'-'*12:12s} {'-'*10:10s} {'-'*18:18s} {'-'*8:8s} {'-'*8:8s} {'-'*10:10s}")

        for e in s.shots:
            status_icon = {
                ShotStatus.SUCCESS: "✅",
                ShotStatus.FAILED:  "❌",
                ShotStatus.PENDING: "⏸",
                ShotStatus.RENDERING: "⏳",
                ShotStatus.SKIPPED: "⏭",
            }.get(e.status, "?")

            time_s = f"{e.render_time_sec:.1f}s" if e.render_time_sec else "—"
            size_s = f"{e.file_size_mb:.2f}MB" if e.file_size_mb else "—"
            print(
                f"  {status_icon} {e.shot_id:10s} "
                f"{e.status:10s} "
                f"{e.preset:18s} "
                f"{time_s:8s} "
                f"{size_s:8s} "
                f"{e.method or '—':10s}"
            )
            if e.error and e.status == ShotStatus.FAILED:
                print(f"         ❌ {e.error[:55]}")

        print(f"  {'-'*12:12s} {'-'*10:10s} {'-'*18:18s} {'-'*8:8s} {'-'*8:8s} {'-'*10:10s}")
        print(f"  Total: {s.total_shots} | ✅ {s.success_count} | ❌ {s.failed_count} | ⏭️ {s.skipped_count}")
        print(f"  Total render time: {s.total_render_time_sec:.1f}s")
        print(f"  Ledger: {self.ledger_path}")
        print("=" * 60)

    def get_scene_manifest_dict(self) -> dict:
        """Return the full ledger as a dict for JSON export."""
        return asdict(self.scene)


# =============================================================================
# STANDALONE
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Show scene render ledger")
    parser.add_argument("ledger", help="Path to scene_render_ledger.json")
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    if not ledger_path.exists():
        print(f"Ledger not found: {ledger_path}")
        exit(1)

    data = json.loads(ledger_path.read_text())
    scene = SceneLedger(**data)

    print(f"\nScene: {scene.project}")
    print(f"Status: {scene.success_count}/{scene.total_shots} shots successful")

    for e in scene.shots:
        icon = {"success": "✅", "failed": "❌", "pending": "⏸", "skipped": "⏭"}.get(e.status, "?")
        time_s = f"{e.render_time_sec:.1f}s" if e.render_time_sec else "—"
        size_s = f"{e.file_size_mb:.2f}MB" if e.file_size_mb else "—"
        print(f"  {icon} [{e.shot_id}] {e.preset:18s} {time_s:8s} {size_s:8s} {e.method or '—':10s}")
        if e.error:
            print(f"      ❌ {e.error[:60]}")
