#!/usr/bin/env python3
"""
preset_isolation.py — Four-stage isolation debugger for cinematic presets.

Tests one preset in progressive layers to pinpoint where failures originate.

RULES:
  1. Any stage failure → subsequent stages STOP (no fallback, no silent continue)
  2. All failures must be explicitly documented with exact failure point
  3. OLD SCHEMA presets are NOT valid test subjects (silently map to static)
  4. All output must be machine-readable (JSON)
  5. No silent fallback — if something fails, it fails visibly

STAGES:
  A — Base camera only (linear zoom, no hold, no easing, no effects)
  B — + Motion layer (micro_shake, breathing)
  C — + Lighting layer (flicker, vignette_pulse, glow_drift)
  D — Full preset with timing/easing/hold

USAGE:
  python3 preset_isolation.py suspense_push 5.0
  python3 preset_isolation.py suspense_push 5.0 --stage A
"""

import subprocess, json, time, sys, tempfile, hashlib
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
from preset import load_preset

INPUT = "/Users/monsterlee/.openclaw/media/inbound/file_3---5223086e-a136-4e3a-9c06-8c2363382b8b.jpg"
OUT  = Path("demo_output")
OUT.mkdir(exist_ok=True)

STAGE_STEPS = ["A_base", "B_motion", "C_lighting", "D_full"]


# =============================================================================
# REPORT SCHEMA
# =============================================================================

@dataclass
class StageReport:
    preset_name: str
    stage: str
    pass_: bool
    failure_type: str          # "" if pass, else: python_stage | ffmpeg | param_mapping | timing_assembly
    exact_failure_point: str    # exact line / expression that failed
    exact_failing_expression: str # the actual failing code/command
    ffmpeg_rc: int
    output_file: str
    stderr_log: str
    command_file: str
    params_file: str
    notes: str = ""
    elapsed_sec: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pass"] = d.pop("pass_")  # JSON-friendly key
        return d


# =============================================================================
# PARAMS SNAPSHOT
# =============================================================================

def build_snapshot(preset_name: str, stage: str, p) -> dict:
    """Build a params snapshot of ACTUAL applied values."""
    return {
        "preset_name": preset_name,
        "stage": stage,
        "engine_mode": "cinematic_pil",
        "move": str(p.move) if hasattr(p, "move") else "push_in",
        "zoom_start": p.zoom_start,
        "zoom_end": p.zoom_end,
        "x_start": p.x_start,
        "x_end": p.x_end,
        "y_start": p.y_start,
        "y_end": p.y_end,
        "rotation_start_deg": getattr(p, "rot_start", 0.0),
        "rotation_end_deg": getattr(p, "rot_end", 0.0),
        "easing": p.easing() if callable(p.easing) else str(p.easing),
        "micro_shake": p.micro_shake,
        "breathing": p.breathing,
        "parallax_strength": getattr(p, "parallax_strength", 0.0),
        "flicker": p.flicker,
        "vignette_pulse": p.vignette_pulse,
        "glow_drift": p.glow_drift,
        "hold_start_sec": p.hold_start_dur,
        "main_move_start_sec": p.move_start,
        "main_move_end_sec": p.move_end,
        "hold_end_sec": p.hold_end_dur,
        "duration_sec": p.duration,
        "fps": 24,
    }


# =============================================================================
# ENGINE IMPORT
# =============================================================================

def get_engine():
    from engine import CinematicShotEngine
    return CinematicShotEngine()


# =============================================================================
# STAGE BUILDERS — each returns modified preset with ONLY that stage's params
# =============================================================================

def apply_stage_a(preset) -> dict:
    """Stage A: base camera only. All else = 0/false."""
    return {
        "camera": {
            "zoom_start": preset.zoom_start,
            "zoom_end": preset.zoom_end,
            "x_start": 0.5, "x_end": 0.5,
            "y_start": 0.5, "y_end": 0.5,
            "rotation_start_deg": 0.0, "rotation_end_deg": 0.0,
            "easing": "linear",
        },
        "motion": {
            "micro_shake": 0.0,
            "breathing": 0.0,
            "parallax_strength": 0.0,
        },
        "lighting": {
            "flicker": 0.0,
            "vignette_pulse": 0.0,
            "glow_drift": 0.0,
        },
        "timing": {
            "hold_start_sec": 0.0,
            "main_move_start_sec": 0.0,
            "main_move_end_sec": 0.0,
            "hold_end_sec": 0.0,
        },
    }


