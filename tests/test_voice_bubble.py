import unittest
from pathlib import Path
from types import SimpleNamespace

from fish_tts_plugin import plugin


class VoiceBubbleTests(unittest.TestCase):
    def test_prefer_voice_bubble_overrides_mp3_output_path(self):
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

        self.assertTrue(want_opus)
        self.assertTrue(file_path.endswith(".ogg"))
        self.assertEqual(plugin._fish_request_format(file_path, want_opus, tts_config["fish"]), "opus")

    def test_default_output_path_uses_ogg_when_voice_bubble_preferred(self):
        base_tts = SimpleNamespace(DEFAULT_OUTPUT_DIR="/tmp/hermes-audio")
        tts_config = {
            "fish": {
                "prefer_voice_bubble": True,
                "format": "mp3",
            }
        }

        file_path, want_opus = plugin._resolve_output_path(base_tts, None, tts_config)

        self.assertTrue(want_opus)
        self.assertEqual(Path(file_path).suffix, ".ogg")
        self.assertEqual(plugin._fish_request_format(file_path, want_opus, tts_config["fish"]), "opus")

    def test_prepare_text_injects_pause_and_laugh_tags(self):
        prepared = plugin._prepare_text_for_fish("Ну да... хаха!!")
        self.assertIn("[pause]", prepared)
        self.assertIn("[laugh]", prepared)

    def test_prepare_text_strips_telegram_sticker_markup(self):
        prepared = plugin._prepare_text_for_fish(
            "Ответь ![sticker](tg://emoji?id=123456) и <tg-emoji emoji-id=\"123\">🔥</tg-emoji> ок"
        )
        self.assertEqual(prepared, "Ответь и ок.")

    def test_prepare_text_strips_unicode_emoji(self):
        prepared = plugin._prepare_text_for_fish("Привет 🙂🔥 ок")
        self.assertEqual(prepared, "Привет ок.")

    def test_prepare_text_strips_ascii_emoticons_without_replacements(self):
        prepared = plugin._prepare_text_for_fish("Ну :) это xD вообще :-P странно")
        self.assertEqual(prepared, "Ну это вообще странно.")

    def test_prepare_text_with_custom_emotion_rules(self):
        """Custom regex→tag rules are applied before built-in rules."""
        custom_rules = [
            {"pattern": r"(кхе-хи)", "tag": "[giggle]"},
            {"pattern": r"(мдаа+|нуу+)", "tag": "[sigh]"},
        ]
        prepared = plugin._prepare_text_for_fish("Ну кхе-хи и мдаа... хаха!", custom_rules=custom_rules)
        self.assertIn("[giggle]", prepared)
        self.assertIn("[sigh]", prepared)
        # Built-in laugh rule still fires after custom, so [laugh] may appear too
        # Order: custom first, then built-in → we check both appear
        self.assertIn("[laugh]", prepared)

    def test_prepare_text_custom_rule_no_tag_on_empty_custom(self):
        """No custom_rules → same output as before."""
        prepared = plugin._prepare_text_for_fish("Ну да... хаха!!")
        self.assertIn("[pause]", prepared)
        self.assertIn("[laugh]", prepared)

    def test_inject_emotion_tags_custom_rules_order(self):
        """Custom rules run BEFORE built-in ones."""
        # If custom says "кхе → [giggle]" and built-in says "ха → [laugh]",
        # both should appear when text contains both patterns.
        custom_rules = [{"pattern": r"(кхе)", "tag": "[giggle]"}]
        text = "кхе ха"
        result = plugin._inject_emotion_tags(text, custom_rules=custom_rules)
        self.assertIn("[giggle]", result)
        self.assertIn("[laugh]", result)

    def test_inject_emotion_tags_bad_regex_skipped(self):
        """Bad regex in custom rules is skipped without crashing."""
        bad_rules = [{"pattern": r"[", "tag": "[boom]"}]  # unclosed char class
        # Should not raise, just log warning
        result = plugin._inject_emotion_tags("кхе ха", custom_rules=bad_rules)
        # Falls through to built-in laugh injection for "ха"
        self.assertIn("[laugh]", result)


if __name__ == "__main__":
    unittest.main()
