# ISOLATION_DEBUGGER_LOCK.md

## Tool Status

- **isolation debugger**: ✅ TRUSTED
- **blocker**: None — all 4 stages pass cleanly

## suspense_push isolation

- **stage A**: ✅ PASS (5.0s) — base camera / linear zoom / zoompan fallback
- **stage B**: ✅ PASS (5.3s) — base camera + motion (micro_shake + breathing)
- **stage C**: ✅ PASS (5.3s) — base camera + motion + lighting (flicker + vignette + glow)
- **stage D**: ✅ PASS (5.4s) — full preset with timing/easing/hold

## First Real Failure

- **none** — all 4 stages pass

## Root Cause Analysis

`suspense_push` is a clean preset. All 4 layers work correctly:

| Stage | Layer | Result | Key Finding |
|-------|-------|--------|-------------|
| A | Base camera (zoom 1.0→1.12, linear) | ✅ | zoompan fallback (no PIL needed) |
| B | + micro_shake=0.006, breathing=0.005 | ✅ | motion layer introduces no errors |
| C | + flicker=0.02, vignette=0.06, glow=0.03 | ✅ | lighting layer is stable |
| D | + hold(1.2s) + ease_in_out + full timing | ✅ | timing assembly correct |

## Tool Verification Checklist

| Requirement | Status |
|-------------|--------|
| Imports complete, no circular deps | ✅ Fixed: scene_schema circular import resolved |
| Stage fail → subsequent stages stop | ✅ Confirmed: B failed once, stopped at B |
| No silent fallback | ✅ Confirmed: exact failure type in every report |
| No old-schema presets allowed | ✅ Confirmed: `suspense`, `heartbreak`, `reveal`, `comedy` blocked |
| Machine-readable report per stage | ✅ All 4 stages: .cmd.txt / .stderr.log / .params.json / .report.json |
| Params snapshot = actual applied values | ✅ Uses `load_preset(variant)` to verify |
| Exact failure point documented | ✅ ZeroDivisionError at Stage B had exact point logged |
| Temp frame paths stable | ✅ `tempfile.gettempdir()` + `shutil` cleanup |
| FFmpeg RC captured | ✅ RC in every report.json |

## Hard Bugs Fixed This Session

1. **`scene_schema.py` circular import**: `GOLDEN_PRESETS` at module-level triggered circular import chain. Moved inside `validate_or_raise()` as local constant.
2. **`scene_schema.py` shot_schema self-import**: Removed broken `from shot_schema import ShotSchema` (file didn't exist).
3. **`preset_isolation.py` undeclared `tempfile`**: Line 7 used `tempfile` without import — rebuilt tool cleanly.
4. **`preset_isolation.py` undeclared `dbg_file`**: Line 26 referenced undefined `dbg_file` variable — removed dead code.
5. **`preset_isolation.py` variant JSON missing `name`**: `Preset.__init__` requires `data["name"]` — added `name` field in `create_stage_variant()`.
6. **`apply_stage_b/c` timing = 0**: Set ALL timing to 0.0 → Stage B div-by-zero → Fixed to preserve `move_start/move_end/hold_start_dur/hold_end_dur` from base preset.

## Files Produced

```
demo_output/
  suspense_push_A_base.mp4          5.0s | 200KB
  suspense_push_A_base.cmd.txt       315B
  suspense_push_A_base.stderr.log      0B
  suspense_push_A_base.params.json   635B
  suspense_push_A_base.report.json  418B

  suspense_push_B_motion.mp4         5.3s | 404KB
  suspense_push_B_motion.cmd.txt     321B
  suspense_push_B_motion.stderr.log    0B
  suspense_push_B_motion.params.json 641B
  suspense_push_B_motion.report.json 425B

  suspense_push_C_lighting.mp4       5.3s | 404KB
  suspense_push_C_lighting.cmd.txt   327B
  suspense_push_C_lighting.stderr.log  0B
  suspense_push_C_lighting.params.json 646B
  suspense_push_C_lighting.report.json 434B

  suspense_push_D_full.mp4           5.4s | 388KB
  suspense_push_D_full.cmd.txt       315B
  suspense_push_D_full.stderr.log      0B
  suspense_push_D_full.params.json   647B
  suspense_push_D_full.report.json   418B

  suspense_push_isolation_summary.json
```

## Next: Awaiting User Instruction

All 4 stages pass. Isolation tool is trusted.
Next step: golden locking OR deeper investigation of why PIL path is slower than zoompan (5.3s vs 1.7s for same content).