def apply_stage_b(preset) -> dict:
    """Stage B: base camera + motion. Lighting = 0, timing preserved."""
    return {
        "camera": {
            "zoom_start": preset.zoom_start,
            "zoom_end": preset.zoom_end,
            "x_start": 0.5, "x_end": 0.5,
            "y_start": 0.5, "y_end": 0.5,
            "rotation_start_deg": 0.0, "rotation_end_deg": 0.0,
            "easing": "linear",
        },
        "motion": {
            "micro_shake": preset.micro_shake,
            "breathing": preset.breathing,
            "parallax_strength": 0.0,
        },
        "lighting": {
            "flicker": 0.0,
            "vignette_pulse": 0.0,
            "glow_drift": 0.0,
        },
        # CRITICAL: timing must be non-zero to avoid div-by-zero in engine
        "timing": {
            "hold_start_sec": preset.hold_start_dur,
            "main_move_start_sec": preset.move_start,
            "main_move_end_sec": preset.move_end,
            "hold_end_sec": preset.hold_end_dur,
        },
    }


def apply_stage_c(preset) -> dict:
    """Stage C: camera + motion + lighting. Timing preserved."""
    return {
        "camera": {
            "zoom_start": preset.zoom_start,
            "zoom_end": preset.zoom_end,
            "x_start": 0.5, "x_end": 0.5,
            "y_start": 0.5, "y_end": 0.5,
            "rotation_start_deg": 0.0, "rotation_end_deg": 0.0,
            "easing": "linear",
        },
        "motion": {
            "micro_shake": preset.micro_shake,
            "breathing": preset.breathing,
            "parallax_strength": 0.0,
        },
        "lighting": {
            "flicker": preset.flicker,
            "vignette_pulse": preset.vignette_pulse,
            "glow_drift": preset.glow_drift,
        },
        "timing": {
            "hold_start_sec": preset.hold_start_dur,
            "main_move_start_sec": preset.move_start,
            "main_move_end_sec": preset.move_end,
            "hold_end_sec": preset.hold_end_dur,
        },
    }


def apply_stage_d(preset) -> dict:
    """Stage D: full preset with all timing restored."""
    return {
        "camera": {
            "zoom_start": preset.zoom_start,
            "zoom_end": preset.zoom_end,
            "x_start": 0.5, "x_end": 0.5,
            "y_start": 0.5, "y_end": 0.5,
            "rotation_start_deg": 0.0, "rotation_end_deg": 0.0,
            "easing": preset.easing() if callable(preset.easing) else str(preset.easing),
        },
        "motion": {
            "micro_shake": preset.micro_shake,
            "breathing": preset.breathing,
            "parallax_strength": 0.0,
        },
        "lighting": {
            "flicker": preset.flicker,
            "vignette_pulse": preset.vignette_pulse,
            "glow_drift": preset.glow_drift,
        },
        "timing": {
            "hold_start_sec": preset.hold_start_dur,
            "main_move_start_sec": preset.move_start,
            "main_move_end_sec": preset.move_end,
            "hold_end_sec": preset.hold_end_dur,
        },
    }


STAGE_BUILDERS = {
    "A_base":    apply_stage_a,
    "B_motion":  apply_stage_b,
    "C_lighting": apply_stage_c,
    "D_full":    apply_stage_d,
}


# =============================================================================
# VARIANT MANAGER — create/test/delete preset variants
# =============================================================================

VARIANT_COUNTER = 0

def create_stage_variant(base_name: str, stage: str, params: dict) -> str:
    """Save a stage variant JSON to presets/ and return the variant name."""
    global VARIANT_COUNTER
    VARIANT_COUNTER += 1
    variant_name = f"__stage_{stage}_{VARIANT_COUNTER}"
    path = Path("presets") / f"{variant_name}.json"
    # Add name field required by Preset.__init__
    params_with_name = {"name": variant_name, **params}
    path.write_text(json.dumps(params_with_name, indent=2))
    return variant_name


