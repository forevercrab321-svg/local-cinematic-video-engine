# 🎬 local_cinematic_video_engine

**Director-grade cinematic shot video engine — no AI, no GPU, pure Python + FFmpeg.**

Input: keyframe image or video frame  
Output: H.264 MP4 with real camera motion, easing curves, micro-effects

---

## Quick Start

```bash
cd ~/.openclaw/workspace/skills/local_cinematic_video_engine

# Single shot
python3 run_shot.py --image KEYFRAME.png --preset reveal_hold_push

# Diagnose FFmpeg filter chain
python3 debug.py --image KEYFRAME.png --preset suspense_push
```

---

## Presets (6 available)

| File | Name | Duration | Camera Motion | Mood |
|------|------|----------|--------------|------|
| `suspense_push` | Suspense Push | 5s | hold→slow→slam (1.0→1.12x) | Dread → slam |
| `heartbreak_drift` | Heartbreak Drift | 5s | slow pull-out (1.0→0.91x) | Slow recession |
| `confrontation_shake` | Confrontation Shake | 4.5s | snap-in + tremor | Conflict, tension |
| `reveal_hold_push` | Reveal Hold → Push | 5s | hold→hold→SLAM (1.0→1.15x) | Recognition → hit |
| `comedy_snap` | Comedy Snap | 3.5s | deadpan hold→micro | The "yeah" face |
| `memory_float` | Memory Float | 6s | slow drift + breath | Dreamlike |

---

## CLI

```bash
# Single shot
python3 run_shot.py --image KEYFRAME.png --preset reveal_hold_push

# With options
python3 run_shot.py \
  --image KEYFRAME.png \
  --preset comedy_snap \
  --duration 3.5 \
  --fps 24 \
  --ratio 9:16 \
  --quality high \
  --camera push_in \
  --intensity 1.2 \
  --shot SHOT_01 \
  --out ./output/

# Batch render
python3 run_shot.py --batch scene_manifests/IN_THE_GROUP_CHAT.json

# Debug FFmpeg filter chain
python3 debug.py --image KEYFRAME.png --preset suspense_push

# Test specific filter
python3 debug.py --image KEYFRAME.png \
  --filter "scale=1458:2592,crop=1458:2592,zoompan=z='1.0':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d=1:fps=24:s=1080x1920"

# List presets
python3 run_shot.py --list-presets

# System check
python3 run_shot.py --check
```

---

## Preset Schema (v1)

```json
{
  "name": "suspense_push",
  "duration_sec": 5.0,
  "fps": 24,
  "aspect_ratio": "9:16",

  "camera": {
    "move": "push_in",
    "zoom_start": 1.00,
    "zoom_end": 1.12,
    "x_start": 0.50,
    "x_end": 0.50,
    "y_start": 0.50,
    "y_end": 0.50,
    "rotation_start_deg": 0.0,
    "rotation_end_deg": 0.1,
    "easing": "ease_in_out"
  },

  "motion": {
    "micro_shake": 0.006,
    "breathing": 0.005,
    "parallax_strength": 0.0
  },

  "lighting": {
    "flicker": 0.02,
    "vignette_pulse": 0.06,
    "glow_drift": 0.03
  },

  "timing": {
    "hold_start_sec": 1.2,
    "main_move_start_sec": 1.2,
    "main_move_end_sec": 4.0,
    "hold_end_sec": 1.0
  },

  "output": {
    "codec": "h264",
    "pix_fmt": "yuv420p"
  }
}
```

---

## Architecture

```
local_cinematic_video_engine/
├── preset.py              ← Preset loader + Preset class
├── engine.py             ← CinematicShotEngine entry point
├── motion.py             ← PIL per-frame camera motion renderer
├── run_shot.py           ← CLI entry point
├── batch.py              ← Batch scene renderer
├── debug.py              ← FFmpeg filter chain debugger
├── presets/
│   ├── PRESET_SPEC.md
│   ├── suspense_push.json
│   ├── heartbreak_drift.json
│   ├── confrontation_shake.json
│   ├── reveal_hold_push.json
│   ├── comedy_snap.json
│   └── memory_float.json
├── scene_manifests/
│   └── IN_THE_GROUP_CHAT.json
└── demo_output/
    ├── DEBUG_*_A_minimal.mp4              ✅ PASS
    ├── DEBUG_*_B_scale_fps.mp4            ✅ PASS
    ├── DEBUG_*_C_zoompan.mp4              ✅ PASS
    ├── DEBUG_*_D_zoompan_dynamic.mp4      ❌ FAIL (zoompan z= doesn't accept if())
    └── DEBUG_*_E_cinematic.mp4             ✅ PASS (PIL pipeline)
```

