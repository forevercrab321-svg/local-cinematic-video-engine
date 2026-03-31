# PRESET_ROUTING_LOCK.md

**Version:** 3.0
**Date:** 2026-03-31
**Status:** LOCKED — Routing rules validated with benchmark

---

## ENGINE ROUTING v3 — Three Validated Modes

### Route A: `static_ffmpeg`
**Input:** keyframe image → pad to target resolution → encode
**Path:** `ffmpeg -loop 1 -i keyframe -vf "scale+pad" -c:v libx264`

| Attribute | Value |
|---|---|
| Motion | None |
| Timing control | None |
| Output resolution | Correct (9:16, 16:9, 1:1) |
| Render time (5s) | ~0.74s |
| File size (5s) | ~72KB |
| Quality | Lossy from single encode |

**Use case:** Text overlays, logo cards, background plates, any shot without motion.

---

### Route B: `simple_zoompan_ffmpeg`
**Input:** keyframe → FFmpeg zoompan with recursive `zoom` variable → scale to target
**Path:**
```bash
ffmpeg -loop 1 -i keyframe \
  -vf "scale=<PRE_S>:force_original_aspect_ratio=decrease,pad=<PRE_S>:<PRE_S>:(ow-iw)/2:(oh-ih)/2:black,setsar=1,\
       zoompan=z='<EXPR>':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',scale=<OUT_W>:<OUT_H>"
```
Where `<PRE_S>` = pre-scale dimension large enough to cover the target zoom range.

**VALIDATED working expressions (RC=0):**
```bash
# Push-in (1.0 → 1.12):     z='min(zoom+0.001,1.12)'
# Pull-out (1.12 → 1.0):    z='max(zoom-0.001,1.0)'
# The zoom variable increments by 0.001 each frame
```

**VALIDATED working for portrait 9:16 (800×800 square source):**
- Pre-scale: 2150×2150
- Zoom expression: `z='min(zoom+0.001,1.12)'`
- Post-scale: `scale=1080:1920`
- Total filter chain: `scale=2150:2150:force_original_aspect_ratio=decrease,pad=2150:2150:(ow-iw)/2:(oh-ih)/2:black,setsar=1,zoompan=...:scale=1080:1920`
- Output: **1080×1920 ✅** | Time: **0.94s** (5.4x faster than PIL) | Frames: 120 ✅

**What the zoom effect looks like:**
- At zoom=1.0: content covers ~56% of portrait width (square in portrait frame)
- At zoom=1.12: content covers 100% of portrait width (square fills portrait width)
- Perceived effect: subject "steps closer" / "camera push-in"
- NOT a true portrait zoom — it expands the visible square content to fill portrait

**⚠️ Requirements for portrait to work:**
1. Source must be upscaled to ≥ `<PRE_S>` where `<PRE_S>` = `target_long_side × zoom_max`
   - For 1080×1920 target with zoom_max=1.12: `<PRE_S>` = 1920 × 1.12 = 2150
2. Post-scale must be explicit: `scale=1080:1920` at end of filter chain
3. Without post-scale, output = `<PRE_S>`×`<PRE_S>` (wrong portrait)

**AVAILABLE expressions (RC=0):** `zoom+Δ` / `min(zoom+Δ,cap)` / `max(zoom-Δ,floor)`
**BROKEN (RC=234):** `n`, `t`, `if(...)`, `zoom+n*Δ`, `zoom+t*Δ`

**Use when:**
- Portrait 9:16 short drama lightweight motion
- Source is square or pre-scaled to large enough canvas
- Simple directional push-in or pull-out only
- No hold / no beat timing / no easing / no emotional timing
- Speed priority over camera quality

---

### Route C: `cinematic_pil` ⭐ PRIMARY ENGINE
**Input:** keyframe → Python/PIL per-frame → JPEG sequence → FFmpeg encode

| Attribute | Value |
|---|---|
| Motion | Hold + easing + push/pull + drift + shake |
| Timing control | Full (hold, beat, reveal, slam, deadpan) |
| Effects | breathing, micro_shake, glow, flicker, vignette |
| Output resolution | Always correct (9:16, 16:9, any) |
| Render time (5s) | ~5.0s |
| File size (5s) | ~340KB |
| Portrait support | ✅ Full |

**Use when:** Any emotionally timed shot. Hold → beat → slam. Reveal. Comedy. All golden cinematic presets.

---

## Benchmark Results (5s @ 24fps, 1080×1920, 800×800 square source)

| Mode | Time | Size | Resolution | Motion Quality | Cinematic Quality | Verdict |
|---|---|---|---|---|---|---|
| `static_ffmpeg` | **0.74s** | 72KB | 1080×1920 ✅ | None | N/A | Fast, correct |
| `simple_zoompan_ffmpeg` | **0.94s** | 72KB | 1080×1920 ✅ | Simple push/pull | Limited | ✅ VALIDATED |
| `cinematic_pil` | **5.04s** | 340KB | 1080×1920 ✅ | Full hold/easing/shake | Director-grade | ✅ PRIMARY |

**Speed ratio:** zoompan = **5.4x faster** than PIL

---

## Preset → Route Mapping

| Preset | Route | Reasoning |
|---|---|---|
| `suspense_push` | `cinematic_pil` | Hold 1.2s → easing push → emotional slam |
| `heartbreak_drift` | `cinematic_pil` | Slow emotional recession + vignette |
| `reveal_hold_push` | `cinematic_pil` | Hold 2.3s → slam, impossible in zoompan |
| `comedy_snap` | `cinematic_pil` | Deadpan micro-stillness, no zoompan equivalent |
| `confrontation_shake` | `cinematic_pil` | Shake + snap, no zoompan equivalent |
| `memory_float` | `cinematic_pil` | Smooth dreamy drift, no zoompan equivalent |
| Text/card overlay | `static_ffmpeg` | No motion |
| Light tension push (square source) | `simple_zoompan_ffmpeg` | Portrait push-in, speed-priority |

---

## Hard Rules

1. **`cinematic_pil` is the primary engine.** Never route a golden cinematic preset to zoompan.
2. **`simple_zoompan_ffmpeg` is validated for portrait push-in/pull-out only.** Other emotional timing presets still go to PIL.
3. **Pre-scale math:** For 9:16 portrait at zoom_max: pre_scale = 1920 × zoom_max.
4. **Always include post-scale:** `scale=1080:1920` after zoompan for portrait output.
5. **Never use `n`, `t`, `if()` in zoompan expressions** — they fail with RC=234.
6. **Square source (800×800) is the validated test case.** Non-square portrait sources require separate validation.

---

## What Changed in v3

v1: Zoompan treated as non-viable (RC=234 on tests).
v2: Found recursive `zoom` works, but portrait output was broken.
v3: Pre-scale (2150×2150) + post-scale (1080:1920) makes portrait zoompan work at 1080×1920 ✅ in 0.94s.

**Limitation:** The zoom effect is "content expansion" not true portrait zoom-in. Pre-scale quality degrades for non-square sources.
