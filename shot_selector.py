#!/usr/bin/env python3
"""
shot_selector.py — Director Brain Interface

Translates emotional intent + intensity into the optimal preset selection.

Input (natural language):
    shot_selection(emotion="doubt", intensity=0.7)
    shot_selection(emotion="shock", intensity=1.0)
    shot_selection(emotion="nostalgia", intensity=0.5)

Output:
    ShotRecommendation with:
      - preset: str
      - shot_type: str
      - camera_recommendation: str
      - timing_note: str
      - rationale: str

Theory:
  emotion  → WHAT the scene needs emotionally
  intensity → HOW HARD the camera pushes (amplitude, speed)

Usage:
    python3 shot_selector.py doubt 0.7
    python3 shot_selector.py --list
"""

from dataclasses import dataclass
from typing import Optional


# =============================================================================
# PRESET REGISTRY (golden 4 locked)
# =============================================================================

PRESETS = {
    "suspense_push": {
        "name": "Suspense Push",
        "duration_range": (4.0, 6.0),
        "emotions": [
            "tension", "fear", "doubt", "anxiety", "suspense",
            "anticipation", "unease", "worry", "nervousness",
        ],
        "intensity_range": (0.3, 1.0),      # works across full range
        "camera": "slow_push",               # push in = closure = dread
        "camera_params": {
            "move": "push_in",
            "zoom_delta": 0.12,              # 1.0 → 1.12
            "speed": "slow",
            "hold_start": 1.0,               # seconds of hold before move
            "feel": "closure",
        },
        "effects": ["breathing", "flicker", "glow_drift", "vignette_pulse"],
        "safe_shot_types": ["hero_front", "face_closeup", "medium"],
    },

    "heartbreak_drift": {
        "name": "Heartbreak Drift",
        "duration_range": (4.5, 7.0),
        "emotions": [
            "sadness", "grief", "loss", "heartbreak", "regret",
            "nostalgia", "longing", "melancholy", "sorrow",
            "disappointment", "emptiness",
        ],
        "intensity_range": (0.2, 0.8),
        "camera": "slow_pull",               # pull out = recession = loss
        "camera_params": {
            "move": "pull_out",
            "zoom_delta": -0.09,             # 1.0 → 0.91
            "speed": "slow",
            "hold_start": 0.5,
            "feel": "recession",
        },
        "effects": ["breathing", "vignette_pulse"],
        "safe_shot_types": ["hero_front", "medium", "reaction"],
    },

    "reveal_hold_push": {
        "name": "Reveal Hold → Push",
        "duration_range": (4.0, 6.0),
        "emotions": [
            "shock", "revelation", "realization", "surprise",
            "awareness", "clarity", "truth", "recognition",
            "punchline", "punch_line", "the moment",
        ],
        "intensity_range": (0.5, 1.0),
        "camera": "hold_then_slam",          # HOLD = tension, then SLAM = release
        "camera_params": {
            "move": "hold_then_push",
            "zoom_delta": 0.15,               # 1.0 → 1.15
            "hold_first": 1.5,                # long hold = maximum tension
            "slam": True,                     # final push is sharp
            "feel": "impact",
        },
        "effects": ["flicker", "glow_drift", "vignette_pulse"],
        "safe_shot_types": ["face_closeup", "hero_front", "reaction"],
    },

    "comedy_snap": {
        "name": "Comedy Snap",
        "duration_range": (2.5, 4.5),
        "emotions": [
            "awkward", "ironic", "deadpan", "realization_awkward",
            "mismatch", "contrast", "absurd", "callback",
            "punchline_soft", "yeah_right", "facepalm",
        ],
        "intensity_range": (0.3, 0.9),
        "camera": "deadpan_static",           # NO motion = more funny
        "camera_params": {
            "move": "static",
            "zoom_delta": 0.015,              # barely there movement
            "hold_start": 0.8,
            "feel": "deadpan",
        },
        "effects": [],                        # minimal effects = clean = funny
        "safe_shot_types": ["reaction", "face_closeup", "medium"],
    },
}


# =============================================================================
# DIRECTOR EMOTION → PRESET MAPPING
# =============================================================================

