# hermes-fish-tts-plugin

Fish Audio TTS provider plugin for Hermes Agent.

This plugin adds `tts.provider: fish` to Hermes without patching Hermes core files. It hooks into the built-in TTS tool at runtime, keeps the default providers intact, and only takes over when Fish is selected in config.

## Features

- Adds Fish Audio as a Hermes TTS provider
- No core-file edits inside Hermes
- Preserves built-in providers and falls back cleanly when Fish is not selected
- Supports Hermes text-to-speech tool output and `/voice` playback flows
- Optimizes Telegram voice-bubble delivery by forcing Opus-in-OGG when desired
- Supports style presets for S2-Pro
- Supports prompt-level emotional instructions
- Auto-injects expressive tags from punctuation and laugh/sigh patterns
- Strips Telegram sticker/emoji markup, Unicode emoji, and ASCII emoticons before sending text to Fish

## How it works

The plugin monkey-patches `tools.tts_tool.text_to_speech_tool` during plugin registration.

Behavior:

- If `tts.provider` is not `fish`, Hermes continues using the original TTS implementation.
- If `tts.provider` is `fish`, the plugin builds a Fish Audio request, generates the audio file, and returns a Hermes-compatible response payload.
- When `prefer_voice_bubble: true` is enabled, the plugin overrides a forced `.mp3` output path and keeps the final output as `.ogg` so Telegram sends it as a native voice bubble.

## Requirements

- Python 3.10+
- Hermes Agent with plugin loading enabled
- A Fish Audio API key available through environment variables or config
- A valid Fish reference voice or reference configuration on your side

## Installation

### Install from a local path

```bash
pip install /path/to/hermes-fish-tts-plugin
```

### Reinstall after local edits

```bash
pip install --force-reinstall /path/to/hermes-fish-tts-plugin
```

## Hermes configuration

Minimal example:

```yaml
tts:
  provider: fish
  fish:
    model: s2-pro
    reference_id: your_fish_reference_id_here
    language: ru
    style: playful
    prefer_voice_bubble: true
    api_key_env: FISH_AUDIO_API_KEY
```

Fuller example:

```yaml
tts:
  provider: fish
  fish:
    model: s2-pro
    reference_id: your_fish_reference_id_here
    language: ru
    style: conversational
    prefer_voice_bubble: true
    latency: normal
    format: mp3
    api_key_env: FISH_AUDIO_API_KEY
    chunk_length: 120
    temperature: 0.35
    top_p: 0.7
    repetition_penalty: 1.08
    condition_on_previous_chunks: true
    prosody:
      speed: 0.94
      volume: 0
```

Environment variable:

```bash
export FISH_AUDIO_API_KEY=***
```

Accepted key environment variables by default:
- `FISH_AUDIO_API_KEY`
- `FISH_API_KEY`

You can also set:
- `tts.fish.api_key_env` to choose a custom env var name
- `tts.fish.api_key` for direct config-based injection, though env vars are strongly preferred

## Configuration reference

### Top-level

- `tts.provider`: must be `fish`

### `tts.fish`

- `model`: Fish model name, default `s2-pro`
- `reference_id`: Fish reference voice identifier
- `language`: language hint passed to Fish
- `style`: one of the built-in style presets
- `prefer_voice_bubble`: prefer Telegram/Signal-style voice delivery
- `api_key_env`: env var name to read the API key from
- `api_key`: direct API key override
- `endpoint`: custom Fish endpoint, default `https://api.fish.audio/v1/tts`
- `timeout`: request timeout in seconds
- `format`: desired output format when voice-bubble mode is not forcing Opus
- `latency`: Fish latency mode
- `normalize`: enable or disable normalization
- `chunk_length`: text chunk length for generation
- `temperature`, `top_p`, `repetition_penalty`: sampling controls
- `condition_on_previous_chunks`: smoother multi-chunk continuation
- `min_chunk_length`, `max_new_tokens`, `early_stop_threshold`, `sample_rate`: optional advanced generation fields
- `mp3_bitrate`, `opus_bitrate`: optional output bitrate controls
- `prosody.speed`, `prosody.volume`: prosody controls
- `emotion_instruction`: text prepended to every utterance before generation

## Style presets

Available values for `tts.fish.style`:

- `conversational` — balanced default for normal chat
- `soft` — calmer and gentler delivery
- `playful` — more lively and expressive
- `assistant` — restrained neutral assistant tone
- `cold` — flatter and more detached delivery
- `dramatic` — stronger expressive swing and sharper emphasis

The style preset fills defaults for fields like chunk length, temperature, top-p, repetition penalty, and chunk conditioning. Any explicit config value still wins.

## Emotional instructions and tags

The plugin supports three emotion mechanisms:

1. `tts.fish.emotion_instruction`
   - optional static prefix prepended to every utterance right before the Fish request
   - useful when you want one persistent delivery mode for the whole voice

2. Built-in auto-tag injection inside `_inject_emotion_tags()`
   - runs automatically during `_prepare_text_for_fish()`
   - converts punctuation / laugh / sigh patterns in the actual message into Fish tags
   - always active, no config needed

