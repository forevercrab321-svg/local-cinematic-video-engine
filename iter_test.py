#!/usr/bin/env python3
"""
iter_test.py — Iterator harness for preset self-tuning.
Round 3 — Precision round.

Focus:
- suspense_push: near-zero breathing (0.0005) for perfect hold
- heartbreak_drift: sync fix from R2 + deeper pull (0.83x)
- confrontation: longer move_duration for sharper snap
- memory_float: ease_in→ease_in_out (revert R2 error)
"""
import json, sys, time, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from preset import load_preset

PRESET_DIR = Path(__file__).parent / "presets"
INPUT = "/Users/monsterlee/.openclaw/media/inbound/file_3---5223086e-a136-4e3a-9c06-8c2363382b8b.jpg"
OUT = Path(__file__).parent / "golden_shots"

ROUND_CONFIGS = {
    "suspense_push": {
        "round": 3,
        "changes": {
            "breathing": {"base": 0.001, "new": 0.0005},  # near-perfect hold
        },
        "reason": "breathing=0.001 still visible at hold; try near-zero"
    },
    "heartbreak_drift": {
        "round": 3,
        "changes": {
            # Already synced in R2 — just adjust params:
            "main_move_start_sec": {"base": 0.7, "new": 0.7},   # keep synced
            "hold_start_dur":      {"base": 0.7, "new": 0.7},   # keep
            "breathing":  {"base": 0.001, "new": 0.0005},       # near-zero breathing
            "zoom_end":   {"base": 0.85,  "new": 0.83},        # deeper pull (emotional recession)
        },
        "reason": "sync fixed in R2; deeper 0.83x pull for stronger heartbreak feel"
    },
    "confrontation_shake": {
        "round": 3,
        "changes": {
            "hold_start_dur": {"base": 0.5, "new": 0.3},        # shorter hold = faster snap
            "main_move_start_sec": {"base": 0.5, "new": 0.3},    # sync
            "zoom_end":   {"base": 1.12, "new": 1.14},          # stronger push
            "micro_shake": {"base": 0.018, "new": 0.025},        # restore aggression
        },
        "reason": "shorter hold (0.3s) = faster confrontation snap; stronger zoom push"
    },
    "memory_float": {
        "round": 3,
        "changes": {
            # R2 had ease_in which creates slow start — revert to dreamy smooth
            "easing":  {"base": "ease_in", "new": "ease_in_out"},  # REVERT
            "hold_start_dur": {"base": 1.5, "new": 1.5},         # keep R2 value
            "main_move_start_sec": {"base": 1.5, "new": 1.5},     # keep synced
            "breathing": {"base": 0.0, "new": 0.0},              # keep zero
            "zoom_end":  {"base": 1.07, "new": 1.05},            # gentler dreamy float
        },
        "reason": "R2 ease_in creates slow buildup = wrong; ease_in_out = smooth dreamy motion"
    },
}


def load_json_preset(name: str) -> dict:
    path = PRESET_DIR / f"{name}.json"
    return json.loads(path.read_text())


def save_json_preset(name: str, data: dict):
    path = PRESET_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2))


SECTION_MAP = {
    "breathing": ("motion", "breathing"),
    "micro_shake": ("motion", "micro_shake"),
    "parallax_strength": ("motion", "parallax_strength"),
    "zoom_start": ("camera", "zoom_start"),
    "zoom_end": ("camera", "zoom_end"),
    "x_start": ("camera", "x_start"),
    "x_end": ("camera", "x_end"),
    "y_start": ("camera", "y_start"),
    "y_end": ("camera", "y_end"),
    "rotation_start_deg": ("camera", "rotation_start_deg"),
    "rotation_end_deg": ("camera", "rotation_end_deg"),
    "easing": ("camera", "easing"),
    "move": ("camera", "move"),
    "hold_start_dur": ("timing", "hold_start_sec"),
    "main_move_start_sec": ("timing", "main_move_start_sec"),
    "move_end": ("timing", "main_move_end_sec"),
    "hold_end_dur": ("timing", "hold_end_sec"),
    "flicker": ("lighting", "flicker"),
    "vignette_pulse": ("lighting", "vignette_pulse"),
    "glow_drift": ("lighting", "glow_drift"),
}


def create_variant(base_name: str, round_num: int, changes: dict) -> str:
    base = load_json_preset(base_name)
    for key, change in changes.items():
        if key not in SECTION_MAP:
            print(f"    ⚠️  Unknown key '{key}'")
            continue
        section, json_key = SECTION_MAP[key]
        old = base.get(section, {}).get(json_key)
        if old is None:
            print(f"    ⚠️  {section}.{json_key} not found")
            continue
        if section not in base:
            base[section] = {}
        base[section][json_key] = change["new"]
        print(f"    {section}.{json_key}: {old} → {change['new']}")
    variant_name = f"{base_name}_r{round_num}"
    save_json_preset(variant_name, base)
    return variant_name


