# PRESET_SCHEMA_STATUS_RULES.md

**Status:** LOCKED

## Schema Status Values

Each preset has exactly ONE schema status:

| Status | Meaning | Validation Outcome |
|--------|---------|-------------------|
| `new` | Uses only new schema keys (`camera`, `motion`, `lighting`, `timing`) | Normal: `pass` or `degraded_pass` |
| `old` | Uses only old schema keys (`camera_moves`, `effects`, `parallax`) | Always `degraded_pass` if render succeeds |
| `mixed` | Contains BOTH old and new schema keys | Always `fail` — must be fixed |
| `invalid` | Contains neither old nor new schema keys, or is unreadable | Always `fail` |

---

## Schema Detection Algorithm

```python
def detect_schema_status(preset_data: dict) -> str:
    keys = set(preset_data.keys())

    old_keys = {"camera_moves", "effects", "parallax"}
    new_keys = {"camera", "motion", "lighting", "timing",
                "duration_sec", "fps", "aspect_ratio",
                "name", "description"}

    has_old = bool(keys & old_keys)
    has_new = bool(keys & new_keys)

    if has_old and has_new:
        return "mixed"
    elif has_old:
        return "old"
    elif has_new:
        return "new"
    else:
        return "invalid"
```

---

## Old Schema Key Reference

These keys mark a preset as `old` schema:

| Key | Type | Notes |
|-----|------|-------|
| `camera_moves` | list/dict | Old camera move definitions |
| `effects` | list/dict | Old effect definitions |
| `parallax` | dict | Old parallax definition |
| `color_grade` | dict | Old color grade (note: also appears in new schema lighting) |

---

## New Schema Key Reference

These keys mark a preset as `new` schema:

| Key | Type | Notes |
|-----|------|-------|
| `camera` | dict | Camera move + zoom + easing |
| `motion` | dict | micro_shake, breathing, parallax_strength |
| `lighting` | dict | flicker, glow_drift, vignette_pulse |
| `timing` | dict | hold_start_sec, main_move_start_sec, main_move_end_sec, hold_end_sec |
| `duration_sec` | float | Duration in seconds |
| `fps` | int | Frames per second |
| `aspect_ratio` | string | e.g. `"9:16"` |

---

## Policy Rules

### Rule 1: Old Schema Is NOT Cinematic

An `old` schema preset:
- **MUST NOT** be described as "cinematic"
- **MUST NOT** be used in scene manifests as a primary artistic shot
- **MAY** be used as a static background pad shot
- **MUST** be rendered with `route_selected = "static_ffmpeg"`
- **MUST** produce `validation_status = "degraded_pass"` (render works, but schema is deprecated)

### Rule 2: Mixed Schema Is a Hard Fail

Any preset detected as `mixed`:
- **MUST NOT** be rendered
- **MUST** produce `validation_status = "fail"`
- **MUST** be flagged in CAPABILITY_REPORT as "needs migration"
- The scene manifest validation **MUST** reject it

### Rule 3: Invalid Schema Is a Hard Fail

Any preset that cannot be loaded or has neither old nor new schema keys:
- **MUST NOT** be rendered
- **MUST** produce `validation_status = "fail"`

### Rule 4: New Schema Is Normal

A `new` schema preset:
- Is subject to normal validation
- Produces `pass` if render succeeds with no degraded effects
- Produces `degraded_pass` if render succeeds but some effects degraded

---

## Current Preset Registry

### Old Schema (deprecated)

| Preset | Schema | Render Route | Policy |
|--------|--------|-------------|--------|
| `suspense` | old | static_ffmpeg | keep_as_static_shell |
| `heartbreak` | old | static_ffmpeg | keep_as_static_shell |
| `reveal` | old | static_ffmpeg | keep_as_static_shell |
| `comedy` | old | static_ffmpeg | keep_as_static_shell |

### New Schema (active)

| Preset | Schema | Render Route | Policy |
|--------|--------|-------------|--------|
| `suspense_push` | new | cinematic_pil | production_ready |
| `heartbreak_drift` | new | cinematic_pil | production_ready |
| `reveal_hold_push` | new | cinematic_pil | production_ready |
| `comedy_snap` | new | cinematic_pil | production_ready |
| `confrontation_shake` | new | cinematic_pil | production_ready (breathing=0.008 → reduce to ≤0.001) |
| `memory_float` | new | cinematic_pil | production_ready (breathing=0.003 → reduce to ≤0.001) |

---

## No Preset May Be Both Old and New

There is no such thing as a "backward-compatible" or "hybrid" preset.
If a preset has BOTH old and new keys, it is `mixed` and fails.

The migration path from old to new is:
1. Create a new preset with new schema keys
2. Validate it independently
3. Update scene manifests to use the new preset
4. Deprecate the old preset

---

## Contract Version

v1.0 — LOCKED 2026-03-31
