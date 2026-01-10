import asyncio
import json
import time
from typing import List, Tuple, Type, Optional

from src.common.logger import get_logger
from src.config.config import global_config
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseAction,
    BaseEventHandler,
    EventType,
    MaiMessages,
    ConfigField
)
from src.plugin_system.apis import generator_api
from src.plugin_system.apis import person_api, database_api
from src.plugin_system.base.component_types import ComponentInfo, ActionActivationType

logger = get_logger("poke_plugin")


class PokeEventHandler(BaseEventHandler):
    """响应戳一戳"""

    event_type = EventType.ON_MESSAGE
    handler_name = "poke_message_handler"
    handler_description = "处理QQ的戳一戳消息并进行回复"

    async def execute(self, message: MaiMessages | None) -> Tuple[bool, bool, str | None, None, None]:
        """执行戳一戳消息事件处理"""
        enable_poke_reply = self.get_config("qq_poke_plugin.enable_poke_reply", False)
        enable_poke_back = self.get_config("qq_poke_plugin.enable_poke_back", False)
        if not enable_poke_back and not enable_poke_reply:
            return True, True, "戳一戳消息回复和回戳均未启用", None, None
        if not message:
            return True, True, "非戳一戳消息", None, None
        raw_message = getattr(message, "raw_message", None)
        if not raw_message:
            return True, True, "非戳一戳消息", None, None
        try:
            json_message = json.loads(raw_message)
            if (
                    not isinstance(json_message, dict)
                    or json_message.get("post_type") != "notice"
                    or json_message.get("sub_type") != "poke"
            ):
                return True, True, "非戳一戳消息", None, None
            target_user_id = json_message.get("target_id", None)
            if str(target_user_id) != global_config.bot.qq_account:
                return True, True, "戳一戳消息目标不为bot", None, None
        except Exception:
            return True, True, "非戳一戳消息", None, None
        user_id: Optional[str] = message.message_base_info.get("user_id", None)
        if not user_id:
            return False, True, "响应戳一戳失败: 无法获取用户ID", None, None
        person_id = person_api.get_person_id("qq", user_id)
        if not person_id:
            return False, True, "响应戳一戳失败: 无法获取用户信息", None, None
        person_name = await person_api.get_person_value(person_id, "person_name")
        if not person_name:
            return False, True, "响应戳一戳失败: 无法获取用户名称", None, None

        # 使用表达器生成回复
        try:
            reply_reason = person_name + message.plain_text
            logger.info(f"接收到戳一戳消息: {reply_reason}")
            if enable_poke_reply:
                poke_reply_prompt = self.get_config("qq_poke_plugin.poke_reply_prompt")
                # 调用表达器生成回复
                result_status, data = await generator_api.generate_reply(
                    chat_id=message.stream_id,
                    reply_reason=reply_reason,
                    enable_chinese_typo=False,
                    extra_info=f"{reply_reason}。{poke_reply_prompt}",
                    reply_time_point=time.time(),
                )
                if result_status:
                    # 发送生成的回复
                    for reply_seg in data.reply_set.reply_data:
                        send_data = reply_seg.content
                        await self.send_text(message.stream_id, send_data, storage_message=True)
                        await asyncio.sleep(0.2)  # 避免消息发送过快顺序错乱
                else:
                    logger.warn("戳一戳回复生成失败，跳过发送回复")
            if enable_poke_back:
                display_message = f"[戳一戳消息: {global_config.bot.nickname} 戳了戳 {person_name}]"
                flag = await self.send_command(
                    message.stream_id,
                    "SEND_POKE",
                    {"qq_id": user_id},
                    display_message,
                    True)
                if not flag:
                    logger.error("回戳失败: 发送戳一戳命令失败")
            return True, True, f"戳一戳已响应", None, None
        except Exception as e:
            logger.error(f"戳一戳响应异常: {e}")
            return False, True, "戳一戳事件处理失败", None, None


class PokeAction(BaseAction):
    action_name = "poke"
    action_description = "使用“戳一戳”功能友好的戳一下某人。这个动作不会发送消息内容，仅会有一个弱提示。"
    activation_type = ActionActivationType.ALWAYS
    parallel_action = True
    associated_types = ["command"]

    action_parameters = {
        "name": "要戳的用户名称",
    }

    action_require = [
        "当你想使用戳一戳功能和别人互动时可以选择使用",
        "想表达情绪时可以选择使用",
        "当你想引起某人注意或提醒某人时可以选择使用",
        "当别人让你戳他时可以选择使用",
        "注意:poke action不视为回复消息，使用该动作不影响回复频率。你可以同时使用reply和poke",
    ]

    async def execute(self) -> Tuple[bool, str]:
        name: Optional[str] = self.action_data.get("name", None)
        if not name:
            return False, "[戳一戳失败] action_data中不存在name"
        person_id = person_api.get_person_id_by_name(name)
        if not person_id:
            return False, "[戳一戳失败] 无法通过name找到对应的人物id"
        user_id = await person_api.get_person_value(person_id, "user_id")
        if not user_id:
            return False, "[戳一戳失败] 无法通过person_id找到对应的user_id"

        logger.debug(f"poke参数: user_id={user_id}")

        payload = {"qq_id": user_id}
        display_message = f"[戳一戳消息: {global_config.bot.nickname}(你) 戳了戳 {name}]"
        flag = await self.send_command("SEND_POKE", payload, display_message, True)
        if not flag:
            return False, "[戳一戳失败] 发送戳一戳命令失败"

        await database_api.store_action_info(
            chat_stream=self.chat_stream,
            action_build_into_prompt=True,
            action_prompt_display=display_message,
            action_done=flag,
            action_data=self.action_data,
            action_name=self.action_name
        )
        return flag, "戳一戳完成"


# ===== 插件注册 =====


@register_plugin
class PokePlugin(BasePlugin):
    # 插件基本信息
    plugin_name: str = "qq_poke_plugin"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 插件依赖列表
    python_dependencies: List[str] = []  # Python包依赖列表
    config_file_name: str = "config.toml"  # 配置文件名
    config_section_descriptions = {"qq_poke_plugin": "戳一戳配置"}
    config_schema = {
        "qq_poke_plugin": {
            # 是否在被戳时进行回戳
            "enable_poke_back": ConfigField(type=bool, default=True, description="是否在被戳时进行回戳"),
            # 是否在被戳时发送文字回复
            "enable_poke_reply": ConfigField(type=bool, default=True, description="是否在被戳时发送文字回复"),
            # 在被戳时进行文字回复的prompt
            "poke_reply_prompt": ConfigField(type=str,
                                             input_type="textarea",
                                             default="这是QQ的“戳一戳”功能，用于友好的和某人互动。请针对这个“戳一戳”消息生成一个回复，注意不要复读你说过的话",
                                             description="在被戳时进行文字回复的prompt"),
            # 戳一戳动作决策prompt
            "action_require": ConfigField(type=str,
                                          input_type="textarea",
                                          default="\n".join(PokeAction.action_require),
                                          description="戳一戳动作决策prompt"),
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        if self.config:
            raw_action_require: Optional[str] = self.config.get("qq_poke_plugin", {}).get("action_require")
            if raw_action_require:
                PokeAction.action_require = raw_action_require.split("\n")
        return [
            (PokeEventHandler.get_handler_info(), PokeEventHandler),
            (PokeAction.get_action_info(), PokeAction),
        ]
