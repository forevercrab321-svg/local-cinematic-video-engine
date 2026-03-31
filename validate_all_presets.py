#!/usr/bin/env python3
"""
validate_all_presets.py — Production validation runner.

Loads each preset, renders it, checks result against RENDER_RESULT_CONTRACT.
Outputs PRESET_VALIDATION_REPORT.json and PRESET_VALIDATION_SUMMARY.md.

Usage:
  python3 validate_all_presets.py
  python3 validate_all_presets.py --preset suspense_push
"""

import subprocess, json, time, sys, os
from pathlib import Path
from datetime import datetime

SKILL_DIR = Path(__file__).parent
DEMO      = SKILL_DIR / "demo_output"
INPUT_IMAGE = "/Users/monsterlee/.openclaw/media/inbound/file_3---5223086e-a136-4e3a-9c06-8c2363382b8b.jpg"

sys.path.insert(0, str(SKILL_DIR))

STATIC_PRESETS     = ["suspense",    "heartbreak",  "reveal",  "comedy"]
CINEMATIC_PRESETS  = [
    "suspense_push", "heartbreak_drift", "reveal_hold_push",
    "comedy_snap",   "confrontation_shake", "memory_float",
]
ALL_PRESETS = STATIC_PRESETS + CINEMATIC_PRESETS


