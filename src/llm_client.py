"""
BidBuddy — 统一多模型 LLM 客户端
支持 DeepSeek / OpenAI / GLM / Moonshot / Qwen 五大提供商
"""
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List

import requests

logger = logging.getLogger("BidBuddy.LLM")

# ─── 模型注册表 ─────────────────────────────────────────────

@dataclass
class ModelInfo:
    """模型元信息"""
    id: str                          # 模型标识符
    name: str                        # 显示名称
    provider: str                    # 提供商
    base_url: str                    # API端点
    description: str = ""            # 简介
    icon: str = "🤖"                 # 图标
    max_tokens: int = 4096
    supports_system: bool = True     # 是否原生支持 system prompt（顶层）


# 完整模型注册表
MODEL_REGISTRY: Dict[str, ModelInfo] = {
    # ── DeepSeek ──
    "deepseek-chat": ModelInfo(
        id="deepseek-chat", name="DeepSeek Chat", provider="DeepSeek",
        base_url="https://api.deepseek.com/chat/completions",
        description="DeepSeek 通用对话模型，性价比极高", icon="🐋",
    ),
    "deepseek-v4-pro": ModelInfo(
        id="deepseek-v4-pro", name="DeepSeek V4 Pro", provider="DeepSeek",
        base_url="https://api.deepseek.com/chat/completions",
        description="DeepSeek 最新旗舰模型，推理能力最强", icon="🐋",
    ),
    # ── OpenAI ──
    "gpt-4o": ModelInfo(
        id="gpt-4o", name="GPT-4o", provider="OpenAI",
        base_url="https://api.openai.com/v1/chat/completions",
        description="OpenAI 最新多模态旗舰模型", icon="🧠",
    ),
    "gpt-4": ModelInfo(
        id="gpt-4", name="GPT-4", provider="OpenAI",
        base_url="https://api.openai.com/v1/chat/completions",
        description="OpenAI 经典高性能模型", icon="🧠",
    ),
    "gpt-3.5-turbo": ModelInfo(
        id="gpt-3.5-turbo", name="GPT-3.5 Turbo", provider="OpenAI",
        base_url="https://api.openai.com/v1/chat/completions",
        description="OpenAI 轻量快速模型", icon="⚡",
    ),
    # ── 智谱 GLM ──
    "glm-4": ModelInfo(
        id="glm-4", name="GLM-4", provider="智谱AI",
        base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        description="智谱最新旗舰大模型，中文能力突出", icon="🏮",
    ),
    "glm-4-flash": ModelInfo(
        id="glm-4-flash", name="GLM-4 Flash", provider="智谱AI",
        base_url="https://open.bigmodel.cn/api/paas/v4/chat/completions",
        description="智谱轻量快速模型，免费使用", icon="🏮",
    ),
    # ── 月之暗面 Moonshot ──
    "moonshot-v1-8k": ModelInfo(
        id="moonshot-v1-8k", name="Moonshot v1 8K", provider="月之暗面",
        base_url="https://api.moonshot.cn/v1/chat/completions",
        description="月之暗面长文本模型 8K", icon="🌙",
    ),
    "moonshot-v1-32k": ModelInfo(
        id="moonshot-v1-32k", name="Moonshot v1 32K", provider="月之暗面",
        base_url="https://api.moonshot.cn/v1/chat/completions",
        description="月之暗面长文本模型 32K", icon="🌙",
    ),
    # ── 通义千问 ──
    "qwen-turbo": ModelInfo(
        id="qwen-turbo", name="Qwen Turbo", provider="阿里云",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        description="通义千问极速轻量模型", icon="☁️",
    ),
    "qwen-plus": ModelInfo(
        id="qwen-plus", name="Qwen Plus", provider="阿里云",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        description="通义千问增强模型，平衡性能与速度", icon="☁️",
    ),
    "qwen-max": ModelInfo(
        id="qwen-max", name="Qwen Max", provider="阿里云",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        description="通义千问最强旗舰模型", icon="☁️",
    ),
}

