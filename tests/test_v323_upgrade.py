"""分叉版上下文与引用归因的回归测试，不依赖已安装的 AstrBot。"""

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
        def __init__(
            self,
            sender_id: str = "",
            sender_nickname: str = "",
            id: str = "",
            message_str: str = "",
            time: int = 0,
        ):
            self.sender_id = sender_id
            self.sender_nickname = sender_nickname
            self.id = id
            self.message_str = message_str
            self.time = time

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


class ImageEvidenceTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _event(
        components: list[object],
        *,
        message_str: str = "",
        outline: str = "",
    ) -> object:
        return SimpleNamespace(
            message_str=message_str,
            message_obj=SimpleNamespace(message_id="media-test", message_str=message_str),
            unified_msg_origin="umo:media-test",
            get_sender_id=lambda: "user",
            get_sender_name=lambda: "用户",
            get_messages=lambda: components,
            get_message_outline=lambda: outline,
            get_message_str=lambda: message_str,
            get_extra=lambda _key, default=None: default,
        )

    @staticmethod
    def _main() -> object:
        instance = object.__new__(plugin.Main)
        instance._analyzer = SimpleNamespace(bot_id="bot")
        instance._image_caption_enabled = False
        instance._show_recent_images_allow_gif = False
        instance._record_structural_messages = True
        return instance

    async def test_plain_image_placeholder_is_not_media_evidence(self):
        instance = self._main()
        record = await instance._extract_message_with_caption(
            self._event([plugin.Plain("[图片] 只是文字")], message_str="[图片] 只是文字")
        )

        self.assertFalse(record.has_image)
        self.assertEqual(record.image_count, 0)

    async def test_outline_only_placeholder_is_not_media_evidence(self):
        instance = self._main()
        record = await instance._extract_message_with_caption(
            self._event([], outline="[图片]")
        )

        self.assertFalse(record.has_image)
        self.assertEqual(record.image_count, 0)

    async def test_scene_marks_literal_image_text_and_keeps_it_out_of_images(self):
        literal = plugin.MessageRecord(
            msg_id="literal",
            sender_id="user",
            sender_name="用户",
            content="[图片] 只是普通文字",
            timestamp=1,
        )
        current = plugin.MessageRecord(
            msg_id="current",
            sender_id="other",
            sender_name="其他人",
            content="我看到了",
            timestamp=2,
        )

        scene = plugin.SceneGenerator().generate(
            trigger_type=plugin.TRIGGER_AT,
            trigger_desc="当前用户明确呼叫你",
            current=current,
            flow=[literal, current],
            bot_status={},
            participants=[],
            image_flow=[literal],
        )

        self.assertIn('image_token_is_text="true"', scene)
        self.assertIn("不要据此描述、分析、搜索或声称看到了图片", scene)
        self.assertNotIn("<recent_images>", scene)

    async def test_real_image_component_still_enters_recent_images(self):
        image = plugin.MessageRecord(
            msg_id="image",
            sender_id="user",
            sender_name="用户",
            content="[图片]",
            timestamp=1,
            has_image=True,
            image_count=1,
        )
        current = plugin.MessageRecord(
            msg_id="current",
            sender_id="other",
            sender_name="其他人",
            content="我看到了",
            timestamp=2,
        )

        scene = plugin.SceneGenerator().generate(
            trigger_type=plugin.TRIGGER_AT,
            trigger_desc="当前用户明确呼叫你",
            current=current,
            flow=[image, current],
            bot_status={},
            participants=[],
            image_flow=[image],
        )

        self.assertIn("<recent_images>", scene)
        self.assertIn('media="image"', scene)
        self.assertNotIn('image_token_is_text="true"', scene)


