"""
event_prompt_generator.py — Generates Sora/Seedance-class event/action prompts.

Core principle:
  Write prompts that describe WHAT IS HAPPENING, not what the frame looks like.
  The event must feel causally real, not visually decorated.

Event prompt anatomy:
  [SUBJECT] + [EVENT] + [CAUSAL CHAIN] + [CAMERA BEHAVIOR] + [ENVIRONMENT] + [MOOD]

Sora/Seedance realism cues we use:
  - Material-specific physics (glass ≠ wood ≠ concrete)
  - Weight and scale cues
  - Temporal markers (sudden, sustained, fading)
  - Environmental coherence
  - Camera-as-witness framing
"""

import json
from dataclasses import dataclass, field
from typing import Optional


# ── MATERIAL PHYSICS LIBRARY ─────────────────────────────────────────────────

MATERIAL_PHYSICS = {
    "glass": {
        "break_pattern": "shatters into angular shards, fragments scatter with high velocity",
        "sound_cue": "sharp crack, then tinkling of falling pieces",
        "motion_profile": "sudden fracture, radial dispersal, pieces tumble with rotation",
        "secondary_effects": ["sparkle in light", "slow-motion clarity", "sharp edge highlight"],
    },
    "concrete": {
        "break_pattern": "cracks propagate from stress point, chunks separate and fall",
        "sound_cue": "deep rumble, grinding of displaced mass",
        "motion_profile": "slower failure than glass, dust cloud generated, heavy chunks",
        "secondary_effects": ["dust plume", "rebar visible", "rubble pile formation"],
    },
    "wood": {
        "break_pattern": "splinters along grain, bends before breaking, splinters scatter",
        "sound_cue": "crack and split, creaking then snap",
        "motion_profile": "bends under load before failure, debris tumbles",
        "secondary_effects": ["splinter cloud", "bark fragments", "lighter debris"],
    },
    "metal": {
        "break_pattern": "bends without breaking, tears with jagged edge, sparks on impact",
        "sound_cue": "metallic ping, screech of deformation",
        "motion_profile": "plastic deformation before failure, sparks trail",
        "secondary_effects": ["sparks", "heat shimmer", "glowing edge"],
    },
    "water": {
        "break_pattern": "surges and recedes, forms turbulent waves, splashes",
        "sound_cue": "rush, crash, gurgling",
        "motion_profile": "fluid, continuous motion, follows gravity and surfaces",
        "secondary_effects": ["mist", "foam", "debris carried in flow"],
    },
    "fire": {
        "break_pattern": "expands outward, licks upward, consumes fuel, creates smoke",
        "sound_cue": "roar, crackle, whoosh of air being drawn in",
        "motion_profile": "turbulent upward motion, fingers of flame, flickering",
        "secondary_effects": ["smoke column", "ember rain", "glow on nearby surfaces"],
    },
}


# ── EVENT TEMPLATE LIBRARY ───────────────────────────────────────────────────

