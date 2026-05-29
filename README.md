# 上下文场景记忆增强

让 AstrBot 在群聊里更会“接上文”、少抢答、少认错说话对象。

这是基于原仓库 [muyouzhi6/astrbot_plugin_context_aware](https://github.com/muyouzhi6/astrbot_plugin_context_aware) 的分叉维护版，当前仓库为 [Whereis-Alice/astrbot_plugin_context_scene_memory](https://github.com/Whereis-Alice/astrbot_plugin_context_scene_memory)。

当前分叉版 `v3.2.1` 已同步上游 `v3.1.6` 的主要更新，同时保留本分叉的插件标识、动态群名片提示、结构化消息记录和临时场景注入修复。

## 这个插件做什么

- 记录每个群的最近消息，让模型能接住前文，不会聊两句就忘。
- 推断“谁在和谁说话”，在 LLM 请求前注入结构化场景提示。
- 跟踪 Bot 最近回复对象、最近发言时间，减少主动回复时的误判。
- 单独注入最近图片和语音转写上下文，避免普通对话窗口把它们挤掉。
- 可选图像转述和历史摘要压缩，适合更长或更多媒体的群聊。

场景提示会被标记为临时内容，只参与当前轮请求，不会写回会话历史；因此保留下来的是群聊真实上下文，而不是反复累积的提示词。

## 安装前提

- 需要 AstrBot `>=4.24.0`。
- 安装后请关闭 AstrBot 内置的「群聊上下文感知(原聊天记忆增强)」。
- 插件标识是 `astrbot_plugin_context_scene_memory`，不要改回上游同名标识，否则后续同步和并存部署都容易冲突。

建议的 AstrBot 配置：

```yaml
provider_ltm_settings:
  group_icl_enable: false
  active_reply:
    enable: true

provider_settings:
  max_context_length: 20
```

## 快速配置

通常保持默认值就能工作：

| 配置项 | 默认值 | 建议 |
| --- | --- | --- |
| `enable` | `true` | 开启插件 |
| `only_group_chat` | `true` | 群聊使用，私聊不做复杂场景分析 |
| `record_structural_messages` | `true` | 记录纯 `@`、纯回复、`@全体`，减少 current 消息错位 |
| `dynamic_name_identity_hint` | `true` | 动态名片/状态昵称场景建议开启 |
| `warn_builtin_ltm` | `true` | 检测到内置群聊上下文时输出警告 |
| `show_recent_images` | `true` | 单独注入最近图片上下文 |
| `show_recent_images_allow_gif` | `false` | 默认过滤 GIF，避免部分模型不支持 `image/gif` |
| `voice_context_window` | `50` | 单独扫描最近语音转写 |
| `history_compress_strategy` | `off` | 上下文真的太长时再改为 `llm_summary` |

如果你使用动态改名插件，建议保留：

```text
dynamic_name_identity_hint = true
dynamic_name_identity_template = 消息里被点名的“{bot_called_names}”就是你当前的群名片/动态昵称，指的就是你，不是另一个AI。
```

## 配置说明

### 基础上下文

| 配置项 | 说明 |
| --- | --- |
| `bot_names` | Bot 的昵称列表，用于检测文本提及 |
| `max_history` | 每个群保留的最大历史消息数，默认 `50` |
| `max_groups` | 最多缓存多少个群/会话，默认 `100` |
| `dialogue_window` | 每轮注入最近多少条对话流，默认 `8` |
| `enable_dialogue_flow` | 是否显示最近对话流 |
| `debug_inference` | 输出说话对象推断日志 |
| `reply_starters` | 自定义“像是在回复 Bot”的前缀词 |

### 图片与语音

| 配置项 | 说明 |
| --- | --- |
| `image_context_window` | 从最近 N 条消息里提取图片上下文，默认 `20` |
| `image_caption` | 是否启用图像转述 |
| `image_caption_provider_id` | 图像转述使用的 provider，留空则使用当前会话 provider |
| `image_caption_prompt` | 图像转述提示词 |
| `image_caption_timeout` | 图像转述超时时间 |
| `voice_context_window` | 从最近 N 条消息里提取语音转写，`0` 表示关闭 |

图片上下文会以 `<recent_images>` 注入；语音转写会以 `<recent_voice_transcripts>` 注入。未开启图像转述时，图片会使用 AstrBot 消息概要或 `[图片]` 占位。

### 历史压缩

| 配置项 | 说明 |
| --- | --- |
| `history_compress_strategy` | `off` 或 `llm_summary` |
| `history_compress_trigger_count` | 达到多少条消息后触发压缩 |
| `history_compress_keep_recent` | 压缩后保留多少条原始近期消息 |
| `history_compress_provider_id` | 压缩使用的 provider，留空则使用当前会话 provider |
| `history_compress_instruction` | 自定义压缩提示词 |
| `history_compress_max_input_chars` | 压缩输入最大字符数 |
| `history_compress_max_summary_chars` | 摘要最大字符数 |

## 分叉版改动

- 插件名称改为 `astrbot_plugin_context_scene_memory`，显示名改为“上下文场景记忆增强”。
- 运行时 extra key 和场景注入 marker 改为分叉专用值，降低与上游并存或同步时的冲突风险。
- 场景注入使用临时 `TextPart`，并在 extra parts 中检查 marker，避免重复注入和历史污染。
- 新增 `record_structural_messages`，让纯 `@`、纯回复、`@全体` 也能被记录。
- 新增 `dynamic_name_identity_hint` 与 `dynamic_name_identity_template`，缓解动态名片被模型当成另一个 AI 的问题。
- 图像转述默认按当前会话选择 provider，适配多模型和多会话场景。

## 已同步的上游能力

- 上游 `v3.1.3`：图片概要上下文和 AstrBot `>=4.24.0` 临时注入要求。
- 上游 `v3.1.4`：最近图片上下文支持 GIF 过滤。
- 上游 `v3.1.5`：兼容 Gemini_STT 语音转写，并按消息 ID 幂等写入。
- 上游 `v3.1.6`：语音转写独立上下文窗口，避免高频群聊把语音挤出最近对话流。

## 公开 API

插件保留以下方法，方便其他插件联动：

- `get_recent_messages(unified_msg_origin, count=10)`
- `get_formatted_context(unified_msg_origin, count=10)`
- `has_session(unified_msg_origin)`
- `remove_message(unified_msg_origin, msg_id)`
- `remove_last_bot_response(unified_msg_origin)`

## 变更记录

详见 [CHANGELOG.md](./CHANGELOG.md)。