# 按提供商分组的模型列表（供前端展示）
PROVIDERS = [
    {
        "name": "DeepSeek",
        "icon": "🐋",
        "color": "#4F46E5",
        "models": ["deepseek-chat", "deepseek-v4-pro"],
    },
    {
        "name": "OpenAI",
        "icon": "🧠",
        "color": "#10A37F",
        "models": ["gpt-4o", "gpt-4", "gpt-3.5-turbo"],
    },
    {
        "name": "智谱AI",
        "icon": "🏮",
        "color": "#E53E3E",
        "models": ["glm-4", "glm-4-flash"],
    },
    {
        "name": "月之暗面",
        "icon": "🌙",
        "color": "#805AD5",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k"],
    },
    {
        "name": "阿里云",
        "icon": "☁️",
        "color": "#FF6A00",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
    },
]


def get_model_list() -> List[Dict]:
    """获取前端可用的模型列表"""
    result = []
    for provider in PROVIDERS:
        provider_models = []
        for mid in provider["models"]:
            if mid in MODEL_REGISTRY:
                m = MODEL_REGISTRY[mid]
                provider_models.append({
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "icon": m.icon,
                })
        result.append({
            "provider": provider["name"],
            "icon": provider["icon"],
            "color": provider["color"],
            "models": provider_models,
        })
    result.append({
        "provider": "自定义",
        "icon": "🔧",
        "color": "#6B7280",
        "models": [{
            "id": "__custom__",
            "name": "自定义 API",
            "description": "使用任意 OpenAI 兼容的 API 端点",
            "icon": "🔧",
        }],
    })
    return result


# ─── LLM 统一客户端 ─────────────────────────────────────────

