import asyncio
import json
import random
import time
from typing import List, Tuple, Optional, Dict

from src.common.logger import get_logger
from src.config.config import global_config
from src.plugin_system import (
    BaseEventHandler,
    EventType,
    MaiMessages
)
from src.plugin_system.apis import generator_api
from src.plugin_system.apis import person_api

logger = get_logger("poke_plugin")


class PokeEventHandler(BaseEventHandler):
    """响应戳一戳"""

    event_type = EventType.ON_MESSAGE
    handler_name = "poke_message_handler"
    handler_description = "处理QQ的戳一戳消息并进行回复"
    # 戳一戳响应黑名单
    poke_response_blacklist: List[str] = []
    # 记录用户戳一戳的时间戳
    _poke_timestamps: Dict[str, List[float]] = {}
    # 记录用户戳一戳的屏蔽截止时间戳
    _poke_block_until: Dict[str, float] = {}

    def _is_blacklisted(self, user_id: str) -> bool:
        """
        检查用户是否在戳一戳响应黑名单中
        :param user_id: 用户ID
        :return: 是否在黑名单中
        """
        return user_id in self.poke_response_blacklist

    def _record_poke(self, user_id: str, now: float, window_seconds: float) -> int:
        """
        记录用户戳一戳的时间戳，并返回在指定时间窗口内的戳一戳次数
        :param user_id: 用户ID
        :param now: 当前时间戳
        :param window_seconds: 时间窗口（秒）
        :return: 在时间窗口内的戳一戳次数
        """
        timestamps = self._poke_timestamps.get(user_id)
        if not timestamps:
            timestamps = []
        timestamps.append(now)  # 记录当前戳一戳时间
        if window_seconds > 0:
            cutoff = now - window_seconds  # 计算时间窗口的起始时间
            while timestamps and timestamps[0] < cutoff:  # 移除窗口外的戳一戳时间
                timestamps.pop(0)
        self._poke_timestamps[user_id] = timestamps
        return len(timestamps)

    def _get_block_until(self, user_id: str) -> float:
        """
        获取用户戳一戳的屏蔽截止时间戳
        :param user_id: 用户ID
        :return: 屏蔽截止时间戳
        """
        return self._poke_block_until.get(user_id, 0.0)

    def _set_block_until(self, user_id: str, until_ts: float) -> None:
        """
        设置用户戳一戳的屏蔽截止时间戳
        :param user_id: 用户ID
        :param until_ts: 屏蔽截止时间戳
        :return: None
        """
        self._poke_block_until[user_id] = until_ts

    def _format_block_prompt(self, user_name: str, block_minutes: int) -> str:
        prompt: str = self.get_config("qq_poke_plugin_guard.poke_limit_block_prompt", "")
        if not prompt:
            return ""
        return (
            prompt
            .replace("{user_name}", user_name)
            .replace("{poke_limit_block_minutes}", str(block_minutes))
        )

    def _evaluate_poke_limit(self, user_id: str) -> Tuple[bool, bool]:
        """
        检查用户是否应该被屏蔽戳一戳响应
        :param user_id: 用户ID
        :return: (是否当前屏蔽, 是否本次触发屏蔽)
        """
        if not self.get_config("qq_poke_plugin_guard.enable_poke_limit", False):
            return False, False
        window_minutes = self.get_config("qq_poke_plugin_guard.poke_limit_window_minutes", 0)
        max_pokes = self.get_config("qq_poke_plugin_guard.poke_limit_max_count", 0)
        block_minutes = self.get_config("qq_poke_plugin_guard.poke_limit_block_minutes", 0)
        if window_minutes <= 0 or max_pokes <= 0 or block_minutes <= 0:
            logger.warn("戳一戳频率限制参数配置错误，跳过频率限制检查")
            return False, False
        now_ts = time.time()
        window_seconds = float(window_minutes) * 60.0
        block_seconds = float(block_minutes) * 60.0
        poke_count = self._record_poke(user_id, now_ts, window_seconds)
        logger.debug(f"用户 {user_id} 在过去 {window_minutes} 分钟内戳了一共 {poke_count} 次")
        block_until = self._get_block_until(user_id)
        if block_until > now_ts:
            logger.info(f"用户 {user_id} 戳一戳处于屏蔽中，剩余 {int(block_until - now_ts)} 秒")
            return True, False
        if poke_count >= max_pokes:
            self._set_block_until(user_id, now_ts + block_seconds)
            logger.info(
                f"用户 {user_id} 触发戳一戳屏蔽: 计数={poke_count}, "
                f"窗口={window_minutes}分钟, 屏蔽={block_minutes}分钟"
            )
            return False, True
        return False, False

    async def execute(self, message: MaiMessages | None) -> Tuple[bool, bool, str | None, None, None]:
        """执行戳一戳消息事件处理"""
        enable_poke_reply = self.get_config("qq_poke_plugin.enable_poke_reply", False)
        enable_poke_back = self.get_config("qq_poke_plugin.enable_poke_back", False)
        if not enable_poke_back and not enable_poke_reply:
            return True, True, "戳一戳消息回复和回戳均未启用", None, None
        if not message:
            return True, True, "message 不存在", None, None
        raw_message = getattr(message, "raw_message", None)
        if not raw_message:
            return True, True, "raw_message 不存在", None, None
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
        # 检查是否在黑名单中
        if self._is_blacklisted(user_id):
            logger.info(f"用户 {user_id} 在戳一戳响应黑名单中，跳过响应")
            return True, True, "用户在戳一戳响应黑名单中，跳过响应", None, None

        is_blocked, will_block_after = self._evaluate_poke_limit(user_id)
        if is_blocked:
            return True, True, "戳一戳已屏蔽，跳过响应", None, None

        person_id = person_api.get_person_id("qq", user_id)
        if not person_id:
            return False, True, "响应戳一戳失败: 无法获取用户信息", None, None
        person_name = await person_api.get_person_value(person_id, "person_name")
        if not person_name:
            return False, True, "响应戳一戳失败: 无法获取用户名称", None, None

        poke_back_prompt = ""
        if enable_poke_back:
            poke_back_probability = self.get_config("qq_poke_plugin.poke_back_probability", 1.0)
            if poke_back_probability < 1.0 and random.random() > poke_back_probability:
                enable_poke_back = False
            if enable_poke_back:
                poke_back_prompt = self.get_config("qq_poke_plugin.poke_back_prompt", "")
                logger.info(f"决定回戳 {person_name} (概率设定: {poke_back_probability})")
            else:
                poke_back_prompt = self.get_config("qq_poke_plugin.poke_no_back_prompt", "")
                logger.info(f"决定不回戳 {person_name} (概率设定: {poke_back_probability})")

        if enable_poke_reply:
            poke_reply_probability = self.get_config("qq_poke_plugin.poke_reply_probability", 1.0)
            # 决定是否回复戳一戳 若即将被屏蔽则不进行概率判断，确保回复最后一次戳一戳
            if will_block_after and poke_reply_probability > 0.0:
                logger.info(f"用户 {person_name} 即将被屏蔽戳一戳响应，强制回复本次戳一戳消息")
            elif poke_reply_probability < 1.0 and random.random() > poke_reply_probability:
                logger.info(f"决定不回复 {person_name} 的戳一戳消息 (概率设定: {poke_reply_probability})")
                enable_poke_reply = False


        # 使用表达器生成回复
        try:
            reply_reason = f"{person_name}{message.plain_text}。"
            logger.info(f"接收到戳一戳消息: {reply_reason}")
            if enable_poke_reply:
                poke_reply_prompt = self.get_config("qq_poke_plugin.poke_reply_prompt")
                extra_info = f"{reply_reason}{poke_reply_prompt}"
                if poke_back_prompt:
                    extra_info += f"\n{poke_back_prompt}"
                if will_block_after:
                    block_minutes = self.get_config("qq_poke_plugin_guard.poke_limit_block_minutes", 0)
                    block_prompt = self._format_block_prompt(person_name, block_minutes)
                    if block_prompt:
                        extra_info += f"\n{block_prompt}"
                        reply_reason += f"{block_prompt}"
                logger.debug(f"生成戳一戳回复使用的额外上下文信息: {extra_info}")
                # 调用表达器生成回复
                result_status, data = await generator_api.generate_reply(
                    chat_id=message.stream_id,
                    reply_reason=reply_reason,
                    enable_chinese_typo=False,
                    extra_info=extra_info,
                    reply_time_point=time.time(),
                )
                if result_status and data and data.reply_set and data.reply_set.reply_data:
                    # 发送生成的回复
                    for reply_seg in data.reply_set.reply_data:
                        send_data = reply_seg.content
                        await self.send_text(message.stream_id, send_data, storage_message=True)
                        await asyncio.sleep(0.2)  # 避免消息发送过快顺序错乱
                else:
                    logger.warn("戳一戳回复生成失败，跳过发送回复")
            if enable_poke_back:
                display_message = f"[戳一戳消息: {global_config.bot.nickname}(你) 戳了戳 {person_name}]"
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
