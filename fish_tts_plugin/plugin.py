from __future__ import annotations

import datetime
import json
import logging
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_PATCHED = False
_ORIGINAL_TEXT_TO_SPEECH_TOOL = None
_ORIGINAL_CHECK_TTS_REQUIREMENTS = None

_DEFAULT_ENV_CANDIDATES = [
    "FISH_AUDIO_API_KEY",
    "FISH_API_KEY",
]

_PLATFORM_ENV_CANDIDATES = [
    "HERMES_SESSION_PLATFORM",
    "HERMES_PLATFORM",
    "PLATFORM",
]


def _import_base_tts_module():
    import tools.tts_tool as base_tts
    return base_tts


def _fish_api_key(fish_config: Dict[str, Any]) -> str:
    explicit = (fish_config.get("api_key") or "").strip()
    if explicit:
        return explicit

    preferred_env = (fish_config.get("api_key_env") or "").strip()
    candidates = [preferred_env] if preferred_env else []
    candidates.extend([x for x in _DEFAULT_ENV_CANDIDATES if x not in candidates])

    for env_name in candidates:
        value = (os.getenv(env_name) or "").strip()
        if value:
            return value
    return ""


def _detect_platform() -> str:
    for env_name in _PLATFORM_ENV_CANDIDATES:
        value = (os.getenv(env_name) or "").strip().lower()
        if value:
            return value
    return ""


def _should_prefer_voice_bubble(fish_config: Dict[str, Any]) -> bool:
    if "prefer_voice_bubble" in fish_config:
        return bool(fish_config.get("prefer_voice_bubble"))
    platform = _detect_platform()
    return platform in {"telegram", "signal"}


def _prepare_text_for_fish(text: str) -> str:
    text = text.strip()
    if not text:
        return text

    text = re.sub(r'```[\s\S]*?```', ' ', text)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'[#*_~]+', ' ', text)
    text = re.sub(r'\s*\n\s*', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text).strip()

    replacements = {
        ':)': ' улыбка ',
        ':(': ' грустно ',
        '—': ', ',
        '–': ', ',
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    if text and text[-1] not in '.!?…':
        text += '.'

    return text


def _fish_request_format(file_path: str, want_opus: bool, fish_config: Dict[str, Any]) -> str:
    if want_opus:
        return "opus"

    suffix = Path(file_path).suffix.lower()
    if suffix in {".ogg", ".opus"}:
        return "opus"
    if suffix == ".wav":
        return "wav"
    if suffix == ".pcm":
        return "pcm"

    configured = (fish_config.get("format") or "").strip().lower()
    if configured in {"opus", "ogg", "wav", "pcm", "mp3"}:
        return "opus" if configured == "ogg" else configured

    return "opus" if want_opus else "mp3"


def _resolve_output_path(base_tts, output_path: Optional[str], tts_config: Dict[str, Any]) -> tuple[str, bool]:
    fish_config = tts_config.get("fish", {})
    want_opus = _should_prefer_voice_bubble(fish_config)

    if output_path:
        path = Path(output_path).expanduser()
        if want_opus and path.suffix.lower() != ".ogg":
            path = path.with_suffix(".ogg")
    else:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(base_tts.DEFAULT_OUTPUT_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)

        configured_format = (fish_config.get("format") or "").strip().lower()
        if want_opus:
            suffix = ".ogg"
        elif configured_format == "wav":
            suffix = ".wav"
        elif configured_format == "pcm":
            suffix = ".pcm"
        else:
            suffix = ".mp3"
        path = out_dir / f"tts_{timestamp}{suffix}"

    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path), want_opus


