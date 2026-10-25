"""
【手机号工具】——候选人端的账号就是手机号，格式必须统一

两个函数：
  normalize_phone：把用户输入的各种写法（带空格、带 +86、带横线）洗成 11 位数字
  is_valid_phone ：判断是不是合法的中国大陆手机号
"""
import re

# 中国大陆手机号：1 开头，第二位 3-9，共 11 位
PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


def normalize_phone(raw: str | None) -> str | None:
    """把手机号洗成纯 11 位数字；空值返回 None。

    能处理：'138 0013 8000'、'138-0013-8000'、'+8613800138000'、'8613800138000'
    """
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "").replace("-", "").replace("－", "")
    if not s:
        return None
    if s.startswith("+86"):
        s = s[3:]
    elif s.startswith("86") and len(s) == 13:
        s = s[2:]
    return s


def is_valid_phone(phone: str | None) -> bool:
    """是不是合法手机号（必须是 normalize 之后的值）。"""
    return bool(phone and PHONE_RE.match(phone))
