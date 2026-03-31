# PRESET_VALIDATION_SUMMARY.md

**Generated:** 2026-03-31T06:45:00.075899

| Preset | Schema | Route | Status | Render Time |
|--------|--------|-------|--------|-------------|
| ⚠️  suspense | old | static_ffmpeg | degraded_pass | 0.7s |
| ⚠️  heartbreak | old | static_ffmpeg | degraded_pass | 0.7s |
| ⚠️  reveal | old | static_ffmpeg | degraded_pass | 0.7s |
| ⚠️  comedy | old | static_ffmpeg | degraded_pass | 0.7s |
| ✅ suspense_push | new | pil | pass | 5.5s |
| ⚠️  heartbreak_drift | new | pil | degraded_pass | 5.2s |
| ✅ reveal_hold_push | new | pil | pass | 5.5s |
| ⚠️  comedy_snap | new | pil | degraded_pass | 3.7s |
| ⚠️  confrontation_shake | new | pil | degraded_pass | 4.8s |
| ⚠️  memory_float | new | pil | degraded_pass | 6.4s |

## Old Schema (static_ffmpeg — degraded by design)
- suspense: `static_ffmpeg` — degraded_pass
- heartbreak: `static_ffmpeg` — degraded_pass
- reveal: `static_ffmpeg` — degraded_pass
- comedy: `static_ffmpeg` — degraded_pass

## New Schema Cinematic
- suspense_push: `pil` — pass
- heartbreak_drift: `pil` — degraded_pass
- reveal_hold_push: `pil` — pass
- comedy_snap: `pil` — degraded_pass
- confrontation_shake: `pil` — degraded_pass
- memory_float: `pil` — degraded_pass

## Failed