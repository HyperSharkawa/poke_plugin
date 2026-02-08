from typing import Tuple, Optional

from src.common.logger import get_logger
from src.config.config import global_config
from src.plugin_system import (
    BaseAction
)
from src.plugin_system.apis import person_api, database_api
from src.plugin_system.base.component_types import ActionActivationType

logger = get_logger("poke_plugin")


class PokeAction(BaseAction):
    action_name = "poke"
    action_description = (
        "使用“戳一戳”功能友好的戳一下某人。这个动作不会发送消息内容，仅会有一个弱提示。"
        "poke action不视为回复消息，使用该动作不影响回复频率。你可以同时使用poke和其他任何动作。"
    )
    activation_type = ActionActivationType.ALWAYS
    parallel_action = True
    associated_types = ["command"]

    action_parameters = {
        "name": "要戳的用户名称",
    }

    action_require = [
        "想表达情绪时",
        "当你想使用戳一戳功能和别人互动时",
        "当你想引起某人注意或提醒某人时",
        "当别人让你戳他时",
        "注意: poke不应该作为emoji和reply的替代，请优先使用emoji和reply。不要连续戳同一个人超过两次！",
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
