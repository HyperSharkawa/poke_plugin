# poke_plugin

MaiBot 的「戳一戳」增强插件，让麦麦能主动戳别人，也能在被戳时回戳并生成自然回复。

## 安装步骤
1. 将仓库克隆/下载至麦麦的 `plugins` 目录下：
   ```powershell
   git clone https://github.com/HyperSharkawa/poke_plugin.git
   ```
2. 重启麦麦。

## 配置项说明

| 字段 | 类型 | 默认值 | 说明                  |
| --- | --- | --- |---------------------|
| `enable_poke_back` | bool | `true` | 是否在被戳后自动回戳对方        |
| `enable_poke_reply` | bool | `true` | 是否在被戳后发送文字回复        |
| `poke_reply_prompt` | str | 详见源码 | 表达器在生成文字回复时附带的提示词   |
| `action_require` | str | 详见源码 | 影响主动 `poke` 动作的决策提示 |

> ⚙️ 修改配置后需重启生效。

## 常见问题
- **为什么没有回戳/回复？**
  - 确认 WebUI 配置里已启用对应开关。
  - 确认麦麦 QQ 账号是否填写正确，否则会被忽略。
  - 检查日志中是否有“戳一戳消息目标不为bot”等提示。