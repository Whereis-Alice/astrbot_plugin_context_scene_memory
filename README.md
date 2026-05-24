# 上下文场景记忆增强

让 AstrBot 在群聊里更会“接上文”，既减少抢答，也减少“聊没两句就忘了前面在说什么”。

这是一个基于上游项目 [muyouzhi6/astrbot_plugin_context_aware](https://github.com/muyouzhi6/astrbot_plugin_context_aware) 的分叉维护版。
本仓库保留了上游“分析谁在和谁说话”的核心思路，并在此基础上补了更适合长期维护和自定义部署的改动。

## 为什么要改名

分叉版使用了新的插件标识：

```yaml
name: astrbot_plugin_context_scene_memory
display_name: 上下文场景记忆增强
```

这样做的目的：

- 避免和上游插件同名，后续 fork 仓库时不会在插件管理层面互相覆盖。
- 避免运行时注入标记与内部 extra key 和上游版本撞车。
- 避免后续你拉上游更新、或用户误装两个版本时产生难排查的冲突。

## 原仓库说明

上游原仓库：

- 项目名：`astrbot_plugin_context_aware`
- 作者：木有知
- 仓库地址：[muyouzhi6/astrbot_plugin_context_aware](https://github.com/muyouzhi6/astrbot_plugin_context_aware)

本仓库不是上游官方延续版本，而是面向你当前使用场景的分叉维护版。
如果你将来 fork 成自己的仓库，建议在仓库首页和 `metadata.yaml` 中继续保留这段来源说明。

## 这个插件解决什么问题

默认的群聊上下文能力，经常只是在“记住最近说了什么”，但不一定能分清：

- 这句话是不是在对 Bot 说
- 用户是在回复谁
- Bot 是被叫到的，还是主动插话的
- 被 `@` 到的动态昵称，到底是不是 Bot 自己

这会导致两类常见问题：

- Bot 抢答别人之间的对话
- LLM 明明看到了上下文，却因为对象判断错了而选择沉默或乱接话

本插件会同时增强两件事：

1. 上下文连续性
   保留每个群的最近消息、Bot 最近回复对象、可选历史摘要，让模型不容易“聊两句就忘”。

2. 场景理解能力
   在每轮 LLM 请求前，生成结构化场景提示，告诉模型当前是谁在说话、在对谁说、你是被叫到还是主动加入。

## 你关心的“上下文增强还在吗”

还在，而且这是这版的核心能力之一。

它现在依然会：

- 记录每个群的最近消息历史
- 跟踪 Bot 最近回复过谁
- 在当前轮把最近对话流一起提供给 LLM
- 可选开启历史压缩，把较长历史压成摘要继续带入

所以它不是“只判断说话对象”，而是“上下文记忆 + 场景理解”一起做。

我这次做的调整，没有去掉上下文增强，只是修正了一个问题：

- 以前每轮生成的 `<conversation_scene>` 可能被写回聊天历史，造成伪上下文越来越多
- 现在场景提示只参与当前轮，不再污染历史

这意味着：

- 真正的聊天上下文还在
- 场景辅助提示还在
- 只是不会把“辅助提示词”误当成“真实历史消息”长期累积

## 与 AstrBot 内置功能的关系

安装本插件后，建议关闭 AstrBot 内置的「群聊上下文感知（原聊天记忆增强）」功能，否则会出现两份群聊历史同时注入的问题。

配置示例：

```yaml
provider_ltm_settings:
  group_icl_enable: false
```

如果你保留主动回复功能，可以只关闭群聊历史注入，继续保留主动回复策略本身。

## 核心能力

- 识别触发类型：`@Bot`、回复 Bot、唤醒词、主动触发、戳一戳、私聊
- 推断说话对象：谁在和谁说话
- 记录对话流：保留最近群聊消息，让模型更容易接住上下文
- 跟踪 Bot 状态：Bot 最近何时说过话、回复过谁
- 可选图像转述：把群友图片简要转成文字
- 可选历史压缩：对较长历史生成摘要
- 可选动态群名片身份提示：告诉模型“被 @ 到的动态昵称就是你自己”
- 可选记录结构化消息：纯 `@`、纯回复、`@全体` 也可以记入上下文

## 适合的场景

- 群聊多、对话链复杂，Bot 容易插错话
- 模型本身不算笨，但经常分不清“用户是在跟谁说”
- 你希望 Bot 既记得最近聊过什么，又不要动不动抢答
- 你用了动态名片/动态昵称，模型偶尔把 Bot 当成另一个对象

## 配置项说明

### 基础项

| 配置项 | 说明 | 默认值 |
|------|------|------|
| `enable` | 是否启用插件 | `true` |
| `bot_names` | Bot 的昵称列表，用于提及识别 | `[]` |
| `max_history` | 每个群最多保留多少条消息 | `50` |
| `max_groups` | 最多缓存多少个群/会话 | `100` |
| `dialogue_window` | 每轮注入多少条最近对话流 | `8` |
| `enable_dialogue_flow` | 是否显示最近对话流 | `true` |
| `only_group_chat` | 是否仅对群聊生效 | `true` |
| `debug_inference` | 是否输出推断调试日志 | `false` |
| `reply_starters` | 用于判断“像是在回复 Bot”的前缀词 | `[]` |

### 结构化消息记录

| 配置项 | 说明 | 默认值 |
|------|------|------|
| `record_structural_messages` | 是否记录纯 `@` / 纯回复 / `@全体` 等没有正文的消息 | `true` |

建议保持开启。关闭后，某些没有正文的消息将不进入上下文分析，可能重新出现 current 消息取错的问题。

### 动态群名片身份提示

| 配置项 | 说明 | 默认值 |
|------|------|------|
| `dynamic_name_identity_hint` | 是否启用“被 @ 到的动态昵称就是你自己”的提示 | `true` |
| `dynamic_name_identity_template` | 提示词模板，可用占位符 `{bot_called_names}` | `消息里被点名的“{bot_called_names}”就是你当前的群名片/动态昵称，指的就是你，不是另一个AI。` |

如果你使用了动态改名、状态名片、运行时昵称变化，建议开启。

### 图像转述

| 配置项 | 说明 | 默认值 |
|------|------|------|
| `image_caption` | 是否启用图像转述 | `false` |
| `image_caption_provider_id` | 图像转述使用的提供商 | `""` |
| `image_caption_prompt` | 图像转述提示词 | `请用中文简洁描述这张图片的内容，不超过50字。` |
| `image_caption_timeout` | 图像转述超时秒数 | `60` |

### 历史压缩

| 配置项 | 说明 | 默认值 |
|------|------|------|
| `history_compress_strategy` | 历史压缩策略，支持 `off` / `llm_summary` | `off` |
| `history_compress_trigger_count` | 达到多少条消息后触发压缩 | `48` |
| `history_compress_keep_recent` | 压缩后保留最近多少条原消息 | `16` |
| `history_compress_min_interval_sec` | 两次压缩最小间隔秒数 | `300` |
| `history_compress_provider_id` | 压缩使用的模型提供商 | `""` |
| `history_compress_instruction` | 历史压缩提示词 | `""` |
| `history_compress_timeout` | 历史压缩超时秒数 | `60` |
| `history_compress_max_input_chars` | 压缩输入最大字符数 | `5000` |
| `history_compress_max_summary_chars` | 压缩结果最大字符数 | `800` |

## 推荐配置

```yaml
provider_ltm_settings:
  group_icl_enable: false
  active_reply:
    enable: true

provider_settings:
  max_context_length: 20
```

插件侧推荐：

- `record_structural_messages = true`
- `dynamic_name_identity_hint = true`
- `history_compress_strategy = off` 或按需启用 `llm_summary`

## 这版相对上游做了什么

当前分叉版主要新增或修复了这些点：

- 改用新的插件名与显示名，降低与上游更新冲突
- 场景注入改为临时内容，不再写回会话历史
- 纯 `@` / 纯回复 / `@全体` 的结构化消息可配置记录
- 动态群名片身份提示改为可配置功能和模板
- 图像转述按当前会话选择 provider
- README 与变更记录改为更适合 fork 维护的说明方式

## 与上游同步的建议

如果你后面要长期维护自己的 fork，建议：

- 只挑选上游你真正需要的修复合并
- 不要再改回与上游相同的插件标识
- 每次合并上游后都更新 `CHANGELOG.md`
- 保留本 README 中的来源说明

## 公开 API

插件仍保留这些对外能力，便于其他插件联动：

- `get_recent_messages(unified_msg_origin, count=10)`
- `get_formatted_context(unified_msg_origin, count=10)`
- `has_session(unified_msg_origin)`
- `remove_message(unified_msg_origin, msg_id)`
- `remove_last_bot_response(unified_msg_origin)`

## 变更记录

请查看 [CHANGELOG.md](./CHANGELOG.md)。