def render_shot(preset_name: str, duration: float, label: str) -> dict:
    from engine import CinematicShotEngine
    engine = CinematicShotEngine()
    dbg = OUT / f"{label}_frames.json"
    out = OUT / f"{label}.mp4"
    t0 = time.perf_counter()
    result = engine.render(
        input_image=INPUT, output_path=str(out), preset_name=preset_name,
        duration=duration, fps=24, width=1080, height=1920,
        frame_debug_path=str(dbg),
    )
    result["wall_time"] = round(time.perf_counter() - t0, 1)
    if dbg.exists():
        frames = json.loads(dbg.read_text())
        n = len(frames)
        zooms = [f["zoom"] for f in frames]
        reverts = 0
        direction = 1 if zooms[-1] > zooms[0] else -1 if zooms[-1] < zooms[0] else 0
        for i in range(2, n):
            d = zooms[i] - zooms[i-1]
            pd = zooms[i-1] - zooms[i-2]
            if abs(d) > 0.0003 and abs(pd) > 0.0003:
                if d * pd < 0:
                    reverts += 1
        result["frame_analysis"] = {
            "n_frames": n,
            "zoom_start": round(zooms[0], 5),
            "zoom_end": round(zooms[-1], 5),
            "zoom_delta": round(zooms[-1] - zooms[0], 5),
            "zoom_min": round(min(zooms), 5),
            "zoom_max": round(max(zooms), 5),
            "zoom_reversions": reverts,
            "frame_0_zoom": round(zooms[0], 5),
            "frame_10_zoom": round(zooms[min(10, n-1)], 5),
            "frame_30_zoom": round(zooms[min(30, n-1)], 5),
            "frame_60_zoom": round(zooms[min(60, n-1)], 5),
        }
    return result


