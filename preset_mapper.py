"""
preset_mapper.py — Director semantics → engine parameters

Maps a LoadedPreset (human-readable preset) into the exact technical
parameters that the render engine uses.

This is the SINGLE SOURCE OF TRUTH for how presets translate to renders.

Director concept          →  Engine parameter
─────────────────────────────────────────────────────────
"slow dread build"         →  hold_start=1.2s, easing=ease_in
"sudden slam"              →  easing=ease_out, zoom_delta large
"eye-level tension"        →  x/y not moving (subject centered)
"push into face"            →  zoom_end=1.12, close-up framing
"isolated, receding"        →  pull_out, zoom_end=0.91
"handheld tremor"           →  micro_shake=0.022
"the beat lands"           →  hold_start=1.0, large zoom_delta after beat
"dreamlike float"          →  breathing=0.015, glow_drift=0.05
"recognition moment"        →  hold_start=1.8, long hold before push
"micro face shift"         →  zoom_end=1.015, x pan micro-movement

Usage:
    from preset_mapper import PresetMapper, EngineParams
    mapper = PresetMapper()
    params = mapper.map(loaded_preset)  # → EngineParams
    print(params.summary())
"""

from dataclasses import dataclass, field
from typing import Optional
from preset_loader import LoadedPreset


# =============================================================================
# ENGINE PARAMS — the exact parameters the engine uses
# =============================================================================

@dataclass
class EngineParams:
    """
    Fully resolved engine parameters from a preset.
    These are the exact values passed to MotionRenderer.
    """
    # Identity
    preset_name: str
    schema_version: str = "v1"

    # Resolution / timing
    duration: float
    fps: int
    aspect_ratio: str
    resolution: tuple[int, int] = (1080, 1920)

    # Camera
    move: str
    zoom_start: float
    zoom_end: float
    x_start: float
    x_end: float
    y_start: float
    y_end: float
    rot_start_deg: float
    rot_end_deg: float
    easing: str

    # Motion effects
    micro_shake: float
    breathing: float
    parallax_strength: float

    # Lighting
    flicker: float
    vignette_pulse: float
    glow_drift: float

    # Timing (seconds)
    hold_start_sec: float
    main_move_start_sec: float
    main_move_end_sec: float
    hold_end_sec: float

    # Render routing hints
    render_path: str = "PIL"       # "static_ffmpeg" | "zoompan" | "PIL"
    effects_applied: list[str] = field(default_factory=list)
    effects_skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_motion(self) -> bool:
        return (
            self.zoom_start != self.zoom_end
            or self.x_start != self.x_end
            or self.y_start != self.y_end
            or self.rot_start_deg != self.rot_end_deg
            or self.micro_shake > 0
            or self.breathing > 0
        )

    @property
    def can_use_zoompan(self) -> bool:
        """True if preset can use fast zoompan path."""
        if self.micro_shake > 0 or self.breathing > 0:
            return False
        if self.easing not in ("linear", "hold"):
            return False
        if abs(self.x_start - self.x_end) > 0.01 or abs(self.y_start - self.y_end) > 0.01:
            return False
        if abs(self.rot_start_deg - self.rot_end_deg) > 0.1:
            return False
        if self.hold_start_sec > 0.1:
            return False
        if self.zoom_start == self.zoom_end:
            return False
        return True

    def summary(self) -> str:
        lines = [
            f"Preset: {self.preset_name}",
            f"  Schema: {self.schema_version}",
            f"  Duration: {self.duration}s | FPS: {self.fps} | Ratio: {self.aspect_ratio}",
            f"  Render: {self.render_path}",
            "",
            f"  Camera:",
            f"    move:    {self.move}",
            f"    zoom:    {self.zoom_start} → {self.zoom_end}  (delta={self.zoom_end - self.zoom_start:+.3f})",
            f"    pan_x:   {self.x_start} → {self.x_end}",
            f"    pan_y:   {self.y_start} → {self.y_end}",
            f"    rotation: {self.rot_start_deg}° → {self.rot_end_deg}°",
            f"    easing:  {self.easing}",
            "",
            f"  Motion:",
            f"    micro_shake:      {self.micro_shake}",
            f"    breathing:         {self.breathing}",
            f"    parallax_strength: {self.parallax_strength}",
            "",
            f"  Lighting:",
            f"    flicker:        {self.flicker}",
            f"    vignette_pulse: {self.vignette_pulse}",
            f"    glow_drift:     {self.glow_drift}",
            "",
            f"  Timing:",
            f"    hold_start={self.hold_start_sec}s | move={self.main_move_start_sec}s→{self.main_move_end_sec}s | hold_end={self.hold_end_sec}s",
            "",
            f"  Effects applied:  {self.effects_applied}",
            f"  Effects skipped:  {self.effects_skipped}",
        ]
        if self.warnings:
            lines.append(f"  Warnings: {self.warnings}")
        return "\n".join(lines)

    def to_manifest(self) -> dict:
        """Convert to render manifest dict."""
        return {
            "preset_name": self.preset_name,
            "schema_version": self.schema_version,
            "timeline_applied": {
                "hold_start_sec": self.hold_start_sec,
                "main_move_start_sec": self.main_move_start_sec,
                "main_move_end_sec": self.main_move_end_sec,
                "hold_end_sec": self.hold_end_sec,
            },
            "camera_params_applied": {
                "move": self.move,
                "zoom_start": self.zoom_start,
                "zoom_end": self.zoom_end,
                "x_start": self.x_start,
                "x_end": self.x_end,
                "y_start": self.y_start,
                "y_end": self.y_end,
                "rotation_start_deg": self.rot_start_deg,
                "rotation_end_deg": self.rot_end_deg,
                "easing": self.easing,
            },
            "effects_requested": self.effects_requested(),
            "effects_applied": self.effects_applied,
            "effects_skipped": self.effects_skipped,
            "render_path": self.render_path,
        }

    def effects_requested(self) -> list[str]:
        """List all effects this preset requests."""
        effects = []
        if self.has_motion:
            effects.append("camera_move")
        if self.micro_shake > 0:
            effects.append("micro_shake")
        if self.breathing > 0:
            effects.append("breathing")
        if self.flicker > 0:
            effects.append("flicker")
        if self.vignette_pulse > 0:
            effects.append("vignette_pulse")
        if self.glow_drift > 0:
            effects.append("glow_drift")
        if self.parallax_strength > 0:
            effects.append("parallax")
        return effects


