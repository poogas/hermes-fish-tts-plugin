# Hermes Fish TTS Plugin

Adds Fish Audio as a `tts.provider: fish` option for Hermes Agent without editing Hermes core files.

## What it does

- Monkey-patches `tools.tts_tool.text_to_speech_tool`
- Keeps all built-in providers working unchanged
- Activates only when `tts.provider: fish`
- Supports both tool-based TTS and CLI `/voice` playback
- Can be installed as a pip plugin via Hermes plugin entry points

## Install

```bash
pip install /workspace/hermes-fish-tts-plugin
```

## Config

```yaml
tts:
  provider: fish
  fish:
    model: s2-pro
    reference_id: 59d43ace8c78460b9adfd204de49c40a
    language: ru
    style: conversational
    prefer_voice_bubble: true
    latency: normal
    format: mp3
    api_key_env: FISH_AUDIO_API_KEY
    prosody:
      speed: 0.94
      volume: 0
```

Environment variable:

```bash
export FISH_AUDIO_API_KEY=your_key_here
```

Accepted key env names by default:
- `FISH_AUDIO_API_KEY`
- `FISH_API_KEY`

## Voice styles

Available `tts.fish.style` presets:
- `conversational` — balanced default, natural chat rhythm
- `soft` — calmer, gentler, slightly more intimate
- `playful` — more lively and expressive
- `assistant` — neutral, clean, restrained
- `cold` — flatter, more detached delivery
- `dramatic` — stronger emotional swing and sharper phrasing

You can still override any low-level parameter manually in config.

## Telegram voice bubbles

For Telegram delivery, the plugin requests Fish `opus` output and stores it as `.ogg`, so Hermes can send it as a native voice bubble.
