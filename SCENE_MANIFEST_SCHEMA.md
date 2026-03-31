# SCENE_MANIFEST_SCHEMA.md

## Scene Manifest Schema (updated)

A valid `scene_manifest.json` defines a multi-shot scene for batch rendering.

### Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project` | string | ✅ | Project name |
| `description` | string | | Scene description |
| `total_shots` | int | auto | Computed from shots array |
| `total_duration_sec` | float | auto | Sum of all shot durations |
| `shots` | Shot[] | ✅ | Ordered list of shots |

### Shot Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `shot_id` | string | ✅ | Unique identifier (e.g. S01_INTRO) |
| `input_image` | string | ✅ | Path to source image |
| `output_file` | string | ✅ | Output MP4 path |
| `preset` | string | ✅ | Preset name (see GOLDEN_PRESETS or `__stage_*` variants) |
| `duration_sec` | float | ✅ | Shot duration in seconds |
| `fps` | int | | Frames per second (default: 24) |
| `aspect_ratio` | string | | e.g. "9:16" (default: "9:16") |
| `camera_override` | string | | Override camera move (optional) |
| `camera_intensity` | float | | Intensity multiplier for camera (default: 1.0) |
| `caption_text` | string | | Optional caption overlay text |
| `dialogue` | string | | Spoken script / subtitle text |
| `note` | string | | Human note (not used in render) |
| `risk_level` | string | | `low` / `medium` / `high` (not enforced) |
| `shot_type` | string | | e.g. "establishing", "reaction", "close_up" |

### GOLDEN_PRESETS (New Schema Only)

Only these presets pass `validate_or_raise()`:

```python
GOLDEN_PRESETS = frozenset({
    "suspense_push",      # cinematic | hold+push | dread
    "heartbreak_drift",   # cinematic | pull+hold | loss
    "reveal_hold_push",    # cinematic | hold+push | reveal
    "comedy_snap",         # cinematic | snap zoom | humor
})
```

### Legacy Presets (Old Schema — route to static_ffmpeg)

These presets are **not** in GOLDEN_PRESETS but are valid render subjects
(they auto-route to `static_ffmpeg`):
- `suspense`, `heartbreak`, `reveal`, `comedy`

They are **exempt** from golden preset validation.

### Validation Rules

1. All required shot fields must be present
2. Preset must be either a golden preset OR a known legacy preset
3. Duration must be positive
4. `shot_id` must be unique within the manifest
5. `input_image` must exist as a file

### Effects Fields (Rendered Output)

After render, each shot record in the ledger contains:

| Field | Type | Description |
|-------|------|-------------|
| `effects_requested` | string[] | All effects the preset requested |
| `effects_applied` | string[] | Effects successfully applied |
| `effects_skipped` | SkipEntry[] | Effects not applied (with reasons) |
| `degraded_mode_used` | bool | True if any effect degraded |

### SkipEntry Format

```json
{
  "effect": "breathing",
  "reason": "unsupported expression in current route"
}
```

Or for zero-intensity skips:

```json
{
  "effect": "flicker",
  "reason": "intensity=0"
}
```
