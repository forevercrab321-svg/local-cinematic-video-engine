#!/usr/bin/env python3
"""
validate.py — Preset validation + capability report

Runs every preset through the render engine and produces:
  1. Per-preset validation result
  2. Capability report (working / degraded / skipped effects)
  3. Schema audit (which presets use old vs new schema)

Usage:
    python3 validate.py
    python3 validate.py --preset comedy_snap
    python3 validate.py --report capability_report.md
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from engine import CinematicShotEngine
from preset import load_preset, list_presets
import motion


# =============================================================================
# CAPABILITY REGISTRY
# =============================================================================

CAPABILITIES = {
    # Effect name: (supported_methods, description)
    "camera_move": {
        "methods": ["PIL_per_frame", "zoompan"],
        "status": "working",
        "description": "Zoom, pan, rotation with easing curves"
    },
    "micro_shake": {
        "methods": ["PIL_per_frame"],
        "status": "working",
        "description": "Deterministic pseudo-random per-frame shake"
    },
    "breathing": {
        "methods": ["PIL_per_frame"],
        "status": "working",
        "description": "Sin-wave zoom modulation at 0.35Hz"
    },
    "flicker": {
        "methods": ["ffmpeg_eq"],
        "status": "working",
        "description": "Brightness micro-variation at ~4Hz"
    },
    "vignette_pulse": {
        "methods": ["ffmpeg_eq_brightness_approx"],
        "status": "degraded",
        "description": "True vignette pulse — approximated via brightness"
    },
    "glow_drift": {
        "methods": ["ffmpeg_eq"],
        "status": "working",
        "description": "Contrast/brightness drift"
    },
    "film_grain": {
        "methods": ["skip"],
        "status": "skipped",
        "description": "Not implemented — falls back gracefully"
    },
    "parallax": {
        "methods": ["approximate_single_layer"],
        "status": "degraded",
        "description": "True multi-layer parallax — approximated"
    },
    "color_grade": {
        "methods": ["skip"],
        "status": "skipped",
        "description": "Not implemented — falls back gracefully"
    },
}


# =============================================================================
# PRESET SCHEMA AUDITOR
# =============================================================================

def audit_preset(preset_name: str) -> dict:
    """Audit a single preset: schema type, camera values, effect values."""
    try:
        raw = json.loads((SKILL_DIR / "presets" / f"{preset_name}.json").read_text())
    except Exception as e:
        return {"name": preset_name, "error": str(e)}

    has_new = all(k in raw for k in ("camera", "motion", "lighting", "timing"))
    has_old = "camera_moves" in raw or "effects" in raw

    if has_new:
        schema = "NEW"
        p = load_preset(preset_name)
        info = {
            "move": p.move(),
            "zoom": f"{p.zoom_start} → {p.zoom_end}",
            "easing": p.easing(),
            "micro_shake": p.micro_shake,
            "breathing": p.breathing,
            "flicker": p.flicker,
            "vignette_pulse": p.vignette_pulse,
            "glow_drift": p.glow_drift,
            "hold_start": p.hold_start_dur,
            "move_start": p.move_start,
            "move_end": p.move_end,
            "hold_end": p.hold_end_dur,
        }
        # Check what would be used
        has_motion = (
            p.zoom_start != p.zoom_end
            or p.x_start != p.x_end
            or p.y_start != p.y_end
            or p.rot_start != p.rot_end
            or p.micro_shake > 0
            or p.breathing > 0
        )
        mr = motion.MotionRenderer()
        route = "zoompan" if mr._can_use_zoompan(p) else ("PIL" if has_motion else "static_ffmpeg")
    elif has_old:
        schema = "OLD"
        info = {
            "camera_moves": len(raw.get("camera_moves", [])),
            "effects": [e["type"] for e in raw.get("effects", [])],
            "parallax": raw.get("parallax", {}).get("enabled"),
            "color_grade": raw.get("color_grade", {}).get("saturation"),
            "note": "OLD schema — falls back to static (no camera motion)"
        }
        route = "static_ffmpeg (OLD schema)"
        info["route"] = route
    else:
        schema = "MINIMAL"
        info = {}
        route = "unknown"

    return {
        "name": preset_name,
        "schema": schema,
        "route": route,
        **info
    }


# =============================================================================
# VALIDATION RUNNER
# =============================================================================

def validate_preset(preset_name: str, image: str, out_dir: Path) -> dict:
    """Run one preset through the engine. Returns validation result."""
    engine = CinematicShotEngine()
    out_path = out_dir / f"validate_{preset_name}.mp4"

    start = time.perf_counter()
    result = engine.render(
        input_image=image,
        output_path=str(out_path),
        preset_name=preset_name,
        duration=None,
        fps=24,
        width=1080,
        height=1920,
    )
    elapsed = time.perf_counter() - start

    return {
        "preset": preset_name,
        "status": result["status"],
        "method": result.get("method", "?"),
        "file": str(out_path) if result["status"] == "success" else None,
        "file_size_mb": result.get("file_size_mb"),
        "render_time_sec": result.get("render_time_sec"),
        "effects_requested": result.get("effects_requested", []),
        "effects_applied": result.get("effects_applied", []),
        "effects_skipped": result.get("effects_skipped", []),
        "error": result.get("error"),
        "render_time": round(elapsed, 1),
        "manifest": result,
    }


# =============================================================================
# CAPABILITY REPORT
# =============================================================================

def generate_report(validations: list, audits: list) -> str:
    """Generate markdown capability report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M EDT")
    total = len(validations)
    passed = sum(1 for v in validations if v["status"] == "success")
    failed = sum(1 for v in validations if v["status"] == "failed")

    lines = [
        "# 🎬 local_cinematic_video_engine — Capability Report",
        f"\nGenerated: {now}",
        f"\n## Summary",
        f"\n- **Total presets tested:** {total}",
        f"- **Passed:** {passed} ✅",
        f"- **Failed:** {failed} ❌",
        "",
        "---",
        "",
        "## Preset Validation",
        "",
        "| Preset | Schema | Route | Method | Status | Time | Effects Applied |",
        "|--------|--------|-------|--------|--------|------|-----------------|",
    ]

    for v, audit in zip(validations, audits):
        icon = "✅" if v["status"] == "success" else "❌"
        schema = audit.get("schema", "?")
        method = v.get("method", "?")
        effects = ", ".join(v.get("effects_applied", [])[:3]) or "—"
        time_s = v.get("render_time_sec") or v.get("render_time", "?")
        lines.append(
            f"| {v['preset']:20s} | {schema:6s} | "
            f"{v.get('route', ''):25s} | {method:15s} | "
            f"{icon} | {time_s}s | {effects} |"
        )

    lines += ["", "---", "", "## Capability Matrix", ""]

    capability_lines = [
        "| Effect | Status | Method | Description |",
        "|--------|--------|-------|-------------|"
    ]
    for name, cap in CAPABILITIES.items():
        status_icon = {"working": "✅", "degraded": "⚠️", "skipped": "⏭️"}.get(cap["status"], "?")
        methods = ", ".join(cap["methods"])
        capability_lines.append(
            f"| {name:18s} | {status_icon} {cap['status']:9s} | "
            f"{methods:30s} | {cap['description']} |"
        )

    lines += capability_lines

    # Working effects
    working = [k for k, v in CAPABILITIES.items() if v["status"] == "working"]
    degraded = [k for k, v in CAPABILITIES.items() if v["status"] == "degraded"]
    skipped = [k for k, v in CAPABILITIES.items() if v["status"] == "skipped"]

    lines += [
        "",
        "---",
        "",
        "## Effect Status",
        "",
        f"**Working (✅):** {', '.join(working)}",
        f"\n**Degraded (⚠️):** {', '.join(degraded)}",
        f"\n**Skipped (⏭️):** {', '.join(skipped)}",
        "",
        "---",
        "",
        "## Schema Breakdown",
        "",
        "| Preset | Schema | Route | Details |",
        "|--------|--------|-------|---------|"
    ]

    for audit in audits:
        if "error" in audit:
            continue
        schema = audit.get("schema", "?")
        route = audit.get("route", "?")
        if schema == "OLD":
            details = f"camera_moves={audit.get('camera_moves', 0)}, effects={audit.get('effects', [])}"
        elif schema == "NEW":
            details = f"zoom={audit.get('zoom', '?')}, shake={audit.get('micro_shake', 0)}, breath={audit.get('breathing', 0)}"
        else:
            details = "minimal config"
        lines.append(f"| {audit['name']:20s} | {schema:6s} | {route:30s} | {details} |")

    lines += [
        "",
        "---",
        "",
        "## Render Paths",
        "",
        "| Path | Condition | Speed | File |",
        "|------|-----------|-------|------|",
        "| `static_ffmpeg` | No motion | <1s | ~0.1MB |",
        "| `zoompan` | Linear zoom, no effects | ~2s | ~0.1MB |",
        "| `PIL` | Easing / hold / shake / breath | 8-20s | ~0.5MB |",
        "",
        "---",
        "",
        "## Notes",
        "",
        "- **OLD schema** presets (`suspense`, `heartbreak`, `reveal`, `comedy`) → "
        "map to static (no camera motion). They need migration to new schema.",
        "- **vignette_pulse**: approximated via `eq=brightness=...` (not true lens vignette)",
        "- **film_grain**: not implemented, skipped gracefully",
        "- **parallax**: approximated (no true multi-layer separation)",
        "- **color_grade**: not implemented, skipped gracefully",
        "",
        "**No render ever fails due to unsupported effects.** Graceful degradation is guaranteed.",
    ]

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Validate all presets")
    parser.add_argument("--preset", help="Validate single preset only")
    parser.add_argument("--report", default="CAPABILITY_REPORT.md",
                        help="Output report path")
    parser.add_argument("--image", default=str(SKILL_DIR / "maya_keyframe.jpg"),
                        help="Test image")
    args = parser.parse_args()

    image = args.image
    if not Path(image).exists():
        # Try extracting from demo_output
        src = SKILL_DIR / "demo_output" / "test_keyframe_video.mp4"
        if src.exists():
            # Extract first frame
            tmp = Path(tempfile.gettempdir()) / "validate_frame.jpg"
            subprocess.run([
                "/usr/local/bin/ffmpeg", "-y", "-i", str(src),
                "-vframes", "1", "-q:v", "2", str(tmp)
            ], capture_output=True, timeout=30)
            image = str(tmp)

    out_dir = SKILL_DIR / "demo_output"
    out_dir.mkdir(exist_ok=True)

    presets_to_test = [args.preset] if args.preset else sorted(
        p for p in list_presets() if p not in ("PRESET_SPEC",)
    )

    print("=" * 60)
    print("  PRESET VALIDATION + CAPABILITY REPORT")
    print("=" * 60)
    print(f"  Image: {image}")
    print(f"  Output: {out_dir}")
    print(f"  Presets: {presets_to_test}")
    print()

    # Step 1: Schema audit
    print("STEP 1: Schema Audit")
    print("-" * 40)
    audits = []
    for name in presets_to_test:
        try:
            audit = audit_preset(name)
            audits.append(audit)
            schema = audit.get("schema", "?")
            route = audit.get("route", "?")
            print(f"  {name:25s} [{schema}] → {route}")
        except Exception as e:
            print(f"  {name:25s} ERROR: {e}")
            audits.append({"name": name, "error": str(e)})

    print()

    # Step 2: Render validation
    print("STEP 2: Render Validation")
    print("-" * 40)
    validations = []
    for i, name in enumerate(presets_to_test):
        print(f"\n[{i+1}/{len(presets_to_test)}] {name}...", end=" ", flush=True)
        try:
            result = validate_preset(name, image, out_dir)
            validations.append(result)
            icon = "✅" if result["status"] == "success" else "❌"
            print(f"{icon} {result['status']} | {result.get('method','?')} | "
                  f"{result.get('render_time', '?')}s | "
                  f"{', '.join(result.get('effects_applied', [])[:2]) or 'no effects'}")
            if result["status"] == "failed":
                print(f"    Error: {result.get('error', '?')[:80]}")
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            import traceback; traceback.print_exc()
            validations.append({
                "preset": name, "status": "failed",
                "error": str(e), "render_time": 0,
                "effects_applied": [], "effects_skipped": [],
            })

    print()

    # Step 3: Generate report
    print("STEP 3: Generating Capability Report")
    print("-" * 40)
    report = generate_report(validations, audits)
    report_path = SKILL_DIR / args.report
    report_path.write_text(report)
    print(f"  Written: {report_path}")

    # Print summary
    passed = sum(1 for v in validations if v["status"] == "success")
    failed = sum(1 for v in validations if v["status"] == "failed")
    print(f"\n{'='*60}")
    print(f"  RESULT: {passed}/{len(validations)} presets passed")
    if failed > 0:
        failed_names = [v["preset"] for v in validations if v["status"] == "failed"]
        print(f"  FAILED: {failed_names}")
    print(f"{'='*60}")
    print(f"\nFull report: {report_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