# =============================================================================
# PRESET MAPPER
# =============================================================================

class PresetMapper:
    """
    Maps LoadedPreset → EngineParams.

    This is the ONLY place where preset values are interpreted.
    No business logic lives in engine.py or motion.py — it all flows
    through these mapping rules.
    """

    # Map director move names → camera parameters
    MOVE_DEFAULTS = {
        "static":     {"zoom_end": 1.00, "x_start": 0.50, "x_end": 0.50,
                       "y_start": 0.50, "y_end": 0.50, "easing": "linear"},
        "push_in":    {"zoom_end": 1.12, "x_start": 0.50, "x_end": 0.50,
                       "y_start": 0.50, "y_end": 0.50, "easing": "ease_in_out"},
        "pull_out":   {"zoom_end": 0.91, "x_start": 0.50, "x_end": 0.50,
                       "y_start": 0.50, "y_end": 0.50, "easing": "ease_in"},
        "shake":      {"zoom_end": 1.06, "x_start": 0.50, "x_end": 0.52,
                       "y_start": 0.50, "y_end": 0.49, "easing": "ease_out"},
        "hesitate":   {"zoom_end": 1.12, "x_start": 0.50, "x_end": 0.50,
                       "y_start": 0.50, "y_end": 0.50, "easing": "hesitate"},
        "snap":       {"zoom_end": 1.15, "x_start": 0.50, "x_end": 0.50,
                       "y_start": 0.50, "y_end": 0.50, "easing": "sudden"},
    }

    def map(self, preset: LoadedPreset) -> EngineParams:
        """
        Map a LoadedPreset to EngineParams.

        Rules:
        1. All values come directly from the preset (no magic defaults)
        2. Unsupported effects → skipped list
        3. Invalid values → warnings (not errors — presets are pre-validated)
        4. Render path auto-selected based on motion profile
        """
        p = preset.raw
        cam = p.get("camera", {})
        mot = p.get("motion", {})
        lit = p.get("lighting", {})
        tim = p.get("timing", {})
        out = p.get("output", {})

        effects_applied = []
        effects_skipped = []
        warnings = []

        # ─── CAMERA ───────────────────────────────────────────────────────────
        move = cam.get("move", "static")
        easing = cam.get("easing", "linear")
        zoom_start = float(cam.get("zoom_start", 1.0))
        zoom_end   = float(cam.get("zoom_end", zoom_start))
        x_start    = float(cam.get("x_start", 0.5))
        x_end      = float(cam.get("x_end", x_start))
        y_start    = float(cam.get("y_start", 0.5))
        y_end      = float(cam.get("y_end", y_start))
        rot_start  = float(cam.get("rotation_start_deg", 0.0))
        rot_end    = float(cam.get("rotation_end_deg", rot_start))

        # ─── MOTION ──────────────────────────────────────────────────────────
        micro_shake = float(mot.get("micro_shake", 0.0))
        breathing  = float(mot.get("breathing", 0.0))
        parallax   = float(mot.get("parallax_strength", 0.0))

        if micro_shake > 0:
            effects_applied.append(f"micro_shake({micro_shake})")
        if breathing > 0:
            effects_applied.append(f"breathing({breathing})")
        if parallax > 0:
            effects_skipped.append(f"parallax({parallax}): not fully implemented")
            warnings.append("parallax approximated (single-layer, no depth separation)")

        # ─── LIGHTING ────────────────────────────────────────────────────────
        flicker = float(lit.get("flicker", 0.0))
        vig_pulse = float(lit.get("vignette_pulse", 0.0))
        glow = float(lit.get("glow_drift", 0.0))

        if flicker > 0:
            effects_applied.append(f"flicker({flicker})")
        if vig_pulse > 0:
            effects_applied.append(f"vignette_pulse({vig_pulse})")
        if glow > 0:
            effects_applied.append(f"glow_drift({glow})")

        # ─── TIMING ─────────────────────────────────────────────────────────
        hold_start = float(tim.get("hold_start_sec", 0.0))
        move_start = float(tim.get("main_move_start_sec", 0.0))
        move_end   = float(tim.get("main_move_end_sec",
                                     float(p.get("duration_sec", 5.0))))
        hold_end   = float(tim.get("hold_end_sec", 0.0))

        # ─── DETERMINE RENDER PATH ──────────────────────────────────────────
        has_motion = (
            zoom_start != zoom_end
            or x_start != x_end
            or y_start != y_end
            or rot_start != rot_end
            or micro_shake > 0
            or breathing > 0
        )

        # Check zoompan eligibility
        can_zoompan = (
            not (micro_shake > 0 or breathing > 0)
            and easing in ("linear", "hold")
            and abs(x_start - x_end) <= 0.01
            and abs(y_start - y_end) <= 0.01
            and abs(rot_start - rot_end) <= 0.1
            and hold_start <= 0.1
            and zoom_start != zoom_end
        )

        if not has_motion:
            render_path = "static_ffmpeg"
        elif can_zoompan:
            render_path = "zoompan"
        else:
            render_path = "PIL"

        # ─── RESOLUTION ─────────────────────────────────────────────────────
        aspect_ratio = p.get("aspect_ratio", "9:16")
        ar_map = {
            "9:16": (1080, 1920), "16:9": (1920, 1080),
            "1:1": (1080, 1080), "4:3": (1440, 1080), "3:4": (1080, 1440),
        }
        resolution = ar_map.get(aspect_ratio, (1080, 1920))

        return EngineParams(
            preset_name=preset.name,
            schema_version="v1",
            duration=float(p.get("duration_sec", 5.0)),
            fps=int(p.get("fps", 24)),
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            # Camera
            move=move,
            zoom_start=zoom_start,
            zoom_end=zoom_end,
            x_start=x_start,
            x_end=x_end,
            y_start=y_start,
            y_end=y_end,
            rot_start_deg=rot_start,
            rot_end_deg=rot_end,
            easing=easing,
            # Motion
            micro_shake=micro_shake,
            breathing=breathing,
            parallax_strength=parallax,
            # Lighting
            flicker=flicker,
            vignette_pulse=vig_pulse,
            glow_drift=glow,
            # Timing
            hold_start_sec=hold_start,
            main_move_start_sec=move_start,
            main_move_end_sec=move_end,
            hold_end_sec=hold_end,
            # Routing
            render_path=render_path,
            effects_applied=effects_applied,
            effects_skipped=effects_skipped,
            warnings=warnings,
        )