# Primary mapping: emotion keyword → preset
EMOTION_PRESET_MAP = {
    # DOUBT / TENSION
    "doubt":          "suspense_push",
    "tension":       "suspense_push",
    "anxiety":       "suspense_push",
    "unease":        "suspense_push",
    "nervousness":   "suspense_push",
    "fear":          "suspense_push",
    "worry":         "suspense_push",
    "anticipation":  "suspense_push",
    "suspense":      "suspense_push",

    # SADNESS / RECESSION
    "sadness":       "heartbreak_drift",
    "grief":         "heartbreak_drift",
    "loss":          "heartbreak_drift",
    "heartbreak":    "heartbreak_drift",
    "regret":        "heartbreak_drift",
    "nostalgia":     "heartbreak_drift",
    "longing":       "heartbreak_drift",
    "melancholy":    "heartbreak_drift",
    "sorrow":        "heartbreak_drift",
    "emptiness":     "heartbreak_drift",
    "disappointment":"heartbreak_drift",

    # REVELATION / SHOCK
    "shock":         "reveal_hold_push",
    "revelation":    "reveal_hold_push",
    "realization":   "reveal_hold_push",
    "surprise":      "reveal_hold_push",
    "awareness":     "reveal_hold_push",
    "clarity":       "reveal_hold_push",
    "truth":         "reveal_hold_push",
    "recognition":   "reveal_hold_push",
    "punchline":     "reveal_hold_push",
    "punch_line":    "reveal_hold_push",
    "the_moment":    "reveal_hold_push",

    # COMEDY / DEADPAN
    "awkward":       "comedy_snap",
    "ironic":        "comedy_snap",
    "deadpan":       "comedy_snap",
    "mismatch":      "comedy_snap",
    "contrast":      "comedy_snap",
    "absurd":        "comedy_snap",
    "callback":      "comedy_snap",
    "facepalm":      "comedy_snap",
    "yeah_right":    "comedy_snap",
    "punchline_soft":"comedy_snap",
    "irony":         "comedy_snap",
}

# Intensity breakpoints → subtle adjustments
INTENSITY_ZOOMS = {
    (0.0, 0.3):   "reduce_movement",   # very soft — minimal push/pull
    (0.3, 0.6):   "standard",          # normal
    (0.6, 0.8):   "enhanced",          # stronger delta
    (0.8, 1.0):   "maximum",           # full power
}

INTENSITY_HOLD = {
    (0.0, 0.4):   "short_hold",       # quick to action
    (0.4, 0.7):   "medium_hold",       # balanced
    (0.7, 1.0):   "long_hold",        # maximum tension
}


# =============================================================================
# RESULT
# =============================================================================

@dataclass
class ShotRecommendation:
    """Result of shot selection."""
    preset: str
    shot_type: str
    camera_recommendation: str
    timing_note: str
    rationale: str
    effects_suggested: list
    confidence: float            # 0–1, how confident the match is

    def describe(self) -> str:
        return (
            f"\n{'='*50}\n"
            f"  🎬 DIRECTOR SHOT SELECTION\n"
            f"{'='*50}\n"
            f"  Preset:    {self.preset}\n"
            f"  Shot type: {self.shot_type}\n"
            f"  Camera:    {self.camera_recommendation}\n"
            f"  Timing:    {self.timing_note}\n"
            f"  Confidence: {self.confidence:.0%}\n"
            f"\n  Rationale:\n"
            f"    {self.rationale}\n"
            f"\n  Suggested effects: {', '.join(self.effects_suggested) or 'none'}\n"
            f"{'='*50}"
        )

    def to_preset_params(self) -> dict:
        """Return parameters ready for scene manifest."""
        p = PRESETS[self.preset]
        cp = p["camera_params"]

        # Adjust duration based on hold preference
        dur_min, dur_max = p["duration_range"]
        duration = (dur_min + dur_max) / 2

        return {
            "preset": self.preset,
            "shot_type": self.shot_type,
            "camera_recommendation": self.camera_recommendation,
            "duration_sec": round(duration, 1),
            "effects_suggested": self.effects_suggested,
            "confidence": self.confidence,
        }


# =============================================================================
# SHOT SELECTOR
# =============================================================================