EVENT_TEMPLATES = {
    "explosion": {
        "template": (
            "a {location} explodes with violent force — "
            "fireball expands outward in a perfect sphere, "
            "{material} fragments {direction} at high velocity, "
            "a thick smoke column rises rapidly, "
            "the shockwave visibly distorts the air, "
            "secondary fires ignite in the surrounding area. "
            "Filmed in {camera_style}. Realistic physics, {duration_quality}."
        ),
        "camera_style_options": [
            "wide establishing shot from distance, camera tremor visible",
            "medium shot, debris flying toward lens, lens dirt hits",
            "POV of standing witness, ground shakes underfoot",
            "slow-motion close-up of fireball edge, debris tumbling",
        ],
        "duration_quality": "sudden ignition, sustained heat, gradual dissipation",
        "required_elements": ["fireball", "smoke", "debris", "shockwave"],
    },
    "collapse": {
        "template": (
            "a {structure_type} loses structural integrity and collapses — "
            "cracks propagate across the surface, "
            "{material} gives way section by section, "
            "a massive dust cloud erupts as the mass hits the ground, "
            "secondary debris continues to fall as the dust settles. "
            "Filmed in {camera_style}. Realistic physics, heavy mass, {duration_quality}."
        ),
        "camera_style_options": [
            "wide shot from across the street, dust cloud fills frame",
            "medium shot from inside, ceiling above gives way",
            "long lens compressed shot, collapse appears sudden",
            "low angle looking up as facade crumbles toward camera",
        ],
        "duration_quality": "creaking anticipation, rapid failure, prolonged dust settling",
        "required_elements": ["crack propagation", "mass falling", "dust cloud", "secondary fall"],
    },
    "car_crash": {
        "template": (
            "a {vehicle_type} loses control and crashes into {impact_target} — "
            "tires screech, the vehicle {crash_behavior}, "
            "glass {glass_behavior}, "
            "the impact causes immediate structural deformation, "
            "debris scatters across the ground, "
            "steam or smoke begins to rise from the damaged area. "
            "Filmed in {camera_style}. Realistic physics, {duration_quality}."
        ),
        "camera_style_options": [
            "dashcam perspective, impact felt through frame jolt",
            "CCTV style, monochromatic, high contrast",
            "slow-motion from roadside, debris arc in frame",
            "interior POV, steering wheel visible, impact through windshield",
        ],
        "duration_quality": "screech leads, impact is instant, aftermath lingers",
        "required_elements": ["screech", "deformation", "glass", "debris", "steam"],
    },
    "fire": {
        "template": (
            "a {fire_context} engulfs in flames — "
            "orange and yellow fire rapidly spreads across {fuel_source}, "
            "thick black smoke billows upward in a massive column, "
            "embers rain down on surrounding areas, "
            "the heat causes visible air distortion, "
            "nearby structures catch secondary fires. "
            "Filmed in {camera_style}. Realistic fire physics, {duration_quality}."
        ),
        "camera_style_options": [
            "night shot, fire is the primary light source, deep shadows",
            "aerial drone shot, smoke column visible for miles",
            "street level, flames fill upper frame, pedestrians fleeing",
            "close-up of fire eating through material, texture of flame visible",
        ],
        "duration_quality": "rapid spread, sustained intensity, gradual fuel depletion",
        "required_elements": ["flame spread", "smoke column", "embers", "air distortion", "secondary ignition"],
    },
    "earthquake": {
        "template": (
            "a powerful earthquake strikes — "
            "the ground fractures and displaces along a visible fault line, "
            "structures {structure_response}, "
            "cars bounce and shift on unstable ground, "
            "a dust cloud rises from the vibrating surface, "
            "the tremors continue for {duration} seconds. "
            "Filmed in {camera_style}. Realistic seismic physics."
        ),
        "camera_style_options": [
            "dashcam, car bouncing, power lines swaying violently",
            "indoor shot, everything on shelves rattling and falling",
            "aerial satellite view, fault rupture visible as line of destruction",
            "security camera, heavy frame shake, dust from crumbling walls",
        ],
        "duration_quality": "sudden onset, sustained shaking, diminishing aftershocks",
        "required_elements": ["ground fracture", "structure response", "dust", "unstable surface"],
    },
    "fight": {
        "template": (
            "a physical altercation unfolds — "
            "a {strike_type} lands with visible impact force, "
            "the recipient staggers and {reaction}, "
            "blood splatter {blood_behavior}, "
            "both parties continue to {ongoing_action}, "
            "surrounding environment reacts with {env_response}. "
            "Filmed in {camera_style}. Grounded, realistic violence, {duration_quality}."
        ),
        "camera_style_options": [
            "single continuous take, handheld, close-quarters",
            "CCTV style, overhead angle, monochromatic",
            "slow-motion impact moment, details of motion blur",
            "wide shot showing full space, characters smaller in frame",
        ],
        "duration_quality": "rapid exchange, brief pause, escalation",
        "required_elements": ["impact", "reaction", "weight of strikes", "environmental response"],
    },
    "shockwave": {
        "template": (
            "a shockwave from {shockwave_source} propagates through air — "
            "it visibly ripples the air like heat distortion, "
            "people and objects are knocked off balance {distance} from the source, "
            "windows {window_response}, "
            "a low rumble is heard as the wave passes. "
            "Filmed in {camera_style}. Realistic pressure wave physics."
        ),
        "camera_style_options": [
            "wide shot, shockwave visible as wall of air distortion approaching",
            "interior, window explodes inward as shockwave hits",
            "face of a person as shockwave passes — eyes close reflexively",
            "debris that was sitting still suddenly lifts and flies outward",
        ],
        "required_elements": ["air distortion", "knockback", "window failure", "rumble"],
    },
}


# ── QUALITY METRICS ──────────────────────────────────────────────────────────

@dataclass
class ActionQualityMetrics:
    event_realism: float       # physics believable
    motion_complexity: float   # multiple moving elements
    causal_consistency: float  # event has logical progression
    visual_readability: float  # subject identifiable amid chaos
    impact_strength: float     # impact feels powerful
    chaos_control_balance: float  # chaos present but not overwhelming
    sora_seedance_similarity: float  # overall resemblance to quality AI video

    def to_dict(self) -> dict:
        return {
            "event_realism": self.event_realism,
            "motion_complexity": self.motion_complexity,
            "causal_consistency": self.causal_consistency,
            "visual_readability": self.visual_readability,
            "impact_strength": self.impact_strength,
            "chaos_control_balance": self.chaos_control_balance,
            "sora_seedance_similarity": self.sora_seedance_similarity,
        }


