from pathlib import Path
from types import SimpleNamespace

from fish_tts_plugin import plugin


def test_prefer_voice_bubble_overrides_mp3_output_path():
    base_tts = SimpleNamespace(DEFAULT_OUTPUT_DIR="/tmp/hermes-audio")
    tts_config = {
        "fish": {
            "prefer_voice_bubble": True,
            "format": "mp3",
        }
    }

    file_path, want_opus = plugin._resolve_output_path(
        base_tts,
        "/tmp/hermes_voice/reply.mp3",
        tts_config,
    )

    assert want_opus is True
    assert file_path.endswith(".ogg")
    assert plugin._fish_request_format(file_path, want_opus, tts_config["fish"]) == "opus"


def test_default_output_path_uses_ogg_when_voice_bubble_preferred():
    base_tts = SimpleNamespace(DEFAULT_OUTPUT_DIR="/tmp/hermes-audio")
    tts_config = {
        "fish": {
            "prefer_voice_bubble": True,
            "format": "mp3",
        }
    }

    file_path, want_opus = plugin._resolve_output_path(base_tts, None, tts_config)

    assert want_opus is True
    assert Path(file_path).suffix == ".ogg"
    assert plugin._fish_request_format(file_path, want_opus, tts_config["fish"]) == "opus"