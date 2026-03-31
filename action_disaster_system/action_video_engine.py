"""
action_video_engine.py — Event Engine for action/disaster shots.

ARCHITECTURE:
  shot_classifier.py       → event_prompt_generator.py
         ↓                              ↓
  action_video_engine.py ──────→ MiniMax T2V API (primary)
         ↓
  PIL cinematic fallback (zoompan / camera reaction overlay)

Usage:
  engine = ActionVideoEngine()
  result = engine.generate_event(
      scene_description="gas station explodes, debris flies toward camera",
      event_type="explosion",
      duration=6.0,
  )
"""

import sys, os, time, uuid, json, subprocess, tempfile, shutil
from pathlib import Path
from dataclasses import dataclass

INPUT_IMAGE = "/Users/monsterlee/.openclaw/media/inbound/file_3---5223086e-a136-4e3a-9c06-8c2363382b8b.jpg"
MINIMAX_KEY  = "sk-cp-YsvwF4c7WYDJRWqXFQlv79tLzoszbtflileIkCegksH9Chat1z673NvbDqb739dBEK_iLvmbIp4QO9lIAu1hcnI05ycU6mX_FifVXkJglKQKJPZcgvODtyU"
MINIMAX_URL  = "https://api.minimax.io/v1/video_generation"


# ── MINIMAX T2V ──────────────────────────────────────────────────────────────

def _submit_t2v(prompt: str, neg_prompt: str = "", duration: int = 6) -> dict:
    payload = {"model": "MiniMax-Hailuo-2.3", "prompt": prompt, "duration": duration}
    if neg_prompt:
        payload["negative_prompt"] = neg_prompt
    r = subprocess.run([
        "curl", "-s", "-X", "POST", MINIMAX_URL,
        "-H", f"Authorization: Bearer {MINIMAX_KEY}",
        "-H", "Content-Type: application/json",
        "-d", json.dumps(payload), "-w", "\n%{http_code}",
    ], capture_output=True, text=True, timeout=30)
    try:
        parts = r.stdout.strip().rsplit("\n", 1)
        body, code = parts[0], parts[1] if len(parts) > 1 else "000"
    except Exception:
        body, code = r.stdout.strip(), "000"
    try:
        resp = json.loads(body)
    except Exception:
        resp = {}
    return {"task_id": resp.get("task_id", ""), "http_code": code,
            "status_code": resp.get("base_resp", {}).get("status_code", -1)}


def _poll_t2v(task_id: str, max_wait: int = 120, interval: int = 8) -> dict:
    """Poll MiniMax. Returns {'status': 'ready'|'timeout'|'error', 'video_url': str}."""
    endpoints = [
        f"https://api.minimax.io/v1/video_generation/{task_id}",
        f"https://api.minimaxi.com/v1/video_generation/{task_id}",
    ]
    start = time.perf_counter()
    consecutive_404 = 0
    while time.perf_counter() - start < max_wait:
        for ep in endpoints:
            raw = subprocess.run(
                ["curl", "-s", ep, "-H", f"Authorization: Bearer {MINIMAX_KEY}"],
                capture_output=True, text=True, timeout=20
            ).stdout.strip()
            if raw in ("", "404 page not found", "Not Found"):
                consecutive_404 += 1
                continue
            consecutive_404 = 0
            try:
                resp = json.loads(raw)
            except Exception:
                resp = {}
            sc = resp.get("base_resp", {}).get("status_code", -1)
            if sc == 2:  # done
                d = resp.get("data", {})
                vu = d.get("video_url") or d.get("url") or "" if isinstance(d, dict) else ""
                return {"status": "ready", "video_url": vu, "task_id": task_id}
            elif sc == 1:  # processing
                elapsed = int(time.perf_counter() - start)
                print(f"    Processing... {elapsed}s elapsed")
                time.sleep(interval)
                break
            elif sc == 0:  # submitted, not started
                pass
            else:
                return {"status": "error", "reason": f"status={sc}", "task_id": task_id}
        if consecutive_404 >= len(endpoints):
            elapsed = int(time.perf_counter() - start)
            print(f"    Polling... {elapsed}s (task may be on different backend)")
        time.sleep(interval)
    return {"status": "timeout", "task_id": task_id}


def _download(url: str, path: str) -> bool:
    r = subprocess.run(
        ["curl", "-s", "-L", "-o", path, "-w", "%{http_code}", url],
        capture_output=True, text=True, timeout=60
    )
    return r.stdout.strip() == "200"


# ── PIL CAMERA REACTION ─────────────────────────────────────────────────────