def _style_defaults(style: str) -> Dict[str, Any]:
    presets: Dict[str, Dict[str, Any]] = {
        "conversational": {
            "latency": "normal",
            "chunk_length": 120,
            "temperature": 0.35,
            "top_p": 0.7,
            "repetition_penalty": 1.08,
            "condition_on_previous_chunks": True,
        },
        "soft": {
            "latency": "normal",
            "chunk_length": 110,
            "temperature": 0.28,
            "top_p": 0.68,
            "repetition_penalty": 1.1,
            "condition_on_previous_chunks": True,
        },
        "playful": {
            "latency": "normal",
            "chunk_length": 100,
            "temperature": 0.48,
            "top_p": 0.82,
            "repetition_penalty": 1.05,
            "condition_on_previous_chunks": True,
        },
        "assistant": {
            "latency": "normal",
            "chunk_length": 140,
            "temperature": 0.22,
            "top_p": 0.62,
            "repetition_penalty": 1.12,
            "condition_on_previous_chunks": True,
        },
        "cold": {
            "latency": "normal",
            "chunk_length": 150,
            "temperature": 0.18,
            "top_p": 0.55,
            "repetition_penalty": 1.15,
            "condition_on_previous_chunks": True,
        },
        "dramatic": {
            "latency": "normal",
            "chunk_length": 90,
            "temperature": 0.6,
            "top_p": 0.88,
            "repetition_penalty": 1.03,
            "condition_on_previous_chunks": True,
        },
    }
    return presets.get(style, presets["conversational"])


def _build_payload(text: str, file_path: str, fish_config: Dict[str, Any], want_opus: bool) -> Dict[str, Any]:
    request_format = _fish_request_format(file_path, want_opus, fish_config)

    style = (fish_config.get("style") or "conversational").strip().lower()
    preset = _style_defaults(style)
    default_latency = preset["latency"]
    default_chunk_length = preset["chunk_length"]
    default_temperature = preset["temperature"]
    default_top_p = preset["top_p"]
    default_repetition_penalty = preset["repetition_penalty"]
    default_condition = preset["condition_on_previous_chunks"]

    payload: Dict[str, Any] = {
        "text": text,
        "format": request_format,
        "latency": fish_config.get("latency", default_latency),
        "normalize": fish_config.get("normalize", True),
        "chunk_length": fish_config.get("chunk_length", default_chunk_length),
    }

    reference_id = fish_config.get("reference_id")
    if reference_id:
        payload["reference_id"] = reference_id

    prosody = fish_config.get("prosody") or {}
    if isinstance(prosody, dict) and prosody:
        payload["prosody"] = {
            "speed": prosody.get("speed", 1.0),
            "volume": prosody.get("volume", 0),
        }

    field_defaults = {
        "temperature": default_temperature,
        "top_p": default_top_p,
        "repetition_penalty": default_repetition_penalty,
        "condition_on_previous_chunks": default_condition,
    }

    for field in (
        "mp3_bitrate",
        "opus_bitrate",
        "temperature",
        "top_p",
        "max_new_tokens",
        "repetition_penalty",
        "min_chunk_length",
        "condition_on_previous_chunks",
        "early_stop_threshold",
        "sample_rate",
        "language",
    ):
        if field in fish_config:
            value = fish_config.get(field)
        else:
            value = field_defaults.get(field)
        if value is not None and value != "":
            payload[field] = value

    return payload


def _fish_headers(fish_config: Dict[str, Any], api_key: str) -> Dict[str, str]:
    model = (fish_config.get("model") or "s2-pro").strip()
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "model": model,
    }


def _generate_fish_audio(text: str, file_path: str, fish_config: Dict[str, Any], want_opus: bool) -> str:
    api_key = _fish_api_key(fish_config)
    if not api_key:
        raise ValueError(
            "Fish Audio API key not found. Set FISH_AUDIO_API_KEY or FISH_API_KEY, "
            "or configure tts.fish.api_key / tts.fish.api_key_env"
        )

    payload = _build_payload(text=text, file_path=file_path, fish_config=fish_config, want_opus=want_opus)
    body = json.dumps(payload).encode("utf-8")
    headers = _fish_headers(fish_config, api_key)
    timeout = int(fish_config.get("timeout", 120) or 120)
    endpoint = (fish_config.get("endpoint") or "https://api.fish.audio/v1/tts").strip()

    request = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            audio = response.read()
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", errors="ignore")[:500]
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"Fish Audio HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Fish Audio connection failed: {exc.reason}") from exc

    if not audio:
        raise RuntimeError("Fish Audio returned empty audio")

    with open(file_path, "wb") as handle:
        handle.write(audio)

    return file_path


