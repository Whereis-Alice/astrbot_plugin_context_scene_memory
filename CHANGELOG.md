# 更新日志

本文档记录分叉维护版 `astrbot_plugin_context_scene_memory` 的重要变更。

原仓库：

- 项目：`astrbot_plugin_context_aware`
- 作者：木有知
- 仓库：[muyouzhi6/astrbot_plugin_context_aware](https://github.com/muyouzhi6/astrbot_plugin_context_aware)

当前分叉仓库：

- 项目：`astrbot_plugin_context_scene_memory`
- 仓库：[Whereis-Alice/astrbot_plugin_context_scene_memory](https://github.com/Whereis-Alice/astrbot_plugin_context_scene_memory)

## v3.2.2

适配 `astrbot_plugin_dynamic_card_plus`，减少动态群名片导致的“Bot 被当成另一个人或另一个 AI”的误判。

### 新增

- 新增 `dynamic_card_plus_compat`，默认开启，自动读取 Dynamic Card Plus 的基础名字、当前群名片和近期名片作为 Bot 文本别名。
- 新增 `dynamic_card_plus_identity_hint` 与 `dynamic_card_plus_identity_template`，命中动态名片别名时使用专用身份提示词。
- 新增 `dynamic_card_plus_alias_max_count` 与 `dynamic_card_plus_alias_min_length`，用于控制动态别名数量和最小长度，降低误触发概率。

### 改进

- 文本消息命中 Bot 动态名片别名时，会被推断为用户正在和 Bot 说话，而不是仅仅“提到 Bot”。
- 回复对象昵称命中 Dynamic Card Plus 名片别名时，即使 Reply 组件没有稳定提供 Bot ID，也会按“回复 Bot”处理。
- Bot 刚回复过当前用户时，短句追问如“你说啥”“啥”“没听懂”等更容易被识别为在继续和 Bot 对话。
- `<conversation_scene>` 在文本点名动态名片时会明确提示“这是你本人，不是另一个人或另一个 AI”。

### 兼容性

- 这是软集成：未安装、未启用或无法读取 `astrbot_plugin_dynamic_card_plus` 时，会自动退回原行为。
- 不需要修改 `astrbot_plugin_dynamic_card_plus` 本体。

## v3.2.1

同步上游 `v3.1.6` 的更新，并保留分叉版改动。

### 同步上游

- 同步最近图片上下文能力，支持把图片单独注入到 `<recent_images>`。
- 同步 `show_recent_images_allow_gif`，默认过滤 GIF，避免部分视觉模型不支持 `image/gif`。
- 同步 Gemini_STT 语音转写上下文兼容，将语音转写记录为普通群聊消息。
- 同步 `voice_context_window`，语音转写会进入独立 `<recent_voice_transcripts>` 窗口。
- 同步按消息 ID 幂等写入，减少同一条消息被 handler 和 LLM 请求兜底重复记录。
- 同步 `warn_builtin_ltm`，检测到 AstrBot 内置群聊上下文感知时输出警告。
- 同步元数据中的 AstrBot 最低版本要求：`>=4.24.0`。

### 保留分叉改动

- 保留插件名 `astrbot_plugin_context_scene_memory` 与显示名“上下文场景记忆增强”。
- 保留分叉专用运行时 extra key 和场景注入 marker，避免与上游版本冲突。
- 保留临时场景注入，并在 extra parts 中检查 marker，避免提示词重复注入或写回历史。
- 保留 `record_structural_messages`，纯 `@`、纯回复、`@全体` 仍可进入上下文分析。
- 保留 `dynamic_name_identity_hint` 与 `dynamic_name_identity_template`，继续缓解动态群名片误判。
- 保留图像转述按当前会话 provider 获取的行为。

### 文档

- 重写 `README.md`，去掉重复段落，补充上游同步范围、版本要求和新增配置说明。
- 更新本变更记录，明确上游来源和分叉维护边界。

## v3.2.0

分叉维护版首个版本，基于上游 `v3.1.2`。

### 调整

- 将插件名称调整为 `astrbot_plugin_context_scene_memory`。
- 将显示名调整为“上下文场景记忆增强”。
- 更新运行时注入标记与内部 extra key 标识，降低与上游版本并存时的冲突风险。

### 修复

- 场景注入改为临时内容，不再写回 AstrBot 会话历史。
- 修复每轮场景描述可能导致伪上下文持续膨胀的问题。
- 修复纯 `@`、纯回复、`@全体` 结构消息可能漏记，导致 current 消息取错的问题。
- 图像转述改为按当前会话选择 provider，减少多模型或会话隔离场景的错配。

### 新增

- 新增 `record_structural_messages`，用于控制是否记录纯 `@`、纯回复、`@全体` 这类结构化消息。
- 新增 `dynamic_name_identity_hint`，用于控制是否启用动态群名片身份提示。
- 新增 `dynamic_name_identity_template`，用于自定义“被 @ 到的动态昵称就是你自己”的提示词模板。
- 新增中文 `README.md` 与 `CHANGELOG.md`，明确说明分叉来源、配置项和维护策略。