def self_evaluate(preset_name: str, result: dict, analysis: dict) -> dict:
    z0 = analysis.get("frame_0_zoom", 1.0)
    z10 = analysis.get("frame_10_zoom", 1.0)
    z30 = analysis.get("frame_30_zoom", 1.0)
    z60 = analysis.get("frame_60_zoom", 1.0)
    zoom_d = analysis.get("zoom_delta", 0)
    zoom_r = analysis.get("zoom_reversions", 0)
    zoom_max = analysis.get("zoom_max", 1.0)
    s = {}

    def hold_score(drift):
        return 9 if abs(drift) < 0.001 else 8 if abs(drift) < 0.002 else 7 if abs(drift) < 0.004 else 6 if abs(drift) < 0.008 else 4

    # 1. Intent clarity
    if "suspense" in preset_name:
        s["intent_clarity"] = 9 if zoom_d > 0.10 else 8 if zoom_d > 0.08 else 7
    elif "heartbreak" in preset_name:
        s["intent_clarity"] = 9 if zoom_d < -0.12 else 8 if zoom_d < -0.08 else 7
    elif "reveal" in preset_name:
        s["intent_clarity"] = 9 if z0 < 1.0015 and zoom_max > 1.12 else 8 if z0 < 1.002 else 7
    elif "comedy" in preset_name:
        s["intent_clarity"] = 9 if abs(zoom_d) < 0.018 else 8 if abs(zoom_d) < 0.025 else 7
    elif "confrontation" in preset_name:
        s["intent_clarity"] = 8 if zoom_d > 0.10 else 7 if zoom_d > 0.07 else 6
    elif "memory" in preset_name:
        s["intent_clarity"] = 8 if zoom_r < 2 else 7 if zoom_r < 4 else 5
    else:
        s["intent_clarity"] = 7

    # 2. Emotional pressure
    if "suspense" in preset_name:
        s["emotional_pressure"] = 9 if z30 < 1.005 else 8 if z30 < 1.02 else 7
    elif "heartbreak" in preset_name:
        s["emotional_pressure"] = 9 if zoom_d < -0.15 else 8 if zoom_d < -0.10 else 7 if zoom_d < -0.05 else 6
    elif "reveal" in preset_name:
        s["emotional_pressure"] = 9 if abs(zoom_d) > 0.15 else 8 if abs(zoom_d) > 0.12 else 7
    elif "comedy" in preset_name:
        s["emotional_pressure"] = 7 if abs(zoom_d) < 0.02 else 6
    elif "confrontation" in preset_name:
        s["emotional_pressure"] = 9 if zoom_d > 0.13 else 8 if zoom_d > 0.10 else 7 if zoom_d > 0.07 else 6
    elif "memory" in preset_name:
        s["emotional_pressure"] = 7 if abs(zoom_d) < 0.12 else 6
    else:
        s["emotional_pressure"] = 7

    # 3. Timing quality
    if "reveal" in preset_name:
        s["timing_quality"] = 9 if z0 < 1.001 else 8 if z0 < 1.002 else 7
    elif "comedy" in preset_name:
        s["timing_quality"] = 9 if abs(zoom_d) < 0.016 else 8 if abs(zoom_d) < 0.022 else 7
    elif "suspense" in preset_name:
        s["timing_quality"] = 9 if z30 < 1.003 else 8 if z30 < 1.01 else 7 if z30 < 1.03 else 6
    else:
        s["timing_quality"] = 8

    # 4. Hold quality
    if "comedy" in preset_name:
        s["hold_quality"] = 9 if abs(z30 - z0) < 0.001 else 8 if abs(z30 - z0) < 0.003 else 7
    elif "confrontation" in preset_name:
        s["hold_quality"] = 9 if z10 < 1.002 else 8 if z10 < 1.005 else 7
    elif "suspense" in preset_name:
        s["hold_quality"] = hold_score(z10 - z0)
    elif "heartbreak" in preset_name:
        s["hold_quality"] = hold_score(z10 - z0)
    elif "memory" in preset_name:
        s["hold_quality"] = hold_score(z30 - z0)
    else:
        s["hold_quality"] = 7

    # 5. Push/pull feel
    if "heartbreak" in preset_name:
        s["push_pull_feel"] = 9 if zoom_d < -0.16 else 8 if zoom_d < -0.12 else 7 if zoom_d < -0.08 else 6
    elif "suspense" in preset_name or "confrontation" in preset_name:
        s["push_pull_feel"] = 9 if zoom_d > 0.13 else 8 if zoom_d > 0.09 else 7 if zoom_d > 0.06 else 6
    elif "reveal" in preset_name:
        s["push_pull_feel"] = 9 if abs(zoom_d) > 0.15 else 8 if abs(zoom_d) > 0.11 else 7
    elif "memory" in preset_name:
        s["push_pull_feel"] = 8 if abs(zoom_d) < 0.10 and zoom_r < 3 else 6
    else:
        s["push_pull_feel"] = 7

    # 6. Cinematic believability
    cb = 8
    if zoom_r > 4: cb -= 3
    elif zoom_r > 2: cb -= 2
    elif zoom_r > 1: cb -= 1
    if z0 > 1.004: cb -= 3
    elif z0 > 1.0025: cb -= 2
    elif z0 > 1.0015: cb -= 1
    s["cinematic_believability"] = max(1, cb)

    # 7. Short drama usability
    s["short_drama_usability"] = 9 if s["cinematic_believability"] >= 8 else 7 if s["cinematic_believability"] >= 6 else 4

    # 8. Over-motion penalty
    if "comedy" in preset_name:
        s["over_motion_penalty"] = 9 if abs(zoom_d) < 0.016 else 8 if abs(zoom_d) < 0.022 else 7
    else:
        s["over_motion_penalty"] = 9 if 0.05 < abs(zoom_d) < 0.20 else 8 if 0.02 < abs(zoom_d) < 0.25 else 7

    # 9. Cheap effect penalty
    cp = 8
    if z0 > 1.003: cp -= 3
    elif z0 > 1.002: cp -= 2
    elif z0 > 1.001: cp -= 1
    if zoom_r > 4: cp -= 3
    elif zoom_r > 2: cp -= 2
    elif zoom_r > 1: cp -= 1
    s["cheap_effect_penalty"] = max(1, cp)

    # 10. Seedance likeness
    seedance = (
        s["intent_clarity"] * 0.15 + s["emotional_pressure"] * 0.15 +
        s["timing_quality"] * 0.10 + s["hold_quality"] * 0.10 +
        s["push_pull_feel"] * 0.15 + s["cinematic_believability"] * 0.20 +
        s["short_drama_usability"] * 0.15
    )
    s["seedance_likeness"] = min(10, round(seedance, 1))

    avg = sum(s.values()) / len(s)
    if s["seedance_likeness"] >= 8.0 and s["over_motion_penalty"] >= 7 and s["cheap_effect_penalty"] >= 7:
        verdict = "LOCK"
    elif avg >= 7.5:
        verdict = "KEEP"
    elif avg >= 6:
        verdict = "ADJUST"
    else:
        verdict = "REJECT"

    notes = []
    if z0 > 1.003:
        notes.append(f"BUG: opening zoom drift z0={z0:.5f}")
    if zoom_r > 2:
        notes.append(f"BUG: {zoom_r} zoom reversions")
    if s["hold_quality"] < 7:
        notes.append(f"WEAK: hold drift={abs(z10-z0):.4f}")
    if s["cheap_effect_penalty"] <= 4:
        notes.append(f"BUG: cheap penalty={s['cheap_effect_penalty']} — looks fake")

    return {"scores": s, "verdict": verdict, "notes": notes}