# ── EVENT PROMPT GENERATOR ──────────────────────────────────────────────────

class EventPromptGenerator:
    """
    Generates Sora/Seedance-class prompts for action and disaster scenes.
    """

    def generate(
        self,
        scene_description: str,
        event_type: str = "explosion",
        causal_chain: list[str] = None,
        main_subject: str = "",
        camera_behavior: str = "",
        duration_sec: float = 6.0,
        aspect_ratio: str = "9:16",
        style: str = "cinematic realism",
    ) -> dict:
        """
        Returns full event prompt package dict.
        """
        if event_type not in EVENT_TEMPLATES:
            event_type = "explosion"  # fallback

        template = EVENT_TEMPLATES[event_type]

        # Build positive prompt
        prompt_parts = [scene_description]
        if causal_chain:
            chain_str = " → ".join(causal_chain[:4])
            prompt_parts.append(f"Causal chain: {chain_str}")
        if camera_behavior:
            prompt_parts.append(f"Camera behavior: {camera_behavior}")

        positive_prompt = ". ".join(prompt_parts) + f". Cinematic, {style}, {duration_sec} seconds."

        # Build negative prompt
        negative_prompt = self._build_negative_prompt(event_type)

        # Quality metrics (pre-generation estimate)
        metrics = ActionQualityMetrics(
            event_realism=0.8,
            motion_complexity=0.8,
            causal_consistency=0.9 if causal_chain else 0.5,
            visual_readability=0.7,
            impact_strength=0.8,
            chaos_control_balance=0.7,
            sora_seedance_similarity=0.75,
        )

        return {
            "event_description": scene_description,
            "event_type": event_type,
            "causal_chain": causal_chain or [],
            "main_subject": main_subject,
            "camera_behavior": camera_behavior,
            "duration_sec": duration_sec,
            "aspect_ratio": aspect_ratio,
            "video_prompt": positive_prompt,
            "negative_prompt": negative_prompt,
            "failure_risks": self._assess_risks(event_type, scene_description),
            "quality_metrics_estimate": metrics.to_dict(),
        }

    def generate_from_classification(
        self,
        scene_description: str,
        event_type: str,
        causal_chain: list[str],
        camera_reaction: bool = False,
        duration_sec: float = 6.0,
    ) -> dict:
        """Generate from ShotClassification output."""
        cam_behavior = ""
        if camera_reaction:
            cam_behavior = (
                "camera shakes from impact, slight delay before reaction, "
                "frame tremor adds to the sense of witness shock"
            )
        else:
            cam_behavior = (
                "stable wide framing, event is observed from safety, "
                "camera does not react — heightens tension as witness"
            )

        return self.generate(
            scene_description=scene_description,
            event_type=event_type,
            causal_chain=causal_chain,
            camera_behavior=cam_behavior,
            duration_sec=duration_sec,
        )

    def _build_negative_prompt(self, event_type: str) -> str:
        """Build negative prompt for event generation."""
        base_negatives = [
            "blurry, out of focus, low quality",
            "插画风格, cartoon, animation, anime",
            "debris only, no fire, no smoke, empty scene",
            "people are standing still, no motion",
            "camera is perfectly still, no reaction",
            "text, watermark, logo, UI elements",
            " distorted face, disfigured hands",
        ]

        event_specific = {
            "explosion": ["tiny fire, candle flame, campfire"],
            "collapse":  ["intact building, pristine, no damage"],
            "car_crash": ["pristine car, no damage, car driving normally"],
            "fire":      ["no flames visible, smoke only, candle"],
            "earthquake": ["stable ground, nothing moving, serene"],
            "fight":     ["balletic, slow-motion only, no impact"],
            "shockwave": ["invisible wave, no effect on environment"],
        }

        specifics = event_specific.get(event_type, [])
        return ", ".join(base_negatives + specifics)

    def _assess_risks(self, event_type: str, description: str) -> list[str]:
        risks = []
        desc_lower = description.lower()

        if len(description) < 50:
            risks.append("description too brief — event may lack specificity")

        if "toward camera" not in desc_lower and "viewer" not in desc_lower:
            risks.append("no directional cue — debris may not fly toward camera")

        if "shockwave" in desc_lower or "explosion" in desc_lower:
            if "camera shake" not in desc_lower and "lens dirt" not in desc_lower:
                risks.append("explosion without camera reaction may feel旁观者")

        if event_type == "collapse":
            if "dust" not in desc_lower and "debris" not in desc_lower:
                risks.append("collapse without dust/debris may look like magic")

        if event_type == "fire":
            if "smoke" not in desc_lower:
                risks.append("fire without smoke column loses scale reference")

        return risks


