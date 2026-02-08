from typing import List, Tuple, Type

from src.common.logger import get_logger
from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ConfigField
)
from src.plugin_system.base.component_types import ComponentInfo
from .components.poke_action import PokeAction
from .components.poke_event_handler import PokeEventHandler

logger = get_logger("poke_plugin")


# ===== 插件注册 =====


@register_plugin
class PokePlugin(BasePlugin):
    # 插件基本信息
    plugin_name: str = "qq_poke_plugin"  # 内部标识符
    enable_plugin: bool = True
    dependencies: List[str] = []  # 插件依赖列表
    python_dependencies: List[str] = []  # Python包依赖列表
    config_file_name: str = "config.toml"  # 配置文件名
    config_section_descriptions = {
        "qq_poke_plugin": "戳一戳配置",
        "qq_poke_plugin_guard": "戳一戳防护配置",
    }
    config_schema = {
        "qq_poke_plugin": {
            # 是否在被戳时进行回戳
            "enable_poke_back": ConfigField(type=bool, default=True, description="是否在被戳时进行回戳"),
            # 是否在被戳时发送文字回复
            "enable_poke_reply": ConfigField(type=bool, default=True, description="是否在被戳时发送文字回复"),
            # 回戳的概率，取值范围0~1，表示每次被戳时有多大概率进行回戳
            "poke_back_probability": ConfigField(type=float, default=0.5,
                                                 description="回戳的概率，取值范围0~1，1表示每次被戳时都会回戳"),
            # 在被戳时进行文字回复的prompt
            "poke_reply_prompt": ConfigField(type=str,
                                             input_type="textarea",
                                             default="这是QQ的“戳一戳”功能，用于友好的和某人互动。请查看上下文针对这个“戳一戳”消息生成一个回复，注意不要复读你说过的话，尽可能为连续的戳一戳输出不同句式的回复。",
                                             description="在被戳时进行文字回复的prompt。如果未启用回复，则该prompt无效"),
            # 当决定回戳时的额外prompt
            "poke_back_prompt": ConfigField(type=str,
                                            input_type="textarea",
                                            default="你决定回戳对方，回戳将会在你的回复之后进行。",
                                            description="当决定回戳时的额外prompt。如果未启用回戳或回复，则该prompt无效"),
            # 当决定不回戳时的额外prompt
            "poke_no_back_prompt": ConfigField(type=str,
                                               input_type="textarea",
                                               default="你决定不回戳对方。",
                                               description="当决定不回戳时的额外prompt。如果未启用回戳或回复，则该prompt无效"),
            # 戳一戳动作决策prompt
            "action_require": ConfigField(type=str,
                                          input_type="textarea",
                                          default="\n".join(PokeAction.action_require),
                                          description="戳一戳动作决策prompt"),
        },
        "qq_poke_plugin_guard": {
            # 被戳响应黑名单 在名单中的用户不会触发被戳响应
            "poke_response_blacklist": ConfigField(type=list, item_type="string", default=["1234567890"],
                                                   description="被戳黑名单,在其中填入你不想让他戳bot的人的QQ号,名单中的用户戳bot不会触发响应"),
            # 是否启用被戳频率限制
            "enable_poke_limit": ConfigField(type=bool, default=True,
                                             description="是否启用被戳频率限制"),
            # 频率限制参数
            "poke_limit_window_minutes": ConfigField(type=int, default=5,
                                                     description="检测分钟数: 在该窗口内统计戳一戳次数"),
            "poke_limit_max_count": ConfigField(type=int, default=5,
                                                description="被戳次数: 超过该次数触发屏蔽"),
            "poke_limit_block_minutes": ConfigField(type=int, default=10,
                                                    description="屏蔽时间(分钟): 触发后该时间内不响应"),
            "poke_limit_block_prompt": ConfigField(
                type=str,
                default="你对{user_name}的戳一戳感到厌烦，你决定在{poke_limit_block_minutes}分钟内不再理他。在此期间，你将不会收到来自他的“戳一戳消息”。",
                description="触发屏蔽时的额外提示词。可以使用变量{user_name}和{poke_limit_block_minutes}分别表示触发屏蔽的用户名称和屏蔽时间。若未启用回复，则该prompt无效"
            ),
        }
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        components = []
        config = self.config.get("qq_poke_plugin", {})
        guard_config = self.config.get("qq_poke_plugin_guard", {})
        if raw_action_require := config.get("action_require"):
            PokeAction.action_require = raw_action_require.split("\n")
        if poke_response_blacklist := guard_config.get("poke_response_blacklist"):
            for uid in poke_response_blacklist:
                uid = uid.strip()
                if uid:
                    PokeEventHandler.poke_response_blacklist.append(uid)
        components.append((PokeAction.get_action_info(), PokeAction))
        enable_poke_reply = config.get("enable_poke_reply")
        enable_poke_back = config.get("enable_poke_back")
        if enable_poke_back or enable_poke_reply:
            components.append((PokeEventHandler.get_handler_info(), PokeEventHandler))
        return components
