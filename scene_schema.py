"""
scene_schema.py — Scene manifest schema definition

Defines what a valid scene_manifest.json looks like and how to validate it.

Usage:
    from scene_schema import SceneManifest, SceneValidationError
    manifest = SceneManifest.from_file("scene_manifest.json")
    manifest.validate()  # raises SceneValidationError on error
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


# =============================================================================
# GOLDEN PRESETS (locked at 4)
# =============================================================================



# =============================================================================
# SHOT SCHEMA
# =============================================================================

SHOT_REQUIRED = {
    "shot_id",
    "input_image",
    "output_file",
    "preset",
    "duration_sec",
}

SHOT_OPTIONAL = {
    "fps": 24,
    "aspect_ratio": "9:16",
    "camera_override": None,
    "camera_intensity": 1.0,
    "caption_text": None,
    "dialogue": None,
    "note": None,
    "risk_level": "safe",     # safe | caution | avoid
    "shot_type": "medium",     # hero_front | face_closeup | medium | reaction | POV
}


# =============================================================================
# SCENE MANIFEST SCHEMA
# =============================================================================

SCENE_REQUIRED = {
    "project",
    "shots",
}

SCENE_OPTIONAL = {
    "scene_manifest_version": "1.0",
    "description": None,
    "total_duration_sec": None,  # computed from shots
    "fps": 24,
    "aspect_ratio": "9:16",
    "render_config": {
        "codec": "h264",
        "pix_fmt": "yuv420p",
        "quality": "high",
        "output_dir": "./renders/",
    },
    "editing_notes": {},
}


# =============================================================================
# VALIDATION ERROR
# =============================================================================

class SceneValidationError(Exception):
    def __init__(self, errors: list[str]):
        msg = "\n".join(f"  ❌ {e}" for e in errors)
        super().__init__(f"Scene manifest validation failed:\n{msg}")
        self.errors = errors


# =============================================================================
# SCENE SHOT
# =============================================================================

@dataclass
class SceneShot:
    """A single shot within a scene manifest."""
    shot_id: str
    input_image: str
    output_file: str
    preset: str
    duration_sec: float

    # Optional fields
    fps: int = 24
    aspect_ratio: str = "9:16"
    camera_override: Optional[str] = None
    camera_intensity: float = 1.0
    caption_text: Optional[str] = None
    dialogue: Optional[str] = None
    note: Optional[str] = None
    risk_level: str = "safe"
    shot_type: str = "medium"

    # Resolved at load time
    resolved_input: Optional[Path] = None
    resolved_output: Optional[Path] = None

    @classmethod
    def from_dict(cls, data: dict) -> "SceneShot":
        """Create from dict, filling defaults for optional fields."""
        d = dict(data)  # copy
        # Apply defaults
        for k, v in SHOT_OPTIONAL.items():
            if k not in d:
                d[k] = v
        return cls(
            shot_id=d["shot_id"],
            input_image=d["input_image"],
            output_file=d["output_file"],
            preset=d["preset"],
            duration_sec=float(d["duration_sec"]),
            fps=int(d.get("fps", 24)),
            aspect_ratio=d.get("aspect_ratio", "9:16"),
            camera_override=d.get("camera_override"),
            camera_intensity=float(d.get("camera_intensity", 1.0)),
            caption_text=d.get("caption_text"),
            dialogue=d.get("dialogue"),
            note=d.get("note"),
            risk_level=d.get("risk_level", "safe"),
            shot_type=d.get("shot_type", "medium"),
        )

    def to_dict(self) -> dict:
        d = {
            "shot_id": self.shot_id,
            "input_image": self.input_image,
            "output_file": self.output_file,
            "preset": self.preset,
            "duration_sec": self.duration_sec,
            "fps": self.fps,
            "aspect_ratio": self.aspect_ratio,
            "camera_override": self.camera_override,
            "camera_intensity": self.camera_intensity,
            "risk_level": self.risk_level,
            "shot_type": self.shot_type,
        }
        if self.caption_text:
            d["caption_text"] = self.caption_text
        if self.dialogue:
            d["dialogue"] = self.dialogue
        if self.note:
            d["note"] = self.note
        return d


# =============================================================================
# SCENE MANIFEST
# =============================================================================

@dataclass
class SceneManifest:
    """
    A complete scene manifest with typed accessors and validation.
    """
    project: str
    shots: list[SceneShot]
    scene_manifest_version: str = "1.0"
    description: Optional[str] = None
    fps: int = 24
    aspect_ratio: str = "9:16"
    render_config: dict = field(default_factory=dict)
    editing_notes: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str) -> "SceneManifest":
        """
        Load a scene_manifest.json file.
        Resolves relative paths and sets defaults.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Scene manifest not found: {path}")

        raw = json.loads(p.read_text())
        manifest_dir = p.parent.resolve()

        shots = []
        for i, shot_data in enumerate(raw.get("shots", [])):
            shot = SceneShot.from_dict(shot_data)
            # Resolve paths relative to manifest dir
            img_path = Path(shot.input_image)
            if not img_path.is_absolute():
                img_path = (manifest_dir.parent / img_path).resolve()
            shot.resolved_input = img_path

            out_path = Path(shot.output_file)
            if not out_path.is_absolute():
                out_path = (manifest_dir / out_path).resolve()
            shot.resolved_output = out_path

            shots.append(shot)

        return cls(
            project=raw["project"],
            shots=shots,
            scene_manifest_version=raw.get("scene_manifest_version", "1.0"),
            description=raw.get("description"),
            fps=raw.get("fps", 24),
            aspect_ratio=raw.get("aspect_ratio", "9:16"),
            render_config=raw.get("render_config", {}),
            editing_notes=raw.get("editing_notes", {}),
            raw=raw,
        )

    @property
    def total_duration_sec(self) -> float:
        return sum(s.duration_sec for s in self.shots)

    @property
    def total_shots(self) -> int:
        return len(self.shots)

    def validate(self) -> list[str]:
        """
        Validate the scene manifest.
        Returns list of errors (empty = valid).
        Does NOT raise.
        """
        errors: list[str] = []

        # Top-level required
        if not self.project:
            errors.append("Missing required field: 'project'")
        if not self.shots:
            errors.append("Missing or empty 'shots' array")
        if not isinstance(self.shots, list):
            errors.append("'shots' must be an array")

        if self.scene_manifest_version != "1.0":
            errors.append(
                f"Unknown scene_manifest_version: '{self.scene_manifest_version}' "
                f"(expected '1.0')"
            )

        # Validate each shot
        for i, shot in enumerate(self.shots):
            if not shot.shot_id:
                errors.append(f"Shot[{i}]: missing 'shot_id'")
            if not shot.input_image:
                errors.append(f"Shot[{i}] ({shot.shot_id}): missing 'input_image'")
            elif not shot.resolved_input or not shot.resolved_input.exists():
                errors.append(
                    f"Shot[{i}] ({shot.shot_id}): "
                    f"input image not found: {shot.input_image}"
                )
            if not shot.output_file:
                errors.append(f"Shot[{i}] ({shot.shot_id}): missing 'output_file'")
            if not shot.preset:
                errors.append(f"Shot[{i}] ({shot.shot_id}): missing 'preset'")
            elif shot.preset not in GOLDEN_PRESETS:
                errors.append(
                    f"Shot[{i}] ({shot.shot_id}): "
                    f"preset '{shot.preset}' not in golden set. "
                    f"Valid presets: {sorted(GOLDEN_PRESETS)}"
                )
            if shot.duration_sec <= 0:
                errors.append(
                    f"Shot[{i}] ({shot.shot_id}): "
                    f"duration_sec must be > 0, got {shot.duration_sec}"
                )

        return errors

    def validate_or_raise(self):
        """Validate and raise SceneValidationError if invalid."""
        from preset import load_preset  # avoid circular import
        errors = self.validate()
        if errors:
            raise SceneValidationError(errors)

    def summary(self) -> str:
        lines = [
            f"Scene: {self.project}",
            f"  Version: {self.scene_manifest_version}",
            f"  Shots: {self.total_shots}",
            f"  Total duration: {self.total_duration_sec}s",
            f"  Aspect ratio: {self.aspect_ratio} @ {self.fps}fps",
            "",
            f"  Shot list:",
        ]
        for s in self.shots:
            lines.append(
                f"    [{s.shot_id}] {s.preset} | {s.duration_sec}s "
                f"| risk={s.risk_level} | {s.input_image}"
            )
        return "\n".join(lines)


# =============================================================================
# STANDALONE CLI
# =============================================================================

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="Validate scene manifest")
    parser.add_argument("manifest", help="Path to scene_manifest.json")
    args = parser.parse_args()

    try:
        manifest = SceneManifest.from_file(args.manifest)
        print(manifest.summary())
        errors = manifest.validate()
        if errors:
            print(f"\n❌ Validation failed ({len(errors)} errors):")
            for e in errors:
                print(f"  {e}")
            sys.exit(1)
        else:
            print(f"\n✅ Valid scene manifest ({len(manifest.shots)} shots)")
            sys.exit(0)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except SceneValidationError as e:
        print(str(e))
        sys.exit(1)