class SpeakerAttributionTests(unittest.TestCase):
    @staticmethod
    def _message(
        msg_id: str,
        sender_id: str,
        content: str,
        **kwargs,
    ):
        return plugin.MessageRecord(
            msg_id=msg_id,
            sender_id=sender_id,
            sender_name="同名用户",
            content=content,
            timestamp=1,
            **kwargs,
        )

    def test_scene_keeps_same_nickname_users_separate_by_platform_id(self):
        other = self._message(
            "other",
            "10001",
            "这是另一位同名用户说过的话",
            has_image=True,
            image_count=1,
        )
        voice = self._message(
            "voice",
            "30003",
            "[语音转写] 这是第三位同名用户的语音",
        )
        current = self._message("current", "20002", "这是当前用户的消息")
        flow = [other, voice, current]

        scene = plugin.SceneGenerator().generate(
            trigger_type=plugin.TRIGGER_AT,
            trigger_desc="当前用户明确呼叫你",
            current=current,
            flow=flow,
            bot_status={},
            participants=plugin._unique_speaker_labels(
                flow,
                plugin.SPEAKER_IDENTITY_PLATFORM_ID,
            ),
            summary="没有身份标签的旧摘要",
            speaker_identity_mode=plugin.SPEAKER_IDENTITY_PLATFORM_ID,
            speaker_attribution_guard=True,
            speaker_attribution_template=plugin.DEFAULT_SPEAKER_ATTRIBUTION_TEMPLATE,
            image_flow=[other],
            voice_flow=[voice],
        )

        self.assertIn('<current_message speaker="user:20002">', scene)
        self.assertIn('current_speaker="user:20002"', scene)
        self.assertIn('current_sender="同名用户 [user:20002]"', scene)
        self.assertIn('speaker="user:10001"', scene)
        self.assertIn('speaker="user:30003"', scene)
        self.assertIn('sender="同名用户 [user:10001]"', scene)
        self.assertIn('sender="同名用户 [user:30003]"', scene)
        self.assertIn("严禁把其他用户说过的话", scene)
        self.assertIn("没有身份标签的历史仅可作为背景", scene)

    def test_bot_reply_target_keeps_platform_identity_for_same_nickname_users(self):
        previous = self._message("previous", "10001", "这是第一位同名用户的问题")
        bot_reply = plugin.MessageRecord(
            msg_id="bot",
            sender_id="bot",
            sender_name="[你]",
            content="这是给第一位同名用户的回答",
            timestamp=2,
            is_bot=True,
            talking_to="10001",
            talking_to_name="同名用户",
        )
        current = self._message("current", "20002", "这是第二位同名用户的追问")

        scene = plugin.SceneGenerator().generate(
            trigger_type=plugin.TRIGGER_AT,
            trigger_desc="当前用户明确呼叫你",
            current=current,
            flow=[previous, bot_reply, current],
            bot_status={},
            participants=plugin._unique_speaker_labels(
                [previous, current],
                plugin.SPEAKER_IDENTITY_PLATFORM_ID,
            ),
            speaker_identity_mode=plugin.SPEAKER_IDENTITY_PLATFORM_ID,
        )

        self.assertIn('speaker="bot:self"', scene)
        self.assertIn('talking_to="同名用户 [user:10001]"', scene)
        self.assertNotIn('talking_to="同名用户 [user:20002]"', scene)

    def test_masked_mode_is_stable_without_exposing_platform_id(self):
        first = self._message("first", "10001", "第一条")
        same_person = self._message("same", "10001", "第二条")
        other = self._message("other", "20002", "第三条")

        first_key = plugin._speaker_identity_key(first, plugin.SPEAKER_IDENTITY_MASKED)
        self.assertEqual(
            first_key,
            plugin._speaker_identity_key(same_person, plugin.SPEAKER_IDENTITY_MASKED),
        )
        self.assertNotEqual(
            first_key,
            plugin._speaker_identity_key(other, plugin.SPEAKER_IDENTITY_MASKED),
        )
        self.assertNotIn("10001", first_key)
        self.assertTrue(first_key.startswith("user:"))

    def test_summary_and_public_context_keep_speaker_identity(self):
        first = self._message("first", "10001", "另一位用户的观点")
        bot_reply = plugin.MessageRecord(
            msg_id="bot",
            sender_id="bot",
            sender_name="[你]",
            content="这是给第一位用户的回答",
            timestamp=2,
            is_bot=True,
            talking_to="10001",
            talking_to_name="同名用户",
        )
        current = self._message("current", "20002", "当前用户的观点")
        instance = object.__new__(plugin.Main)
        instance._speaker_identity_mode = plugin.SPEAKER_IDENTITY_PLATFORM_ID
        instance._sessions = plugin.SessionManager(max_messages=10, max_sessions=10)
        instance._sessions.add_message("umo:identity", first)
        instance._sessions.add_message("umo:identity", bot_reply)
        instance._sessions.add_message("umo:identity", current)

        summary_input = instance._build_summary_input(
            [first, bot_reply, current], max_chars=1000
        )
        recent = instance.get_recent_messages("umo:identity")
        formatted = instance.get_formatted_context("umo:identity")

        self.assertIn("同名用户 [user:10001]", summary_input)
        self.assertIn("同名用户 [user:20002]", summary_input)
        self.assertEqual(recent[0]["sender_id"], "10001")
        self.assertEqual(recent[0]["speaker_id"], "user:10001")
        self.assertEqual(recent[1]["talking_to_id"], "10001")
        self.assertEqual(
            recent[1]["talking_to_speaker"],
            "同名用户 [user:10001]",
        )
        self.assertEqual(recent[2]["speaker"], "同名用户 [user:20002]")
        self.assertIn("同名用户 [user:10001]", formatted)
        self.assertIn("同名用户 [user:20002]", formatted)


