"""
shot_schema.py — Shot schema constants

Used by scene_schema.py for validation.
"""

# Shot required/optional field sets (used in scene_schema validation)
SHOT_REQUIRED = {
    "shot_id",
    "input_image",
    "output_file",
    "preset",
    "duration_sec",
}

SHOT_OPTIONAL = {
    "fps",
    "aspect_ratio",
    "camera_override",
    "camera_intensity",
    "caption_text",
    "dialogue",
    "note",
    "risk_level",
    "shot_type",
}