# ── ENHANCED HYBRID PROMPT ─────────────────────────────────────────────────

    def generate_hybrid(
        self,
        emotional_subject: str,
        event_description: str,
        event_type: str = "explosion",
        causal_chain: list[str] = None,
        blend_type: str = "cut",  # cut | composite | reaction_shot
    ) -> dict:
        """
        Generate hybrid prompt for scenes with BOTH emotion and disaster.
        blend_type: cut (alternating shots) | composite (same frame) | reaction_shot (event as background)
        """
        if blend_type == "cut":
            # Two separate shots, alternating
            emotional_prompt = (
                f"close-up of {emotional_subject}, "
                "expression shifts from normal to shock/horror/fear in real time, "
                "pupils dilate, face drains of color, "
                "camera is still, subject fills frame. Cinematic, emotional realism."
            )
            event_prompt = self.generate(
                scene_description=event_description,
                event_type=event_type,
                causal_chain=causal_chain,
                camera_behavior="",
            )
            return {
                "blend_type": "alternating_shot",
                "shot_1_emotional": emotional_prompt,
                "shot_2_event": event_prompt,
                "failure_risks": [
                    "cut timing critical — too fast loses emotion, too slow loses tension",
                    "both shots must match in lighting and mood",
                ],
            }

        elif blend_type == "reaction_shot":
            # Wide event + close-up reaction in same frame
            event_prompt = self.generate(
                scene_description=event_description,
                event_type=event_type,
                causal_chain=causal_chain,
            )
            emotional_prompt = (
                f"in the foreground, {emotional_subject} reacts with visible shock, "
                "their face lit by the event behind them (or the event occurs behind them), "
                "expression shows genuine fear/surprise, "
                "camera slightly pushed in on face. Cinematic emotional realism."
            )
            return {
                "blend_type": "reaction_shot",
                "prompt": f"{event_prompt['video_prompt']} AND {emotional_prompt}",
                "negative_prompt": event_prompt["negative_prompt"],
                "failure_risks": [
                    "foreground face may be lost if event overwhelms frame",
                    "lighting balance between event and face is critical",
                ],
            }

        else:  # composite
            return self.generate(
                scene_description=f"{emotional_subject} during {event_description}",
                event_type=event_type,
                causal_chain=causal_chain,
            )


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    gen = EventPromptGenerator()

    test_cases = [
        {
            "scene_description": "gas station erupts in massive explosion, fireball expands, debris flies toward camera, second explosion follows",
            "event_type": "explosion",
            "causal_chain": ["fuel ignition", "fireball expansion", "shockwave", "debris dispersal"],
            "camera_behavior": "camera trembles from blast, slight delay, debris hits lens",
        },
        {
            "scene_description": "building crumbles section by section, dust cloud erupts, cars in parking lot shift and fall",
            "event_type": "collapse",
            "causal_chain": ["structural failure", "section collapse", "dust eruption", "secondary debris"],
        },
        {
            "scene_description": "during a restaurant explosion, a woman's face in the foreground fills the frame as glass explodes behind her",
            "event_type": "hybrid",
            "emotional_subject": "woman, late 30s, her expression changes from normal to absolute horror in 2 seconds",
        },
    ]

    for tc in test_cases:
        print(f"\n{'='*60}")
        if tc.get("event_type") == "hybrid":
            r = gen.generate_hybrid(
                emotional_subject=tc["emotional_subject"],
                event_description=tc["scene_description"],
                event_type="explosion",
                causal_chain=tc.get("causal_chain"),
                blend_type="reaction_shot",
            )
            print(f"TYPE: hybrid (reaction_shot)")
            print(f"PROMPT: {r['prompt'][:200]}...")
            print(f"NEGATIVE: {r['negative_prompt'][:100]}")
        else:
            r = gen.generate(**tc)
            print(f"TYPE: {r['event_type']}")
            print(f"PROMPT: {r['video_prompt'][:200]}...")
            print(f"NEGATIVE: {r['negative_prompt'][:100]}")
            print(f"CHAIN: {' → '.join(r['causal_chain'])}")
            print(f"RISKS: {r['failure_risks']}")
            print(f"METRICS: {r['quality_metrics_estimate']}")