class ShotSelector:
    """
    Director brain: maps emotional intent → preset + shot parameters.

    Usage:
        selector = ShotSelector()
        rec = selector.select(emotion="doubt", intensity=0.7)
        print(rec.describe())
    """

    def __init__(self):
        self.presets = PRESETS
        self.emotion_map = EMOTION_PRESET_MAP

    def select(
        self,
        emotion: str,
        intensity: float = 0.5,
        shot_type_hint: Optional[str] = None,
        duration_hint: Optional[float] = None,
    ) -> ShotRecommendation:
        """
        Select the optimal preset for a given emotional state.

        Args:
            emotion:        Natural language emotion (e.g. "doubt", "shock", "nostalgia")
            intensity:      0.0–1.0, how intense the moment is
            shot_type_hint: Override shot type (hero_front | face_closeup | medium | reaction)
            duration_hint:  Override total shot duration in seconds

        Returns:
            ShotRecommendation
        """
        intensity = max(0.0, min(1.0, float(intensity)))
        emotion_clean = emotion.lower().strip().replace(" ", "_").replace("-", "_")

        # ── 1. Find preset ──────────────────────────────────────────
        preset_key = self.emotion_map.get(emotion_clean)

        # Fallback: fuzzy match on partial
        if preset_key is None:
            for key, preset_name in self.emotion_map.items():
                if key in emotion_clean or emotion_clean in key:
                    preset_key = preset_name
                    break

        # Last resort: default to suspense_push
        if preset_key is None:
            preset_key = "suspense_push"

        preset_data = self.presets[preset_key]

        # ── 2. Confidence ──────────────────────────────────────────
        # Exact match = high confidence, fuzzy = medium
        confidence = 1.0 if emotion_clean in self.emotion_map else 0.7

        # Out-of-range intensity reduces confidence slightly
        i_min, i_max = preset_data["intensity_range"]
        if not (i_min <= intensity <= i_max):
            confidence *= 0.85

        # ── 3. Shot type ──────────────────────────────────────────
        if shot_type_hint and shot_type_hint in preset_data["safe_shot_types"]:
            shot_type = shot_type_hint
        else:
            shot_type = preset_data["safe_shot_types"][0]   # default: safest

        # ── 4. Camera recommendation ─────────────────────────────────
        cp = preset_data["camera_params"]
        move = cp["move"]
        feel = cp["feel"]

        camera_recommendation = f"{move} ({feel})"

        # Intensity modifier on zoom delta
        zoom_delta = cp["zoom_delta"]
        if intensity >= 0.8:
            zoom_delta *= 1.25          # amplify at high intensity
        elif intensity <= 0.3:
            zoom_delta *= 0.6          # soften at low intensity

        # ── 5. Timing note ───────────────────────────────────────────
        dur_min, dur_max = preset_data["duration_range"]

        # Hold time scales with intensity
        if intensity >= 0.7:
            hold_label = "long hold first"
            hold_frac = 0.35
        elif intensity >= 0.4:
            hold_label = "medium hold"
            hold_frac = 0.25
        else:
            hold_label = "quick"
            hold_frac = 0.15

        timing_note = (
            f"{hold_label} → main action → hold end. "
            f"Total: {dur_min}–{dur_max}s"
        )

        if duration_hint:
            timing_note = f"Override {duration_hint}s | {timing_note}"

        # ── 6. Rationale ─────────────────────────────────────────────
        rationale = (
            f"Emotion '{emotion}' (intensity={intensity:.1f}) → {preset_data['name']}. "
            f"Camera: {feel}-style {move}. "
            f"Intensity {intensity:.1f} = "
            f"{'high' if intensity > 0.7 else 'medium' if intensity > 0.3 else 'low'} power."
        )

        # ── 7. Effects ────────────────────────────────────────────────
        effects = preset_data["effects"]
        # Intensity cuts effects at low end
        if intensity < 0.3:
            effects = [e for e in effects if e == "breathing"]

        return ShotRecommendation(
            preset=preset_key,
            shot_type=shot_type,
            camera_recommendation=camera_recommendation,
            timing_note=timing_note,
            rationale=rationale,
            effects_suggested=effects,
            confidence=confidence,
        )

    def list_emotions(self):
        """Show all supported emotions."""
        print("\nSupported emotions (direct mapping):")
        for emotion, preset in sorted(self.emotion_map.items()):
            print(f"  {emotion:20s} → {preset}")
        print()


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="Director shot selector")
    parser.add_argument("emotion", nargs="?", help="Emotion keyword (e.g. doubt, shock, sadness)")
    parser.add_argument("intensity", nargs="?", type=float, default=0.5,
                        help="Intensity 0.0–1.0 (default 0.5)")
    parser.add_argument("--shot-type", help="Shot type hint (hero_front, face_closeup, medium, reaction)")
    parser.add_argument("--duration", type=float, help="Duration override in seconds")
    parser.add_argument("--list", action="store_true", help="List all supported emotions")
    args = parser.parse_args()

    selector = ShotSelector()

    if args.list or not args.emotion:
        selector.list_emotions()
        print("\nUsage:")
        print("  python3 shot_selector.py doubt 0.7")
        print("  python3 shot_selector.py shock 1.0 --shot-type face_closeup")
        print("  python3 shot_selector.py nostalgia 0.4")
        sys.exit(0)

    rec = selector.select(
        emotion=args.emotion,
        intensity=args.intensity,
        shot_type_hint=args.shot_type,
        duration_hint=args.duration,
    )
    print(rec.describe())
