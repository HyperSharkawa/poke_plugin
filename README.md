# poke_plugin

MaiBot 的「戳一戳」增强插件，让麦麦能主动戳别人，也能在被戳时回戳并生成自然回复。

## 安装步骤
1. 将仓库克隆/下载至麦麦的 `plugins` 目录下：
   ```powershell
   git clone https://github.com/HyperSharkawa/poke_plugin.git
   ```
2. 重启麦麦。

## 配置项说明

`qq_poke_plugin`：基础功能配置

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enable_poke_back` | bool | `true` | 是否在被戳后自动回戳对方 |
| `poke_back_probability` | float | `0.5` | 回戳的概率（0~1），1表示每次必回戳 |
| `enable_poke_reply` | bool | `true` | 是否在被戳后发送文字回复 |
| `poke_reply_prompt` | str | 详见源码 | 在被戳时进行文字回复的提示词 |
| `poke_back_prompt` | str | 详见源码 | 当决定回戳时的额外提示词 |
| `poke_no_back_prompt` | str | 详见源码 | 当决定不回戳时的额外提示词 |
| `action_require` | str | 详见源码 | 影响主动 `poke` 动作的决策提示词 |

`qq_poke_plugin_guard`：防护与频率限制配置

| 字段 | 类型 | 默认值 | 说明                                                             |
| --- | --- | --- |----------------------------------------------------------------|
| `poke_response_blacklist` | list[str] | `[`"1234567890"`]` | 被戳黑名单，名单中的用户戳 bot 不会触发响应                                       |
| `enable_poke_limit` | bool | `true` | 是否启用被戳频率限制                                                     |
| `poke_limit_window_minutes` | int | `5` | 检测分钟数：在该窗口内统计戳一戳次数                                             |
| `poke_limit_max_count` | int | `3` | 被戳次数：在窗口时间内戳一戳超过该次数触发屏蔽                                        |
| `poke_limit_block_minutes` | int | `10` | 屏蔽时间（分钟）：触发后该时间内不响应                                            |
| `poke_limit_block_prompt` | str | 详见源码 | 触发屏蔽时的额外提示词，支持占位符 `{user_name}` 和 `{poke_limit_block_minutes}` |

> ⚙️ 修改配置后需重启生效。

## 常见问题
- **为什么没有回戳/回复？**
  - 确认 WebUI 配置里已启用对应开关。
  - 确认麦麦 QQ 账号是否填写正确，否则会被忽略。
  - 检查日志中是否有“戳一戳消息目标不为bot”等提示。
  - 检查是否触发了频率限制。
- **频率限制没有生效，且日志中提示“戳一戳频率限制参数配置错误，跳过频率限制检查”？**
  - 可在webui中点 `重置` 按钮恢复默认配置，或手动检查配置项：
  - 确保配置文件中 `poke_limit_window_minutes`、`poke_limit_max_count` 和 `poke_limit_block_minutes` 均为正整数。