class ReplyDirectionHintTests(unittest.TestCase):
    @staticmethod
    def _main() -> object:
        instance = object.__new__(plugin.Main)
        instance._bot_id = "bot"
        instance._speaker_identity_mode = plugin.SPEAKER_IDENTITY_PLATFORM_ID
        instance._reply_direction_hint_enabled = True
        instance._reply_direction_hint_template = (
            plugin.DEFAULT_REPLY_DIRECTION_HINT_TEMPLATE
        )
        return instance

    @staticmethod
    def _event(platform_name: str) -> object:
        return SimpleNamespace(
            get_platform_name=lambda: platform_name,
            get_platform_id=lambda: "instance",
        )

    @staticmethod
    def _message(
        msg_id: str,
        sender_id: str,
        sender_name: str,
        content: str,
        **kwargs,
    ):
        timestamp = kwargs.pop("timestamp", 100)
        return plugin.MessageRecord(
            msg_id=msg_id,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            timestamp=timestamp,
            **kwargs,
        )

    def test_reply_metadata_is_preserved_from_reply_component(self):
        record = self._message("current", "20002", "当前用户", "引用回复")
        reply = plugin.Reply(
            sender_id="10001",
            sender_nickname="被引用用户",
            id="quoted-message-id",
            message_str="被引用原文",
            time=123,
        )

        plugin._apply_reply_reference(record, reply)

        self.assertEqual(record.reply_to_id, "10001")
        self.assertEqual(record.reply_to_name, "被引用用户")
        self.assertEqual(record.reply_to_message_id, "quoted-message-id")
        self.assertEqual(record.reply_to_content, "被引用原文")
        self.assertEqual(record.reply_to_timestamp, 123)

    def test_reply_hint_identifies_bot_reply_target_and_stays_temporary(self):
        instance = self._main()
        bot_reply = self._message(
            "bot-message-id",
            "bot",
            "[你]",
            "这是给第一位同名用户的回答",
            timestamp=300,
            is_bot=True,
            talking_to="10001",
            talking_to_name="同名用户",
        )
        current = self._message(
            "current",
            "20002",
            "同名用户",
            "我引用这条回复继续问",
            reply_to_id="bot",
            reply_to_name="[你]",
            reply_to_message_id="bot-message-id",
            reply_to_content="这是给第一位同名用户的回答",
            reply_to_timestamp=300,
        )

        hint = instance._build_reply_direction_hint(
            self._event("aiocqhttp"),
            current,
            [bot_reply, current],
        )
        scene = plugin.SceneGenerator().generate(
            trigger_type=plugin.TRIGGER_REPLY,
            trigger_desc="当前用户引用回复 Bot",
            current=current,
            flow=[bot_reply, current],
            bot_status={},
            participants=[],
            reply_direction_hint=hint,
            speaker_identity_mode=plugin.SPEAKER_IDENTITY_PLATFORM_ID,
        )

        self.assertIn("当前发言人是 user:20002", hint)
        self.assertIn("你 [bot:self]", hint)
        self.assertIn("同名用户 [user:10001]", hint)
        self.assertIn(plugin.REPLY_DIRECTION_INJECTED_MARKER, scene)
        self.assertIn('<reply_direction source="scene_memory">', scene)

    def test_reply_hint_skips_qq_official_and_ambiguous_bot_reply_target(self):
        instance = self._main()
        first_reply = self._message(
            "bot-1",
            "bot",
            "[你]",
            "相同回复",
            timestamp=100,
            is_bot=True,
            talking_to="10001",
            talking_to_name="同名用户",
        )
        second_reply = self._message(
            "bot-2",
            "bot",
            "[你]",
            "相同回复",
            timestamp=200,
            is_bot=True,
            talking_to="30003",
            talking_to_name="同名用户",
        )
        current = self._message(
            "current",
            "20002",
            "当前用户",
            "引用 Bot 回复",
            reply_to_id="bot",
            reply_to_content="相同回复",
        )

        ambiguous_hint = instance._build_reply_direction_hint(
            self._event("aiocqhttp"),
            current,
            [first_reply, second_reply, current],
        )

        self.assertIn("无法从当前引用安全确认", ambiguous_hint)
        self.assertNotIn("user:10001", ambiguous_hint)
        self.assertNotIn("user:30003", ambiguous_hint)
        self.assertEqual(
            instance._build_reply_direction_hint(
                self._event("qq_official"),
                current,
                [first_reply, second_reply, current],
            ),
            "",
        )

    def test_internal_markers_are_removed_from_request_copies(self):
        old_scene = (
            f"{plugin.ExtraKeys.SCENE_INJECTED_MARKER}\n"
            "<conversation_scene>旧场景</conversation_scene>"
        )
        old_reply_hint = (
            f"{plugin.REPLY_DIRECTION_INJECTED_MARKER}\n"
            '<reply_direction source="scene_memory">旧引用说明</reply_direction>'
        )
        dirty = f"保留前缀 {old_scene} 中间 {old_reply_hint} 保留后缀"
        text_part = plugin.TextPart(text=dirty)
        request = SimpleNamespace(
            system_prompt=dirty,
            contexts=[
                {"role": "assistant", "content": dirty},
                {
                    "role": "user",
                    "content": [{"type": "text", "text": dirty}],
                },
            ],
            extra_user_content_parts=[text_part],
        )

        plugin.Main._clean_request_internal_markers(request)

        for cleaned in (
            request.system_prompt,
            request.contexts[0]["content"],
            request.contexts[1]["content"][0]["text"],
            text_part.text,
            plugin.Main._strip_internal_scene_markers(dirty),
        ):
            self.assertIn("保留前缀", cleaned)
            self.assertIn("保留后缀", cleaned)
            self.assertNotIn("scene_memory_", cleaned)
            self.assertNotIn("旧场景", cleaned)
            self.assertNotIn("旧引用说明", cleaned)


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