def cleanup_variant(variant_name: str):
    """Delete a stage variant JSON."""
    p = Path("presets") / f"{variant_name}.json"
    if p.exists():
        p.unlink()


# =============================================================================
# STAGE RUNNER
# =============================================================================

def run_stage(preset_name: str, base_preset, stage: str, duration: float) -> StageReport:
    """
    Run a single stage. Returns StageReport.
    On failure: records exact failure point and DOES NOT fall through.
    """
    builder = STAGE_BUILDERS[stage]
    variant_name = create_stage_variant(preset_name, stage, builder(base_preset))

    prefix = f"{preset_name}_{stage}"
    dbg_path = OUT / f"{prefix}_frames.json"
    out_mp4  = OUT / f"{prefix}.mp4"
    cmd_path = OUT / f"{prefix}.cmd.txt"
    err_path = OUT / f"{prefix}.stderr.log"
    snap_path = OUT / f"{prefix}.params.json"
    rep_path = OUT / f"{prefix}.report.json"

    # Write command file
    cmd_file_content = (
        f"python3 engine.render(\n"
        f"  preset_name='{variant_name}',\n"
        f"  duration={duration},\n"
        f"  fps=24,\n"
        f"  input_image='{INPUT}',\n"
        f"  output_path='{out_mp4}',\n"
        f"  frame_debug_path='{dbg_path}',\n"
        f")\n"
    )
    cmd_path.write_text(cmd_file_content)

    # Save params snapshot
    p = load_preset(variant_name)
    snap = build_snapshot(preset_name, stage, p)
    snap_path.write_text(json.dumps(snap, indent=2))

    # Run engine
    from engine import CinematicShotEngine
    engine = CinematicShotEngine()

    t0 = time.perf_counter()
    ffmpeg_rc = -1
    stderr_log = ""
    error_msg = ""

    try:
        result = engine.render(
            input_image=INPUT,
            output_path=str(out_mp4),
            preset_name=variant_name,
            duration=duration,
            fps=24,
            width=1080, height=1920,
            frame_debug_path=str(dbg_path),
        )
    except Exception as e:
        elapsed = time.perf_counter() - t0
        error_msg = f"{type(e).__name__}: {e}"
        stderr_log = error_msg
        err_path.write_text(error_msg)

        rep = StageReport(
            preset_name=preset_name, stage=stage,
            pass_=False,
            failure_type="python_stage",
            exact_failure_point=f"engine.render() raised {type(e).__name__}",
            exact_failing_expression=error_msg,
            ffmpeg_rc=-1,
            output_file=str(out_mp4),
            stderr_log=error_msg,
            command_file=str(cmd_path),
            params_file=str(snap_path),
            elapsed_sec=round(elapsed, 2),
        )
        rep_path.write_text(json.dumps(rep.to_dict(), indent=2))
        cleanup_variant(variant_name)
        return rep

    elapsed = time.perf_counter() - t0
    ffmpeg_rc = result.get("returncode", 0) if isinstance(result, dict) else 0
    status = result.get("status", "unknown")
    err_msg = result.get("error", "") if isinstance(result, dict) else ""
    stderr_log = err_msg
    err_path.write_text(err_msg)

    passed = (status == "success" and out_mp4.exists() and out_mp4.stat().st_size > 1000)

    rep = StageReport(
        preset_name=preset_name, stage=stage,
        pass_=bool(passed),
        failure_type="" if passed else (result.get("failure_type", "unknown") if isinstance(result, dict) else "unknown"),
        exact_failure_point="" if passed else f"status={status}, error={err_msg[:100]}",
        exact_failing_expression="" if passed else err_msg[:200],
        ffmpeg_rc=ffmpeg_rc,
        output_file=str(out_mp4),
        stderr_log=err_msg[:500],
        command_file=str(cmd_path),
        params_file=str(snap_path),
        elapsed_sec=round(elapsed, 2),
    )
    rep_path.write_text(json.dumps(rep.to_dict(), indent=2))

    # Cleanup variant
    cleanup_variant(variant_name)

    return rep


