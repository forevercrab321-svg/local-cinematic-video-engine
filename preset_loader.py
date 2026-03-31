"""
preset_loader.py — PRESET_SCHEMA v1 loader with strict validation
Strict loading:
  - Required fields enforced, no silent defaults
  - Unknown fields → warning (not error)
  - Type checking on all numeric fields
  - Value range validation
  - Human-readable error messages

Usage:
    from preset_loader import PresetLoader
    loader = PresetLoader("presets/")
    preset = loader.load("suspense_push")  # raises on error
    issues = loader.validate("suspense_push")  # returns issues without raising
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# SCHEMA SPEC — exactly what PRESET_SPEC.md defines
# =============================================================================

REQUIRED_TOP = {"name", "duration_sec", "fps", "aspect_ratio", "camera", "motion", "lighting", "timing"}

CAMERA_REQUIRED = {"move", "zoom_start", "zoom_end", "x_start", "x_end", "y_start", "y_end",
                   "rotation_start_deg", "rotation_end_deg", "easing"}
CAMERA_OPTIONAL = set()

MOTION_REQUIRED = {"micro_shake", "breathing", "parallax_strength"}
MOTION_OPTIONAL = set()

LIGHTING_REQUIRED = {"flicker", "vignette_pulse", "glow_drift"}
LIGHTING_OPTIONAL = set()

TIMING_REQUIRED = {"hold_start_sec", "main_move_start_sec", "main_move_end_sec", "hold_end_sec"}
TIMING_OPTIONAL = set()

OUTPUT_REQUIRED = {"codec", "pix_fmt"}
OUTPUT_OPTIONAL = set()

VALID_MOVES = {"static", "push_in", "pull_out", "shake", "hesitate", "snap"}
VALID_EASINGS = {"linear", "ease_in", "ease_out", "ease_in_out", "sudden", "hold", "hesitate"}
VALID_ASPECT_RATIOS = {"9:16", "16:9", "1:1", "4:3", "3:4"}


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: str          # "error" | "warning" | "info"
    path: str              # e.g. "camera.zoom_start"
    message: str
    value: any = None


@dataclass
class LoadedPreset:
    """Fully loaded + validated preset."""
    raw: dict
    name: str
    path: Path
    issues: list[ValidationIssue] = field(default_factory=list)
    schema_version: str = "v1"

    # Typed accessors
    @property
    def duration(self) -> float:
        return self.raw["duration_sec"]

    @property
    def fps(self) -> int:
        return self.raw["fps"]

    @property
    def aspect_ratio(self) -> str:
        return self.raw["aspect_ratio"]

    @property
    def cam(self) -> dict:
        return self.raw.get("camera", {})

    @property
    def motion(self) -> dict:
        return self.raw.get("motion", {})

    @property
    def lighting(self) -> dict:
        return self.raw.get("lighting", {})

    @property
    def timing(self) -> dict:
        return self.raw.get("timing", {})

    # Camera
    def move(self) -> str:      return self.cam.get("move", "static")
    def easing(self) -> str:    return self.cam.get("easing", "linear")
    def zoom_start(self) -> float:  return float(self.cam.get("zoom_start", 1.0))
    def zoom_end(self) -> float:     return float(self.cam.get("zoom_end", self.zoom_start()))
    def x_start(self) -> float:     return float(self.cam.get("x_start", 0.5))
    def x_end(self) -> float:       return float(self.cam.get("x_end", self.x_start()))
    def y_start(self) -> float:     return float(self.cam.get("y_start", 0.5))
    def y_end(self) -> float:       return float(self.cam.get("y_end", self.y_start()))
    def rot_start(self) -> float:   return float(self.cam.get("rotation_start_deg", 0.0))
    def rot_end(self) -> float:     return float(self.cam.get("rotation_end_deg", self.rot_start()))

    # Motion
    @property def micro_shake(self):    return self.motion.get("micro_shake", 0.0)
    @property def breathing(self):      return self.motion.get("breathing", 0.0)
    @property def parallax(self):       return self.motion.get("parallax_strength", 0.0)

    # Lighting
    @property def flicker(self):         return self.lighting.get("flicker", 0.0)
    @property def vignette_pulse(self):  return self.lighting.get("vignette_pulse", 0.0)
    @property def glow_drift(self):      return self.lighting.get("glow_drift", 0.0)

    # Timing
    @property def hold_start_dur(self): return self.timing.get("hold_start_sec", 0.0)
    @property def move_start(self):     return self.timing.get("main_move_start_sec", 0.0)
    @property def move_end(self):       return self.timing.get("main_move_end_sec", self.duration)
    @property def hold_end_dur(self):   return self.timing.get("hold_end_sec", 0.0)

    # Computed
    @property
    def total_duration(self) -> float:
        return (self.hold_start_dur
                + (self.move_end - self.move_start)
                + self.hold_end_dur)

    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

    def __repr__(self):
        return f"<LoadedPreset {self.name} ({len(self.issues)} issues)>"


# =============================================================================
# PRESET LOADER
# =============================================================================

class PresetLoadError(Exception):
    """Raised when a preset fails to load or validate."""
    def __init__(self, preset_name: str, issues: list[ValidationIssue]):
        error_msgs = [f"  [{i.severity}] {i.path}: {i.message}" for i in issues if i.severity == "error"]
        super().__init__(f"Preset '{preset_name}' has {len(error_msgs)} error(s):\n" + "\n".join(error_msgs))
        self.preset_name = preset_name
        self.issues = issues


class PresetLoader:
    """
    Strict preset loader with validation.

    load(name)      → raises PresetLoadError if invalid
    validate(name)  → returns list of ValidationIssue (doesn't raise)
    list_presets()  → returns available preset names
    load_all()      → loads all, returns {name: LoadedPreset}
    """

    def __init__(self, preset_dir: str = None):
        if preset_dir is None:
            preset_dir = Path(__file__).parent / "presets"
        self.preset_dir = Path(preset_dir)

    def _preset_path(self, name: str) -> Path:
        return self.preset_dir / f"{name}.json"

    # -------------------------------------------------------------------------
    # Core validation
    # -------------------------------------------------------------------------

    def _validate_raw(self, name: str, raw: dict) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        # Top-level required fields
        for field_name in REQUIRED_TOP:
            if field_name not in raw:
                issues.append(ValidationIssue(
                    "error", field_name,
                    f"Missing required top-level field: '{field_name}'"
                ))

        if "camera" not in raw or "motion" not in raw:
            # Can't continue validating nested fields
            return issues

        # Top-level types
        def check_type(path, val, expected_type, extra_info=""):
            if val is None:
                return
            if not isinstance(val, expected_type):
                issues.append(ValidationIssue(
                    "error", path,
                    f"Must be {expected_type.__name__}{extra_info}, got {type(val).__name__}: {repr(val)[:50]}",
                    val
                ))

        check_type("duration_sec", raw.get("duration_sec"), (int, float), " (seconds)")
        check_type("fps", raw.get("fps"), int, " (integer)")
        check_type("aspect_ratio", raw.get("aspect_ratio"), str)
        check_type("camera", raw.get("camera"), dict)
        check_type("motion", raw.get("motion"), dict)
        check_type("lighting", raw.get("lighting"), dict)
        check_type("timing", raw.get("timing"), dict)

        # Duration range
        dur = raw.get("duration_sec")
        if dur is not None and (dur <= 0 or dur > 120):
            issues.append(ValidationIssue(
                "warning", "duration_sec",
                f"Duration {dur}s is unusual (0 < x ≤ 120 recommended)", dur
            ))

        # FPS range
        fps = raw.get("fps")
        if fps is not None and (fps <= 0 or fps > 60):
            issues.append(ValidationIssue(
                "error", "fps",
                f"FPS {fps} out of range (1-60)", fps
            ))

        # Aspect ratio
        ar = raw.get("aspect_ratio")
        if ar and ar not in VALID_ASPECT_RATIOS:
            issues.append(ValidationIssue(
                "warning", "aspect_ratio",
                f"Non-standard aspect_ratio '{ar}'. Valid: {VALID_ASPECT_RATIOS}", ar
            ))

        # Unknown top-level keys
        known_top = REQUIRED_TOP | {"description", "output"}
        for key in raw:
            if key not in known_top:
                issues.append(ValidationIssue(
                    "info", key,
                    f"Unknown top-level field (ignored by engine)", raw[key]
                ))

        # --- CAMERA ---
        cam = raw.get("camera", {})
        for field_name in CAMERA_REQUIRED:
            if field_name not in cam:
                issues.append(ValidationIssue(
                    "error", f"camera.{field_name}",
                    f"Missing required camera field: '{field_name}'"
                ))

        # Camera types
        check_type("camera.zoom_start", cam.get("zoom_start"), (int, float))
        check_type("camera.zoom_end",   cam.get("zoom_end"), (int, float))
        check_type("camera.x_start",    cam.get("x_start"), (int, float))
        check_type("camera.x_end",      cam.get("x_end"), (int, float))
        check_type("camera.y_start",    cam.get("y_start"), (int, float))
        check_type("camera.y_end",      cam.get("y_end"), (int, float))
        check_type("camera.rotation_start_deg", cam.get("rotation_start_deg"), (int, float))
        check_type("camera.rotation_end_deg",   cam.get("rotation_end_deg"), (int, float))

        # Camera value ranges
        for key in ["zoom_start", "zoom_end"]:
            v = cam.get(key)
            if v is not None and (v < 0.5 or v > 2.0):
                issues.append(ValidationIssue(
                    "warning", f"camera.{key}",
                    f"Zoom {v} is extreme (0.5-2.0 recommended)", v
                ))

        for key in ["x_start", "x_end", "y_start", "y_end"]:
            v = cam.get(key)
            if v is not None and (v < 0 or v > 1):
                issues.append(ValidationIssue(
                    "error", f"camera.{key}",
                    f"{key} must be 0.0-1.0, got {v}", v
                ))

        # Camera move
        move = cam.get("move")
        if move and move not in VALID_MOVES:
            issues.append(ValidationIssue(
                "error", "camera.move",
                f"Unknown camera move: '{move}'. Valid: {VALID_MOVES}", move
            ))

        # Camera easing
        easing = cam.get("easing")
        if easing and easing not in VALID_EASINGS:
            issues.append(ValidationIssue(
                "error", "camera.easing",
                f"Unknown easing: '{easing}'. Valid: {VALID_EASINGS}", easing
            ))

        # Unknown camera keys
        cam_known = CAMERA_REQUIRED | CAMERA_OPTIONAL
        for key in cam:
            if key not in cam_known:
                issues.append(ValidationIssue(
                    "info", f"camera.{key}",
                    f"Unknown camera field (ignored)", cam[key]
                ))

        # --- MOTION ---
        mot = raw.get("motion", {})
        for field_name in MOTION_REQUIRED:
            if field_name not in mot:
                issues.append(ValidationIssue(
                    "error", f"motion.{field_name}",
                    f"Missing required motion field: '{field_name}'"
                ))

        for key in MOTION_REQUIRED:
            v = mot.get(key)
            if v is not None and not isinstance(v, (int, float)):
                issues.append(ValidationIssue(
                    "error", f"motion.{key}",
                    f"Must be numeric, got {type(v).__name__}", v
                ))
            if v is not None and v < 0:
                issues.append(ValidationIssue(
                    "error", f"motion.{key}",
                    f"Cannot be negative: {v}", v
                ))

        # --- LIGHTING ---
        lit = raw.get("lighting", {})
        for field_name in LIGHTING_REQUIRED:
            if field_name not in lit:
                issues.append(ValidationIssue(
                    "error", f"lighting.{field_name}",
                    f"Missing required lighting field: '{field_name}'"
                ))

        for key in LIGHTING_REQUIRED:
            v = lit.get(key)
            if v is not None and not isinstance(v, (int, float)):
                issues.append(ValidationIssue(
                    "error", f"lighting.{key}",
                    f"Must be numeric, got {type(v).__name__}", v
                ))
            if v is not None and v < 0:
                issues.append(ValidationIssue(
                    "error", f"lighting.{key}",
                    f"Cannot be negative: {v}", v
                ))

        # --- TIMING ---
        tim = raw.get("timing", {})
        for field_name in TIMING_REQUIRED:
            if field_name not in tim:
                issues.append(ValidationIssue(
                    "error", f"timing.{field_name}",
                    f"Missing required timing field: '{field_name}'"
                ))

        for key in TIMING_REQUIRED:
            v = tim.get(key)
            if v is not None and not isinstance(v, (int, float)):
                issues.append(ValidationIssue(
                    "error", f"timing.{key}",
                    f"Must be numeric (seconds), got {type(v).__name__}", v
                ))

        # Timing consistency
        dur = raw.get("duration_sec", 0)
        ms = tim.get("main_move_start_sec", 0)
        me = tim.get("main_move_end_sec", dur)
        if me > dur and dur > 0:
            issues.append(ValidationIssue(
                "error", "timing.main_move_end_sec",
                f"main_move_end_sec ({me}) > duration_sec ({dur})", me
            ))

        # --- OUTPUT ---
        out = raw.get("output", {})
        for field_name in OUTPUT_REQUIRED:
            if field_name not in out:
                issues.append(ValidationIssue(
                    "warning", f"output.{field_name}",
                    f"Missing optional output field: '{field_name}'", out.get(field_name)
                ))

        return issues

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def list_presets(self) -> list[str]:
        """List available preset names (excluding SPEC file)."""
        return sorted(
            p.stem for p in self.preset_dir.glob("*.json")
            if p.stem not in ("PRESET_SPEC",)
        )

    def validate(self, name: str) -> list[ValidationIssue]:
        """Validate a preset without raising. Returns issues."""
        path = self._preset_path(name)
        if not path.exists():
            return [ValidationIssue("error", "file",
                                    f"Preset file not found: {path}")]

        try:
            raw = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            return [ValidationIssue("error", "file",
                                    f"Invalid JSON: {e}")]

        return self._validate_raw(name, raw)

    def load(self, name: str, strict: bool = True) -> LoadedPreset:
        """
        Load and validate a preset.

        Args:
            name: Preset name (without .json)
            strict: If True, raises PresetLoadError on any error.
                    If False, returns LoadedPreset with issues (doesn't raise).

        Returns:
            LoadedPreset

        Raises:
            PresetLoadError: if strict=True and preset has errors
        """
        issues = self.validate(name)
        errors = [i for i in issues if i.severity == "error"]

        path = self._preset_path(name)
        raw = json.loads(path.read_text()) if path.exists() else {}

        loaded = LoadedPreset(
            raw=raw,
            name=name,
            path=path,
            issues=issues,
        )

        if strict and errors:
            raise PresetLoadError(name, issues)

        return loaded

    def load_all(self, strict: bool = False) -> dict[str, LoadedPreset]:
        """Load all presets. Returns {name: LoadedPreset}."""
        results = {}
        for name in self.list_presets():
            results[name] = self.load(name, strict=strict)
        return results

    def print_validation_report(self, name: str):
        """Print a human-readable validation report."""
        issues = self.validate(name)
        errors   = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        infos    = [i for i in issues if i.severity == "info"]

        path = self._preset_path(name)
        exists = path.exists()

        print(f"\n{'='*50}")
        print(f"  Preset: {name}")
        print(f"  File:   {path}")
        print(f"  Exists: {exists}")
        print(f"{'='*50}")

        if not exists:
            print("  ❌ File not found")
            return

        if not issues:
            print("  ✅ No issues — preset is valid")
            return

        if errors:
            print(f"  ❌ {len(errors)} error(s):")
            for i in errors:
                print(f"    [{i.severity}] {i.path}")
                print(f"         {i.message}")
                if i.value is not None:
                    print(f"         value: {i.value!r}")

        if warnings:
            print(f"  ⚠️  {len(warnings)} warning(s):")
            for i in warnings:
                print(f"    {i.path}: {i.message}")

        if infos:
            print(f"  ℹ️  {len(infos)} info(s):")
            for i in infos:
                print(f"    {i.path}: {i.message}")

        print(f"{'='*50}")


# =============================================================================
# STANDALONE CLI
# =============================================================================

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="Preset schema validator")
    parser.add_argument("name", nargs="?", help="Preset name (or 'all')")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on error")
    parser.add_argument("--list", action="store_true", help="List all presets")
    args = parser.parse_args()

    loader = PresetLoader()

    if args.list or not args.name:
        print("Available presets:")
        for n in loader.list_presets():
            print(f"  {n}")
        sys.exit(0)

    if args.name == "all":
        all_issues = {}
        for name in loader.list_presets():
            issues = loader.validate(name)
            all_issues[name] = issues
        errors = sum(1 for v in all_issues.values() for i in v if i.severity == "error")
        print(f"\nValidation: {len(all_issues)} presets, {errors} total errors")
        for name, issues in sorted(all_issues.items()):
            errs = [i for i in issues if i.severity == "error"]
            icon = "❌" if errs else "✅"
            print(f"  {icon} {name}: {len(issues)} issue(s) ({len(errs)} errors)")
        sys.exit(1 if errors else 0)

    loader.print_validation_report(args.name)

    issues = loader.validate(args.name)
    errors = [i for i in issues if i.severity == "error"]
    sys.exit(1 if (args.strict and errors) else 0)
