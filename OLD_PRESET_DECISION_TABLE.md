# OLD_PRESET_DECISION_TABLE.md

**Purpose:** Decide fate of each OLD schema preset.

## Decision Criteria

| Decision | Criteria |
|----------|----------|
| `keep_as_static_shell` | Preset is intentionally a static pad / utility. Has no cinematic motion intent. Confirmed as OLD schema with `degraded_pass` is acceptable. |
| `migrate_to_new_schema` | Has cinematic intent but wrong schema. Should create new schema counterpart and deprecate old. |
| `deprecate` | Misleading name or redundant with existing new-schema preset. Remove from available presets. |

---

## OLD Schema Presets

### `suspense`

| Field | Value |
|-------|-------|
| Current schema | OLD (`camera_moves`, `effects`) |
| Current route | `static_ffmpeg` |
| Current validation | `degraded_pass` |
| Cinematic intent | None (static pad) |
| New schema counterpart | `suspense_push` (exists) |
| **Decision** | **keep_as_static_shell** |

**Rationale:** `suspense` is a static utility preset (no camera motion). Its name suggests suspense but it is intentionally static. New schema users should use `suspense_push`. Old schema `suspense` can remain as a fast static pad.

---

### `heartbreak`

| Field | Value |
|-------|-------|
| Current schema | OLD |
| Current route | `static_ffmpeg` |
| Current validation | `degraded_pass` |
| Cinematic intent | None (static) |
| New schema counterpart | `heartbreak_drift` (exists) |
| **Decision** | **keep_as_static_shell** |

**Rationale:** Static utility preset. `heartbreak_drift` provides cinematic drift for new productions.

---

### `reveal`

| Field | Value |
|-------|-------|
| Current schema | OLD |
| Current route | `static_ffmpeg` |
| Current validation | `degraded_pass` |
| Cinematic intent | None (static) |
| New schema counterpart | `reveal_hold_push` (exists) |
| **Decision** | **keep_as_static_shell** |

**Rationale:** Static utility preset. `reveal_hold_push` provides cinematic reveal for new productions.

---

### `comedy`

| Field | Value |
|-------|-------|
| Current schema | OLD |
| Current route | `static_ffmpeg` |
| Current validation | `degraded_pass` |
| Cinematic intent | None (static) |
| New schema counterpart | `comedy_snap` (exists) |
| **Decision** | **keep_as_static_shell** |

**Rationale:** Static utility preset. `comedy_snap` provides cinematic snap for new productions.

---

## Summary Table

| Preset | Schema | Route | Validation | New Schema Replacement | Decision |
|--------|--------|-------|-----------|----------------------|----------|
| `suspense` | old | static_ffmpeg | degraded_pass | `suspense_push` | **keep_as_static_shell** |
| `heartbreak` | old | static_ffmpeg | degraded_pass | `heartbreak_drift` | **keep_as_static_shell** |
| `reveal` | old | static_ffmpeg | degraded_pass | `reveal_hold_push` | **keep_as_static_shell** |
| `comedy` | old | static_ffmpeg | degraded_pass | `comedy_snap` | **keep_as_static_shell** |

---

## Policy

1. OLD presets remain usable as static shells in scene manifests
2. Scene manifests should prefer NEW schema presets for cinematic shots
3. OLD presets are marked `degraded_pass` to make the schema difference visible
4. No OLD preset is deprecated — all have valid static utility purpose
5. Scene manifests may freely mix OLD (static pad shots) and NEW (cinematic) presets

## Migration Path

For scene productions:
- Static background / establishing shots → OLD presets (fast, <1s)
- Cinematic shots → NEW schema presets (full effects, 5-6s)