# =============================================================================
# QUICK LOOKUP — map preset name → EngineParams directly
# =============================================================================

_DEFAULT_MAPPER = PresetMapper()
_DEFAULT_LOADER = None

def get_engine_params(preset_name: str) -> EngineParams:
    """Load and map a preset by name in one call."""
    global _DEFAULT_LOADER
    if _DEFAULT_LOADER is None:
        from preset_loader import PresetLoader
        _DEFAULT_LOADER = PresetLoader()

    preset = _DEFAULT_LOADER.load(preset_name, strict=False)
    return _DEFAULT_MAPPER.map(preset)


if __name__ == "__main__":
    from preset_loader import PresetLoader

    loader = PresetLoader()
    mapper = PresetMapper()

    print("\n" + "="*55)
    print("  PRESET → ENGINE PARAMS MAPPER")
    print("="*55)

    for name in loader.list_presets():
        preset = loader.load(name, strict=False)
        params = mapper.map(preset)

        print(f"\n{'─'*50}")
        print(f"  {name}")
        print(f"  {'─'*50}")
        print(f"  Route: {params.render_path}")
        print(f"  zoom:  {params.zoom_start} → {params.zoom_end}")
        print(f"  ease:  {params.easing}")
        print(f"  shake: {params.micro_shake} | breath: {params.breathing}")
        print(f"  effects applied: {params.effects_applied or 'none'}")
        print(f"  effects skipped: {params.effects_skipped or 'none'}")
        if params.warnings:
            print(f"  ⚠️  {params.warnings}")