def apply_camera_reaction(video_path: str, reaction: str, output_path: str) -> bool:
    """Add camera shake overlay to video using PIL."""
    import math, random
    from PIL import Image

    presets = {
        "shake":       {"x": 3,  "y": 2,  "rot": 0.3, "sc": 0.995},
        "heavy_shake": {"x": 8,  "y": 6,  "rot": 1.0, "sc": 0.990},
        "lag":         {"x": 2,  "y": 1,  "rot": 0.1, "sc": 0.998},
        "impact_snap": {"x": 12, "y": 8,  "rot": 2.0, "sc": 0.985},
    }
    p = presets.get(reaction, presets["shake"])
    tmp = Path(tempfile.mkdtemp(prefix="rxn_"))

    try:
        # Get video info
        info = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries",
            "stream=width,height,r_frame_rate,nb_frames", "-of", "json", video_path
        ], capture_output=True, text=True, timeout=10)
        try:
            st = json.loads(info.stdout).get("streams", [{}])[0]
            fps = eval(st.get("r_frame_rate", "30/1"))
            nb  = int(st.get("nb_frames", 0) or fps * 6)
            W, H = st.get("width", 1080), st.get("height", 1920)
        except Exception:
            fps, nb, W, H = 30, 180, 1080, 1920

        # Extract
        fr_dir = tmp / "fr"; fr_dir.mkdir()
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-vf", f"fps={fps}", "-q:v", "2",
            str(fr_dir / "f%04d.png"),
        ], capture_output=True, timeout=60)

        out_fr = tmp / "out"; out_fr.mkdir()
        for i, fp in enumerate(sorted(fr_dir.glob("f*.png"))):
            t = i / max(1, nb - 1)
            curve = math.sin(t * math.pi)
            dx  = int((random.random() - .5) * 2 * p["x"]  * curve)
            dy  = int((random.random() - .5) * 2 * p["y"]  * curve)
            dro = (random.random() - .5)       * p["rot"] * curve
            sc  = p["sc"] + (1 - p["sc"])     * (1 - curve)
            img = Image.open(fp).convert("RGB")
            nW, nH = int(W / sc), int(H / sc)
            large = img.resize((nW, nH), Image.LANCZOS)
            lft = (nW - W) // 2 + dx
            top = (nH - H) // 2 + dy
            shaken = large.crop((lft, top, lft + W, top + H))
            shaken.save(out_fr / fp.name, "PNG")

        rc = subprocess.run([
            "ffmpeg", "-y", "-framerate", str(fps),
            "-i", str(out_fr / "f%04d.png"),
            "-vf", f"scale={W}:{H}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
            output_path,
        ], capture_output=True, timeout=60).returncode == 0
        return rc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── PIL FALLBACK ───────────────────────────────────────────────────────────

def _pil_fallback(output_path: str, event_type: str, duration: float,
                  W: int, H: int) -> dict:
    """Use PIL cinematic engine as fallback when T2V is unavailable."""
    skill_dir = Path(__file__).parent.parent
    if str(skill_dir) not in sys.path:
        sys.path.insert(0, str(skill_dir))
    from engine import CinematicShotEngine
    preset_map = {
        "explosion":  "suspense_push_golden",
        "collapse":   "suspense_push_golden",
        "car_crash":  "confrontation_shake",
        "fire":       "suspense_push_golden",
        "earthquake": "confrontation_shake",
        "fight":      "heartbreak_drift",
        "action":     "suspense_push_golden",
        "disaster":   "suspense_push_golden",
    }
    preset = preset_map.get(event_type, "suspense_push_golden")
    eng = CinematicShotEngine()
    return eng.render(
        input_image=INPUT_IMAGE,
        output_path=output_path,
        preset_name=preset,
        duration=duration, fps=24, width=W, height=H,
    )


# ── RESULT TYPE ─────────────────────────────────────────────────────────────

@dataclass
class EventRenderResult:
    status: str
    output_path: str
    event_type: str
    prompt_used: str
    duration_sec: float
    render_time_sec: float
    task_id: str
    api_status: str
    file_size_mb: float
    quality_metrics: dict
    failure_risks: list
    camera_reaction_applied: bool


# ── MAIN ENGINE ─────────────────────────────────────────────────────────────

