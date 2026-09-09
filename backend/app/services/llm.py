"""
【这个文件是干什么的？】
负责「跟 AI 说话」——把我们的问题发给大模型，把它的回答拿回来。

现在国内外主流大模型（GLM、Qwen、DeepSeek、OpenAI…）的接口格式基本一样，都叫「OpenAI 兼容格式」：
  往 <base_url>/chat/completions 这个网址 POST 一段 JSON，里面写：用哪个模型、说了什么话。
  它回一段 JSON，回答藏在 choices[0].message.content 里。
所以我们只写一套代码，用户在设置页填不同的网址和密钥，就能换不同的 AI。

这个文件不关心「问什么」，只负责「怎么发、怎么收、收到的 JSON 怎么解析」。问什么在 ai_screen.py 里。
"""
import json
import re

import httpx

from app.models import AiApiConfig

REQUEST_TIMEOUT = 90.0  # 最多等 AI 90 秒，再不回就放弃（AI 有时候想得慢）


class LlmError(Exception):
    """跟 AI 说话过程中的任何问题（网络不通、它回了乱码…）都抛这个错。"""

    pass


def completions_url(base_url: str) -> str:
    """把用户填的网址整理成完整的接口地址。

    用户可能填 https://xxx.com/v1  也可能填 https://xxx.com/v1/  也可能直接填全 .../chat/completions，
    这里统一处理：去掉结尾多余的斜杠，缺 /chat/completions 就补上。
    """
    url = base_url.strip().rstrip("/")
    if not url.endswith("/chat/completions"):
        url += "/chat/completions"
    return url


async def chat(cfg: AiApiConfig, system_prompt: str, user_prompt: str) -> str:
    """发一轮对话给 AI，返回它回答的文字。

    async 的意思是「异步」：等 AI 回话的这几秒钟，程序可以先去干别的（比如同时问另一个 AI），
    而不是傻等。批量筛简历时把好几份一起发出去，就是靠它。

    system_prompt：给 AI 的「人设」——你是谁、要守什么规矩
    user_prompt  ：具体的问题——岗位列表 + 简历内容 + 要它怎么回答
    """
    payload = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,  # 「温度」越低回答越稳定、越少发挥；筛简历要的是稳定判断，所以调低
    }
    headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}  # 出示门票
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            resp = await client.post(completions_url(cfg.base_url), json=payload, headers=headers)
    except httpx.HTTPError as e:
        # 网络层面的问题：连不上、超时、DNS 解析失败……
        raise LlmError(f"[{cfg.name}] 请求失败：{e.__class__.__name__}") from e
    if resp.status_code >= 400:
        # 对方回了错误码：401 密钥错、429 调太频繁被限流、500 它自己坏了……只截前 200 字避免刷屏
        raise LlmError(f"[{cfg.name}] HTTP {resp.status_code}：{resp.text[:200]}")
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise LlmError(f"[{cfg.name}] 响应格式异常：{resp.text[:200]}") from e


# 正则：匹配开头的 ```json 或 ``` 以及结尾的 ```，用来剥掉 AI 爱加的「代码围栏」
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def parse_json_object(content: str) -> dict:
    """把 AI 回的文字变成 Python 字典。

    我们明明让它「只输出 JSON」，但 AI 经常不听话，会加 ```json 围栏、前面加一句「好的，结果如下：」……
    这里做三层容错：① 剥围栏直接解析 → ② 失败就用正则从文字里挖出第一个 {…} 再解析 → ③ 还不行就报错。
    """
    cleaned = _FENCE.sub("", content.strip())
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)  # DOTALL 让 . 也能匹配换行，跨行的 JSON 才挖得出来
        if not m:
            raise LlmError(f"模型未返回 JSON：{content[:200]}")
        try:
            obj = json.loads(m.group(0))
        except json.JSONDecodeError as e:
            raise LlmError(f"模型返回的 JSON 无法解析：{content[:200]}") from e
    if not isinstance(obj, dict):
        raise LlmError("模型返回的不是 JSON 对象")
    return obj
