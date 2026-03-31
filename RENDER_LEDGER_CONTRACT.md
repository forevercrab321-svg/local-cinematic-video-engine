# RENDER_LEDGER_CONTRACT.md

**Status:** LOCKED

The render ledger is the authoritative record of a batch render session.
One ledger file per scene manifest render.

---

## Top-Level Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `ledger_version` | string | ✅ | Contract version, e.g. `"v1.0"` |
| `scene_id` | string | ✅ | From manifest or derived from manifest filename |
| `manifest_file` | string | ✅ | Absolute path to manifest that was rendered |
| `render_started_at` | string | ✅ | ISO-8601 timestamp when render began |
| `render_completed_at` | string | ✅ | ISO-8601 timestamp when render finished |
| `total_shots` | int | ✅ | Total shots in manifest |
| `passed` | int | ✅ | Shots with `validation_status = pass` |
| `degraded_passed` | int | ✅ | Shots with `validation_status = degraded_pass` |
| `failed` | int | ✅ | Shots with `validation_status = fail` |
| `skipped` | int | ✅ | Shots skipped (already rendered, `--skip-existing`) |
| `total_render_time_sec` | float | ✅ | Wall-clock time for entire batch |
| `all_pass` | bool | ✅ | `true` if `failed == 0` |
| `effects_summary` | EffectsSummary | ✅ | Aggregate effect stats |
| `shot_results` | ShotResult[] | ✅ | Per-shot records (in order) |

### Invariants (must always hold)

```
passed + degraded_passed + failed + skipped == total_shots
all_pass == (failed == 0)
```

---

## EffectsSummary

```json
{
  "total_effects_requested": 18,
  "total_effects_applied": 11,
  "total_effects_skipped": 7,
  "degraded_count": 2,
  "unique_effects_applied": ["flicker", "glow_drift", "vignette_pulse"],
  "unique_effects_skipped": ["breathing", "micro_shake", "color_grade"]
}
```

All fields required.

---

## ShotResult

Each entry in `shot_results[]` is the full RENDER_RESULT_CONTRACT dict for that shot.

In addition, it MUST contain:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `shot_id` | string | ✅ | From manifest |
| `shot_index` | int | ✅ | 0-based index in manifest |
| `ledger_note` | string | | Human-readable one-liner for this shot |

---

## Ledger File Naming

```
 scene_manifest_{scene_id}_render_ledger.json
```

Placed in the same directory as the manifest, or in `--output-dir` if specified.

---

## Contract Version

v1.0 — LOCKED 2026-03-31