def validate_one(name: str, duration: float = 5.0) -> dict:
    """Render one preset and return a contract-compliant result."""
    from engine import CinematicShotEngine
    from preset import Preset, load_preset

    out_path = DEMO / f"validation_{name}.mp4"

    engine = CinematicShotEngine()
    t0 = time.perf_counter()

    try:
        result = engine.render(
            input_image=INPUT_IMAGE,
            output_path=str(out_path),
            preset_name=name,
            duration=duration,
            fps=24,
            width=1080, height=1920,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return {
            "preset_name": name,
            "schema_status": "invalid",
            "engine_mode": "unknown",
            "route_selected": "unknown",
            "status": "failed",
            "validation_status": "fail",
            "render_time_sec": round(elapsed, 2),
            "output_path": None,
            "file_size_mb": None,
            "duration_sec": duration,
            "fps": 24,
            "resolution": "1080×1920",
            "source_image": INPUT_IMAGE,
            "source_frame_extracted_from_video": None,
            "timeline_applied": {},
            "camera_params_applied": {},
            "effects_requested": [],
            "effects_applied": [],
            "effects_skipped": [],
            "degraded_mode_used": False,
            "error": f"{type(exc).__name__}: {exc}",
            "ffmpeg_rc": None,
            "cmd_file": None,
            "stderr_file": None,
            "render_log": [],
            "render_status": "python_error",
            "error": str(exc),
        }

    elapsed = time.perf_counter() - t0

    # Merge with contract fields from result
    validation_status = result.get("validation_status", "fail")
    passed = validation_status in ("pass", "degraded_pass")

    return {
        "preset_name":               result.get("preset_name", name),
        "schema_status":            result.get("schema_status", "unknown"),
        "engine_mode":              result.get("engine_mode", result.get("method", "unknown")),
        "route_selected":           result.get("route_selected", result.get("method", "unknown")),
        "status":                   result.get("status", "failed"),
        "validation_status":         validation_status,
        "render_time_sec":          round(result.get("render_time_sec", elapsed), 2),
        "output_path":              result.get("output_path", str(out_path) if passed else None),
        "file_size_mb":             result.get("file_size_mb"),
        "duration_sec":             result.get("duration_sec", duration),
        "fps":                      result.get("fps", 24),
        "resolution":               result.get("resolution", "1080×1920"),
        "source_image":             result.get("source_image", INPUT_IMAGE),
        "source_frame_extracted_from_video": result.get("source_frame_extracted_from_video"),
        "timeline_applied":         result.get("timeline_applied", {}),
        "camera_params_applied":    result.get("camera_params_applied", {}),
        "effects_requested":        result.get("effects_requested", []),
        "effects_applied":          result.get("effects_applied", []),
        "effects_skipped":          result.get("effects_skipped", []),
        "degraded_mode_used":       result.get("degraded_mode_used", False),
        "render_status":            result.get("render_status", result.get("status", "failed")),
        "error":                   result.get("error"),
        "ffmpeg_rc":                result.get("ffmpeg_rc"),
        "cmd_file":                 result.get("cmd_file"),
        "stderr_file":              result.get("stderr_file"),
        "render_log":               result.get("render_log", []),
    }


def main():
    targets = ALL_PRESETS
    if "--preset" in sys.argv:
        idx = sys.argv.index("--preset")
        targets = [sys.argv[idx + 1]]

    print(f"\n{'='*60}")
    print(f"  PRESET VALIDATION RUNNER — {len(targets)} presets")
    print(f"{'='*60}\n")

    results = []
    for name in targets:
        r = validate_one(name)
        results.append(r)
        icon = "✅" if r["validation_status"] in ("pass","degraded_pass") else "❌"
        vs = r["validation_status"].upper()
        print(f"  {icon} [{vs}] {name:25s} "
              f"{r['schema_status']:6s} {r['engine_mode']:22s} "
              f"{r['render_time_sec']:.1f}s")
        if r.get("effects_applied"):
            print(f"       Applied:   {r['effects_applied']}")
        sk = [e for e in r.get("effects_skipped", []) if isinstance(e, dict) and e.get("reason") != "intensity=0"]
        if sk:
            print(f"       Skipped:   {sk}")
        if r["validation_status"] == "fail":
            err = (r.get("error") or "unknown")[:80]; print(f"       ❌ {err}")

    # ── Summary ──────────────────────────────────────────────
    passed      = [r for r in results if r["validation_status"] == "pass"]
    deg_passed  = [r for r in results if r["validation_status"] == "degraded_pass"]
    failed      = [r for r in results if r["validation_status"] == "fail"]

    summary = {
        "validation_ts":   datetime.now().isoformat(),
        "total":          len(results),
        "passed":         len(passed),
        "degraded_passed": len(deg_passed),
        "failed":         len(failed),
        "results":        results,
    }

    report_path = DEMO / "PRESET_VALIDATION_REPORT.json"
    report_path.write_text(json.dumps(summary, indent=2))

    # ── Markdown summary ──────────────────────────────────────
    md_lines = [
        "# PRESET_VALIDATION_SUMMARY.md",
        f"\n**Generated:** {datetime.now().isoformat()}\n",
        "| Preset | Schema | Route | Status | Render Time |",
        "|--------|--------|-------|--------|-------------|",
    ]
    for r in results:
        icon = {"pass":"✅","degraded_pass":"⚠️ ","fail":"❌"}.get(r["validation_status"], "?")
        md_lines.append(
            f"| {icon} {r['preset_name']} | {r['schema_status']} | "
            f"{r['engine_mode']} | {r['validation_status']} | "
            f"{r['render_time_sec']:.1f}s |"
        )

    md_lines += [
        "",
        "## Old Schema (static_ffmpeg — degraded by design)",
        *(f"- {p['preset_name']}: `{p['engine_mode']}` — {p['validation_status']}"
          for p in deg_passed if p['schema_status'] == 'old'),
        "",
        "## New Schema Cinematic",
        *(f"- {p['preset_name']}: `{p['engine_mode']}` — {p['validation_status']}"
          for p in results if p['schema_status'] == 'new'),
        "",
        "## Failed",
        *(f"- {p['preset_name']}: {p.get('error','?')}" for p in failed),
    ]

    md_path = DEMO / "PRESET_VALIDATION_SUMMARY.md"
    md_path.write_text("\n".join(md_lines))

    print(f"\n{'='*60}")
    print(f"  RESULT: {len(passed)} pass | {len(deg_passed)} degraded_pass | {len(failed)} fail")
    print(f"  Report: {report_path}")
    print(f"  Summary: {md_path}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