def _fish_text_to_speech_tool(text: str, output_path: Optional[str] = None) -> str:
    base_tts = _import_base_tts_module()

    if not text or not text.strip():
        return json.dumps({"success": False, "error": "Text is required"}, ensure_ascii=False)

    if len(text) > base_tts.MAX_TEXT_LENGTH:
        logger.warning("Fish TTS text too long (%d chars), truncating to %d", len(text), base_tts.MAX_TEXT_LENGTH)
        text = text[: base_tts.MAX_TEXT_LENGTH]

    text = _prepare_text_for_fish(text)

    # Prepend emotion instruction if configured
    emotion_instruction = (fish_config.get("emotion_instruction") or "").strip()
    if emotion_instruction:
        text = f"{emotion_instruction} {text}"

    tts_config = base_tts._load_tts_config()
    provider = base_tts._get_provider(tts_config)
    if provider != "fish":
        return _ORIGINAL_TEXT_TO_SPEECH_TOOL(text=text, output_path=output_path)

    fish_config = tts_config.get("fish", {})
    file_path, want_opus = _resolve_output_path(base_tts, output_path, tts_config)

    try:
        _generate_fish_audio(text=text, file_path=file_path, fish_config=fish_config, want_opus=want_opus)

        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            return json.dumps({"success": False, "error": "Fish TTS generation produced no output"}, ensure_ascii=False)

        request_format = _fish_request_format(file_path, want_opus, fish_config)
        voice_compatible = request_format == "opus" and file_path.endswith(".ogg")
        media_tag = f"MEDIA:{file_path}"
        if voice_compatible:
            media_tag = f"[[audio_as_voice]]\n{media_tag}"

        return json.dumps(
            {
                "success": True,
                "file_path": file_path,
                "media_tag": media_tag,
                "provider": "fish",
                "voice_compatible": voice_compatible,
            },
            ensure_ascii=False,
        )
    except Exception as exc:
        error_msg = f"TTS generation failed (fish): {exc}"
        logger.error("%s", error_msg, exc_info=True)
        return json.dumps({"success": False, "error": error_msg}, ensure_ascii=False)


def _fish_check_tts_requirements() -> bool:
    try:
        base_tts = _import_base_tts_module()
        tts_config = base_tts._load_tts_config()
        provider = base_tts._get_provider(tts_config)
        if provider == "fish":
            return bool(_fish_api_key(tts_config.get("fish", {})))
    except Exception:
        pass

    if _ORIGINAL_CHECK_TTS_REQUIREMENTS is None:
        return False
    return _ORIGINAL_CHECK_TTS_REQUIREMENTS()


def _patch_base_tts() -> None:
    global _PATCHED, _ORIGINAL_TEXT_TO_SPEECH_TOOL, _ORIGINAL_CHECK_TTS_REQUIREMENTS
    if _PATCHED:
        return

    base_tts = _import_base_tts_module()
    _ORIGINAL_TEXT_TO_SPEECH_TOOL = base_tts.text_to_speech_tool
    _ORIGINAL_CHECK_TTS_REQUIREMENTS = getattr(base_tts, "check_tts_requirements", None)

    base_tts.text_to_speech_tool = _fish_text_to_speech_tool
    if _ORIGINAL_CHECK_TTS_REQUIREMENTS is not None:
        base_tts.check_tts_requirements = _fish_check_tts_requirements

    _PATCHED = True
    logger.info("Fish TTS plugin patched tools.tts_tool successfully")


def register(ctx) -> None:
    _patch_base_tts()
