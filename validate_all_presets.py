#!/usr/bin/env python3
"""
validate_all_presets.py — Production validation render for all presets.

Tests every preset and captures:
  - schema status
  - route selected
  - render time
  - effects_requested / applied / skipped
  - degraded mode used
  - output file

Usage:
  python3 validate_all_presets.py [--preset <name>]
"""

import subprocess, json, time, sys, os
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).parent
DEMO = SKILL_DIR / "demo_output"
DEMO.mkdir(exist_ok=True)

INPUT_IMAGE = "/Users/monsterlee/.openclaw/media/inbound/file_3---5223086e-a136-4e3a-9c06-8c2363382b8b.jpg"

sys.path.insert(0, str(SKILL_DIR))

# All presets to validate
STATIC_PRESETS = ["suspense", "heartbreak", "reveal", "comedy"]
CINEMATIC_PRESETS = [
    "suspense_push",
    "heartbreak_drift",
    "reveal_hold_push",
    "comedy_snap",
    "confrontation_shake",
    "memory_float",
]
ALL_PRESETS = STATIC_PRESETS + CINEMATIC_PRESETS

VALIDATION_REPORT = DEMO / "PRESET_VALIDATION_REPORT.json"


def get_preset_schema_status(preset_name: str) -> str:
    """Return 'old_schema', 'new_schema', or 'unknown'."""
    try:
        import preset
        p = preset.load_preset(preset_name)
        keys = set(p._d.keys())
        if "camera_moves" in keys or "effects" in keys:
            return "old_schema"
        if "camera" in keys or "motion" in keys:
            return "new_schema"
        return "unknown"
    except Exception:
        return "load_failed"


def validate_preset(preset_name: str, duration: float = 5.0) -> dict:
    """Render one preset and capture full validation data."""
    import preset as preset_module
    from engine import CinematicShotEngine
    from motion import EffectApplier

    output_path = DEMO / f"validation_{preset_name}.mp4"
    report_path = DEMO / f"validation_{preset_name}_report.json"

    # Get schema status
    schema_status = get_preset_schema_status(preset_name)

    # Get effects requested
    try:
        p = preset_module.load_preset(preset_name)
        ea = EffectApplier(p)
        _, ff_app, ff_sk = ea.build_ffmpeg_effects_chain()
        effects_requested = []
        if p.micro_shake > 0:
            effects_requested.append(f"micro_shake({p.micro_shake})")
        if p.breathing > 0:
            effects_requested.append(f"breathing({p.breathing})")
        if p.flicker > 0:
            effects_requested.append(f"flicker({p.flicker})")
        if p.glow_drift > 0:
            effects_requested.append(f"glow_drift({p.glow_drift})")
        if p.vignette_pulse > 0:
            effects_requested.append(f"vignette_pulse({p.vignette_pulse})")
        # FFmpeg effects
        for e in ff_app:
            if e not in effects_requested:
                effects_requested.append(e)
    except Exception as e:
        effects_requested = [f"error: {e}"]

    # Render
    engine = CinematicShotEngine()
    t0 = time.perf_counter()
    try:
        result = engine.render(
            input_image=INPUT_IMAGE,
            output_path=str(output_path),
            preset_name=preset_name,
            duration=duration,
            fps=24,
            width=1080, height=1920,
        )
        elapsed = time.perf_counter() - t0
    except Exception as e:
        elapsed = time.perf_counter() - t0
        result = {"status": "python_error", "error": str(e)}

    # Extract result fields
    status = result.get("status", "unknown")
    ffmpeg_rc = result.get("returncode", -1)
    effects_applied = result.get("effects_applied", [])
    effects_skipped = result.get("effects_skipped", [])
    route_selected = result.get("route_selected", "unknown")
    degraded_mode = result.get("degraded_mode", False)

    # Determine pass/fail
    passed = (
        status == "success"
        and output_path.exists()
        and output_path.stat().st_size > 1000
    )

    # File size
    size_mb = output_path.stat().st_size / (1024 * 1024) if output_path.exists() else 0

    report = {
        "preset_name": preset_name,
        "schema_status": schema_status,
        "route_selected": route_selected,
        "render_status": status,
        "render_time_sec": round(elapsed, 2),
        "output_file": str(output_path),
        "file_size_mb": round(size_mb, 4),
        "effects_requested": effects_requested,
        "effects_applied": effects_applied,
        "effects_skipped": effects_skipped,
        "degraded_mode_used": degraded_mode,
        "ffmpeg_rc": ffmpeg_rc,
        "passed": passed,
        "validation_ts": datetime.now().isoformat(),
    }

    report_path.write_text(json.dumps(report, indent=2))
    return report


def main():
    targets = ALL_PRESETS
    if "--preset" in sys.argv:
        idx = sys.argv.index("--preset")
        targets = [sys.argv[idx + 1]]

    print(f"\n{'='*60}")
    print(f"  PRESET VALIDATION — {len(targets)} presets")
    print(f"{'='*60}\n")

    results = []
    for name in targets:
        print(f"[{name}]")
        r = validate_preset(name)
        icon = "✅" if r["passed"] else "❌"
        print(f"  {icon} {r['schema_status']:12s} | {r['route_selected']:20s} "
              f"| {r['render_time_sec']:.1f}s | {r['file_size_mb']:.2f}MB")
        if r['effects_applied']:
            print(f"  Applied:  {r['effects_applied']}")
        if r['effects_skipped']:
            print(f"  Skipped: {r['effects_skipped']}")
        if not r['passed']:
            print(f"  ❌ FAIL: {r['render_status']} | RC={r['ffmpeg_rc']}")
        results.append(r)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r['passed'])
    failed = total - passed
    degraded = sum(1 for r in results if r['degraded_mode_used'])

    print(f"\n{'='*60}")
    print(f"  VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Total:    {total}")
    print(f"  Passed:   {passed} ✅")
    print(f"  Failed:   {failed} ❌")
    print(f"  Degraded: {degraded}")

    # Save combined report
    combined = {
        "validation_ts": datetime.now().isoformat(),
        "total": total,
        "passed": passed,
        "failed": failed,
        "degraded": degraded,
        "results": results,
    }
    VALIDATION_REPORT.write_text(json.dumps(combined, indent=2))
    print(f"\n  Report: {VALIDATION_REPORT}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
