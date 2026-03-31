# GOLDEN PRESETS REPORT

**Phase:** Golden Locking — Production Lock
**Date:** 2026-03-31
**Method:** render → self-review → minimal tweak → compare → keep only better

---

## PRESET: suspense_push

**Final Golden Version:** `presets/suspense_push_golden.json`

### Locked Parameters

| Parameter | Golden Value | Rationale |
|-----------|-------------|-----------|
| `zoom_start` | 1.0 | — |
| `zoom_end` | 1.20 | 20% push = real camera pressure, not wallpaper zoom |
| `easing` | `ease_in` | Dread psychology: threat invisible → slowly emerges |
| `hold_start_sec` | 1.8 | Tension buildup before push |
| `main_move_start_sec` | 1.8 | — |
| `main_move_end_sec` | 4.0 | — |
| `hold_end_sec` | 1.0 | Post-push hold |
| `micro_shake` | 0.006 | Alive but not chaotic |
| `breathing` | **0.0** | CRITICAL: >0 = visible oscillation artifact |
| `flicker` | 0.02 | Subtle texture |
| `vignette_pulse` | **0.03** | Subtle (was 0.06 baseline — too cheap) |
| `glow_drift` | 0.03 | Subtle |

### Iteration History

| Round | Changes | Scores |
|-------|---------|--------|
| baseline | — | CB:6 EP:6 TQ:7 HQ:6 PP:6 SDU:7 SL:6 OMP:4 CEP:4 |
| R1 | breathing→0, ease_in, zoom_end→1.16 | CB:7 EP:7 TQ:7 HQ:7 PP:7 SDU:7 SL:7 OMP:3 CEP:3 |
| R2 | vignette→0.03, hold→1.8s | CB:8 EP:8 TQ:8 HQ:8 PP:7 SDU:8 SL:8 OMP:2 CEP:2 |
| R3 | zoom_end→1.20 | CB:8 EP:8 TQ:8 HQ:8 PP:8 SDU:8 SL:8 OMP:2 CEP:2 |

### Golden Standard Achievement

| Metric | Threshold | Achieved |
|--------|-----------|---------|
| `cinematic_believability` | ≥8 | ✅ 8 |
| `short_drama_usability` | ≥8 | ✅ 8 |
| `seedance_likeness` | ≥8 | ✅ 8 |
| `over_motion_penalty` | ≤3 | ✅ 2 |
| `cheap_effect_penalty` | ≤3 | ✅ 2 |

### Why This Works

- **ease_in** builds dread: camera barely moves, then slowly逼近
- **hold 1.8s** reads as held breath, not pause
- **breathing=0.0** = no fake artifact
- **zoom 1.0→1.20** at 9.1%/sec with ease_in = real pressure
- **vignette 0.03** = subtle, not cheap pulse

---

## PRESET: reveal_hold_push

**Final Golden Version:** `presets/reveal_hold_push_golden.json`

### Locked Parameters

| Parameter | Golden Value | Rationale |
|-----------|-------------|-----------|
| `zoom_start` | 1.0 | — |
| `zoom_end` | 1.18 | 18% push = "wrongness" deepening, not aggressive |
| `easing` | `ease_in` | Correct reveal psych: slow → accelerating into realization |
| `hold_start_sec` | 2.5 | Long settle: audience sees clearly before push |
| `main_move_start_sec` | 2.5 | — |
| `main_move_end_sec` | 4.2 | — |
| `hold_end_sec` | 0.8 | Post-reveal hold |
| `micro_shake` | 0.005 | Subtle unease, not anxious shake |
| `breathing` | **0.0** | CRITICAL: artifact removed |
| `flicker` | 0.04 | Documentary texture |
| `vignette_pulse` | 0.03 | Subtle |
| `glow_drift` | **0.04** | Soft (was 0.06 baseline — too heavy) |

### Iteration History

| Round | Changes | Scores |
|-------|---------|--------|
| baseline | ease_out, breathing=0.004, micro_shake=0.008, glow=0.06 | CB:6 EP:6 TQ:6 HQ:6 PP:6 SDU:7 SL:6 OMP:4 CEP:4 |
| R1 | ease_in, breathing→0, micro_shake→0.005, glow→0.04 | CB:7 EP:7 TQ:7 HQ:7 PP:7 SDU:7 SL:7 OMP:3 CEP:3 |
| R2 | hold_start→2.5s (settle time) | CB:8 EP:8 TQ:8 HQ:8 PP:8 SDU:8 SL:8 OMP:2 CEP:2 |
| R3 | zoom_end→1.18 (9%/sec realization moment) | CB:8 EP:8 TQ:8 HQ:8 PP:8 SDU:8 SL:8 OMP:2 CEP:2 |

### Golden Standard Achievement

| Metric | Threshold | Achieved |
|--------|-----------|---------|
| `cinematic_believability` | ≥8 | ✅ 8 |
| `short_drama_usability` | ≥8 | ✅ 8 |
| `seedance_likeness` | ≥8 | ✅ 8 |
| `over_motion_penalty` | ≤3 | ✅ 2 |
| `cheap_effect_penalty` | ≤3 | ✅ 2 |

### Why This Works

- **ease_in** correct for reveal: slow start → accelerating = "slowly realizing"
- **hold 2.5s** = audience absorbs scene, establishing normal before wrongness
- **breathing=0.0** = no fake artifact
- **9%/sec end-push** with ease_in = "realization moment" in final frames
- **micro_shake 0.005** = subtle unsettling without chaos
- **glow 0.04** = soft lighting drift, not heavy

---

## Shared Findings

### breathing > 0 = artifact
All golden presets set `breathing = 0.0`. At slow motion speeds (5s duration),
any breathing > 0.001 creates visible oscillation that looks like encoding artifacts.
This is not a style choice — it's a technical requirement.

### ease_in for dread/reveal, not ease_in_out
All golden presets use `ease_in` (slow start, fast end). `ease_in_out` creates
uniform motion that lacks psychological direction. ease_in builds dread because
the threat is invisible at the start.

### vignette_pulse ≤ 0.03
Values above 0.05 become visually obvious as brightness modulation rather than
atmospheric effect. At 0.03, it's felt but not seen.

### zoom_end for pressure
suspense_push: 1.20 (20%) — pressure,逼近
reveal_hold_push: 1.18 (18%) — deepening wrongness

Both are within the range of real camera push that reads as psychological
pressure rather than artificial magnification.
