# 更新日志

本文档记录分叉维护版 `astrbot_plugin_context_scene_memory` 的重要变更。

原仓库：

- 项目：`astrbot_plugin_context_aware`
- 作者：木有知
- 仓库：[muyouzhi6/astrbot_plugin_context_aware](https://github.com/muyouzhi6/astrbot_plugin_context_aware)

当前分叉仓库：

- 项目：`astrbot_plugin_context_scene_memory`
- 仓库：[Whereis-Alice/astrbot_plugin_context_scene_memory](https://github.com/Whereis-Alice/astrbot_plugin_context_scene_memory)

## v3.4.0

本版本新增可选的引用回复指向优化，默认关闭，不改变原有聊天发送内容。

### 新增

- 新增 `reply_direction_hint`。开启后会在当前 LLM 请求中临时注入中文说明，标明当前发言人、被引用消息发送者，以及能够唯一确认时被引用 Bot 回复原本回复给谁。
- 新增 `reply_direction_hint_template`，支持 `{current_speaker}`、`{quoted_speaker}` 和 `{quoted_bot_reply_target_note}` 占位符。
- 新增 `reply_direction_cleanup_internal_markers`，默认开启，仅清理本轮请求副本中的旧内部场景标记，并移除模型误回显的内部标记。

### 安全与兼容性

- QQ 官方 Bot 的 Reply 组件缺少可靠的被引用消息发送者 ID，因此引用回复指向优化会自动跳过该平台。
- 对被引用 Bot 回复的原始对象，只有引用消息 ID、引用原文或引用时间能唯一定位到本插件已记录的 Bot 回复时才会写入；信息不足或存在歧义时明确标为未知，不会用“最近一条 Bot 回复”进行猜测。
- 临时说明通过 `TextPart.mark_as_temp()` 参与本轮请求，不写入会话历史；不会批量迁移旧历史，也不会改写正常聊天内容。

## v3.3.1

本版本继续收紧同名用户场景中的归因链路，补足“Bot 上一句在回复谁”的精确标识。

### 改进

- 场景中的 `speaker` 统一为可直接比较的稳定身份键，例如 `user:<QQ号>`、`user:<脱敏摘要>` 或 `bot:self`；昵称保留在独立展示字段中，不再参与身份比较。
- 最近对话、图片上下文和语音转写的 `talking_to` 现在也会附带稳定身份标签。Bot 回复过同名用户 A 后，用户 B 发言时，模型能明确区分那句 Bot 回复属于 A 而非 B。
- 主动或未知触发时的“谁在和谁说话”指导同样使用身份标签，避免同名接收对象被昵称混淆。
- `get_recent_messages()` 新增 `speaker_id`、`talking_to_id` 与 `talking_to_speaker`；保留原有 `talking_to` 字段，属于向后兼容的扩展。

### 兼容性

- `speaker_attribution_template` 中的 `{current_speaker}` 现在固定展开为可直接比较的身份键，例如 `user:123456`，便于自定义提示词与场景中的 `speaker` 字段精确对齐。

## v3.3.0

本版本修复群聊场景中“模型把其他成员的历史发言误认为当前用户说过”的归因问题。

### 新增

- 默认用 AstrBot `sender_id` 生成稳定的 `user:<平台ID>` 标签；QQ/OneBot 平台中该 ID 即 QQ 号，同名或改名成员不会再仅凭昵称被合并。
- 当前消息、最近对话、图片上下文、语音转写、参与者列表、历史压缩输入和公开上下文 API 均使用同一身份标签。
- 新增 `speaker_attribution_guard` 与 `speaker_attribution_template`。默认规则明确要求模型：只有身份标签完全相同的内容才能归属给当前用户；无身份标签的旧摘要只能作为背景。
- 新增 `speaker_identity_mode`：默认 `platform_id`，可选 `masked` 脱敏稳定标签或 `name_only` 兼容旧行为。

### 兼容性与隐私

- `platform_id` 模式会把平台用户 ID 发给所选模型提供商；QQ/OneBot 场景下即 QQ 号。需要避免发送原始 ID 时，请改用 `masked`，归因精度仍保持稳定。
- `get_recent_messages()` 增加 `sender_id` 与 `speaker` 字段，属于向后兼容的扩展。

## v3.2.4

本版本核对上游最新 `v3.4.3` 后，手工吸收其中与会话一致性直接相关的低风险改进；不覆盖分叉版已有的动态群名片适配、会话级 Provider 选择和临时场景注入。

### 新增

- 在记录消息前识别 `/reset` 和 `/new`，先清理当前 UMO 的插件上下文，再让 AstrBot 或其他插件继续处理命令。
- 兼容 `astrbot_plugin_cmdmask` 的伪装指令，使用其 target extra 中的真实命令判断是否需要清理。
- 兼容 AstrBot 新版 `_clean_group_context_session` 和旧版 `_clean_ltm_session` 会话清理标记。

### 兼容性

- 本插件不注册 `/reset`、`/new`，不会抢占命令，也不会把清空命令本身写进历史。
- 上游 `v3.4.0` 之后的图片压缩、引用图片归一化和 GIF 首帧处理暂不引入，避免给当前无额外依赖的图片转述链路增加请求改写与缓存生命周期风险。

## v3.2.3

本版本是对上游 `v3.3.0`、`v3.3.1` 的筛选式手工升级，不覆盖分叉版已有的动态群名片适配和会话级 Provider 选择。

### 新增

- 新增 `strict_mode`，默认关闭。开启后，只有在主动或未知触发且当前仅由上下文推断为“正在和 Bot 说话”时，才会回退为群聊。
- `strict_mode` 不会覆盖 `@`、回复、唤醒词或 Dynamic Card Plus 动态名片文本点名等明确触发证据。

### 改进

- 兼容 QQ/NapCat 等平台直接传入 `data:image/...;base64,...` 图片的场景。图像转述会将其解码为短临时本地文件路径再调用视觉 Provider，避免部分 Provider 将超长 data URI 当作文件名而出现 `[Errno 36] File name too long`。
- data URI 在内存 LRU 中使用完整 SHA-256 摘要作为缓存键，不再把超长 base64 原文保留在缓存中。
- 图像转述超时、空响应、临时文件转换失败和异常都会写入失败哨兵；同一图片后续不会反复请求视觉模型。
- 保留按 `unified_msg_origin` 获取当前会话 Provider 的分叉行为，避免多模型或多会话时转述请求误用全局默认 Provider。
- 修正规则 4 的插话保护时间基准，改为以当前消息判断此前对话是否仍在 60 秒窗口内。

### 未引入

- 未直接引入上游的延迟图像转述、远程图片下载缓存和后台清理任务。这些功能会新增网络下载、持久化缓存和生命周期管理；当前分叉保持即时转述，只为 data URI 创建并清理临时文件。

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
