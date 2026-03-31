"""
shot_classifier.py — Classifies each shot into engine type.

Usage:
    classifier = ShotClassifier()
    result = classifier.classify(
        scene_description="...",
        scriptbeat="...",
        shot_id="S01_EXPLOSION"
    )
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ShotClassification:
    shot_type: str          # dialogue | suspense | reveal | action | disaster | hybrid
    primary_driver: str     # emotion | camera | event
    recommended_engine: str # camera_engine | event_engine | hybrid
    confidence: float       # 0.0–1.0
    requires_camera_reaction: bool
    causal_chain: list[str]  # if event type, the causal chain
    hybrid_parts: dict|None  # if hybrid, breakdown
    reasoning: str
    failure_risks: list[str]


# ── KEYWORD DEFINITIONS ────────────────────────────────────────────────────────

EVENT_KEYWORDS = {
    "explosion", "explode", "blast", "detonate", "bomb",
    "collapse", "crumble", "crash", "falling", "fall",
    "fire", "flames", "burning", "inferno",
    "earthquake", "trembling", "shaking",
    "car crash", "vehicle", "chase", "pursuit",
    "flood", "wave", "water rushing", "tsunami",
    "lightning", "thunder", "storm",
    "gunfire", "shooting", "bullet",
    "fight", "punch", "kick", "brawl",
    "debris", "rubble", "dust cloud",
    "shockwave", "blast wave",
}

CAMERA_MOTION_KEYWORDS = {
    "push in", "pull out", "drift", "track",
    "slow zoom", "camera rise", "camera fall",
    "pan left", "pan right", "tilt up", "tilt down",
}

EMOTION_KEYWORDS = {
    "worried", "nervous", "tense", "fear", "shock",
    "sad", "crying", "heartbroken",
    "angry", "furious", "rage",
    "surprise", "disbelief", "realization",
    "hope", "relief",
}

# Scenes that are clearly dialogue/interaction
DIALOGUE_SCENES = {
    "talking", "speaking", "conversation", "dialogue",
    "interview", "phone call", "argument",
}

# Scenes that are clearly action/disaster
ACTION_SCENES = {
    "explosion", "car chase", "fight scene", "battle",
    "earthquake", "building collapse", "fire", "disaster",
}


def _score_keywords(text: str, keyword_set: set) -> float:
    """Return score 0–1 based on keyword density."""
    text = text.lower()
    words = set(text.split())
    matched = words & keyword_set
    if not keyword_set:
        return 0.0
    return min(1.0, len(matched) / max(1, len(keyword_set) * 0.2))


def _detect_causal_chain(text: str) -> list[str]:
    """Detect event causal chain from scene description."""
    text = text.lower()
    chains = []

    # Explosion chain
    if any(k in text for k in ["explosion", "explode", "bomb"]):
        chains += ["trigger", "ignition", "expansion", "debris_dispersal", "shockwave"]
    # Collapse chain
    if any(k in text for k in ["collapse", "crumble", "fall"]):
        chains += ["structural_weakness", "failure_point", "cascade", "rubble_formation", "dust_cloud"]
    # Fire chain
    if any(k in text for k in ["fire", "flame", "burn"]):
        chains += ["ignition", "spread", "intensification", "containment_failure"]
    # Car crash chain
    if any(k in text for k in ["crash", "collision", "impact"]):
        chains += ["brake_failure", "point_of_impact", "spin", "roll", "stop"]
    # Earthquake chain
    if any(k in text for k in ["earthquake", "tremor"]):
        chains += ["p_wave", "s_wave", "ground_rupture", "aftershock"]
    # Fight chain
    if any(k in text for k in ["fight", "punch", "brawl"]):
        chains += ["anticipation", "impact", "reaction", "escalation"]

    return chains


def _detect_camera_reaction(event_text: str) -> bool:
    """Does the scene require camera to react to events?"""
    event_text = event_text.lower()
    reactive_phrases = [
        "camera shake", "camera shudder", "frame shakes",
        "debris toward camera", "toward viewer", "approaching camera",
        "explosion in background", "fire in frame", "rush toward",
        "impact on camera", "lens flare", "frame distortion",
    ]
    return any(p in event_text for p in reactive_phrases)


# ── MAIN CLASSIFIER ──────────────────────────────────────────────────────────

class ShotClassifier:
    """
    Classifies a shot into one of:
      - camera_engine: emotion / dialogue / suspense / reveal
      - event_engine:  action / disaster (explosion, collapse, chase, etc.)
      - hybrid:         scene has both emotional subject AND disaster/background
    """

    def classify(
        self,
        scene_description: str,
        scriptbeat: str = "",
        shot_id: str = "",
        dialogue: str = "",
    ) -> ShotClassification:
        """
        Returns ShotClassification with recommended engine and reasoning.
        """
        combined = " ".join(filter(None, [scene_description, scriptbeat, dialogue, shot_id]))
        combined_lower = combined.lower()

        # ── Step 1: Score each category ─────────────────────────────────
        event_score   = _score_keywords(combined_lower, EVENT_KEYWORDS)
        emotion_score  = _score_keywords(combined_lower, EMOTION_KEYWORDS)
        camera_score   = _score_keywords(combined_lower, CAMERA_MOTION_KEYWORDS)
        dialogue_score = _score_keywords(combined_lower, DIALOGUE_SCENES)

        has_event     = event_score > 0
        has_emotion   = emotion_score > 0
        has_dialogue  = dialogue_score > 0
        camera_reacts = _detect_camera_reaction(combined_lower)
        causal_chain  = _detect_causal_chain(combined)

        # ── Step 2: Classify shot type ────────────────────────────────────
        if has_event and has_emotion:
            shot_type = "hybrid"
        elif has_event:
            disaster_keywords = ["explosion", "collapse", "earthquake", "flood", "fire", "crash"]
            shot_type = "disaster" if any(k in combined_lower for k in disaster_keywords) else "action"
        elif has_dialogue:
            shot_type = "dialogue"
        else:
            # Default to camera-driven cinematic
            if camera_score > 0 or emotion_score > 0:
                # Determine subtype
                if any(k in combined_lower for k in ["fear", "tension", "worry", "dread"]):
                    shot_type = "suspense"
                elif any(k in combined_lower for k in ["realize", "understand", "see"]):
                    shot_type = "reveal"
                else:
                    shot_type = "suspense"  # default cinematic
            else:
                shot_type = "dialogue"

        # ── Step 3: Determine engine ──────────────────────────────────────
        if shot_type in ("action", "disaster"):
            recommended_engine = "event_engine"
            primary_driver = "event"
        elif shot_type == "hybrid":
            recommended_engine = "hybrid"
            primary_driver = "event"  # event is the primary visual driver
        elif shot_type in ("suspense", "reveal"):
            recommended_engine = "camera_engine"
            primary_driver = "camera"
        else:
            # dialogue / other
            recommended_engine = "camera_engine"
            primary_driver = "emotion"

        # ── Step 4: Confidence ────────────────────────────────────────────
        confidence = min(1.0, event_score * 1.5 + emotion_score * 0.5)
        if has_event:
            confidence = max(confidence, 0.7)
        if causal_chain:
            confidence = min(1.0, confidence + 0.2)

        # ── Step 5: Failure risks ─────────────────────────────────────────
        risks = []
        if shot_type in ("action", "disaster", "hybrid"):
            if not causal_chain:
                risks.append("no causal chain — action will feel random")
            if not camera_reacts:
                risks.append("no camera reaction — will feel旁观者")
            if event_score < 0.3:
                risks.append("weak event keywords — may not trigger event_engine")
        if shot_type == "hybrid":
            risks.append("hybrid requires precise blend or subject gets lost")

        # ── Step 6: Hybrid breakdown ───────────────────────────────────────
        hybrid_parts = None
        if shot_type == "hybrid":
            hybrid_parts = {
                "emotional_subject": "character reaction / face",
                "event_background": "disaster / action element",
                "camera_engine_role": "close-up on character face / emotion",
                "event_engine_role": "wide shot of disaster event",
                "blend_strategy": "cut between or composite both"
            }

        return ShotClassification(
            shot_type=shot_type,
            primary_driver=primary_driver,
            recommended_engine=recommended_engine,
            confidence=round(confidence, 2),
            requires_camera_reaction=camera_reacts,
            causal_chain=causal_chain,
            hybrid_parts=hybrid_parts,
            reasoning=f"event={event_score:.2f} emotion={emotion_score:.2f} camera={camera_score:.2f} dialogue={dialogue_score:.2f}",
            failure_risks=risks,
        )


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json, sys

    classifier = ShotClassifier()

    test_cases = [
        ("S01", "Character sees gas station explode in the distance, face filled with horror", "", "A character stares as an explosion tears through a gas station, fire erupting toward the sky"),
        ("S02", "Building crumbles under earthquake, dust fills the air", "", "An earthquake causes a building to collapse in seconds"),
        ("S03", "Man reads a text message, face turns pale", "Man reads text: 'she's gone'", "Man's face as he reads devastating news"),
        ("S04", "Hero catches partner during earthquake, pulls them to safety", "", "During an earthquake, a hero pulls their partner to safety as the ground shakes"),
        ("S05", "Explosion rips through restaurant, glass shatters, diners scream", "", "An explosion in a restaurant shatters all windows, people screaming and running"),
    ]

    for shot_id, desc, dialogue, note in test_cases:
        r = classifier.classify(desc, note, shot_id, dialogue)
        print(f"\n[{shot_id}] {desc[:50]}...")
        print(f"  Type:        {r.shot_type}")
        print(f"  Engine:      {r.recommended_engine}")
        print(f"  Driver:      {r.primary_driver}")
        print(f"  Confidence:  {r.confidence}")
        print(f"  Camera rxn:  {r.requires_camera_reaction}")
        if r.causal_chain:
            print(f"  Chain:       {' → '.join(r.causal_chain)}")
        if r.failure_risks:
            print(f"  Risks:       {r.failure_risks}")
        if r.hybrid_parts:
            print(f"  Hybrid:      {r.hybrid_parts}")
