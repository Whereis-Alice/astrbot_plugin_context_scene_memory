# 上下文场景记忆增强

让 AstrBot 在群聊里更会“接上文”。

这个插件主要做两件事：

- 增强上下文连续性，减少“聊没两句就忘了前面说过什么”
- 增强场景理解能力，减少 Bot 抢答、插错话、认错对话对象

这是基于上游项目 [muyouzhi6/astrbot_plugin_context_aware](https://github.com/muyouzhi6/astrbot_plugin_context_aware) 的分叉维护版。

## 快速开始

### 1. 安装插件

当前插件标识：

```yaml
name: astrbot_plugin_context_scene_memory
display_name: 上下文场景记忆增强
```

### 2. 关闭 AstrBot 内置群聊上下文感知

强烈建议关闭，否则会出现两份群聊历史同时注入的问题。

```yaml
provider_ltm_settings:
  group_icl_enable: false
```

### 3. 推荐保留的插件配置

建议优先保持这几个默认值：

- `record_structural_messages = true`
- `dynamic_name_identity_hint = true`
- `history_compress_strategy = off`

如果后面上下文太长，再考虑开启 `llm_summary` 压缩。

## 这个插件解决什么问题

群聊里最常见的问题，不是模型完全没记忆，而是它经常记住了内容，却没分清场景。

典型表现：

- A 在问 B，Bot 抢答
- 用户只是顺手接了一句，Bot 以为在问自己
- 被主动回复触发后，Bot 把群友之间的对话误判成对自己说
- 动态群名片变化后，模型把被 `@` 到的名字当成另一个对象

这个插件同时补两块能力：

1. 上下文记忆
   保留最近群聊消息、Bot 最近回复对象，以及可选的历史摘要。

2. 场景理解
   在每轮 LLM 请求前，为模型补一段结构化场景提示，告诉它当前是谁在说话、在对谁说、你是被叫到还是主动加入。

## 你最关心的一点：上下文增强还在吗

还在，而且没有被删。

这版依然会：

- 记录每个群的最近消息历史
- 跟踪 Bot 最近回复过谁
- 在当前轮把最近对话流提供给 LLM
- 可选把较长历史压成摘要继续带入

这次调整只修了一个问题：

- 以前每轮生成的场景提示，可能被误写回聊天历史
- 现在场景提示只参与当前轮，不再污染会话历史

所以现在保留下来的，更偏“真实聊天上下文”，而不是“历史里混进越来越多提示词”。

## 分叉说明

### 上游原仓库

- 项目名：`astrbot_plugin_context_aware`
- 作者：木有知
- 仓库地址：[muyouzhi6/astrbot_plugin_context_aware](https://github.com/muyouzhi6/astrbot_plugin_context_aware)

### 为什么这版改了名字

分叉版使用了新的插件名和显示名，是为了：

- 避免和上游同名，后续 fork 或部署时互相覆盖
- 避免运行时注入标记和内部 key 与上游版本撞车
- 避免你以后同步上游修复时，难以区分当前运行的是哪一版

如果你将来继续维护自己的仓库，建议始终保留来源说明。

## 核心能力

- 识别触发类型：`@Bot`、回复 Bot、唤醒词、主动触发、戳一戳、私聊
- 推断说话对象：谁在和谁说话
- 记录最近对话流：帮助模型接住前文
- 跟踪 Bot 状态：Bot 最近何时发言、回复过谁
- 可选图像转述：把群友发送的图片简要变成文字
- 可选历史压缩：对较长历史生成摘要
- 可选动态群名片身份提示：告诉模型“被 @ 到的动态昵称就是你自己”
- 可选记录结构化消息：纯 `@`、纯回复、`@全体` 也能进入上下文

## 适合的场景

- 群聊活跃、多人对话多，Bot 容易插错话
- 模型并不笨，但总分不清“用户是在跟谁说”
- 你希望 Bot 不只记住最近内容，还能判断清楚说话关系
- 你使用了动态名片或状态昵称，模型偶尔把 Bot 当成别人

## 配置说明

### 基础配置

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

如果你使用动态改名、状态名片、运行时昵称变化，建议开启。

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

### AstrBot 配置

```yaml
provider_ltm_settings:
  group_icl_enable: false
  active_reply:
    enable: true

provider_settings:
  max_context_length: 20
```

### 插件侧建议

- `record_structural_messages = true`
- `dynamic_name_identity_hint = true`
- `history_compress_strategy = off`

如果后面上下文偏长，再考虑切到：

- `history_compress_strategy = llm_summary`

## 这版相对上游做了什么

- 改用新的插件名与显示名，降低与上游更新冲突
- 场景注入改为临时内容，不再写回会话历史
- 纯 `@` / 纯回复 / `@全体` 的结构化消息改为可配置记录
- 动态群名片身份提示改为可配置功能和模板
- 图像转述改为按当前会话选择 provider
- README 与 CHANGELOG 改成更适合 fork 维护的中文说明

## 与上游同步的建议

- 只合并你真正需要的上游修复
- 不要改回与上游相同的插件标识
- 每次同步上游后都更新 `CHANGELOG.md`
- 继续保留本 README 里的来源说明

## 公开 API

插件仍保留这些对外能力，便于其他插件联动：

- `get_recent_messages(unified_msg_origin, count=10)`
- `get_formatted_context(unified_msg_origin, count=10)`
- `has_session(unified_msg_origin)`
- `remove_message(unified_msg_origin, msg_id)`
- `remove_last_bot_response(unified_msg_origin)`

## 变更记录

详见 [CHANGELOG.md](./CHANGELOG.md)。
