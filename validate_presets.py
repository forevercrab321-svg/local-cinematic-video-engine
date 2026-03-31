#!/usr/bin/env python3
"""
validate_presets.py — Batch preset validation + golden sample renderer

Produces:
  demo_output/
    golden_suspense_push/
      shot_00.mp4          ← rendered video
      shot_manifest.json   ← per-shot metadata
    golden_heartbreak_drift/
    golden_reveal_hold_push/
    golden_comedy_snap/
    golden_confrontation_shake/
    golden_memory_float/
    validation_report.json  ← all results
    VALIDATION_REPORT.md

Golden sample criteria:
  - Every effect requested → clearly applied or explicitly skipped
  - Render completes without error
  - Manifest is complete and accurate
  - Video is playable H.264 MP4

Usage:
    python3 validate_presets.py
    python3 validate_presets.py --preset suspense_push
    python3 validate_presets.py --golden suspense_push heartbreak_drift reveal_hold_push
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from preset_loader import PresetLoader, PresetLoadError
from preset_mapper import PresetMapper
from engine import CinematicShotEngine


# =============================================================================
# GOLDEN RENDERER
# =============================================================================

class GoldenRenderer:
    """
    Renders a preset to a golden sample with complete manifest.

    Output structure:
      golden_<preset_name>/
        shot_00.mp4
        shot_manifest.json   ← all metadata
        render_log.txt       ← step-by-step
    """

    def __init__(self, image_path: str, out_dir: Path):
        self.image_path = image_path
        self.out_dir = Path(out_dir)
        self.loader = PresetLoader()
        self.mapper = PresetMapper()
        self.engine = CinematicShotEngine()

    def render(
        self,
        preset_name: str,
        index: int = 0,
    ) -> dict:
        """
        Render one preset as golden sample.
        Returns full result dict with manifest.
        """
        start_time = time.perf_counter()

        # Load + validate preset
        try:
            preset = self.loader.load(preset_name, strict=True)
        except PresetLoadError as e:
            return {
                "status": "preset_load_failed",
                "preset": preset_name,
                "error": str(e),
            }

        # Map to engine params
        params = self.mapper.map(preset)

        # Create output dir
        golden_dir = self.out_dir / f"golden_{preset_name}"
        golden_dir.mkdir(parents=True, exist_ok=True)

        # Render
        shot_file = golden_dir / "shot_00.mp4"
        result = self.engine.render(
            input_image=self.image_path,
            output_path=str(shot_file),
            preset_name=preset_name,
            duration=None,
            fps=params.fps,
            width=params.resolution[0],
            height=params.resolution[1],
        )

        elapsed = time.perf_counter() - start_time

        # Build complete manifest
        manifest = {
            # Shot identity
            "shot_id": f"golden_{preset_name}",
            "shot_index": index,
            "preset_name": preset_name,
            "schema_version": params.schema_version,

            # Timeline (applied)
            "timeline_applied": params.timeline_applied,

            # Camera (applied)
            "camera_params_applied": params.camera_params_applied,

            # Effects
            "effects_requested": params.effects_requested(),
            "effects_applied": params.effects_applied,
            "effects_skipped": params.effects_skipped,

            # Render result
            "render_status": result.get("status"),
            "render_method": result.get("method"),
            "render_time_sec": result.get("render_time_sec"),
            "file_size_mb": result.get("file_size_mb"),
            "resolution": params.resolution,
            "fps": params.fps,
            "duration_sec": params.duration,
            "output_file": str(shot_file) if result.get("status") == "success" else None,

            # Warnings
            "warnings": params.warnings,

            # Validation
            "preset_load_errors": [str(i) for i in preset.issues if i.severity == "error"],
            "preset_load_warnings": [str(i) for i in preset.issues if i.severity == "warning"],
            "render_path_hint": params.render_path,
            "can_use_zoompan": params.can_use_zoompan,
            "has_motion": params.has_motion,

            # Timing
            "render_wall_clock_sec": round(elapsed, 2),
            "rendered_at": datetime.now().isoformat(),
        }

        # Save manifest
        manifest_path = golden_dir / "shot_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))

        # Save render log
        log_lines = result.get("render_log", [])
        log_path = golden_dir / "render_log.txt"
        log_path.write_text("\n".join(log_lines))

        # Save params summary
        params_path = golden_dir / "params.txt"
        params_path.write_text(params.summary())

        return manifest


# =============================================================================
# VALIDATION REPORT
# =============================================================================

def build_report(results: list[dict]) -> str:
    """Generate markdown validation report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M EDT")

    passed = sum(1 for r in results if r.get("render_status") == "success")
    failed = sum(1 for r in results if r.get("render_status") != "success")
    total = len(results:

    lines = [
        "# 🎬 Preset Validation Report",
        f"\nGenerated: {now}",
        f"\n## Summary",
        f"\n- **Total:** {total} presets",
        f"- **Passed:** {passed} ✅",
        f"- **Failed:** {failed} ❌",
        "",
        "---",
        "",
        "## Golden Samples",
        "",
        "| # | Preset | Method | Duration | FPS | Render Time | Size | Effects Applied |",
        "|--:|--------|--------|----------|-----|-------------|------|-----------------|",
    ]

    for i, r in enumerate(results):
        if r.get("render_status") == "success":
            effects = ", ".join(r.get("effects_applied", [])[:4]) or "—"
            size = f"{r.get('file_size_mb', '?')}MB"
            time_s = f"{r.get('render_time_sec', '?')}s"
        else:
            effects = "❌ FAILED"
            size = "—"
            time_s = "—"
        lines.append(
            f"| {i+1} | {r.get('preset_name', '?'):22s} "
            f"| {r.get('render_method', '?'):15s} "
            f"| {r.get('duration_sec', '?')}s "
            f"| {r.get('fps', '?'):3s} "
            f"| {time_s:10s} "
            f"| {size:7s} "
            f"| {effects} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Effects Detail",
        "",
        "| Preset | Requested | Applied | Skipped |",
        "|--------|-----------|---------|---------|"
    ]

    for r in results:
        req = ", ".join(r.get("effects_requested", [])[:5]) or "—"
        app = ", ".join(r.get("effects_applied", [])[:5]) or "—"
        skip = ", ".join(r.get("effects_skipped", [])[:3]) or "—"
        lines.append(f"| {r.get('preset_name', '?'):22s} | {req} | {app} | {skip} |")

    lines += [
        "",
        "---",
        "",
        "## Render Paths",
        "",
        "| Preset | Render Path | Zoompan-Eligible | Has Motion |",
        "|--------|------------|-----------------|------------|"
    ]

    for r in results:
        zp = "✅" if r.get("can_use_zoompan") else "❌"
        mot = "✅" if r.get("has_motion") else "❌"
        lines.append(
            f"| {r.get('preset_name', '?'):22s} "
            f"| {r.get('render_method', '?'):13s} "
            f"| {zp} | {mot} |"
        )

    # Issues section
    issues = [(r["preset_name"], r) for r in results if r.get("render_status") != "success"]
    if issues:
        lines += ["", "---", "", "## Failed Presets", ""]
        for name, r in issues:
            lines.append(f"### {name}")
            lines.append(f"```\n{r.get('error', 'unknown error')}\n```")

    # Warnings
    presets_with_warnings = [r for r in results if r.get("warnings")]
    if presets_with_warnings:
        lines += ["", "---", "", "## Warnings", ""]
        for r in presets_with_warnings:
            lines.append(f"- **{r['preset_name']}**: {', '.join(r.get('warnings', []))}")

    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Validate presets and produce golden samples")
    parser.add_argument("--preset", help="Validate single preset")
    parser.add_argument("--golden", nargs="+",
                        help="Golden render specific presets (default: all 6 new-schema)")
    parser.add_argument("--image", help="Keyframe image")
    parser.add_argument("--out", default="demo_output", help="Output dir")
    args = parser.parse_args()

    out_dir = SKILL_DIR / args.out
    out_dir.mkdir(exist_ok=True)

    # Find test image
    if args.image and Path(args.image).exists():
        image = args.image
    else:
        candidates = [
            SKILL_DIR / "maya_keyframe.jpg",
            SKILL_DIR / "maya_reference.jpg",
            SKILL_DIR / "demo_output" / "test_keyframe_video.mp4",
        ]
        image = None
        for c in candidates:
            if c.exists():
                image = str(c)
                break
        if not image:
            # Extract from demo video
            tmp = Path(tempfile.gettempdir()) / "golden_ref.jpg"
            subprocess.run([
                "/usr/local/bin/ffmpeg", "-y",
                "-i", str(SKILL_DIR / "demo_output" / "test_keyframe_video.mp4"),
                "-vframes", "1", "-q:v", "2", str(tmp)
            ], capture_output=True, timeout=30)
            image = str(tmp) if tmp.exists() else str(candidates[0])

    print("="*60)
    print("  VALIDATE_PRESETS — Golden Sample Renderer")
    print("="*60)
    print(f"  Image: {image}")
    print(f"  Output: {out_dir}")
    print()

    # Determine which presets to golden-render
    loader = PresetLoader()
    if args.golden:
        presets_to_render = args.golden
    elif args.preset:
        presets_to_render = [args.preset]
    else:
        # All new-schema presets
        presets_to_render = [
            n for n in loader.list_presets()
            if n not in ("PRESET_SPEC",)
            # Only new-schema (has "camera" field)
        ]
        new_schema = []
        for n in presets_to_render:
            raw = (SKILL_DIR / "presets" / f"{n}.json")
            if raw.exists():
                d = json.loads(raw.read_text())
                if "camera" in d and "motion" in d:
                    new_schema.append(n)
        presets_to_render = new_schema

    print(f"  Presets: {presets_to_render}")
    print()

    # Step 1: Schema audit
    print("STEP 1: Schema Audit")
    print("-"*40)
    audit_results = []
    for name in presets_to_render:
        issues = loader.validate(name)
        errors = [i for i in issues if i.severity == "error"]
        warnings = [i for i in issues if i.severity == "warning"]
        icon = "✅" if not errors else "❌"
        print(f"  {icon} {name:25s} | {len(errors)} errors, {len(warnings)} warnings")
        audit_results.append({
            "preset": name,
            "errors": errors,
            "warnings": warnings,
        })

    print()

    # Step 2: Golden render
    print("STEP 2: Golden Render")
    print("-"*40)
    renderer = GoldenRenderer(image, out_dir)
    render_results = []

    for i, name in enumerate(presets_to_render):
        print(f"\n  [{i+1}/{len(presets_to_render)}] Rendering {name}...", end=" ", flush=True)
        result = renderer.render(name, index=i)
        render_results.append(result)

        icon = "✅" if result.get("render_status") == "success" else "❌"
        method = result.get("render_method", "?")
        time_s = result.get("render_time_sec", "?")
        size = result.get("file_size_mb", "?")
        print(f"{icon} | {method} | {time_s}s | {size}MB")

        if result.get("render_status") != "success":
            print(f"    Error: {result.get('error', '?')[:100]}")

    print()

    # Step 3: Generate reports
    print("STEP 3: Generating Reports")
    print("-"*40)

    # JSON report
    report_path = out_dir / "validation_report.json"
    report_path.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(),
        "image": image,
        "audit_results": [
            {
                "preset": a["preset"],
                "errors": [str(e) for e in a["errors"]],
                "warnings": [str(w) for w in a["warnings"]],
            }
            for a in audit_results
        ],
        "render_results": render_results,
    }, indent=2))
    print(f"  JSON: {report_path}")

    # Markdown report
    md_report = build_report(render_results)
    md_path = out_dir / "VALIDATION_REPORT.md"
    md_path.write_text(md_report)
    print(f"  MD:   {md_path}")

    # Summary
    passed = sum(1 for r in render_results if r.get("render_status") == "success")
    failed = sum(1 for r in render_results if r.get("render_status") != "success")

    print()
    print(f"{'='*60}":
    print(f"  RESULT: {passed}/{len(render_results)} golden samples passed")
    if failed > 0:
        for r in render_results:
            if r.get("render_status") != "success":
                print(f"  ❌ {r.get('preset_name')}: {r.get('error', '?')[:80]}")
    print(f"{'='*60}")

    # Schema issues summary
    all_errors = [(a["preset"], a["errors"]) for a in audit_results if a["errors"]]
    if all_errors:
        print()
        print("SCHEMA ERRORS:")
        for name, errors in all_errors:
            for e in errors:
                print(f"  ❌ {name}: {e}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
