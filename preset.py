"""
preset.py — Preset loader and Preset class.

Separated to avoid circular imports between engine.py and motion.py.
"""

import json
from pathlib import Path


class Preset:
    """Loaded preset with typed accessors."""

    def __init__(self, data: dict):
        self._d = data
        self.name = data["name"]
        self.duration = data.get("duration_sec", 5.0)
        self.fps = data.get("fps", 24)
        self.aspect_ratio = data.get("aspect_ratio", "9:16")

    @property
    def cam(self) -> dict:
        return self._d.get("camera", {})

    @property
    def motion(self) -> dict:
        return self._d.get("motion", {})

    @property
    def lighting(self) -> dict:
        return self._d.get("lighting", {})

    @property
    def timing(self) -> dict:
        return self._d.get("timing", {})

    def move(self) -> str:
        return self.cam.get("move", "static")

    def easing(self) -> str:
        return self.cam.get("easing", "linear")

    @property
    def zoom_start(self) -> float:
        return self.cam.get("zoom_start", 1.0)

    @property
    def zoom_end(self) -> float:
        return self.cam.get("zoom_end", self.zoom_start)

    @property
    def x_start(self) -> float:
        return self.cam.get("x_start", 0.5)

    @property
    def x_end(self) -> float:
        return self.cam.get("x_end", self.x_start)

    @property
    def y_start(self) -> float:
        return self.cam.get("y_start", 0.5)

    @property
    def y_end(self) -> float:
        return self.cam.get("y_end", self.y_start)

    @property
    def rot_start(self) -> float:
        return self.cam.get("rotation_start_deg", 0.0)

    @property
    def rot_end(self) -> float:
        return self.cam.get("rotation_end_deg", self.rot_start)

    @property
    def hold_start_dur(self) -> float:
        return self.timing.get("hold_start_sec", 0.0)

    @property
    def move_start(self) -> float:
        return self.timing.get("main_move_start_sec", 0.0)

    @property
    def move_end(self) -> float:
        return self.timing.get("main_move_end_sec", self.duration)

    @property
    def hold_end_dur(self) -> float:
        return self.timing.get("hold_end_sec", 0.0)

    @property
    def micro_shake(self) -> float:
        return self.motion.get("micro_shake", 0.0)

    @property
    def breathing(self) -> float:
        return self.motion.get("breathing", 0.0)

    @property
    def parallax(self) -> float:
        return self.motion.get("parallax_strength", 0.0)

    @property
    def flicker(self) -> float:
        return self.lighting.get("flicker", 0.0)

    @property
    def vignette_pulse(self) -> float:
        return self.lighting.get("vignette_pulse", 0.0)

    @property
    def glow_drift(self) -> float:
        return self.lighting.get("glow_drift", 0.0)


def load_preset(name: str) -> Preset:
    """Load a preset JSON file by name."""
    path = Path(__file__).parent / "presets" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Preset not found: {name}")
    return Preset(json.loads(path.read_text()))


def list_presets() -> list[str]:
    """Return all available preset names."""
    preset_dir = Path(__file__).parent / "presets"
    return sorted(
        p.stem for p in preset_dir.glob("*.json")
        if p.stem not in ("PRESET_SPEC",)
    )
