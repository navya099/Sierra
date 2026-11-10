"""Stable S3-D regression fixtures; independent of editable production JSON."""
from pathlib import Path
from profile_presets.loader import load_preset as _load_preset

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "test_fixtures" / "profile_presets"

def load_preset(mode, horizontal_scale, vertical_scale):
    return _load_preset(mode, horizontal_scale, vertical_scale, root=FIXTURE_ROOT)
