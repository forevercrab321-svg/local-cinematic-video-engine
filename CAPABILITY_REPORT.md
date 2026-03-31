# 🎬 local_cinematic_video_engine — Capability Report

Generated: 2026-03-31 04:15 EDT

## Summary

- **Total presets tested:** 10
- **Passed:** 10 ✅
- **Failed:** 0 ❌

---

## Preset Validation

| Preset | Schema | Route | Method | Status | Time | Effects Applied |
|--------|--------|-------|--------|--------|------|-----------------|
| comedy               | OLD    |                           | static_ffmpeg   | ✅ | 0.8s | — |
| comedy_snap          | NEW    |                           | pil             | ✅ | 4.1s | — |
| confrontation_shake  | NEW    |                           | pil             | ✅ | 5.1s | flicker(0.03), vignette_pulse(0.05) |
| heartbreak           | OLD    |                           | static_ffmpeg   | ✅ | 0.8s | — |
| heartbreak_drift     | NEW    |                           | pil             | ✅ | 5.9s | vignette_pulse(0.04) |
| memory_float         | NEW    |                           | pil             | ✅ | 6.9s | glow_drift(0.05) |
| reveal               | OLD    |                           | static_ffmpeg   | ✅ | 0.8s | — |
| reveal_hold_push     | NEW    |                           | pil             | ✅ | 6.0s | flicker(0.04), glow_drift(0.06), vignette_pulse(0.03) |
| suspense             | OLD    |                           | static_ffmpeg   | ✅ | 0.8s | — |
| suspense_push        | NEW    |                           | pil             | ✅ | 5.9s | flicker(0.02), glow_drift(0.03), vignette_pulse(0.06) |

---

## Capability Matrix

| Effect | Status | Method | Description |
|--------|--------|-------|-------------|
| camera_move        | ✅ working   | PIL_per_frame, zoompan         | Zoom, pan, rotation with easing curves |
| micro_shake        | ✅ working   | PIL_per_frame                  | Deterministic pseudo-random per-frame shake |
| breathing          | ✅ working   | PIL_per_frame                  | Sin-wave zoom modulation at 0.35Hz |
| flicker            | ✅ working   | ffmpeg_eq                      | Brightness micro-variation at ~4Hz |
| vignette_pulse     | ⚠️ degraded  | ffmpeg_eq_brightness_approx    | True vignette pulse — approximated via brightness |
| glow_drift         | ✅ working   | ffmpeg_eq                      | Contrast/brightness drift |
| film_grain         | ⏭️ skipped   | skip                           | Not implemented — falls back gracefully |
| parallax           | ⚠️ degraded  | approximate_single_layer       | True multi-layer parallax — approximated |
| color_grade        | ⏭️ skipped   | skip                           | Not implemented — falls back gracefully |

---

## Effect Status

**Working (✅):** camera_move, micro_shake, breathing, flicker, glow_drift

**Degraded (⚠️):** vignette_pulse, parallax

**Skipped (⏭️):** film_grain, color_grade

---

## Schema Breakdown

| Preset | Schema | Route | Details |
|--------|--------|-------|---------|
| comedy               | OLD    | static_ffmpeg (OLD schema)     | camera_moves=3, effects=['breathing', 'film_grain'] |
| comedy_snap          | NEW    | PIL                            | zoom=1.0 → 1.015, shake=0.0, breath=0.006 |
| confrontation_shake  | NEW    | PIL                            | zoom=1.0 → 1.06, shake=0.022, breath=0.0 |
| heartbreak           | OLD    | static_ffmpeg (OLD schema)     | camera_moves=3, effects=['breathing', 'vignette_pulse', 'film_grain'] |
| heartbreak_drift     | NEW    | PIL                            | zoom=1.0 → 0.91, shake=0.0, breath=0.012 |
| memory_float         | NEW    | PIL                            | zoom=1.0 → 1.06, shake=0.0, breath=0.015 |
| reveal               | OLD    | static_ffmpeg (OLD schema)     | camera_moves=3, effects=['lens_flare', 'glow_flicker', 'color_grade_shift'] |
| reveal_hold_push     | NEW    | PIL                            | zoom=1.0 → 1.15, shake=0.008, breath=0.004 |
| suspense             | OLD    | static_ffmpeg (OLD schema)     | camera_moves=3, effects=['vignette_pulse', 'film_grain', 'glow_flicker'] |
| suspense_push        | NEW    | PIL                            | zoom=1.0 → 1.12, shake=0.006, breath=0.005 |

---

## Render Paths

| Path | Condition | Speed | File |
|------|-----------|-------|------|
| `static_ffmpeg` | No motion | <1s | ~0.1MB |
| `zoompan` | Linear zoom, no effects | ~2s | ~0.1MB |
| `PIL` | Easing / hold / shake / breath | 8-20s | ~0.5MB |

---

## Notes

- **OLD schema** presets (`suspense`, `heartbreak`, `reveal`, `comedy`) → map to static (no camera motion). They need migration to new schema.
- **vignette_pulse**: approximated via `eq=brightness=...` (not true lens vignette)
- **film_grain**: not implemented, skipped gracefully
- **parallax**: approximated (no true multi-layer separation)
- **color_grade**: not implemented, skipped gracefully

**No render ever fails due to unsupported effects.** Graceful degradation is guaranteed.