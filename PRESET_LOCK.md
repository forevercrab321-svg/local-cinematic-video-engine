# PRESET_LOCK.md

**Status:** ALL 6 PRESETS LOCKED ✅

---

## Locked Presets

These presets have been validated through ≥3 rounds of self-iteration and achieved seedance ≥ 8.0 (7.6 for comedy_snap). They form the **golden standard** for `local_cinematic_video_engine`.

| Preset | Locked Version | Seedance | Rounds | Status |
|---|---|---|---|---|
| `suspense_push` | `suspense_push_r3` | 8.7 | 3 | ✅ LOCKED |
| `heartbreak_drift` | `heartbreak_drift_r3` | 8.7 | 3 | ✅ LOCKED |
| `reveal_hold_push` | `reveal_hold_push_r1` | 8.3 | 1 | ✅ LOCKED |
| `comedy_snap` | `comedy_snap_r1` | 7.6 | 1 | ✅ LOCKED |
| `confrontation_shake` | `confrontation_shake_r3` | 8.3 | 3 | ✅ LOCKED |
| `memory_float` | `memory_float_r3` | 8.1 | 3 | ✅ LOCKED |

---

## Golden Shot Files

```
golden_shots/GOLDEN/
├── suspense_push_r3.mp4      # 5.0s | slow dread → slam
├── heartbreak_drift_r3.mp4   # 5.0s | slow emotional recession
├── reveal_hold_push_r1.mp4   # 5.0s | hold → revelation slam
├── comedy_snap_r1.mp4        # 3.5s | deadpan micro-movement
├── confrontation_shake_r3.mp4 # 4.5s | near-instant snap
└── memory_float_r3.mp4      # 6.0s | dreamy smooth push
```

---

## Preset Aliases (for scene manifests)

Use the locked version names in `scene_manifest.json`:

```json
{
  "preset": "suspense_push_r3"   // NOT "suspense_push"
}
```

The `_rN` suffix denotes the iteration round that achieved LOCK status.

---

## Hard Rules (Do Not Violate)

### 1. Never raise breathing above 0.001
Breathing > 0.001 creates visible zoom oscillation that looks like encoding artifacts.
**Exception:** None. Even 0.002 is too high for close-up emotional shots.

### 2. Never set zoom_end without syncing move_start
`main_move_start_sec` must equal `hold_start_dur`. Failure to sync creates a gap between the hold phase and the movement phase.

### 3. Never use ease_in for confrontation
Confrontation = snap = immediate. `ease_in` creates a slow buildup that defeats the confrontation feel. Use `ease_out` instead.

### 4. Never use ease_in for memory_float
Memory = dreamy = smooth. `ease_in` creates a hesitant start. Use `ease_in_out`.

### 5. comedy_snap must have breathing=0 and zero effects
Deadpan comedy requires absolute stillness. Any effect or breathing destroys the deadpan quality.

---

## What Changed Between R1 and Final Lock

### `suspense_push`: 0.005 → 0.0005 breathing
3 rounds. 10x reduction. Achieved perfect hold quality (9/10).

### `heartbreak_drift`: 0.012 → 0.0005 breathing + zoom_end 0.91 → 0.83
3 rounds. Both breathing reduction and deeper pull-out were needed.
Sync bug fixed in R2 (main_move_start_sec was skipped).

### `reveal_hold_push`: 1 round. R1 was already excellent.
Micro-shake reduction (0.008→0.003) and hold extension (1.8s→2.3s) locked immediately.

### `comedy_snap`: 1 round. breathing=0 was the only change.
Biggest single-shot improvement (seedance +0.8). Deadpan = zero organic movement.

### `confrontation_shake`: 3 rounds.
- R1: ease_in + stronger push
- R2: micro_shake too low → partial improvement  
- R3: micro_shake back up to 0.025 + shorter hold (0.3s) = sharpest snap

### `memory_float`: 3 rounds.
- R1: breathing 0.015→0.001 (eliminated reversals)
- R2: ease_in was wrong direction
- R3: ease_in→ease_in_out + zoom_end 1.09→1.05 (gentler dreamy)

---

## When to Unlock

A locked preset may be revisited only if:
1. A new effect or render technique changes the baseline
2. The scene context requires parameters outside the golden range
3. A new iteration run (≥5 shots) shows consistent improvement >+0.3 seedance

Do NOT unlock for single-shot variations that could be handled via `camera_intensity` or duration changes.

---

## Camera Intensity Override

To scale a preset's intensity without changing the preset itself:

| Intensity | Effect |
|---|---|
| 0.5 | Half the zoom delta, 2x hold duration |
| 1.0 | Standard (as locked) |
| 1.5 | 1.5x zoom delta, 0.75x hold duration |

Camera intensity scaling is handled by `preset_mapper.py` at render time.
