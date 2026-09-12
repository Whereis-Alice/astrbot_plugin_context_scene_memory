"""v3.5.0 低风险上游同步与并发修复的回归测试。"""

from __future__ import annotations

import asyncio
import re
import time
import unittest
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_v323_upgrade import _make_caption_plugin, plugin


PLUGIN_PATH = Path(__file__).resolve().parents[1] / "main.py"


class _AtEvent:
    def __init__(self, component: object) -> None:
        self.component = component
        self.message_obj = SimpleNamespace(message_id="at-test")
        self.message_str = ""
        self.unified_msg_origin = "umo:at-test"

    def get_sender_id(self) -> str:
        return "alice"

    def get_sender_name(self) -> str:
        return "Alice"

    def get_messages(self) -> list[object]:
        return [self.component]

    def get_message_outline(self) -> str:
        return ""


class AtAllTests(unittest.TestCase):
    def test_extract_message_checks_at_all_before_at(self) -> None:
        class DummyAt:
            def __init__(self, qq: str = "", name: str = "") -> None:
                self.qq = qq
                self.name = name

        class DummyAtAll(DummyAt):
            pass

        with patch.object(plugin, "At", DummyAt), patch.object(plugin, "AtAll", DummyAtAll):
            analyzer = plugin.SceneAnalyzer(bot_id="bot")
            record = analyzer.extract_message(
                _AtEvent(DummyAtAll(qq="all", name="全体成员"))
            )

        self.assertTrue(record.at_all)
        self.assertFalse(record.at_bot)

    def test_runtime_extractor_treats_at_qq_all_as_at_all(self) -> None:
        instance = object.__new__(plugin.Main)
        instance._analyzer = plugin.SceneAnalyzer(bot_id="bot")
        instance._image_caption_enabled = False
        instance._show_recent_images_allow_gif = False
        instance._record_structural_messages = True

        record = asyncio.run(
            instance._extract_message_with_caption(_AtEvent(plugin.At(qq="all", name="全体成员")))
        )

        self.assertTrue(record.at_all)
        self.assertFalse(record.at_bot)


class ImageCaptionCacheTests(unittest.TestCase):
    def _plugin(self) -> plugin.Main:
        instance = object.__new__(plugin.Main)
        instance._image_caption_cache = OrderedDict()
        instance._image_caption_cache_hits = 0
        instance._image_caption_cache_max = 100
        instance._image_caption_cache_ttl = 3600.0
        return instance

    def test_caption_cache_expires_after_ttl(self) -> None:
        instance = self._plugin()
        now = time.time()
        instance._image_caption_cache["fresh"] = ("新描述", now)
        instance._image_caption_cache["stale"] = ("旧描述", now - 3601)

        self.assertEqual(instance._get_cached_image_caption("fresh"), (True, "新描述"))
        self.assertEqual(instance._get_cached_image_caption("stale"), (False, None))
        self.assertNotIn("stale", instance._image_caption_cache)


class CancelledCaptionProvider:
    async def text_chat(self, *, prompt: str, image_urls: list[str]):
        raise asyncio.CancelledError


class CancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_caption_cancellation_is_not_cached_as_failure(self) -> None:
        provider = CancelledCaptionProvider()
        instance = _make_caption_plugin(provider)
        image_url = "https://example.com/image.png"

        with patch.object(plugin, "Provider", CancelledCaptionProvider):
            with self.assertRaises(asyncio.CancelledError):
                await instance._get_image_caption(image_url, "umo:test")

        cache_key = plugin.Main._image_caption_cache_key(image_url)
        self.assertNotIn(cache_key, instance._image_caption_cache)
        self.assertEqual(instance._image_caption_errors, 0)


class PublicRemoveApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_remove_apis_use_session_manager(self) -> None:
        instance = object.__new__(plugin.Main)
        instance._sessions = plugin.SessionManager(max_messages=10, max_sessions=10)
        await instance._sessions.add_message_async(
            "umo:test",
            plugin.MessageRecord(
                msg_id="m1",
                sender_id="bot",
                sender_name="[你]",
                content="Bot 回复",
                timestamp=1,
                is_bot=True,
            ),
        )
        await instance._sessions.add_message_async(
            "umo:test",
            plugin.MessageRecord(
                msg_id="m2",
                sender_id="user",
                sender_name="用户",
                content="用户消息",
                timestamp=2,
            ),
        )

        self.assertTrue(await instance.remove_message_async("umo:test", "m2"))
        self.assertFalse(instance._sessions.has_session("umo:test") is False)
        self.assertTrue(await instance.remove_last_bot_response_async("umo:test"))
        self.assertEqual(instance._sessions.get_message_count("umo:test"), 0)


class InferenceTests(unittest.TestCase):
    def test_bot_followup_window_is_twenty_seconds(self) -> None:
        analyzer = plugin.SceneAnalyzer(bot_id="bot")

        def message(timestamp: float, *, is_bot: bool = False) -> plugin.MessageRecord:
            return plugin.MessageRecord(
                msg_id=f"m{timestamp}",
                sender_id="bot" if is_bot else "user",
                sender_name="[你]" if is_bot else "用户",
                content="Bot 回复" if is_bot else "好的",
                timestamp=timestamp,
                is_bot=is_bot,
            )

        inside = message(81, is_bot=True)
        current = message(100)
        self.assertEqual(
            analyzer.infer_addressee(current, [inside], bot_replied_to="user"),
            plugin.InferenceReason.RULE_4_BOT_REPLIED,
        )
        self.assertEqual(current.talking_to, "bot")

        outside = message(80, is_bot=True)
        current = message(100)
        self.assertEqual(
            analyzer.infer_addressee(current, [outside], bot_replied_to="user"),
            plugin.InferenceReason.DEFAULT_GROUP,
        )
        self.assertEqual(current.talking_to, "group")

    def test_quick_follow_inference_is_removed(self) -> None:
        analyzer = plugin.SceneAnalyzer(bot_id="bot")
        previous = plugin.MessageRecord(
            msg_id="previous",
            sender_id="other",
            sender_name="其他人",
            content="对群说的话",
            timestamp=95,
            talking_to="group",
        )
        current = plugin.MessageRecord(
            msg_id="current",
            sender_id="user",
            sender_name="用户",
            content="我补充一下",
            timestamp=100,
        )

        self.assertEqual(
            analyzer.infer_addressee(current, [previous]),
            plugin.InferenceReason.DEFAULT_GROUP,
        )
        self.assertEqual(current.talking_to, "group")


class VersionTests(unittest.TestCase):
    def test_declared_versions_match(self) -> None:
        source = PLUGIN_PATH.read_text(encoding="utf-8")
        metadata = PLUGIN_PATH.with_name("metadata.yaml").read_text(encoding="utf-8")

        source_version = re.search(r"^Version:\s*(\S+)", source, re.MULTILINE)
        metadata_version = re.search(r"^version:\s*(\S+)", metadata, re.MULTILINE)

        self.assertIsNotNone(source_version)
        self.assertIsNotNone(metadata_version)
        self.assertEqual(source_version.group(1), metadata_version.group(1))


if __name__ == "__main__":
    unittest.main()