---

## FFmpeg Debug Report (Definitive)

```
✅ A_minimal              RC=0   — scale+crop baseline
✅ B_scale_fps            RC=0   — + fps filter
✅ C_zoompan_static       RC=0   — zoompan z='1.0' works
❌ D_zoompan_dynamic      RC=234 — z='if(lt(t,4.5),...)' → zoompan z= NO t/n variables
✅ E_cinematic_PIL        RC=0   — PIL per-frame (universal)
```

**Critical findings:**

| zoompan z= expression | Result |
|----------------------|--------|
| `z='1.0'` (static) | ✅ WORKS |
| `z='min(zoom+0.0015,1.2)'` (recursive) | ✅ WORKS — `zoom` is recursive |
| `z='if(lt(t,4.5),1.0,1.12)'` (t-based) | ❌ RC 234 — `t` NOT available in zoompan |
| `z='if(lt(n,48),1.0,1.12)'` (n-based) | ❌ RC 234 — `n` NOT available in zoompan |

**zoompan limitation:** `z=` only has access to the `zoom` variable (previous frame zoom value).
Cannot do: hold windows, easing curves, or time-based conditional zoom without `t` or `n`.

**Working zoompan formula:**
```bash
# Pre-scale → zoompan (recursive) → output
-vf "scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},zoompan=z='min(zoom+{delta},{max_zoom})':x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=1:fps={fps}:s={out_w}x{out_h}"
```
Where `delta = (zoom_end - zoom_start) / total_frames`

**Performance comparison (5s @ 24fps, 1080×1920):**
| Method | Time | File size |
|--------|------|-----------|
| direct FFmpeg | 0.8s | 0.1MB |
| zoompan (linear) | 2s | 0.1MB |
| PIL per-frame | 8-17s | 0.5-0.7MB |

**Engine routing (auto-selects):**
- `has_motion=False` → direct FFmpeg (static pad)
- `linear zoom + no effects` → zoompan (recursive, fast)
- `easing / hold windows / shake / breathing` → PIL per-frame (universal)



```
✅ A_minimal              RC=0   — scale + crop + libx264 encode (baseline)
✅ B_scale_fps            RC=0   — + fps filter (framerate control)
✅ C_zoompan_static       RC=0   — zoompan z='1.0' (static zoompan works)
❌ D_zoompan_dynamic      RC=234 — zoompan z='if(lt(t,4.5),1.0,1.12)' (❌ BROKEN)
✅ E_cinematic_PIL        RC=0   — PIL per-frame → FFmpeg (✅ WORKING PIPELINE)
```

**Critical finding:**
- FFmpeg zoompan `z=` parameter does **NOT** support `if()` expressions
- `zoompan=z='1.0'` works (static)
- `zoompan=z='if(lt(t,4.5),1.0,1.12)'` → **RC 234, "Undefined constant or missing '('"**
- The working pipeline is **PIL per-frame generation → FFmpeg encode** (motion.py)

**Why PIL instead of FFmpeg expressions?**
- FFmpeg 8.1 `scale=w='expr'` evaluates only at init time (not per-frame)
- FFmpeg `zoompan z=` doesn't support `if()` conditionals
- PIL `Image.resize()` + `crop()` works correctly per-frame

---

## Timing System

```
total = hold_start + (main_move_end - main_move_start) + hold_end
         |--- dead --||------- main move ----||--- dead ---|
```

The **beat** (most dramatic moment) is at `main_move_end`.  
The **hold** before the beat = dread/dread/dread.

---

## How motion.py Works

```
1. Extract first frame if input is video (FFmpeg -vframes 1)
2. For each frame at fps:
   a. t = frame_index / total_frames  (0→1)
   b. eased_t = ease(t)               (apply easing curve)
   c. zoom = lerp(zoom_start, zoom_end, eased_t)
   d. pan  = lerp(x_start, x_end, eased_t)
   e. Add micro-shake (deterministic pseudo-random per frame)
   f. Add breathing (sin wave at 0.35Hz)
   g. resize() → crop() → save JPEG
3. FFmpeg encode frame sequence → H.264 MP4
4. Cleanup temp frames
```

---

## Batch Render

```bash
python3 batch.py scene_manifests/IN_THE_GROUP_CHAT.json
# Output: render_ledger.json tracking every shot
```

---

## Hardware

| Component | Requirement | Status |
|-----------|-------------|--------|
| ffmpeg | libx264 | ✅ `/usr/local/bin/ffmpeg` v8.1 |
| Python | 3.8+ | ✅ 3.13 |
| PIL | Image processing | ✅ |
| GPU | Not required | N/A |

**Production-ready. Real MP4 output. No cloud, no AI model needed.**