class ActionVideoEngine:

    def __init__(self, output_dir: str = None):
        self.out_dir = Path(output_dir or "action_disaster_system/output")
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.history: list[dict] = []

    def generate_event(
        self,
        scene_description: str,
        event_type: str = "explosion",
        causal_chain: list = None,
        duration: float = 6.0,
        reaction: str = "none",
        width: int = 1080,
        height: int = 1920,
    ) -> EventRenderResult:
        """
        Generate action/disaster video.

        Route priority:
          1. MiniMax T2V → 2. PIL cinematic fallback
        """
        from event_prompt_generator import EventPromptGenerator
        t0 = time.perf_counter()
        tid = str(uuid.uuid4())[:8]

        # Build prompt
        gen = EventPromptGenerator()
        pd = gen.generate(
            scene_description=scene_description,
            event_type=event_type,
            causal_chain=causal_chain or [],
        )
        out = str(self.out_dir / f"event_{event_type}_{tid}.mp4")

        print(f"\n  🎬 [{event_type}] {scene_description[:60]}...")
        print(f"  Route: MiniMax T2V")

        # Try MiniMax T2V
        submit = _submit_t2v(pd["video_prompt"], pd.get("negative_prompt",""), int(duration))
        t2v_ok = bool(submit.get("task_id"))
        if t2v_ok:
            tid = submit["task_id"]
            print(f"  Task: {tid} | Polling...")
            poll = _poll_t2v(tid, max_wait=120)
            if poll["status"] == "ready" and poll["video_url"]:
                print(f"  Downloading...")
                dl_ok = _download(poll["video_url"], out)
                if not dl_ok:
                    print(f"  Download failed — PIL fallback")
                    t2v_ok = False
            else:
                print(f"  Poll: {poll['status']} — PIL fallback")
                t2v_ok = False
        else:
            print(f"  Submit failed — PIL fallback")

        # Process
        camera_rx = False
        if t2v_ok and Path(out).exists() and Path(out).stat().st_size > 1000:
            if reaction != "none":
                print(f"  Camera reaction: {reaction}...")
                tmp = str(self.out_dir / f"_tmp_{tid}.mp4")
                shutil.move(out, tmp)
                ok = apply_camera_reaction(tmp, reaction, out)
                camera_rx = ok
                if not ok:
                    shutil.move(tmp, out)
            elapsed = time.perf_counter() - t0
            size = Path(out).stat().st_size / (1024*1024)
            print(f"  ✅ {out} | {size:.2f}MB | {elapsed:.1f}s")
            self.history.append({"task_id": tid, "event_type": event_type, "status": "success"})
            return EventRenderResult(
                status="success", output_path=out, event_type=event_type,
                prompt_used=pd["video_prompt"], duration_sec=duration,
                render_time_sec=round(elapsed,1), task_id=tid,
                api_status="t2v_completed", file_size_mb=round(size,3),
                quality_metrics=pd["quality_metrics_estimate"],
                failure_risks=pd["failure_risks"],
                camera_reaction_applied=camera_rx,
            )

        # PIL fallback
        print(f"  Using PIL cinematic fallback...")
        cr = _pil_fallback(out, event_type, duration, width, height)
        elapsed = time.perf_counter() - t0
        size = (Path(out).stat().st_size / (1024*1024) if Path(out).exists() else 0)
        print(f"  {'✅' if cr.get('status')=='success' else '❌'} PIL | {size:.2f}MB | {elapsed:.1f}s")
        self.history.append({"task_id": tid, "event_type": event_type, "status": cr.get("status","failed")})
        return EventRenderResult(
            status=cr.get("status","failed")+"_fallback",
            output_path=out, event_type=event_type,
            prompt_used=pd["video_prompt"], duration_sec=duration,
            render_time_sec=round(elapsed,1), task_id=tid,
            api_status="t2v_unavailable_used_pil",
            file_size_mb=round(size,3),
            quality_metrics={**pd["quality_metrics_estimate"], "route": "pil_cinematic"},
            failure_risks=pd["failure_risks"]+["T2V unavailable, used PIL cinematic"],
            camera_reaction_applied=False,
        )

    def generate_from_scene(self, scene_description: str, shot_type: str,
                            causal_chain: list = None,
                            camera_reaction: bool = False,
                            duration: float = 6.0) -> EventRenderResult:
        """Generate from scene description (auto-classify or use provided type)."""
        if shot_type == "hybrid":
            from event_prompt_generator import EventPromptGenerator
            gen = EventPromptGenerator()
            hd = gen.generate_hybrid(emotional_subject=scene_description,
                                    event_description=scene_description,
                                    event_type="explosion",
                                    causal_chain=causal_chain)
            prompt = hd.get("prompt", scene_description)
        else:
            prompt = scene_description
        return self.generate_event(
            scene_description=prompt,
            event_type=shot_type,
            causal_chain=causal_chain,
            duration=duration,
            reaction="heavy_shake" if camera_reaction else "none",
        )


# ── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys as _sys
    if "--test" in _sys.argv:
        eng = ActionVideoEngine()
        r = eng.generate_event(
            scene_description=(
                "a gas station erupts in massive explosion, fireball expands outward "
                "toward camera, debris flies at high velocity, thick smoke column rises"
            ),
            event_type="explosion",
            causal_chain=["fuel ignition","fireball expansion","shockwave","debris dispersal"],
            reaction="heavy_shake",
        )
        print(f"\nResult: {r.status} | {r.output_path} | {r.render_time_sec}s | {r.file_size_mb}MB")
        print(f"API: {r.api_status} | T2V OK: {r.status=='success'}")
