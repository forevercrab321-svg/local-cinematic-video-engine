# RENDER_RESULT_CONTRACT.md

**Status:** LOCKED

Every shot render MUST return a dict that conforms to this contract.
No exceptions. No partial results. No silent omissions.

---

## Top-Level Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `status` | string | ✅ Always | `"success"` \| `"failed"` \| `"skipped"` |
| `preset_name` | string | ✅ Always | The preset name used |
| `schema_status` | string | ✅ Always | `"new"` \| `"old"` \| `"mixed"` \| `"invalid"` |
| `engine_mode` | string | ✅ Always | `"static_ffmpeg"` \| `"simple_zoompan_ffmpeg"` \| `"cinematic_pil"` |
| `route_selected` | string | ✅ Always | Same as `engine_mode` |
| `output_path` | string | ✅ Success only | Absolute or relative path to output MP4 |
| `file_size_mb` | float | ✅ Success only | File size in MB |
| `duration_sec` | float | ✅ Always | Actual output duration in seconds |
| `render_time_sec` | float | ✅ Always | Wall-clock time for this shot |
| `resolution` | string | ✅ Always | e.g. `"1080×1920"` |
| `fps` | int | ✅ Always | Frames per second |
| `source_image` | string | ✅ Always | Path to source image |
| `source_frame_extracted_from_video` | string\|null | ✅ Always | If frame extracted from video, path to video |
| `timeline_applied` | Timeline | ✅ Always | Applied timing values |
| `camera_params_applied` | CameraParams | ✅ Always | Applied camera values |
| `effects_requested` | string[] | ✅ Always | Effects the preset requested |
| `effects_applied` | string[] | ✅ Always | Effects successfully applied |
| `effects_skipped` | SkipEntry[] | ✅ Always | Effects not applied with reasons |
| `degraded_mode_used` | bool | ✅ Always | True if any effect degraded |
| `validation_status` | string | ✅ Always | `"pass"` \| `"degraded_pass"` \| `"fail"` |
| `cmd_file` | string\|null | Success only | Path to saved FFmpeg command |
| `stderr_file` | string\|null | Success only | Path to saved FFmpeg stderr log |
| `render_log` | string[] | ✅ Always | All log lines from this render |
| `error` | string\|null | Failed only | Error message |
| `ffmpeg_rc` | int\|null | Always | FFmpeg return code (0=success) |
| `frame_debug_path` | string\|null | If debug used | Path to per-frame debug JSON |

---

## Sub-schemas

### Timeline

```json
{
  "hold_start_sec": 1.2,
  "main_move_start_sec": 1.2,
  "main_move_end_sec": 4.0,
  "hold_end_sec": 1.0
}
```

All fields required. If a timing value is 0 (not used), it MUST still be present as `0.0`.

### CameraParams

```json
{
  "move": "push_in",
  "zoom_start": 1.0,
  "zoom_end": 1.12,
  "x_start": 0.5,
  "x_end": 0.5,
  "y_start": 0.5,
  "y_end": 0.5,
  "rotation_start_deg": 0.0,
  "rotation_end_deg": 0.0,
  "easing": "ease_in_out",
  "breathing": 0.0,
  "micro_shake": 0.0
}
```

All fields required. Values reflect **actual applied values**, not raw preset defaults.

### SkipEntry

```json
{
  "effect": "breathing",
  "reason": "intensity=0"
}
```

OR for real skips:

```json
{
  "effect": "color_grade",
  "reason": "unsupported in current route"
}
```

---

## Null Rules

| Field | Allowed null when |
|-------|-------------------|
| `output_path` | `status != "success"` |
| `file_size_mb` | `status != "success"` |
| `cmd_file` | `status != "success"` |
| `stderr_file` | `status != "success"` |
| `error` | `status != "failed"` |
| `frame_debug_path` | Debug not requested |
| `source_frame_extracted_from_video` | Source is a still image |

**No other field may be null.**

---

## Validation Status Rules

| `schema_status` | `status` | `validation_status` |
|----------------|----------|---------------------|
| `new` | `success` | `pass` |
| `new` | `success` + `degraded_mode_used=true` | `degraded_pass` |
| `new` | `failed` | `fail` |
| `old` | `success` | `degraded_pass` (schema degraded, but render works) |
| `old` | `failed` | `fail` |
| `mixed` | any | `fail` |
| `invalid` | any | `fail` |

---

## Failed Render Rules

Even when `status = "failed"`, these fields **MUST** still be present:
- `status`
- `preset_name`
- `schema_status`
- `engine_mode`
- `route_selected`
- `duration_sec`
- `render_time_sec`
- `resolution`
- `fps`
- `source_image`
- `timeline_applied` (may have 0.0 values)
- `camera_params_applied` (may have 0.0 values)
- `effects_requested`
- `effects_applied` (may be [])
- `effects_skipped`
- `degraded_mode_used`
- `validation_status`
- `error`
- `ffmpeg_rc`
- `render_log`

Fields that **MAY** be null on failure:
- `output_path`
- `file_size_mb`
- `cmd_file`
- `stderr_file`
- `frame_debug_path`

---

## Effects Format

`effects_requested` entries: `"{name}({value})"` e.g. `"breathing(0.005)"`
`effects_applied` entries: same format
`effects_skipped`: SkipEntry objects

Zero-intensity effects MUST appear in `effects_skipped` as:
`{"effect": "flicker", "reason": "intensity=0"}`

Real skips MUST appear as:
`{"effect": "color_grade", "reason": "unsupported in current route"}`

---

## Contract Version

v1.0 — LOCKED 2026-03-31
