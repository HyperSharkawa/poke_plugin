import time
from src.common.logger import get_logger
from src.config.config import global_config
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseAction,
    BaseEventHandler,
    EventType,
    MaiMessages,
)
from src.plugin_system.apis import generator_api
from src.plugin_system.apis import person_api, database_api
from src.plugin_system.base.component_types import ComponentInfo, ActionActivationType
from typing import List, Tuple, Type, Optional

logger = get_logger("poke_plugin")


class PokeEventHandler(BaseEventHandler):
    """响应戳一戳"""

    event_type = EventType.ON_MESSAGE
    handler_name = "poke_message_handler"
    handler_description = "处理QQ的戳一戳消息并进行回复"

    async def execute(self, message: MaiMessages | None) -> Tuple[bool, bool, str | None, None, None]:
        """执行戳一戳消息事件处理"""
        if not message:
            return True, True, "非戳一戳消息", None, None
        raw_message = getattr(message, "raw_message", None)
        if not raw_message:
            return True, True, "非戳一戳消息", None, None

        try:
            import json
            json_message = json.loads(raw_message)
        except Exception as e:
            return True, True, "非戳一戳消息", None, None
        if json_message.get("post_type") != "notice" or json_message.get("sub_type") != "poke":
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

        target_user_id = json_message.get("target_id", None)

        if str(target_user_id) != global_config.bot.qq_account:
            return True, True, "戳一戳消息目标不为bot", None, None
        # logger.info(f"接收到戳一戳消息: {message}")

        # 使用表达器生成回复
        try:
            reply_reason = person_name + message.plain_text
            logger.info(f"接收到戳一戳消息: {reply_reason}")
            # 调用表达器生成回复
            result_status, data = await generator_api.generate_reply(
                chat_id=message.stream_id,
                reply_reason=reply_reason,
                enable_chinese_typo=False,
                extra_info=f"{reply_reason}。这是QQ的“戳一戳”功能，用于友好的和某人互动。请针对这个“戳一戳”消息生成一个回复",
                reply_time_point=time.time()
            )
            flag = await self.send_command(
                message.stream_id,
                "SEND_POKE",
                {"qq_id": user_id},
                storage_message=False)
            if not flag:
                logger.error("回戳失败: 发送戳一戳命令失败")
            if result_status:
                # 发送生成的回复
                for reply_seg in data.reply_set.reply_data:
                    send_data = reply_seg.content
                    await self.send_text(message.stream_id, send_data, storage_message=True)
                    logger.info(f"戳一戳已回复: {send_data}")
                return True, True, f"戳一戳已响应", None, None
        except Exception as e:
            logger.error(f"表达器生成失败: {e}")

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

        flag = await self.send_command("SEND_POKE", {"qq_id": user_id}, storage_message=False)
        if not flag:
            return False, "[戳一戳失败] 发送戳一戳命令失败"

        await database_api.store_action_info(
            chat_stream=self.chat_stream,
            action_build_into_prompt=True,
            action_prompt_display=f"使用了戳一戳，原因：{self.action_reasoning}",
            action_done=True,
            action_data=self.action_data,
            action_name=self.action_name
        )
        return True, "戳一戳成功"


# ===== 插件注册 =====


@register_plugin
class PokePlugin(BasePlugin):
    # 插件基本信息
    plugin_name: str = "poke_plugin"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 插件依赖列表
    python_dependencies: List[str] = []  # Python包依赖列表
    config_file_name: str = "config.toml"  # 配置文件名
    config_schema = {}  # 配置文件模式（目前为空）

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        return [
            (PokeEventHandler.get_handler_info(), PokeEventHandler),
            (PokeAction.get_action_info(), PokeAction),
        ]
