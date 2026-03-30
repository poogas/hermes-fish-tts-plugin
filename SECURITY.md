# Security notes

## Secret handling

This repository is intended to stay free of real credentials.

Recommended practice:
- store Fish API keys in environment variables
- avoid committing local runtime config files with secrets
- avoid committing generated audio, logs, dumps, or debug payloads
- sanitize `reference_id` values in public examples unless you explicitly want them public

Supported env vars by default:
- `FISH_AUDIO_API_KEY`
- `FISH_API_KEY`

You may also point the plugin at a custom env var with `tts.fish.api_key_env`.

## Reporting

If you discover a credential leak or a bug with security impact, rotate the affected credentials first and then report the issue privately before publishing details.
