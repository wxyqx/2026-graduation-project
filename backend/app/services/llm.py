"""调用用户自配的 OpenAI 兼容 chat/completions 接口（GLM / Qwen / DeepSeek 等）。"""
import json
import re

import httpx

from app.models import AiApiConfig

REQUEST_TIMEOUT = 90.0


class LlmError(Exception):
    pass


def completions_url(base_url: str) -> str:
    url = base_url.strip().rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    return url


async def chat(cfg: AiApiConfig, system_prompt: str, user_prompt: str) -> str:
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(completions_url(cfg.base_url), json=payload, headers=headers)
    except httpx.HTTPError as e:
        raise LlmError(f"[{cfg.name}] 请求失败：{e.__class__.__name__}") from e
    if resp.status_code >= 400:
        raise LlmError(f"[{cfg.name}] HTTP {resp.status_code}：{resp.text[:200]}")
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise LlmError(f"[{cfg.name}] 响应格式异常：{resp.text[:200]}") from e


_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def parse_json_object(content: str) -> dict:
    """容忍 ```json 围栏与前后杂讯，提取第一个 JSON 对象。"""
    cleaned = _FENCE.sub("", content.strip())
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not m:
            raise LlmError(f"模型未返回 JSON：{content[:200]}")
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise LlmError(f"模型返回的 JSON 无法解析：{content[:200]}") from e
    if not isinstance(obj, dict):
        raise LlmError("模型返回的不是 JSON 对象")
    return obj