def run_round(round_num: int, configs: dict):
    print(f"\n{'='*60}\n  ROUND {round_num}\n{'='*60}")
    results = []
    for base_name, cfg in configs.items():
        rn = cfg["round"]
        changes = cfg["changes"]
        reason = cfg["reason"]
        r1_path = PRESET_DIR / f"{base_name}_r1.json"
        r2_path = PRESET_DIR / f"{base_name}_r2.json"
        base_name_to_use = f"{base_name}_r{round_num-1}" if round_num > 1 else base_name

        print(f"\n--- {base_name.upper()} (base={base_name_to_use}) ---")
        print(f"  {reason}")

        variant_name = f"{base_name}_r{round_num}"
        create_variant(base_name, round_num, changes)
        print(f"  Created: {variant_name}")

        p = load_preset(base_name_to_use)
        dur = p.duration

        print(f"  BASE ({base_name_to_use})...")
        res_base = render_shot(base_name_to_use, dur, f"round{round_num}_{base_name}_BASE")
        print(f"    zoom Δ={res_base.get('frame_analysis',{}).get('zoom_delta')} | z0={res_base.get('frame_analysis',{}).get('frame_0_zoom')}")

        print(f"  VAR  ({variant_name})...")
        res_var = render_shot(variant_name, dur, f"round{round_num}_{base_name}_VAR")
        print(f"    zoom Δ={res_var.get('frame_analysis',{}).get('zoom_delta')} | z0={res_var.get('frame_analysis',{}).get('frame_0_zoom')}")

        ev_base = self_evaluate(base_name_to_use, res_base, res_base.get("frame_analysis", {}))
        ev_var = self_evaluate(variant_name, res_var, res_var.get("frame_analysis", {}))

        print(f"\n  BASE: seedance={ev_base['scores']['seedance_likeness']} | {ev_base['verdict']}")
        print(f"  VAR:  seedance={ev_var['scores']['seedance_likeness']} | {ev_var['verdict']}")
        for k in ["intent_clarity", "emotional_pressure", "hold_quality", "push_pull_feel", "cinematic_believability"]:
            print(f"    {k}: BASE={ev_base['scores'][k]} VAR={ev_var['scores'][k]}")
        if ev_var['notes']: print(f"  VAR notes: {ev_var['notes']}")

        winner = "VARIANT" if ev_var['scores']['seedance_likeness'] >= ev_base['scores']['seedance_likeness'] else "BASE"
        winner_name = variant_name if winner == "VARIANT" else base_name_to_use
        winner_ev = ev_var if winner == "VARIANT" else ev_base
        ws = ev_var['scores']['seedance_likeness'] if winner == "VARIANT" else ev_base['scores']['seedance_likeness']
        print(f"\n  → WINNER: {winner} ({winner_name}) seedance={ws}")

        best = OUT / f"round{round_num}_{base_name}_BEST.mp4"
        src = OUT / f"round{round_num}_{base_name}_VAR.mp4" if winner == "VARIANT" else OUT / f"round{round_num}_{base_name}_BASE.mp4"
        if src.exists():
            shutil.copy(src, best)

        results.append({
            "preset": base_name, "round": round_num, "winner": winner,
            "winner_preset": winner_name,
            "seedance_before": round(ev_base['scores']['seedance_likeness'], 1),
            "seedance_after": round(ev_var['scores']['seedance_likeness'], 1),
            "changes": {k: v["new"] for k, v in changes.items()},
            "reason": reason, "eval": winner_ev,
        })

    return results


if __name__ == "__main__":
    rn = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    configs = {k: v for k, v in ROUND_CONFIGS.items() if v["round"] == rn}
    results = run_round(rn, configs)

    log_path = Path(__file__).parent / "SELF_TUNING_LOG.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {"schema_version": "1.0", "iterations": [], "presets_locked": []}
    log["rounds_completed"] = rn
    log["iterations"].append({"round": rn, "results": results})

    locked = set(log.get("presets_locked", []))
    for r in results:
        if r["eval"]["verdict"] == "LOCK":
            locked.add(r["preset"])
        # Carry forward best preset name
        r["locked_preset"] = r["winner_preset"]
    log["presets_locked"] = sorted(locked)
    log_path.write_text(json.dumps(log, indent=2))
    print(f"\nLocked: {sorted(locked)}")
