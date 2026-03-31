# PRESET SPEC — Cinematic Shot Preset Schema

## Version 1.0

All presets follow this exact schema. Values are normalized and deterministic.

---

## Schema

```json
{
  "name": "preset_name",
  "description": "One-line director description",
  "duration_sec": 5.0,
  "fps": 24,
  "aspect_ratio": "9:16",

  "camera": {
    "move": "push_in",          // move type: push_in | pull_out | static | shake | hesitate | snap
    "zoom_start": 1.00,         // zoom at t=0
    "zoom_end": 1.12,           // zoom at end of main_move
    "x_start": 0.50,            // pan-x center at start (0=left, 0.5=center, 1=right)
    "x_end": 0.52,              // pan-x center at end
    "y_start": 0.50,            // pan-y center at start (0=top, 0.5=center, 1=bottom)
    "y_end": 0.48,             // pan-y center at end
    "rotation_start_deg": 0.0,  // rotation at start
    "rotation_end_deg": 0.3,    // rotation at end
    "easing": "ease_in_out"      // easing for main move: linear | ease_in | ease_out | ease_in_out | sudden | hold
  },

  "motion": {
    "micro_shake": 0.012,       // micro handheld amplitude (0 = none, 0.02 = heavy)
    "breathing": 0.008,         // subtle zoom pulse (0 = none, 0.01 = visible)
    "parallax_strength": 0.18   // layer depth offset (0 = flat, 0.3 = strong depth)
  },

  "lighting": {
    "flicker": 0.03,            // brightness fluctuation (0 = none)
    "vignette_pulse": 0.04,     // vignette intensity oscillation (0 = none)
    "glow_drift": 0.02          // subtle highlight drift (0 = none)
  },

  "timing": {
    "hold_start_sec": 0.6,      // dead time before main move begins
    "main_move_start_sec": 0.6, // exact second main camera move begins
    "main_move_end_sec": 4.2,   // exact second main camera move ends
    "hold_end_sec": 0.8         // dead time after main move (total = hold_start + duration + hold_end)
  },

  "output": {
    "codec": "h264",
    "pix_fmt": "yuv420p"
  }
}
```

---

## Field Rules

### camera.move
| Value | Description |
|-------|-------------|
| `static` | No camera motion |
| `push_in` | Zoom toward subject |
| `pull_out` | Zoom away from subject |
| `shake` | Handheld tremor (uses micro_shake) |
| `hesitate` | Slow → pause → fast (easing drives this) |
| `snap` | Instant push (use `easing: "sudden"`) |

### Easing
| Value | FFmpeg expression |
|-------|------------------|
| `linear` | `t/dur` |
| `ease_in` | `pow(t/dur, 3)` — slow start |
| `ease_out` | `1-pow(1-t/dur, 3)` — slow end |
| `ease_in_out` | Cubic in-out |
| `sudden` | Full motion instantly |
| `hold` | No motion |

### Normalization
- `x`, `y`: 0.0–1.0 (fraction of frame, 0.5 = center)
- `rotation_deg`: degrees, typically ±0.5° max
- `micro_shake`, `breathing`, `flicker`, etc.: 0.0–1.0 normalized intensity

### Duration Math
```
total = hold_start_sec + (main_move_end_sec - main_move_start_sec) + hold_end_sec
```

---

## Effect Behavior

### micro_shake
Applied continuously. Amplitude in normalized coordinates (frame fraction).
- Frequency: ~3-5 Hz (ffmpeg random noise at 4Hz)
- Amplitude: `micro_shake * 1920` pixels max displacement

### breathing
Subtle periodic zoom pulse. `breathing * 0.01` fraction, ~0.3Hz.
Expressed as: `sin(t * 2 * PI * 0.3) * amplitude`

### flicker
Brightness variation. `flicker * 0.1` max deviation from 1.0.
Expressed as: `1 ± flicker * sin(t * 8 * PI)`

### vignette_pulse
Vignette strength oscillation. 0.3-1.0 Hz range.
Expressed as: `minlevel + (maxlevel-minlevel) * (0.5 + 0.5 * sin(t * freq * 2 * PI))`

### glow_drift
Subtle highlight shift. Applies ±0.5px micro-pan on highlight layer.

---

## Presets

| File | Name | Mood | Duration |
|------|------|------|----------|
| `suspense_push.json` | Suspense Push | Dread → slam | 5s |
| `heartbreak_drift.json` | Heartbreak Drift | Slow recession | 5s |
| `confrontation_shake.json` | Confrontation Shake | Conflict, tension | 4.5s |
| `reveal_hold_push.json` | Reveal Hold → Push | Recognition → slam | 5s |
| `comedy_snap.json` | Comedy Snap | Deadpan → micro face | 3.5s |
| `memory_float.json` | Memory Float | Dreamlike drift | 6s |