# =============================================================================
# MAIN
# =============================================================================

def main():
    if len(sys.argv) < 3:
        print("Usage: preset_isolation.py <preset_name> <duration> [--stage A|B|C|D]")
        print("Stages: A_base → B_motion → C_lighting → D_full")
        sys.exit(1)

    preset_name = sys.argv[1]
    duration    = float(sys.argv[2])

    # Optional: run only one stage
    run_stages = STAGE_STEPS
    if "--stage" in sys.argv:
        idx = sys.argv.index("--stage")
        target = sys.argv[idx + 1]
        run_stages = [s for s in STAGE_STEPS if stage_letter(s) == target.upper()]
        if not run_stages:
            print(f"Unknown stage: {target}")
            sys.exit(1)

    # Verify preset is NOT old schema
    if preset_name in ("suspense", "heartbreak", "reveal", "comedy"):
        print(f"\n❌ BLOCKED: '{preset_name}' is OLD SCHEMA.")
        print("   Old schema presets silently map to static (move=static, zoom_start=zoom_end=1.0).")
        print("   These are NOT valid isolation test subjects.")
        print("   Use: suspense_push, heartbreak_drift, reveal_hold_push, comedy_snap")
        sys.exit(1)

    # Load base preset
    try:
        base = load_preset(preset_name)
    except Exception as e:
        print(f"❌ Cannot load preset '{preset_name}': {e}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  PRESET ISOLATION: {preset_name}")
    print(f"  Duration: {duration}s")
    print(f"  Stages: {' → '.join(run_stages)}")
    print(f"{'='*60}")

    results = {}
    first_failure = None

    for stage in run_stages:
        prefix = f"{preset_name}_{stage}"
        rep_path = OUT / f"{prefix}.report.json"

        print(f"\n--- Stage {stage} ---")
        t0 = time.perf_counter()
        rep = run_stage(preset_name, base, stage, duration)
        elapsed = time.perf_counter() - t0
        results[stage] = rep

        icon = "✅" if rep.pass_ else "❌"
        print(f"  {icon} {stage}: {'PASS' if rep.pass_ else 'FAIL'} ({elapsed:.1f}s)")

        if not rep.pass_ and first_failure is None:
            first_failure = stage
            print(f"\n  ⚠️  FIRST FAILURE at {stage}")
            print(f"  Type:    {rep.failure_type}")
            print(f"  Point:   {rep.exact_failure_point}")
            print(f"  Detail:  {rep.exact_failing_expression[:100]}")
            # STOP on first failure — hard rule
            print(f"\n  ⏹  STOPPING — subsequent stages cancelled")
            break

    # Print summary
    print(f"\n{'='*60}")
    print(f"  ISOLATION SUMMARY: {preset_name}")
    print(f"{'='*60}")
    print(f"  {'Stage':12s} {'Pass':6s} {'Type':20s} {'Point'}")
    print(f"  {'-'*12:12s} {'-'*6:6s} {'-'*20:20s} {'-'*20:20s}")
    for stage, rep in results.items():
        print(f"  {stage:12s} {'✅' if rep.pass_ else '❌':6s} "
              f"{rep.failure_type or 'ok':20s} {rep.exact_failure_point[:40]}")

    if first_failure:
        rep = results[first_failure]
        print(f"\n  FIRST FAILURE: {first_failure}")
        print(f"  Type:    {rep.failure_type}")
        print(f"  Point:   {rep.exact_failure_point}")
        print(f"  File:    {rep.params_file}")

    # Save summary
    summary = {
        "preset_name": preset_name,
        "duration": duration,
        "all_pass": all(r.pass_ for r in results.values()),
        "first_failure": first_failure,
        "stages": {stage: rep.to_dict() for stage, rep in results.items()},
    }
    sum_path = OUT / f"{preset_name}_isolation_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2))
    print(f"\n  Summary: {sum_path}")


def stage_letter(s: str) -> str:
    return s.split("_")[0]


if __name__ == "__main__":
    main()
