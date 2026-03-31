# RENDER_LEDGER_SCHEMA.md

## Render Ledger Schema (updated)

The ledger (`scene_render_ledger.json`) is the authoritative record of a
batch render session. One ledger per scene manifest render.

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `project` | string | Project name |
| `manifest_file` | string | Path to the manifest that was rendered |
| `total_shots` | int | Number of shots in manifest |
| `success_count` | int | Shots that produced a valid MP4 |
| `failed_count` | int | Shots that failed |
| `skipped_count` | int | Shots skipped (already rendered, --skip-existing) |
| `total_render_time_sec` | float | Wall-clock time for entire batch |
| `render_completed_at` | string | ISO-8601 timestamp |
| `effects_summary` | EffectsSummary | Aggregate effect application stats |
| `shots` | ShotRecord[] | Per-shot detailed records |

### EffectsSummary

| Field | Type | Description |
|-------|------|-------------|
| `total_effects_requested` | int | Sum across all shots |
| `total_effects_applied` | int | Sum across all shots |
| `total_effects_skipped` | int | Sum across all shots |
| `degraded_count` | int | Shots using degraded mode |
| `unique_effects_applied` | string[] | List of distinct effects applied |
| `unique_effects_skipped` | string[] | List of distinct effects skipped |

### ShotRecord

Each entry in `shots[]` records one shot's render:

| Field | Type | Description |
|-------|------|-------------|
| `shot_id` | string | From manifest |
| `preset` | string | Preset used |
| `engine_mode` | string | Route used: `static_ffmpeg`, `simple_zoompan_ffmpeg`, `cinematic_pil` |
| `schema_status` | string | `old_schema` or `new_schema` |
| `status` | string | `success`, `failed`, `skipped` |
| `render_time_sec` | float | Wall-clock time for this shot |
| `file_size_mb` | float | Output file size in MB |
| `frame_count` | int | Frames in output (fps × duration) |
| `file_path` | string | Absolute path to output MP4 |
| `input_image` | string | Source image path |
| `source_frame_extracted_from_video` | string/null | If frame was extracted from video |
| `camera_params_applied` | CameraParams | Actual camera values used |
| `effects_requested` | string[] | All effects requested by preset |
| `effects_applied` | string[] | Effects successfully applied |
| `effects_skipped` | SkipEntry[] | Effects skipped with reasons |
| `degraded_mode_used` | bool | True if any effect was degraded |
| `validation_status` | string | `passed`, `failed`, `skipped` |
| `error` | string/null | Error message if failed |
| `ffmpeg_rc` | int | FFmpeg return code (0=success) |
| `ledger_note` | string | Human-readable one-liner |

### CameraParams

| Field | Type | Description |
|-------|------|-------------|
| `move` | string | Camera move name (e.g. `push_in`) |
| `zoom_start` | float | Starting zoom |
| `zoom_end` | float | Ending zoom |
| `x_start` | float | Horizontal start position (0–1) |
| `x_end` | float | Horizontal end position |
| `y_start` | float | Vertical start position |
| `y_end` | float | Vertical end position |
| `easing` | string | Easing curve name |
| `hold_start_dur` | float | Hold before movement (sec) |
| `move_start` | float | Movement start time (sec) |
| `move_end` | float | Movement end time (sec) |
| `hold_end_dur` | float | Hold after movement (sec) |
| `breathing` | float | Breathing intensity applied |
| `micro_shake` | float | Micro-shake intensity applied |

### SkipEntry

```json
{
  "effect": "color_grade",
  "reason": "unsupported in current route"
}
```

### Validation Rules for Ledger

1. `success_count + failed_count + skipped_count == total_shots`
2. Each `ShotRecord.status` must be one of: `success`, `failed`, `skipped`
3. `failed` shots must have an `error` field
4. `skipped` shots must have a `ledger_note` explaining why
5. All file paths should be absolute or relative to manifest directory
