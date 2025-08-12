from astrbot.api.all import *
from astrbot.api.event.filter import command, permission_type, event_message_type, EventMessageType, PermissionType
import json
import logging
import os
import requests

logger = logging.getLogger("CustomCommandPlugin")

@register("自定义回复插件", "Varrge", "关键词回复插件", "1.0.1", "https://github.com/KiritoLifeF/AstrBot_CustomCommand")
class CustomCommandPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

        # 修复：手动创建插件数据目录
        plugin_data_dir = os.path.join("data", "plugins", "astrbot_plugin_custom_command")
        os.makedirs(plugin_data_dir, exist_ok=True)
        self.config_path = os.path.join(plugin_data_dir, "custom_command_config.json")
        self.command_map = self._load_config()
        self.api_token = self._load_token()
        logger.info(f"配置文件路径：{self.config_path}")

    def _load_config(self) -> dict:
        """加载本地配置文件"""
        try:
            if not os.path.exists(self.config_path):
                return {}
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"配置加载失败: {str(e)}")
            return {}

    def _save_config(self, data: dict):
        """保存配置到文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"配置保存失败: {str(e)}")

    def _load_token(self) -> str:
        """加载API令牌"""
        token_path = os.path.join("data", "plugins", "astrbot_plugin_custom_command", "api_token.json")
        try:
            if not os.path.exists(token_path):
                logger.info("API令牌文件不存在，返回空字符串")
                return ""
            with open(token_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                token = data.get("token", "")
                logger.info("API令牌加载成功")
                return token
        except Exception as e:
            logger.error(f"API令牌加载失败: {str(e)}")
            return ""

    def _save_token(self, token: str):
        """保存API令牌到文件"""
        token_path = os.path.join("data", "plugins", "astrbot_plugin_custom_command", "api_token.json")
        try:
            with open(token_path, "w", encoding="utf-8") as f:
                json.dump({"token": token}, f, ensure_ascii=False, indent=2)
            logger.info("API令牌保存成功")
        except Exception as e:
            logger.error(f"API令牌保存失败: {str(e)}")

    def _parse_list_input(self, raw: str) -> list:
        """
        将用户传入的“数组”解析为列表。
        支持两种形式：
        1) JSON 数组：如 '["a","b"]' 或 '[1,true]'
        2) 逗号分隔：如 'a,b,c' （会按字符串处理）
        空字符串或 '[]' 视为 []
        """
        if raw is None:
            return []
        s = str(raw).strip()
        if s == "" or s == "[]":
            return []
        # 优先尝试 JSON
        try:
            data = json.loads(s)
            if isinstance(data, list):
                return data
        except Exception:
            pass
        # 回退为逗号分隔
        parts = [p.strip() for p in s.split(",") if p.strip() != ""]
        return parts

    def _auto_cast(self, v):
        """
        对值做一次 JSON 反序列化尝试，能转成数字/布尔/null 就转，失败则原样字符串。
        """
        if isinstance(v, (int, float, bool)) or v is None:
            return v
        if not isinstance(v, str):
            return v
        try:
            return json.loads(v)
        except Exception:
            return v

    @command("添加自定义回复")
    @permission_type(PermissionType.ADMIN)
    async def add_reply(self, event: AstrMessageEvent, keyword: str, reply: str):
        """/添加自定义回复 关键字 内容"""
        self.command_map[keyword.strip().lower()] = reply
        self._save_config(self.command_map)
        yield event.plain_result(f"✅ 已添加关键词回复： [{keyword}] -> {reply}")

    @command("查看自定义回复")
    async def list_replies(self, event: AstrMessageEvent):
        """查看所有关键词回复"""
        if not self.command_map:
            yield event.plain_result("暂无自定义回复")
            return
        msg = "当前关键词回复列表：\n" + "\n".join(
            [f"{i+1}. [{k}] -> {v}" for i, (k, v) in enumerate(self.command_map.items())]
        )
        yield event.plain_result(msg)

    @command("删除自定义回复")
    @permission_type(PermissionType.ADMIN)
    async def delete_reply(self, event: AstrMessageEvent, keyword: str):
        """/删除自定义回复 关键字 """
        keyword = keyword.strip().lower()
        if keyword not in self.command_map:
            yield event.plain_result(f"❌ 未找到关键词：{keyword}")
            return
        del self.command_map[keyword]
        self._save_config(self.command_map)
        yield event.plain_result(f"✅ 已删除关键词：{keyword}")

    @command("设置API令牌")
    @permission_type(PermissionType.ADMIN)
    async def set_api_token(self, event: AstrMessageEvent, token: str):
        """/设置API令牌 令牌"""
        self._save_token(token)
        self.api_token = token
        yield event.plain_result("✅ API令牌已设置成功")

    @command("调用API")
    async def call_api(self, event: AstrMessageEvent, keyword: str, endpoint: str):
        """/调用API 关键词 接口地址"""
        # 保存关键词与接口地址的映射
        key = keyword.strip().lower()
        self.command_map[key] = endpoint
        self._save_config(self.command_map)
        if not self.api_token:
            yield event.plain_result("❌ API令牌未设置，请先使用“设置API令牌”命令设置令牌。")
            return
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            'Accept': 'Application/vnd.pterodactyl.v1+json',
            'Content-Type': 'application/json'
            }
        try:
            response = requests.get(endpoint, headers=headers, timeout=10)
            response.raise_for_status()
            try:
                result = response.json()
                yield event.plain_result(f"API响应（JSON）：\n{json.dumps(result, ensure_ascii=False, indent=2)}")
            except Exception:
                yield event.plain_result(f"API响应（文本）：\n{response.text}")
        except Exception as e:
            yield event.plain_result(f"❌ 调用API失败: {str(e)}")

    @command("调用POSTAPI")
    async def call_post_api(self, event: AstrMessageEvent, keyword: str, endpoint: str, data_keys: str = "[]", data_values: str = "[]"):
        """/调用POSTAPI 关键词 接口地址 数据键名[] 数据值[]"""
        # 保存关键词与接口地址的映射
        key = keyword.strip().lower()
        self.command_map[key] = endpoint
        self._save_config(self.command_map)
        if not self.api_token:
            yield event.plain_result("❌ API令牌未设置，请先使用“设置API令牌”命令设置令牌。")
            return

        # 解析数据键名与数据值
        keys = self._parse_list_input(data_keys)
        values = self._parse_list_input(data_values)
        if len(keys) != len(values):
            yield event.plain_result(f"❌ 数据键名与数据值数量不一致：{len(keys)} != {len(values)}")
            return
        payload = {str(k): self._auto_cast(v) for k, v in zip(keys, values)}

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            'Accept': 'Application/vnd.pterodactyl.v1+json',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            try:
                result = response.json()
                yield event.plain_result(f"API响应（JSON）：\n{json.dumps(result, ensure_ascii=False, indent=2)}")
            except Exception:
                yield event.plain_result(f"API响应（文本）：\n{response.text}")
        except Exception as e:
            yield event.plain_result(f"❌ 调用POST API失败: {str(e)}")

    @event_message_type(EventMessageType.ALL)
    async def handle_message(self, event: AstrMessageEvent):
        msg = event.message_str.strip().lower()
        if reply := self.command_map.get(msg):
            yield event.plain_result(reply)
            return
        for keyword, reply in self.command_map.items():
            if keyword in msg:
                yield event.plain_result(reply)
                return