3. Custom user-defined regex-to-tag rules (`tts.fish.emotion_tags`)
   - enabled via `emotion_tags.enabled: true`
   - user provides a list of `pattern` / `tag` pairs
   - applied first, before built-in rules

Example for a static global instruction:

```yaml
tts:
  provider: fish
  fish:
    style: playful
    emotion_instruction: "[sarcastic]"
```

Example with custom emotion tag rules:

```yaml
tts:
  provider: fish
  fish:
    emotion_tags:
      enabled: true
      custom:
        - pattern: "(кхе-хи)"
          tag: "[giggle]"
        - pattern: "(мда+|нуу+)"
          tag: "[sigh]"
```

Custom rules are applied before built-in ones. Built-in rules still fire for any patterns they match, so you can extend — not replace — the defaults.

Common tags you can experiment with in `emotion_instruction` or directly in text:
- `[laugh]`
- `[sigh]`
- `[chuckle]`
- `[pause]`
- `[emphasis]`
- `[sarcastic]`
- `[whisper]`
- `[excited]`
- `[sad]`
- `[angry]`
- `[inhale]`
- `[exhale]`
- `[tsk]`
- `[giggle]`
- `[groan]`

You can also chain them:

```text
[excited] Невероятно! [laugh] Ха!
```

## Auto-injected expression tags

Before sending text to Fish, the plugin lightly cleans Hermes output and injects a few expressive tags based on hardcoded regex rules in `_inject_emotion_tags()`:

- ellipsis (`...` or `…`) → `[pause]`
- repeated exclamation marks → `[excited]` (more `!` = more intense)
- laugh patterns (`ха`, `хаха`, `хех`, `хихи`, etc.) → `[laugh]`
- sigh patterns (`ох`, `оха`, `охау`, etc. when used as sigh-like interjections) → `[sigh]`
- `вздох` (sigh word mid-sentence) → `[sigh] вздох`

This is intentionally lightweight, not a full linguistic engine.

## Text preprocessing

The `_prepare_text_for_fish` function sanitizes text before it reaches Fish Audio:

### What is stripped

- **Telegram sticker markup**: `<tg-emoji>`, `![name](tg://emoji?id=...)`, `![name](url)`
- **Unicode emoji**: all pictographs, symbols, flags, and misc emoji characters
- **ASCII emoticons**: `:)`, `:(` `:D`, `xD`, `:-P`, `<3`, and variants
- **Markdown**: code blocks, link syntax, inline code, emphasis markers (`#*_~`)
- **URLs**: `https://...` and `http://...` links
- **Em dashes / en dashes**: replaced with commas

### What is preserved

- Emotion tags in brackets like `[laugh]`, `[sigh]`, `[excited]`, `[pause]` — these survive the cleaning because they are injected *before* markdown stripping
- Cyrillic and Latin text, punctuation, numbers

### Order of operations

1. Strip Telegram sticker markup
2. Strip Unicode emoji characters
3. Strip ASCII emoticons
4. Inject auto-emotion tags (laugh, sigh, excited, pause)
5. Remove markdown (code blocks, links, inline code, emphasis)
6. Normalize whitespace and dashes
7. Ensure sentence-ending punctuation

## Telegram voice bubbles

Hermes Telegram delivery decides whether audio becomes a voice bubble mainly from the file extension.

This plugin therefore does two important things when `prefer_voice_bubble: true` is enabled:

- requests Fish `opus`
- ensures the saved file extension is `.ogg`

That means voice-bubble preference wins even if Hermes passed an `.mp3` output path or your config still says `format: mp3`.

## Security notes

This repository should not contain real API keys, tokens, or personal secrets.

Safe practice:
- keep your Fish API key in environment variables
- keep private voice identifiers out of public examples if you treat them as sensitive
- avoid committing generated audio, logs, or local configs with secrets

A sanitized example config is provided in `examples/config.snippet.yaml`.

## Repository layout

```
fish_tts_plugin/
  __init__.py
  plugin.py        # main plugin logic
  plugin.yaml      # plugin metadata
examples/
  config.snippet.yaml
tests/
  test_voice_bubble.py
```

## Development

### Run a quick syntax check

```bash
python -m py_compile fish_tts_plugin/plugin.py
```

### Run tests with pytest

```bash
pytest -q
```

If `pytest` is unavailable in your environment, install it first or adapt the tests to your preferred runner.

## Limitations

- The plugin currently patches Hermes TTS internals rather than using a first-class provider API.
- Fish request fields may need updates if the upstream Fish API changes.
- Advanced emotional control quality depends on the model and the selected reference voice.

## Troubleshooting

### Hermes still uses the default voice

Check that:
- the plugin is installed into the same Python environment Hermes uses
- Hermes plugin loading is enabled
- `tts.provider: fish` is set
- the API key env var is present in the runtime environment

### Voice bubble is sent as normal audio

Check that:
- `prefer_voice_bubble: true` is enabled
- the final output path ends in `.ogg`
- the generated request format is Opus-compatible

### Fish request fails

Check that:
- your API key is valid
- your endpoint is correct
- your `reference_id` exists and belongs to your Fish setup
- your model name is supported by the account and endpoint you are using

## License

MIT
