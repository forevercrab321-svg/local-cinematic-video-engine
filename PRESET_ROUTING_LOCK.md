# PRESET_ROUTING_LOCK.md

**Version:** 2.0
**Date:** 2026-03-31
**Status:** LOCKED — Do not change routing rules without new evidence

---

## ENGINE ROUTING v2 — Three Modes

### Route A: `static_ffmpeg`
**Input:** keyframe image → pad to target resolution → encode
**Path:** `ffmpeg -loop 1 -i keyframe -vf "scale+pad" -c:v libx264`

| Attribute | Value |
|---|---|
| Motion | None |
| Timing control | None |
| Output resolution | Correct (9:16, 16:9, 1:1) |
| Render time (5s) | ~0.67s |
| File size (5s) | ~69KB |
| Use case | Text overlays, logo, static plates |

**When to use:** When no camera motion is needed. Background plate, caption card.

---

### Route B: `simple_zoompan_ffmpeg`
**Input:** keyframe image → FFmpeg zoompan filter with recursive `zoom` variable
**Path:** `ffmpeg -loop 1 -i keyframe -vf "zoompan=z='min(zoom+Δ,capped)'" -c:v libx264`

| Attribute | Value |
|---|---|
| Motion | Single directional zoom-in or zoom-out |
| Timing control | None (linear, constant speed) |
| Easing | None |
| Hold phase | Not supported |
| Effects | None |
| Output resolution | **BROKEN for portrait** (see below) |

**Zoom expression (verified working):**
```bash
# Push-in (zoom in):  z='min(zoom+0.001,1.12)'
# Pull-out (zoom out): z='max(zoom-0.001,0.90)'
```

**Zoom expression (FAILS with RC=234):**
```bash
# These ALL fail with FFmpeg zoompan:
# - z='if(lt(t,1),zoom+0.001,zoom)'    ← t variable unavailable
# - z='if(zoom<1.1,zoom+0.001,zoom)'  ← if() not supported
# - z='zoom+t*0.001'                   ← t unavailable
# - z='zoom+n*0.001'                   ← n unavailable
```

#### ⚠️ Portrait Output Broken
Zoompan produces output resolution = zoompan INPUT resolution (not the scaled/padded output).
- Portrait pad (1080x1920) → zoompan → **1280x720 landscape** ❌
- This is a FFmpeg zoompan structural limitation, not configurable.

**Use only when:**
- Source image aspect ratio = output aspect ratio (square → square, or landscape → landscape)
- No hold / beat / reveal timing needed
- Lightweight motion is acceptable (no emotional timing)

**Portrait 9:16 short drama: NOT usable.** Portrait video requires correct 1080x1920 output — zoompan cannot provide this with recursive zoom expressions.

---

### Route C: `cinematic_pil` ⭐ PRIMARY
**Input:** keyframe image → Python/PIL per-frame transform → JPEG sequence → FFmpeg encode

| Attribute | Value |
|---|---|
| Motion | Hold + easing + push/pull + drift + shake |
| Timing control | Full (hold duration, move start/end, easing curves) |
| Effects | breathing, micro_shake, glow, flicker, vignette |
| Output resolution | Always correct (9:16, 16:9, any) |
| Render time (5s) | ~5.0s |
| File size (5s) | ~340KB |
| Portrait support | ✅ Full |

**Use when:** Any emotionally timed shot. Hold → beat → slam. Reveal. Comedy timing. All core cinematic presets.

---

## Benchmark Results (5s @ 24fps, 1080×1920)

| Mode | Time | Size | Resolution | Verdict |
|---|---|---|---|---|
| `static_ffmpeg` | **0.67s** | 69KB | ✅ 1080×1920 | Fast, correct, no motion |
| `simple_zoompan_ffmpeg` | **0.89s** | 40KB | ❌ 1280×720 (broken) | Fast but WRONG resolution |
| `cinematic_pil` | **4.96s** | 340KB | ✅ 1080×1920 | Slow but correct + full control |

> **Zoompan is 5.6x faster but produces broken portrait output.**
> PIL is the only production-safe path for portrait video.

---

## Preset → Route Mapping

| Preset | Route | Reasoning |
|---|---|---|
| `suspense_push` | `cinematic_pil` | Hold → push-in with easing, emotional timing |
| `heartbreak_drift` | `cinematic_pil` | Slow pull-out with breathing, vignette |
| `reveal_hold_push` | `cinematic_pil` | Hold (2.3s) → slam, impossible in zoompan |
| `comedy_snap` | `cinematic_pil` | Deadpan micro-movement, no zoompan equivalent |
| `confrontation_shake` | `cinematic_pil` | Shake + snap, no zoompan equivalent |
| `memory_float` | `cinematic_pil` | Smooth dreamy drift, no zoompan equivalent |
| Text/card overlay | `static_ffmpeg` | No motion |
| Simple push-in (landscape only) | `simple_zoompan_ffmpeg` | Only for square/landscape where aspect ratio matches |

---

## Hard Rules

1. **Portrait 9:16 → always `cinematic_pil`.** There is no alternative.
2. **`simple_zoompan_ffmpeg` is NOT a general-purpose motion path.** It is a narrow case for square/landscape inputs only.
3. **Never route a cinematic preset through zoompan** just because "it looks similar."
4. **Zoompan recursive `zoom` variable works. `t`, `n`, `if()` do not.**
5. **PIL is the primary engine.** Zoompan is never the default for short drama production.

---

## What Changed in v2

v1 routing treated `static_ffmpeg` and `simple_zoompan_ffmpeg` as valid fallback paths.
v2 clarifies that zoompan's portrait output bug makes it **non-viable for portrait production**.
`cinematic_pil` is the only production-safe path for all cinematic presets.
