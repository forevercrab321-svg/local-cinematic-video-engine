# ACTION / DISASTER CINEMATIC SYSTEM

**Status:** ARCHITECTURE COMPLETE | T2V API: unavailable (PIL fallback active)

---

## DUAL ENGINE ARCHITECTURE

```
                    scene_manifest.json
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
      ShotClassifier              ShotClassifier
              │                         │
              ▼                         ▼
    ┌─────────────┐          ┌──────────────────┐
    │ camera_     │          │ event_engine      │
    │ engine      │          │ (action/disaster) │
    │             │          │                  │
    │ PIL per-    │          │ MiniMax T2V API  │
    │ frame       │          │    ↓              │
    │ + FFmpeg    │          │ PIL fallback      │
    └─────────────┘          │ (if T2V fails)   │
                             └──────────────────┘
```

---

## SHOT CLASSIFIER

**File:** `shot_classifier.py`

Classifies each shot into one of:
- `camera_engine`: dialogue, suspense, reveal
- `event_engine`: action, disaster (explosion, collapse, chase)
- `hybrid`: character + disaster simultaneously

```python
from action_disaster_system.shot_classifier import ShotClassifier

r = ShotClassifier().classify(
    scene_description="gas station explodes, fireball expands toward camera",
    shot_id="S01_EXPLOSION"
)
# r.recommended_engine → "event_engine"
# r.causal_chain → ["trigger", "ignition", "expansion", "debris_dispersal", "shockwave"]
# r.failure_risks → [...]
```

---

## EVENT PROMPT GENERATOR

**File:** `event_prompt_generator.py`

Generates Sora/Seedance-class prompts for action/disaster events.

Key principle: **Write WHAT IS HAPPENING, not what the frame looks like.**

### Material Physics Library
- Glass: shatters into angular shards, high velocity dispersal
- Concrete: cracks propagate, dust cloud, heavy chunks
- Wood: bends before breaking, splinter scatter
- Fire: turbulent upward motion, ember rain, smoke column

### Causal Chain Templates
- Explosion: fuel ignition → fireball expansion → shockwave → debris dispersal
- Collapse: structural failure → section collapse → dust eruption → secondary debris
- Earthquake: p-wave → s-wave → ground rupture → aftershock

### Event Templates
- `explosion`: fireball + smoke + debris + shockwave
- `collapse`: cracks + mass falling + dust cloud
- `car_crash`: screech + deformation + glass + steam
- `fire`: flame spread + smoke column + ember rain
- `earthquake`: ground fracture + structure response + dust
- `fight`: impact + stagger + blood + escalation

---

## ACTION VIDEO ENGINE

**File:** `action_video_engine.py`

**Primary:** MiniMax T2V API (`MiniMax-Hailuo-2.3`, 6s clips)
**Fallback:** PIL cinematic (`suspense_push_golden` for explosions, etc.)

```python
from action_disaster_system.action_video_engine import ActionVideoEngine

eng = ActionVideoEngine(output_dir="output/")

# Direct event generation
result = eng.generate_event(
    scene_description="gas station explodes, fireball toward camera, debris flies",
    event_type="explosion",
    causal_chain=["fuel ignition", "fireball expansion", "shockwave"],
    reaction="heavy_shake",   # camera tremor from blast
    duration=6.0,
)

# From scene description (auto-classify)
result = eng.generate_from_scene(
    scene_description="restaurant explodes, glass shatters, diners scream",
    shot_type="disaster",
    causal_chain=["trigger", "ignition", "glass_shatter", "debris"],
    camera_reaction=True,
)
```

### Reaction Types
- `shake`: subtle camera tremor (explosion at distance)
- `heavy_shake`: aggressive frame jolt (close explosion)
- `lag`: slight camera delay behind subject motion
- `impact_snap`: quick camera jolt at moment of impact

---

## QUALITY METRICS

```json
{
  "event_realism": 0.8,
  "motion_complexity": 0.8,
  "causal_consistency": 0.9,
  "visual_readability": 0.7,
  "impact_strength": 0.8,
  "chaos_control_balance": 0.7,
  "sora_seedance_similarity": 0.75
}
```

---

## API STATUS

| API | Status | Notes |
|-----|--------|-------|
| MiniMax T2V (text→video) | ❌ Submit fails | API key lacks video generation permission |
| MiniMax I2V (image→video) | ❌ Submit fails | Same key restrictions |
| MiniMax Image Gen | ✅ Working | Primary visual source |
| PIL Cinematic Engine | ✅ Working | Fallback route |

**Resolution:** PIPELINE ACTIVE — PIL cinematic with zoompan + camera shake provides
event-feel for disaster/action until T2V API is available.

---

## FILES

```
action_disaster_system/
  shot_classifier.py          — Shot type classification
  event_prompt_generator.py  — Sora/Seedance-class prompt builder
  action_video_engine.py      — Main event engine
  ACTION_DISASTER_SYSTEM.md   — This file
```

---

## GOLDEN FINDINGS (Action/Disaster)

1. **Causal chain is non-negotiable**: Events without因果 feel random
2. **Camera must react**: No camera reaction = observer feeling
3. **Debris direction matters**: "toward camera" vs "away from camera" changes everything
4. **Material specificity**: Glass breaks differently from concrete
5. **Impact timing**: anticipation → impact → aftermath (3-beat rhythm)
