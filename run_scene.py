#!/usr/bin/env python3
"""
run_scene.py — Scene batch renderer for local_cinematic_video_engine

Loads a scene_manifest.json and renders all shots in order.
Outputs scene_render_ledger.json with complete per-shot traceability.

Usage:
    python3 run_scene.py scene_manifests/IN_THE_GROUP_CHAT.json
    python3 run_scene.py scene_manifests/IN_THE_GROUP_CHAT.json --verbose
    python3 run_scene.py scene_manifests/IN_THE_GROUP_CHAT.json --continue-on-error
    python3 run_scene.py --validate-only scene_manifests/IN_THE_GROUP_CHAT.json
    python3 run_scene.py --list-scenes
"""

import argparse
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR))

from scene_schema import SceneManifest, SceneValidationError, GOLDEN_PRESETS
from render_ledger import RenderLedger


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Batch render a scene from scene_manifest.json"
    )
    parser.add_argument(
        "manifest",
        nargs="?",
        help="Path to scene_manifest.json"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Keep rendering even if a shot fails"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate manifest, don't render"
    )
    parser.add_argument(
        "--list-scenes",
        action="store_true",
        help="Show available scene manifests in scene_manifests/"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output directory for renders"
    )
    args = parser.parse_args()

    # List scenes
    if args.list_scenes:
        scenes_dir = SKILL_DIR / "scene_manifests"
        if not scenes_dir.exists():
            scenes_dir.mkdir(exist_ok=True)
            print(f"Created: {scenes_dir}")
            print("  (no scene manifests found — create scene_manifests/ directory)")
            return

        manifests = sorted(scenes_dir.glob("*.json"))
        if not manifests:
            print(f"Scene manifests: {scenes_dir}")
            print("  (no manifests found)")
            return

        print(f"Scene manifests in {scenes_dir}:")
        for m in manifests:
            try:
                sm = SceneManifest.from_file(str(m))
                errors = sm.validate()
                status = "✅" if not errors else f"❌ ({len(errors)} errors)"
                print(f"  {status} {m.name}")
                print(f"       Project: {sm.project} | Shots: {sm.total_shots} | Duration: {sm.total_duration_sec}s")
            except Exception as e:
                print(f"  ❌ {m.name}: {e}")
        return

    # Require manifest
    if not args.manifest:
        parser.print_help()
        print()
        print("  Examples:")
        print(f"    python3 run_scene.py scene_manifests/IN_THE_GROUP_CHAT.json")
        print(f"    python3 run_scene.py --validate-only scene_manifests/IN_THE_GROUP_CHAT.json")
        return

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"❌ Manifest not found: {manifest_path}")
        sys.exit(1)

    # Load manifest
    try:
        scene = SceneManifest.from_file(str(manifest_path))
    except Exception as e:
        print(f"❌ Failed to load manifest: {e}")
        sys.exit(1)

    # Validate
    errors = scene.validate()
    if errors:
        print(f"❌ Scene manifest validation failed ({len(errors)} errors):")
        for err in errors:
            print(f"  {err}")
        sys.exit(1)

    print()
    print("=" * 60)
    print(f"  SCENE: {scene.project}")
    print("=" * 60)
    print(f"  Shots:       {scene.total_shots}")
    print(f"  Duration:    {scene.total_duration_sec}s")
    print(f"  Aspect:      {scene.aspect_ratio} @ {scene.fps}fps")
    print(f"  Golden presets: {sorted(GOLDEN_PRESETS)}")
    print()
    print("  Shot list:")
    for s in scene.shots:
        print(f"    [{s.shot_id}] {s.preset:20s} {s.duration_sec}s | {s.input_image}")
    print()

    if args.validate_only:
        print("✅ Manifest valid — no rendering performed.")
        return

    # Output dir
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = manifest_path.parent / "renders"

    print(f"  Output dir:  {output_dir}")
    print()
    print("=" * 60)

    # Create ledger and render
    ledger = RenderLedger(scene.project, output_dir=output_dir)
    ledger.add_scene(scene)

    print(f"\nStarting render of {scene.total_shots} shots...")
    ledger.render_all(scene, verbose=args.verbose, continue_on_error=args.continue_on_error)
    ledger.print_summary()

    # Final exit code
    if ledger.scene.failed_count > 0:
        print(f"\n⚠️  {ledger.scene.failed_count} shot(s) failed. See ledger for details.")
        sys.exit(1)
    else:
        print(f"\n✅ Scene render complete. Ledger: {ledger.ledger_path}")
        sys.exit(0)


if __name__ == "__main__":
    main()
