# EFFECT_POLICY_LOCK.md

## Working Effects (A-list — apply freely)

| Effect | Route | Policy |
|--------|-------|--------|
| `push_in` | zoompan / PIL | ✅ Apply — core camera move |
| `pull_out` | zoompan / PIL | ✅ Apply — reverse push |
| `micro_shake` | PIL only | ✅ Apply — deterministic per-frame, Stage B confirmed |
| `breathing` | PIL only | ✅ Apply ≤0.001 — validated Stage B at 0.005, artifact-free at ≤0.001 |
| `hold_timing` | PIL only | ✅ Apply — frame counting, confirmed working |
| `easing` | PIL only | ✅ Apply — ease_in / ease_out / ease_in_out confirmed |
| `flicker` | FFmpeg eq | ✅ Apply — `eq=brightness={f}*sin(t*25)` confirmed |
| `glow_drift` | FFmpeg eq | ✅ Apply — `eq=contrast={1+g}` confirmed |
| `vignette_pulse` | FFmpeg eq | ✅ Apply — brightness oscillation approximation confirmed |
| `brightness_modulation` | FFmpeg eq | ✅ Apply — via flicker/glow/vignette |
| `contrast_modulation` | FFmpeg eq | ✅ Apply — via glow_drift |

## Degraded Effects (B-list — apply with fallback)

| Effect | Route | Policy | Degraded Mode |
|--------|-------|--------|---------------|
| `drift_x` | PIL pan | ⚠️ Degrade | Skip pan, zoompan fallback still works |
| `drift_y` | PIL pan | ⚠️ Degrade | Skip pan, zoompan fallback still works |
| `rotation_drift` | PIL rotate | ⚠️ Degrade | Skip rotation, no visible artifact |
| `parallax` | PIL layer | ⚠️ Degrade | Approximate with single-layer, no depth |
| `film_grain` | FFmpeg noise | ⚠️ Degrade | Skip silently, grain unregistered in presets |

## Skipped Effects (C-list — graceful skip, never crash)

| Effect | Reason | Behavior |
|--------|--------|----------|
| `color_grade` | Not implemented, explicitly disabled in registry | Skip with logged reason, continue render |
| `temperature_shift` | Not implemented | Skip silently |
| `layered_depth_split` | Not implemented | Skip silently |
| `foreground_offset` | Not implemented | Skip silently |
| Any effect with `intensity=0` | Zero value | Skip, no warning |
| Any effect in wrong route | e.g. PIL effect on zoompan path | Graceful skip, no error |

## Forbidden Effects (D-list — must not reach production)

| Effect | Reason |
|--------|--------|
| Any old-schema `camera_moves` raw entry | Old schema silently maps to static. Never use directly in cinematic presets. |
| `breathing > 0.015` | Visible artifact in slow motion. Self-tuning confirmed optimal ≤0.001. |
| FFmpeg expressions with `if()` conditionals in zoompan | zoompan RC=1 on this Mac. Confirmed RC=0 only with simple `z='min(zoom+0.001,cap)'`. |
| Un-padded non-square sources in zoompan | Produces wrong aspect ratio (1280×720 vs 1080×1920). Must pre-scale. |

## Effect Application Rules

### Graceful Skip Rule
Any effect that cannot be applied in the current route:
1. **MUST** be added to `effects_skipped[]`
2. **MUST** include a reason string
3. **MUST NOT** stop or crash the render
4. **MUST** allow render to continue with remaining effects

### Degraded Mode Rule
If an effect has a degraded form:
1. **MUST** record `degraded_mode_used: true` in render result
2. **MUST** log what was degraded and why
3. **MUST** still produce a valid output

### No Crash Rule
One effect failure ≠ one shot failure. Unless the effect is explicitly marked
`required_for_render=True`, it must degrade or skip, never crash.

### Zero-Value Skip Rule
Effects with intensity/value = 0 are **not errors**. They are correctly skipped
and **MUST NOT** appear in `effects_skipped` as failures.
They appear only in the `effects_skipped` list as `"{name}: intensity=0"`.

## Render Result Schema (effects fields)

Every render result **MUST** contain:

```json
{
  "effects_requested": ["micro_shake(0.006)", "breathing(0.005)", "flicker(0.02)"],
  "effects_applied":   ["flicker(0.02)", "glow_drift(0.03)", "vignette_pulse(0.06)"],
  "effects_skipped":   ["breathing(0.005): route_cinematic_pil"],
  "degraded_mode":     false
}
```

`effects_skipped` entries for real skips (not zero-intensity) follow this format:
`"{effect_name}: {reason}"`

## Per-Route Effect Support

| Route | micro_shake | breathing | flicker | glow_drift | vignette_pulse | color_grade |
|-------|------------|-----------|---------|------------|----------------|-------------|
| `static_ffmpeg` | skip | skip | apply | apply | apply | skip |
| `simple_zoompan_ffmpeg` | skip | skip | apply | apply | apply | skip |
| `cinematic_pil` | apply | apply | apply | apply | apply | skip |
