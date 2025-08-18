from astrbot.api.all import *
from astrbot.api.event.filter import command, permission_type, event_message_type, EventMessageType, PermissionType
import json
import logging
import os
import requests

logger = logging.getLogger("CustomCommandPlugin")

@register("自定义回复插件", "Varrge", "关键词回复插件", "1.1.0", "https://github.com/KiritoLifeF/AstrBot_CustomCommand")
class CustomCommandPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # 确保插件日志能在控制台输出（即使宿主已配置 logging）
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            _handler = logging.StreamHandler()
            _handler.setFormatter(logging.Formatter("[%(levelname)s] %(asctime)s %(name)s: %(message)s"))
            logger.addHandler(_handler)
        # 为避免重复输出，保持向上冒泡为 False（因为我们自己加了 handler）
        logger.propagate = False

        # 修复：手动创建插件数据目录
        plugin_data_dir = os.path.join("data", "plugins", "astrbot_plugin_custom_command")
        os.makedirs(plugin_data_dir, exist_ok=True)
        self.config_path = os.path.join(plugin_data_dir, "custom_command_config.json")
        self.command_map = self._load_config()
        self.api_token = self._load_token()
        logger.info(f"配置文件路径：{self.config_path}")
        # 白名单配置
        self.plugin_data_dir = os.path.join("data", "plugins", "astrbot_plugin_custom_command")
        self.whitelist_path = os.path.join(self.plugin_data_dir, "whitelist.json")
        self.whitelist_enabled = True  # 默认开启白名单策略
        self.whitelist = self._load_whitelist()
        # 新增：多令牌支持
        self.tokens_path = os.path.join(plugin_data_dir, "api_tokens.json")
        self.token_list = self._load_tokens()

    def _load_config(self) -> dict:
        """加载本地配置文件，并修正 JSON 导致的 key 类型问题（如 code_map 的整型被转成字符串）。"""
        try:
            if not os.path.exists(self.config_path):
                return {}
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 兼容：把 post_api 的 code_map 的键从 str 恢复为 int
            if isinstance(data, dict):
                for _, v in data.items():
                    if isinstance(v, dict) and v.get("type") == "post_api":
                        cmap = v.get("code_map")
                        if isinstance(cmap, dict):
                            fixed = {}
                            for kk, vv in cmap.items():
                                try:
                                    fixed[int(kk)] = vv
                                except Exception:
                                    # 无法转为 int 的键保持原样
                                    fixed[kk] = vv
                            v["code_map"] = fixed
            return data
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

    def _load_tokens(self) -> list[str]:
        """加载API令牌列表，兼容旧版单令牌文件"""
        try:
            # 优先读取新文件
            if os.path.exists(self.tokens_path):
                with open(self.tokens_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                lst = data.get("tokens", [])
                return [str(x) for x in lst if str(x).strip() != ""]

            # 回落：如果旧的单令牌存在，则用作索引0
            if hasattr(self, "api_token") and self.api_token:
                return [self.api_token]
            token_path = os.path.join("data", "plugins", "astrbot_plugin_custom_command", "api_token.json")
            if os.path.exists(token_path):
                with open(token_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tok = data.get("token", "")
                return [tok] if tok else []
            return []
        except Exception as e:
            logger.error(f"API令牌列表加载失败: {str(e)}")
            return []

    def _save_tokens(self):
        """保存API令牌列表到新文件"""
        try:
            os.makedirs(os.path.dirname(self.tokens_path), exist_ok=True)
            with open(self.tokens_path, "w", encoding="utf-8") as f:
                json.dump({"tokens": self.token_list}, f, ensure_ascii=False, indent=2)
            logger.info("API令牌列表保存成功")
        except Exception as e:
            logger.error(f"API令牌列表保存失败: {str(e)}")

    def _load_whitelist(self) -> set:
        """加载白名单，存为字符串集合"""
        try:
            if not os.path.exists(self.whitelist_path):
                return set()
            with open(self.whitelist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 存为字符串集合，避免类型不一致
                return set(str(x) for x in data.get("ids", []))
        except Exception as e:
            logger.error(f"白名单加载失败: {str(e)}")
            return set()

    def _save_whitelist(self):
        """保存白名单到文件"""
        try:
            os.makedirs(self.plugin_data_dir, exist_ok=True)
            with open(self.whitelist_path, "w", encoding="utf-8") as f:
                json.dump({"ids": sorted(self.whitelist)}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"白名单保存失败: {str(e)}")

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

    def _request_api(self, method: str, endpoint: str, payload: dict | None = None, token_index: int | None = None):
        """统一的HTTP请求方法，支持按索引选择令牌。返回 (ok: bool, message: str, status_code: int|None)"""
        # 选择令牌：优先使用传入索引；否则回退到列表的第0个；再回退到旧版 self.api_token
        token_to_use = None
        try:
            if token_index is not None:
                if isinstance(token_index, str):
                    token_index = int(token_index)
                if 0 <= token_index < len(self.token_list):
                    token_to_use = self.token_list[token_index]
        except Exception:
            pass
        if token_to_use is None and getattr(self, "token_list", None):
            if len(self.token_list) > 0:
                token_to_use = self.token_list[0]
        if token_to_use is None:
            token_to_use = self.api_token if getattr(self, "api_token", "") else None

        if not token_to_use:
            return False, "❌ API令牌未设置，请先使用“/tokenAdd”添加令牌（或 /设置API令牌 兼容旧版）。", None

        headers = {
            "Authorization": f"Bearer {token_to_use}",
            'Accept': 'Application/vnd.pterodactyl.v1+json',
            'Content-Type': 'application/json'
        }
        try:
            if method.upper() == "GET":
                response = requests.get(endpoint, headers=headers, timeout=10)
            else:
                response = requests.post(endpoint, headers=headers, json=(payload or {}), timeout=10)
            response.raise_for_status()
            try:
                result = response.json()
                return True, f"API响应（JSON）：\n{json.dumps(result, ensure_ascii=False, indent=2)}", response.status_code
            except Exception:
                return True, f"API响应（文本）：\n{response.text}", response.status_code
        except requests.HTTPError as e:
            status = getattr(e.response, 'status_code', None)
            text = None
            try:
                text = e.response.text if e.response is not None else None
            except Exception:
                pass
            msg = f"❌ 调用{method.upper()} API失败: {str(e)}"
            if text:
                msg += f"\n响应体：\n{text}"
            return False, msg, status
        except Exception as e:
            return False, f"❌ 调用{method.upper()} API失败: {str(e)}", None

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
        lines = []
        for i, (k, v) in enumerate(self.command_map.items()):
            if isinstance(v, dict):
                if v.get("type") == "get_api":
                    lines.append(f"{i + 1}. [GET] {k} -> {v.get('endpoint', '')} (token_idx={v.get('token_index', 0)})")
                elif v.get("type") == "post_api":
                    ep = v.get('endpoint', '')
                    payload = v.get('payload', {})
                    lines.append(
                        f"{i + 1}. [POST] {k} -> {ep}  payload={json.dumps(payload, ensure_ascii=False)} (token_idx={v.get('token_index', 0)})")
                else:
                    lines.append(f"{i + 1}. [未知类型] {k} -> {v}")
            else:
                lines.append(f"{i+1}. [文本] {k} -> {v}")
        msg = "当前关键词回复列表：\n" + "\n".join(lines)
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

    @command("添加白名单")
    @permission_type(PermissionType.ADMIN)
    async def add_whitelist(self, event: AstrMessageEvent, user_id: str):
        """/添加白名单 用户ID"""
        uid = str(user_id).strip()
        if not uid:
            yield event.plain_result("❌ 用户ID不能为空")
            return
        self.whitelist.add(uid)
        self._save_whitelist()
        yield event.plain_result(f"✅ 已加入白名单：{uid}")

    @command("删除白名单")
    @permission_type(PermissionType.ADMIN)
    async def remove_whitelist(self, event: AstrMessageEvent, user_id: str):
        """/删除白名单 用户ID"""
        uid = str(user_id).strip()
        if uid in self.whitelist:
            self.whitelist.remove(uid)
            self._save_whitelist()
            yield event.plain_result(f"✅ 已从白名单移除：{uid}")
        else:
            yield event.plain_result(f"ℹ️ 白名单中不存在：{uid}")

    @command("查看白名单")
    @permission_type(PermissionType.ADMIN)
    async def list_whitelist(self, event: AstrMessageEvent):
        """查看白名单列表"""
        if not self.whitelist:
            yield event.plain_result("白名单为空")
            return
        ids = "\n".join(sorted(self.whitelist))
        status = "开启" if self.whitelist_enabled else "关闭"
        yield event.plain_result(f"白名单（{status}）列表：\n{ids}")

    @command("白名单开关")
    @permission_type(PermissionType.ADMIN)
    async def toggle_whitelist(self, event: AstrMessageEvent, on_off: str = "开"):
        """/白名单开关 开|关（默认开）"""
        flag = str(on_off).strip().lower()
        if flag in ("开", "on", "true", "1"):
            self.whitelist_enabled = True
        elif flag in ("关", "off", "false", "0"):
            self.whitelist_enabled = False
        else:
            yield event.plain_result("❌ 参数仅支持：开/关")
            return
        yield event.plain_result(f"✅ 白名单已{'开启' if self.whitelist_enabled else '关闭'}")

    @command("设置API令牌")
    @permission_type(PermissionType.ADMIN)
    async def set_api_token(self, event: AstrMessageEvent, token: str):
        """/设置API令牌 令牌（兼容旧版；会追加到令牌列表末尾）"""
        self._save_token(token)
        self.api_token = token
        # 兼容：同时追加到多令牌列表
        self.token_list.append(token)
        self._save_tokens()
        yield event.plain_result("✅ API令牌已设置成功")

    @command("tokenAdd")
    @permission_type(PermissionType.ADMIN)
    async def token_add(self, event: AstrMessageEvent, token: str):
        """/tokenAdd 令牌 —— 将令牌追加到列表末尾"""
        t = str(token).strip()
        if not t:
            yield event.plain_result("❌ 令牌不能为空")
            return
        self.token_list.append(t)
        self._save_tokens()
        yield event.plain_result(f"✅ 令牌已添加。索引 = {len(self.token_list)-1}")

    @command("tokenDel")
    @permission_type(PermissionType.ADMIN)
    async def token_del(self, event: AstrMessageEvent, index: str):
        """/tokenDel 索引 —— 删除指定索引的令牌（0 开始）"""
        try:
            i = int(str(index).strip())
        except Exception:
            yield event.plain_result("❌ 索引必须是整数")
            return
        if i < 0 or i >= len(self.token_list):
            yield event.plain_result(f"❌ 索引越界：{i}（当前共有 {len(self.token_list)} 个令牌）")
            return
        self.token_list.pop(i)
        self._save_tokens()
        yield event.plain_result(f"✅ 已删除索引 {i} 的令牌")

    @command("tokenUpdate")
    @permission_type(PermissionType.ADMIN)
    async def token_update(self, event: AstrMessageEvent, index: str, token: str):
        """/tokenUpdate 索引 新令牌 —— 用新令牌覆盖指定索引"""
        try:
            i = int(str(index).strip())
        except Exception:
            yield event.plain_result("❌ 索引必须是整数")
            return
        if i < 0 or i >= len(self.token_list):
            yield event.plain_result(f"❌ 索引越界：{i}（当前共有 {len(self.token_list)} 个令牌）")
            return
        t = str(token).strip()
        if not t:
            yield event.plain_result("❌ 新令牌不能为空")
            return
        self.token_list[i] = t
        self._save_tokens()
        yield event.plain_result(f"✅ 已更新索引 {i} 的令牌")

    @command("tokenList")
    @permission_type(PermissionType.ADMIN)
    async def token_list(self, event: AstrMessageEvent):
        """查看令牌列表及索引（脱敏显示）"""
        if not getattr(self, "token_list", None):
            yield event.plain_result("当前没有任何令牌。请使用 /tokenAdd 添加。")
            return
        lines = []
        for i, tok in enumerate(self.token_list):
            masked = self._mask_token(tok)
            lines.append(f"{i}. {masked} (len={len(tok)})")
        msg = "令牌列表（索引从 0 开始）：\n" + "\n".join(lines)
        yield event.plain_result(msg)

    def _mask_token(self, tok: str) -> str:
        """对令牌做脱敏展示：保留前4后4，其余以*代替。"""
        if not isinstance(tok, str):
            tok = str(tok)
        n = len(tok)
        if n <= 8:
            return "*" * n
        return f"{tok[:4]}{'*' * (n - 8)}{tok[-4:]}"

    @command("调用API")
    async def call_api(self, event: AstrMessageEvent, keyword: str, endpoint: str, api_index: str):
        """/调用API 关键词 接口地址 API列表索引"""
        # 保存关键词与接口地址及令牌索引
        key = keyword.strip().lower()
        try:
            idx = int(str(api_index).strip())
        except Exception:
            yield event.plain_result("❌ API列表索引必须是整数")
            return
        self.command_map[key] = {"type": "get_api", "endpoint": endpoint, "token_index": idx}
        self._save_config(self.command_map)
        ok, msg, _status = self._request_api("GET", endpoint, token_index=idx)
        yield event.plain_result(msg)

    @command("调用POSTAPI")
    async def call_post_api(self, event: AstrMessageEvent, keyword: str, endpoint: str, api_index: str,
                            data_keys: str = "[]", data_values: str = "[]", resp_codes: str = "[]",
                            resp_texts: str = "[]"):
        """/调用POSTAPI 关键词 接口地址 API列表索引 数据键名[] 数据值[] 响应代码[] 对应响应代码回复[]"""
        # 保存关键词与接口地址（payload / code_map 稍后填充）
        key = keyword.strip().lower()
        try:
            idx = int(str(api_index).strip())
        except Exception:
            yield event.plain_result("❌ API列表索引必须是整数")
            return

        self.command_map[key] = {"type": "post_api", "endpoint": endpoint, "payload": None, "code_map": None,
                                 "token_index": idx}
        self._save_config(self.command_map)

        # 解析数据键名与数据值
        keys = self._parse_list_input(data_keys)
        values = self._parse_list_input(data_values)
        if len(keys) != len(values):
            yield event.plain_result(f"❌ 数据键名与数据值数量不一致：{len(keys)} != {len(values)}")
            return
        payload = {str(k): self._auto_cast(v) for k, v in zip(keys, values)}

        # 解析自定义响应代码与对应回复
        code_list = self._parse_list_input(resp_codes)
        text_list = self._parse_list_input(resp_texts)
        code_map = None
        if code_list or text_list:
            if len(code_list) != len(text_list):
                yield event.plain_result(f"❌ 响应代码与对应回复数量不一致：{len(code_list)} != {len(text_list)}")
                return
            tmp_map = {}
            for c, t in zip(code_list, text_list):
                c_val = self._auto_cast(c)
                try:
                    c_int = int(c_val)
                    tmp_map[c_int] = str(t)
                except Exception:
                    continue
            code_map = tmp_map if tmp_map else None

        # 持久化 payload 和 code_map
        self.command_map[key]["payload"] = payload
        self.command_map[key]["code_map"] = code_map
        self._save_config(self.command_map)

        ok, msg, status = self._request_api("POST", endpoint, payload, token_index=idx)
        if status is not None and code_map and status in code_map:
            yield event.plain_result(code_map[status])
            return
        yield event.plain_result(msg)

    def _get_event_text(self, event) -> str:
        """尽量从不同类型的 event/Context 中提取文本消息，兼容 message_str / get_message_str 等。"""
        # 1) 直接属性或可调用属性 message_str
        try:
            v = getattr(event, "message_str", None)
            if callable(v):
                v = v()
            if isinstance(v, str):
                return v
        except Exception:
            pass

        # 2) 常见的取文本方法/属性
        for name in ("get_message_str", "get_message_text", "get_text", "text"):
            try:
                attr = getattr(event, name, None)
                val = attr() if callable(attr) else attr
                if isinstance(val, str):
                    return val
            except Exception:
                continue

        # 3) event.message 以及其 text 字段
        try:
            msg = getattr(event, "message", None)
            if isinstance(msg, str):
                return msg
            if hasattr(msg, "text"):
                t = msg.text
                if isinstance(t, str):
                    return t
        except Exception:
            pass

        return ""

    def _get_sender_id(self, event):
        """兼容不同 event/Context 的取发送者ID方法。"""
        # 优先使用统一方法
        try:
            fn = getattr(event, "get_sender_id", None)
            if callable(fn):
                return fn()
        except Exception:
            pass

        # 常见属性名尝试
        for name in ("sender_id", "user_id", "uid"):
            try:
                v = getattr(event, name, None)
                if v is not None:
                    return v
            except Exception:
                continue

        # 兼容 sender 对象
        try:
            sender = getattr(event, "sender", None)
            if sender is not None:
                for n in ("id", "user_id", "uid"):
                    if hasattr(sender, n):
                        return getattr(sender, n)
        except Exception:
            pass

        return None

    @event_message_type(EventMessageType.ALL)
    async def handle_message(self, event: AstrMessageEvent):
        raw = self._get_event_text(event)
        msg = (raw or "").strip().lower()
        print(f"[DEBUG] 收到消息: {msg}")
        # 白名单校验：仅当开启时才限制自动回复
        if self.whitelist_enabled:
            print(f"[DEBUG] 白名单已开启，正在检查发送者ID...")
            sid = self._get_sender_id(event)
            print(f"[DEBUG] 发送: {sid}")
            if sid is None or str(sid) not in self.whitelist:
                print(f"[DEBUG] 发送者不在白名单内，忽略消息")
                # 不在白名单则直接忽略，不打扰用户
                return
        v = self.command_map.get(msg)
        print(f"[DEBUG] 匹配到的关键词映射: {v}")
        if v is None:
            print(f"[DEBUG] 尝试模糊匹配...")
            # 模糊匹配文本回复（兼容旧逻辑）
            for keyword, reply in self.command_map.items():
                if isinstance(reply, str) and keyword in msg:
                    print(f"[DEBUG] 模糊匹配成功: {keyword} -> {reply}")
                    yield event.plain_result(reply)
                    return
            return

        # 命中精确关键词，类型: {type(v)}
        print(f"[DEBUG] 命中精确关键词，类型: {type(v)}")
        if isinstance(v, dict):
            vtype = v.get("type")
            if vtype == "get_api":
                print(f"[DEBUG] 调用 {vtype.upper()} 接口: {v.get('endpoint', '')}")
                ok, out, _status = self._request_api("GET", v.get("endpoint", ""), token_index=v.get("token_index"))
                yield event.plain_result(out)
                return
            if vtype == "post_api":
                print(f"[DEBUG] 调用 {vtype.upper()} 接口: {v.get('endpoint', '')}")
                ok, out, status = self._request_api("POST", v.get("endpoint", ""), v.get("payload") or {}, token_index=v.get("token_index"))
                code_map = v.get("code_map") or {}
                try:
                    status_int = int(status) if status is not None else None
                except Exception:
                    status_int = None
                if status_int is not None and status_int in code_map:
                    yield event.plain_result(code_map[status_int])
                else:
                    yield event.plain_result(out)
                return
            # 未知类型，回退为文本
            yield event.plain_result(str(v))
            return

        # 兼容旧版：纯文本回复
        if isinstance(v, str):
            print(f"[DEBUG] 返回纯文本回复: {v}")
            yield event.plain_result(v)
            return

        # 其他类型（理论不存在）
        yield event.plain_result(str(v))