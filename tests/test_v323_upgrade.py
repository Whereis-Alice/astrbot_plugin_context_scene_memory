"""v3.2.4 的回归测试，不依赖已安装的 AstrBot。"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import os
import sys
import types
import unittest
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PLUGIN_PATH = Path(__file__).resolve().parents[1] / "main.py"


def _decorator(*_args, **_kwargs):
    def wrap(func):
        return func

    return wrap


def _install_astrbot_stubs() -> None:
    """让 CI 在未安装 AstrBot 时仍能导入插件模块。"""
    astrbot_mod = types.ModuleType("astrbot")
    api_mod = types.ModuleType("astrbot.api")
    event_mod = types.ModuleType("astrbot.api.event")
    components_mod = types.ModuleType("astrbot.api.message_components")
    provider_mod = types.ModuleType("astrbot.api.provider")
    core_mod = types.ModuleType("astrbot.core")
    agent_mod = types.ModuleType("astrbot.core.agent")
    message_mod = types.ModuleType("astrbot.core.agent.message")

    class Logger:
        def debug(self, *_args, **_kwargs):
            pass

        def error(self, *_args, **_kwargs):
            pass

        def info(self, *_args, **_kwargs):
            pass

        def warning(self, *_args, **_kwargs):
            pass

    class Star:
        def __init__(self, context):
            self.context = context

    class PlatformAdapterType:
        ALL = object()

    class Plain:
        def __init__(self, text: str = ""):
            self.text = text

    class Image:
        def __init__(self, url: str = "", file: str = ""):
            self.url = url
            self.file = file

    class At:
        def __init__(self, qq: str = "", name: str = ""):
            self.qq = qq
            self.name = name

    class AtAll:
        pass

    class Reply:
        def __init__(self, sender_id: str = ""):
            self.sender_id = sender_id

    class Provider:
        pass

    class ProviderRequest:
        pass

    class TextPart:
        def __init__(self, text: str):
            self.text = text

        def mark_as_temp(self):
            return self

    astrbot_mod.logger = Logger()
    astrbot_mod.api = api_mod
    astrbot_mod.core = core_mod
    api_mod.star = SimpleNamespace(Star=Star, Context=object)
    api_mod.event = event_mod
    api_mod.message_components = components_mod
    api_mod.provider = provider_mod
    event_mod.AstrMessageEvent = object
    event_mod.filter = SimpleNamespace(
        PlatformAdapterType=PlatformAdapterType,
        after_message_sent=_decorator,
        on_llm_request=_decorator,
        on_llm_response=_decorator,
        platform_adapter_type=_decorator,
    )
    components_mod.At = At
    components_mod.AtAll = AtAll
    components_mod.Image = Image
    components_mod.Plain = Plain
    components_mod.Reply = Reply
    provider_mod.LLMResponse = object
    provider_mod.Provider = Provider
    provider_mod.ProviderRequest = ProviderRequest
    core_mod.agent = agent_mod
    agent_mod.message = message_mod
    message_mod.TextPart = TextPart

    sys.modules.update(
        {
            "astrbot": astrbot_mod,
            "astrbot.api": api_mod,
            "astrbot.api.event": event_mod,
            "astrbot.api.message_components": components_mod,
            "astrbot.api.provider": provider_mod,
            "astrbot.core": core_mod,
            "astrbot.core.agent": agent_mod,
            "astrbot.core.agent.message": message_mod,
        }
    )


if importlib.util.find_spec("astrbot") is None:
    _install_astrbot_stubs()

spec = importlib.util.spec_from_file_location("context_scene_memory_main", PLUGIN_PATH)
assert spec is not None and spec.loader is not None
plugin = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = plugin
spec.loader.exec_module(plugin)


class CaptionProvider:
    def __init__(self, completion_text: str):
        self.completion_text = completion_text
        self.calls = 0
        self.file_seen = False
        self.image_ref = ""

    async def text_chat(self, *, prompt: str, image_urls: list[str]):
        self.calls += 1
        self.image_ref = image_urls[0]
        self.file_seen = os.path.isfile(self.image_ref)
        return SimpleNamespace(completion_text=self.completion_text)


class CaptionContext:
    def __init__(self, provider: CaptionProvider):
        self.provider = provider
        self.last_umo = None

    def get_using_provider(self, umo):
        self.last_umo = umo
        return self.provider


def _make_caption_plugin(provider: CaptionProvider):
    instance = object.__new__(plugin.Main)
    instance._context = CaptionContext(provider)
    instance._image_caption_cache = OrderedDict()
    instance._image_caption_cache_hits = 0
    instance._image_caption_cache_max = 100
    instance._image_caption_count = 0
    instance._image_caption_enabled = True
    instance._image_caption_errors = 0
    instance._image_caption_prompt = "请描述图片"
    instance._image_caption_provider_id = ""
    instance._image_caption_semaphore = asyncio.Semaphore(1)
    instance._image_caption_timeout = 1.0
    return instance


class CommandEvent:
    def __init__(
        self,
        text: str,
        *,
        is_at_or_wake_command: bool = True,
        extras: dict[str, object] | None = None,
    ) -> None:
        self.text = text
        self.is_at_or_wake_command = is_at_or_wake_command
        self.extras = extras or {}
        self.unified_msg_origin = "umo:command-test"

    def get_message_str(self) -> str:
        return self.text

    def get_extra(self, key: str, default=None):
        return self.extras.get(key, default)


class SessionResetTests(unittest.IsolatedAsyncioTestCase):
    def _make_plugin(self):
        instance = object.__new__(plugin.Main)
        instance._sessions = plugin.SessionManager(max_messages=10, max_sessions=10)
        instance._enabled = True
        instance._group_only = False
        return instance

    def test_extracts_native_reset_and_new_commands(self):
        instance = self._make_plugin()

        self.assertEqual(
            instance._session_reset_command(CommandEvent("/reset extra")),
            "reset",
        )
        self.assertEqual(
            instance._session_reset_command(CommandEvent(".new")),
            "new",
        )
        self.assertEqual(
            instance._session_reset_command(CommandEvent("/reset", is_at_or_wake_command=False)),
            "",
        )

    def test_extracts_cmdmask_target_instead_of_alias_text(self):
        instance = self._make_plugin()
        event = CommandEvent(
            "/wipe",
            extras={
                plugin.ExtraKeys.CMDMASK_APPLIED: True,
                plugin.ExtraKeys.CMDMASK_TARGET: "/reset",
            },
        )

        self.assertEqual(instance._session_reset_command(event), "reset")

    async def test_reset_command_is_cleared_before_recording(self):
        instance = self._make_plugin()
        await instance._sessions.add_message_async(
            "umo:command-test",
            plugin.MessageRecord(
                msg_id="old",
                sender_id="user",
                sender_name="用户",
                content="旧上下文",
                timestamp=1,
            ),
        )

        await instance.on_message(CommandEvent("/reset"))

        self.assertFalse(instance._sessions.has_session("umo:command-test"))

    async def test_after_message_sent_accepts_new_and_legacy_markers(self):
        instance = self._make_plugin()
        for marker in (
            plugin.ExtraKeys.SESSION_CLEAN_GROUP,
            plugin.ExtraKeys.SESSION_CLEAN_LEGACY,
        ):
            await instance._sessions.add_message_async(
                "umo:command-test",
                plugin.MessageRecord(
                    msg_id=marker,
                    sender_id="user",
                    sender_name="用户",
                    content="旧上下文",
                    timestamp=1,
                ),
            )
            await instance.after_message_sent(CommandEvent("", extras={marker: True}))
            self.assertFalse(instance._sessions.has_session("umo:command-test"))


def _png_data_uri() -> str:
    raw = b"\x89PNG\r\n\x1a\nscene-memory-test"
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


class ImageCaptionDataUriTests(unittest.IsolatedAsyncioTestCase):
    async def test_data_uri_uses_temporary_local_path_and_keeps_umo_provider(self):
        provider = CaptionProvider("一张测试图片")
        instance = _make_caption_plugin(provider)
        data_uri = _png_data_uri()

        with patch.object(plugin, "Provider", CaptionProvider):
            result = await instance._get_image_caption(data_uri, "umo:test")

        self.assertEqual(result, "一张测试图片")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(instance._context.last_umo, "umo:test")
        self.assertTrue(provider.file_seen)
        self.assertLess(len(provider.image_ref), 300)
        self.assertFalse(os.path.exists(provider.image_ref))

        cache_key = plugin.Main._image_caption_cache_key(data_uri)
        self.assertTrue(cache_key.startswith("data:sha256:"))
        self.assertLess(len(cache_key), 100)
        self.assertIn(cache_key, instance._image_caption_cache)
        self.assertNotIn(data_uri, instance._image_caption_cache)

    async def test_empty_caption_is_cached_as_failure_sentinel(self):
        provider = CaptionProvider("")
        instance = _make_caption_plugin(provider)
        data_uri = _png_data_uri()

        with patch.object(plugin, "Provider", CaptionProvider):
            first = await instance._get_image_caption(data_uri, "umo:test")
            second = await instance._get_image_caption(data_uri, "umo:test")

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(
            instance._image_caption_cache[plugin.Main._image_caption_cache_key(data_uri)],
            "",
        )


class InferenceSafetyTests(unittest.TestCase):
    def test_strict_mode_only_changes_active_or_unknown_bot_inference(self):
        instance = object.__new__(plugin.Main)
        instance._strict_mode = True
        current = plugin.MessageRecord(
            msg_id="m1",
            sender_id="user",
            sender_name="用户",
            content="嗯",
            timestamp=1,
            talking_to="bot",
            talking_to_name="你",
        )

        changed = instance._apply_strict_mode(plugin.TRIGGER_ACTIVE, current)

        self.assertTrue(changed)
        self.assertEqual(current.talking_to, "group")
        self.assertEqual(current.talking_to_name, "群聊")

        explicit = plugin.MessageRecord(
            msg_id="m2",
            sender_id="user",
            sender_name="用户",
            content="Alice",
            timestamp=1,
            talking_to="bot",
            talking_to_name="Alice",
        )
        changed = instance._apply_strict_mode(plugin.TRIGGER_MENTION, explicit)

        self.assertFalse(changed)
        self.assertEqual(explicit.talking_to, "bot")

    def test_rule_4_interruption_guard_uses_current_message_time(self):
        analyzer = plugin.SceneAnalyzer(bot_id="bot")
        previous_user_message = plugin.MessageRecord(
            msg_id="p1",
            sender_id="other",
            sender_name="其他人",
            content="问你一件事",
            timestamp=0,
            talking_to="user",
            talking_to_name="用户",
        )
        bot_reply = plugin.MessageRecord(
            msg_id="b1",
            sender_id="bot",
            sender_name="Bot",
            content="我是插话",
            timestamp=50,
            is_bot=True,
            talking_to="user",
            talking_to_name="用户",
        )
        current = plugin.MessageRecord(
            msg_id="m3",
            sender_id="user",
            sender_name="用户",
            content="好的",
            timestamp=80,
        )

        reason = analyzer.infer_addressee(
            current,
            [previous_user_message, bot_reply],
            bot_replied_to="user",
        )

        self.assertEqual(reason, plugin.InferenceReason.RULE_4_BOT_REPLIED)
        self.assertEqual(current.talking_to, "bot")
