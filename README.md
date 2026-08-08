# 上下文场景记忆增强

让 AstrBot 在群聊里更会“接上文”、少抢答、少认错说话对象，并在清空会话时同步清理插件自己的场景记忆。

这是基于原仓库 [muyouzhi6/astrbot_plugin_context_aware](https://github.com/muyouzhi6/astrbot_plugin_context_aware) 的分叉维护版，当前仓库为 [Whereis-Alice/astrbot_plugin_context_scene_memory](https://github.com/Whereis-Alice/astrbot_plugin_context_scene_memory)。

当前分叉版为 `v3.4.0`。它已同步上游 `v3.1.6` 的主要能力，并手工吸收了上游 `v3.3.0`、`v3.3.1` 与 `v3.4.0` 中适合本分叉的改进；同时保留插件标识、临时场景注入、动态群名片提示和 `astrbot_plugin_dynamic_card_plus` 适配。上游目前已更新到 `v3.4.3`，本分叉没有直接引入其图片压缩和 GIF 首帧处理链路。

## 这个插件做什么

- 记录每个群的最近消息，让模型能接住前文，不会聊两句就忘。
- 推断“谁在和谁说话”，在 LLM 请求前注入结构化场景提示。
- 用稳定平台 ID 标记消息发送者和明确接收对象，避免同名、改名或动态昵称成员之间串人。
- 跟踪 Bot 最近回复对象、最近发言时间，并保留其精确身份标签，减少主动回复时的误判。
- 可选注入引用回复指向，说明当前发言人、被引用消息发送者，以及能唯一确认时的 Bot 原始回复对象。
- 跟随 `/reset`、`/new` 和系统会话清理标记清空插件历史，避免旧上下文在新会话中复活。
- 单独注入最近图片和语音转写上下文，避免普通对话窗口把它们挤掉。
- 可选图像转述和历史摘要压缩，适合更长或更多媒体的群聊。

场景提示会被标记为临时内容，只参与当前轮请求，不会写回会话历史；因此保留下来的是群聊真实上下文，而不是反复累积的提示词。

## 安装前提

- 需要 AstrBot `>=4.24.0`。
- 安装后请关闭 AstrBot 内置的「群聊上下文感知(原聊天记忆增强)」。
- 插件标识是 `astrbot_plugin_context_scene_memory`，不要改回上游同名标识，否则后续同步和并存部署都容易冲突。
- 默认会将 AstrBot 的平台用户 ID 发送给当前模型；QQ/OneBot 场景中该 ID 即 QQ 号。若不希望发送原始 ID，请把 `speaker_identity_mode` 改为 `masked`。

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
| `speaker_identity_mode` | `platform_id` | 默认使用 QQ/平台 ID 精确区分成员；介意原始 ID 时改为 `masked` |
| `speaker_attribution_guard` | `true` | 强制模型按发送者和接收者的身份标签归属历史内容，建议保持开启 |
| `dynamic_name_identity_hint` | `true` | 动态名片/状态昵称场景建议开启 |
| `dynamic_card_plus_compat` | `true` | 自动识别 Dynamic Card Plus 当前群名片，减少把 Bot 当成另一个人的误判 |
| `warn_builtin_ltm` | `true` | 检测到内置群聊上下文时输出警告 |
| `show_recent_images` | `true` | 单独注入最近图片上下文 |
| `show_recent_images_allow_gif` | `false` | 默认过滤 GIF，避免部分模型不支持 `image/gif` |
| `voice_context_window` | `50` | 单独扫描最近语音转写 |
| `strict_mode` | `false` | 主动/未知触发时更保守，降低 Bot 误把群聊当成对自己说话的概率 |
| `reply_direction_hint` | `false` | 可选优化引用回复指向；QQ 官方 Bot 自动跳过 |
| `history_compress_strategy` | `off` | 上下文真的太长时再改为 `llm_summary` |

会话清理不需要额外配置。本插件不注册 `/reset` 或 `/new` 指令，只监听 AstrBot 已识别的命令和清理标记，因此不会抢占其他插件的命令处理；安装了 `astrbot_plugin_cmdmask` 时，也会按它写入的真实命令目标清理上下文。

如果你使用动态改名插件，建议保留：

```text
dynamic_name_identity_hint = true
dynamic_card_plus_compat = true
dynamic_card_plus_identity_hint = true
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
| `strict_mode` | 仅在主动或未知触发时，撤销低置信度的“正在和 Bot 说话”推断。默认关闭；不会覆盖 `@`、回复或动态群名片文本点名等明确证据 |
| `reply_starters` | 自定义“像是在回复 Bot”的前缀词 |

### 用户身份归因

| 配置项 | 说明 |
| --- | --- |
| `speaker_identity_mode` | `platform_id` 默认值会生成 `user:<平台ID>`，QQ/OneBot 中即为 `user:<QQ号>`；`masked` 用稳定 SHA-256 短标签替代原始 ID；`name_only` 只使用昵称，不建议用于多人群聊。 |
| `speaker_attribution_guard` | 是否注入“不能把其他身份标签的历史内容归给当前用户”的强制规则。默认开启。 |
| `speaker_attribution_template` | 归因保护提示词，可用 `{current_speaker}`，其值是可直接比较的身份键，如 `user:<QQ号>`。留空时使用内置默认值。 |

场景中的当前消息会带有 `speaker="user:<平台ID>"`。历史对话、图片和语音也会把发送者写入同一个 `speaker` 字段，并在 `talking_to` 中标出明确接收对象的身份标签；因此 Bot 的上一句是回复给谁，也不会只靠昵称判断。这样即使两个人昵称一样，模型仍能区分是谁说过哪句话、哪一句是在回复谁。身份标签用于上下文归因，不是权限认证。

### 引用回复指向优化

| 配置项 | 说明 |
| --- | --- |
| `reply_direction_hint` | 默认 `false`。开启后，引用回复会在当前模型请求中临时说明当前发言人和被引用消息发送者。 |
| `reply_direction_hint_template` | 提示词模板，可用 `{current_speaker}`、`{quoted_speaker}`、`{quoted_bot_reply_target_note}`。 |
| `reply_direction_cleanup_internal_markers` | 默认 `true`。只清理当前请求副本中的旧内部场景标记，并移除模型误回显的内部标记。 |

引用的是 Bot 消息时，插件只会在引用消息 ID、引用原文或引用时间能唯一匹配已记录 Bot 回复时，说明这条 Bot 回复原本是回复给谁。不能唯一确认时会明确提示未知，绝不会把“最近一条 Bot 回复”的对象硬套给当前引用。QQ 官方 Bot 的 `Reply` 组件不提供可靠的被引用消息发送者信息，因此该优化会自动跳过。

所有说明均以临时 `TextPart` 注入，仅参与当前请求；真实发送到聊天平台的消息不会改变。旧会话不做批量迁移，内部标记只在当前请求副本中清理。

### 动态群名片

| 配置项 | 说明 |
| --- | --- |
| `dynamic_name_identity_hint` | 是否注入“被点名的动态昵称就是你自己”的身份提示 |
| `dynamic_name_identity_template` | 通用动态名片身份提示词模板，可用 `{bot_called_names}` |
| `dynamic_card_plus_compat` | 是否读取 `astrbot_plugin_dynamic_card_plus` 的基础名字、当前群名片和近期名片 |
| `dynamic_card_plus_identity_hint` | 命中 Dynamic Card Plus 别名时是否使用专用身份提示 |
| `dynamic_card_plus_identity_template` | Dynamic Card Plus 专用身份提示词模板，可用 `{bot_called_names}` |
| `dynamic_card_plus_alias_max_count` | 每次请求最多使用多少个动态名片别名，默认 `6` |
| `dynamic_card_plus_alias_min_length` | 动态别名最小长度，默认 `2`，用于降低单字误触发 |

适配逻辑是软集成：如果没有安装或启用 `astrbot_plugin_dynamic_card_plus`，本插件会自动退回原有行为。开启后会把基础名、当前群 `last_card`、可构建出的当前名片和手动完整名片提炼成 Bot 别名；当用户文本点名这些别名，或回复对象昵称命中这些别名时，会优先判定为在和 Bot 说话。

### 图片与语音

| 配置项 | 说明 |
| --- | --- |
| `image_context_window` | 从最近 N 条消息里提取图片上下文，默认 `20` |
| `image_caption` | 是否启用图像转述 |
| `image_caption_provider_id` | 图像转述使用的 provider，留空则使用当前会话 provider |
| `image_caption_prompt` | 图像转述提示词 |
| `image_caption_timeout` | 图像转述超时时间 |
| `voice_context_window` | 从最近 N 条消息里提取语音转写，`0` 表示关闭 |

图片上下文会以 `<recent_images>` 注入；语音转写会以 `<recent_voice_transcripts>` 注入。未开启图像转述时，图片会使用 AstrBot 消息概要或 `[图片]` 占位。启用图像转述后，QQ/NapCat 等平台传入的 `data:image/...;base64,...` 图片会在本次视觉调用内转换为临时本地文件，避免超长 data URI 被部分 Provider 误当成文件名；临时文件在调用结束后会自动删除。

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
- 新增 `dynamic_card_plus_compat` 等配置，适配 `astrbot_plugin_dynamic_card_plus` 的动态群名片别名。
- 图像转述默认按当前会话选择 provider，适配多模型和多会话场景。
- 在消息写入前识别 `/reset`、`/new`，并兼容 `astrbot_plugin_cmdmask` 的伪装指令；同时兼容 AstrBot 新旧会话清理标记。
- 新增稳定用户身份标签和归因保护，避免将别的成员的历史发言、图片、语音或旧摘要错误归属给当前用户。

## 手工吸收的上游改进

- 上游 `v3.1.3`：图片概要上下文和 AstrBot `>=4.24.0` 临时注入要求。
- 上游 `v3.1.4`：最近图片上下文支持 GIF 过滤。
- 上游 `v3.1.5`：兼容 Gemini_STT 语音转写，并按消息 ID 幂等写入。
- 上游 `v3.1.6`：语音转写独立上下文窗口，避免高频群聊把语音挤出最近对话流。
- 上游 `v3.3.0`：图像转述失败哨兵缓存，以及可配置的严格触发模式。
- 上游 `v3.3.1`：兼容平台直接传入的 base64 data URI 图片。分叉版改为使用短临时本地路径，而非重新传递 data URI，以适配 OpenAI、Gemini、Anthropic 等不同 Provider 的本地文件处理逻辑。
- 上游 `v3.4.0`：吸收 `/reset`、`/new` 在记录前清空插件上下文，以及 `astrbot_plugin_cmdmask` 真实命令目标识别。

上游 `v3.4.0` 之后的图片压缩、远程图片下载缓存、引用文件归一化和 GIF 首帧处理没有直接引入。它们会改写请求中的图片组件并增加 Pillow、网络下载、磁盘缓存和生命周期管理复杂度；当前版本保留即时转述的简单行为，并只在遇到 data URI 时创建短生命周期临时文件。

## 公开 API

插件保留以下方法，方便其他插件联动：

- `get_recent_messages(unified_msg_origin, count=10)`
- `get_formatted_context(unified_msg_origin, count=10)`
- `has_session(unified_msg_origin)`
- `remove_message(unified_msg_origin, msg_id)`
- `remove_last_bot_response(unified_msg_origin)`

`get_recent_messages()` 的每条记录还包含稳定的 `speaker_id`、兼顾可读性的 `speaker`、原始 `talking_to_id` 和带身份标签的 `talking_to_speaker`。原有的 `talking_to` 字段仍保留昵称化描述，便于旧调用方继续使用。

## 变更记录

详见 [CHANGELOG.md](./CHANGELOG.md)。