class LLMClient:
    """统一多模型 LLM 客户端"""

    def __init__(self, model_id: str = "deepseek-chat", api_key: str = "",
                 custom_url: str = "", log_callback: Callable = None):
        self.model_id = model_id
        self.api_key = api_key
        self.custom_url = custom_url
        self.log = log_callback or (lambda x: logger.info(x))

        # 解析模型信息
        if model_id == "__custom__":
            self.model_info = None
            self.base_url = custom_url
        else:
            self.model_info = MODEL_REGISTRY.get(model_id)
            self.base_url = self.model_info.base_url if self.model_info else custom_url

    def chat(self, messages: List[Dict], temperature: float = 0.3,
             max_tokens: int = 1024, timeout: int = 60) -> Optional[str]:
        """
        发送对话请求

        Args:
            messages: 标准 messages 列表 [{"role": "...", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大输出token
            timeout: 超时秒数

        Returns:
            AI 回复文本，失败返回 None
        """
        if not self.api_key:
            self.log("⚠️ 未配置 API Key")
            return None

        if not self.base_url:
            self.log("⚠️ 未配置 API 端点")
            return None

        model_name = self.model_id if self.model_id != "__custom__" else "custom"
        self.log(f"🤖 [{model_name}] 正在请求...")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        payload = {
            "model": model_name if model_name != "custom" else "gpt-3.5-turbo",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        for attempt in range(2):
            try:
                resp = requests.post(
                    self.base_url.rstrip('/'),
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = data['choices'][0]['message']['content']
                    self.log(f"✅ [{model_name}] 响应成功 ({len(content)} 字符)")
                    return content
                else:
                    error = resp.text[:200]
                    self.log(f"❌ [{model_name}] HTTP {resp.status_code}: {error}")
                    if attempt == 0:
                        time.sleep(1)

            except requests.exceptions.Timeout:
                self.log(f"⏰ [{model_name}] 请求超时")
                if attempt == 0:
                    time.sleep(2)
            except requests.exceptions.ConnectionError:
                self.log(f"🔌 [{model_name}] 连接失败")
                break
            except Exception as e:
                self.log(f"❌ [{model_name}] 异常: {str(e)[:100]}")
                break

        return None

    def parse_intent(self, user_input: str) -> Dict[str, Any]:
        """
        用 LLM 解析用户的自然语言意图

        输入示例：
        - "每天上午9点帮我查光伏巡检的招标信息"
        - "查一下风电项目的招标，排除大疆"
        - "立即搜索新能源无人机的招标公告"

        输出：
        {
            "keywords": "光伏,风电,新能源",
            "exclude": "大疆",
            "must_contain": "无人机",
            "schedule": "daily/09:00",  # 或 "immediate"
            "summary": "已理解：每天9点搜索光伏巡检相关招标"
        }
        """
        prompt = """你是一个招投标搜索助手。请解析用户意图，提取搜索参数。

返回纯JSON（不要markdown代码块）：
{
    "keywords": "逗号分隔的搜索关键词",
    "exclude": "需要排除的关键词（没有则为空字符串）",
    "must_contain": "必须包含的关键词（没有则为空字符串）",
    "schedule": "immediate 或 daily/HH:MM 或 hourly/MM 或 weekly/周几/HH:MM",
    "summary": "一句话概括你理解的任务（不超过30字）"
}

规则：
- keywords 提取招标相关的行业词、产品词
- schedule 默认为 "immediate"
- 如果用户说了"每天X点"→ "daily/HH:MM"
- 如果用户说了"每X分钟/小时"→ "hourly/MM"
- summary 要友好简洁"""

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_input}
        ]

        result = self.chat(messages, temperature=0.1, max_tokens=300)
        if not result:
            return self._fallback_parse(user_input)

        try:
            # 尝试提取JSON
            text = result.strip()
            if '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            if text.startswith('{'):
                parsed = json.loads(text)
                return {
                    "keywords": parsed.get("keywords", user_input),
                    "exclude": parsed.get("exclude", ""),
                    "must_contain": parsed.get("must_contain", ""),
                    "schedule": parsed.get("schedule", "immediate"),
                    "summary": parsed.get("summary", "已理解您的搜索需求"),
                }
        except json.JSONDecodeError:
            pass

        return self._fallback_parse(user_input)

    @staticmethod
    def _fallback_parse(user_input: str) -> Dict:
        """当LLM解析失败时的回退逻辑"""
        return {
            "keywords": user_input,
            "exclude": "",
            "must_contain": "",
            "schedule": "immediate",
            "summary": f"直接搜索：{user_input[:30]}",
        }

    def filter_bid(self, title: str, content: str = "",
                   keywords: str = "", context: str = "") -> Dict:
        """
        用 LLM 判断招标信息是否相关
        返回: {"relevant": bool, "reason": str}
        """
        prompt = f"""你是一个专业的招投标项目筛选专家。请判断以下招标信息是否与用户的搜索意图相关。

用户关注的关键词：{keywords}
{f'项目背景：{context}' if context else ''}

请判断该项目是否值得关注。

返回JSON：{{"relevant": true/false, "reason": "30字以内的判断理由"}}"""

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"标题：{title}\n内容：{content[:500]}"}
        ]

        result = self.chat(messages, temperature=0.1, max_tokens=200)
        if not result:
            return {"relevant": True, "reason": "AI未响应，默认保留"}

        try:
            text = result.strip()
            if '```' in text:
                text = text.split('```')[1].split('```')[0].strip()
            if '{' in text:
                start = text.find('{')
                end = text.rfind('}') + 1
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

        return {"relevant": True, "reason": "AI解析异常，默认保留"}

    def test_connection(self) -> Dict:
        """测试连接"""
        messages = [
            {"role": "user", "content": "你好，请用一句话回复：连接成功"}
        ]
        result = self.chat(messages, max_tokens=30, timeout=20)
        if result:
            return {"success": True, "message": result[:80]}
        return {"success": False, "message": "连接失败，请检查API Key和网络"}
