"""
【这个文件是干什么的？】——AI 筛选的「提示词工厂」+「回答翻译官」

两件事：

一、拼提示词（build_messages）
   每次筛简历，要发给 AI 两段话：
     · 系统消息（system）= 人设 + 你在设置页写的筛选规则 + 铁律（只输出 JSON）
     · 用户消息（user）  = 岗位信息 + 简历内容 + 要它做的判断 + 规定的回答格式
   其中**回答格式由系统锁定**，你改不了——因为格式一乱，程序就读不懂它的回答（这正是之前
   「AI 回答通过、系统却说看不懂」的根源）。你能改的是「筛选规则」那部分。

二、翻译 AI 的回答（normalize_result / pick_position_id / extract_json）
   AI 不像程序那么听话：让它回 pass，它可能回「通过」「合格」「是」「true」「1」；
   让 position_id 回数字，它可能回 "1"、"1.0"、"岗位1"、甚至岗位名字。
   这个文件负责把这些五花八门的写法翻译成程序能懂的值。
"""

import json
import re

from app.models import Position

# ======================================================================
# 一、提示词
# ======================================================================

# 默认筛选规则（你在设置页没写规则时用这个）
DEFAULT_RULES = (
    "按岗位要求逐条比对候选人的技能、经验年限、项目经历，判断是否符合。\n"
    "经验、技能明显不足，或方向不符的，判为不通过。"
)

# 系统锁定：铁律 + 回答格式。这部分**不允许用户改**，否则解析不了。
FORMAT_RULES = (
    "【必须遵守的回答铁律】\n"
    "1. 你的回复必须且只能是一个 JSON 对象，不要输出任何解释、前后缀、markdown 代码块标记。\n"
    '2. 对象必须包含四个键：name（候选人姓名，字符串）、position_id（岗位编号，整数或 null）、'
    'result（只能是字符串 "pass" 或 "fail"）、reason（判断理由，不超过 120 字）。\n'
    '3. result 只能是 "pass" 或 "fail" 这两个英文单词之一，不要写「通过」「合格」等中文，'
    "不要写 true/false。\n"
    "4. 示例（仅供格式参考）："
    '{"name": "张三", "position_id": 1, "result": "pass", "reason": "5年Java经验，符合岗位要求"}'
)

SYSTEM_HEAD = "你是一名专业的招聘助理，负责阅读候选人简历并根据岗位要求做初步筛选。"


def build_system_prompt(user_rules: str | None) -> str:
    """组装系统消息：人设 + 你的筛选规则 + 回答铁律。"""
    rules = (user_rules or "").strip() or DEFAULT_RULES  # 没写规则就用默认的
    return f"{SYSTEM_HEAD}\n\n【筛选规则】\n{rules}\n\n{FORMAT_RULES}"


def positions_block(positions: list[Position], extras: dict[str, str] | None = None) -> str:
    """把岗位整理成 JSON 文字给 AI。带上负责人，方便区分同名岗位。

    extras：各岗位的额外限制（前端浏览器本地存的，不入库），形如 {"1": "只要985"}。
    """
    extras = extras or {}
    rows = []
    for p in positions:
        row = {
            "id": p.id,
            "name": p.position_name or "",
            "owner": p.owner or "",  # 负责人：同名岗位靠它区分
            "requirements": (p.position_requirements or "")[:2000],  # 与数据库列长一致，不再截到 1500
        }
        extra = (extras.get(str(p.id)) or "").strip()
        if extra:
            row["extra"] = extra[:500]  # 附加条件，AI 必须同样满足
        rows.append(row)
    return json.dumps(rows, ensure_ascii=False, indent=1)


def build_user_prompt(
    positions_block_text: str,
    resume_text: str,
    *,
    fixed_position: Position | None = None,
    resume_chars: int = 8000,
    strict: bool = False,
) -> str:
    """组装用户消息：岗位信息 + 简历 + 任务 + 格式要求。

    fixed_position：如果用户在界面上已经选好了岗位，就传进来——这时提示词只给这一个岗位，
                    并明确告诉 AI「岗位已指定，你只需判断是否符合」，不用它去挑岗位。
    strict        ：重试时用更严厉的措辞，逼它按格式回答。
    """
    if fixed_position is not None:
        # ---- 指定岗位模式：只给一个岗位，不让 AI 挑 ----
        job_part = (
            "## 已指定的应聘岗位（你在判断是否匹配时只看这一个岗位）\n"
            f"{positions_block_text}\n\n"
            "## 简历内容\n"
            f"{resume_text[:resume_chars]}\n\n"
            "## 任务\n"
            "1. 识别候选人姓名，填入 name；确实无法识别时填空字符串。\n"
            f"2. 岗位已由使用者指定为编号 {fixed_position.id}（{fixed_position.position_name}），"
            f"position_id 一律填 {fixed_position.id}，不要改动、不要选别的岗位。\n"
            '3. 严格依据该岗位的 requirements 判断 result 为 "pass" 或 "fail"，'
            "并在 reason 中用不超过 120 字说明理由。\n"
            "4. 若岗位带 extra 字段（额外硬性限制），必须同时满足 extra 才算 pass；"
            "违反任何一条一律 fail，并在 reason 中指出违反了哪一条。"
        )
    else:
        # ---- 自动模式：让 AI 从岗位里挑，但标准收紧 ----
        job_part = (
            "## 在招岗位列表（JSON）\n"
            f"{positions_block_text}\n\n"
            "## 简历内容\n"
            f"{resume_text[:resume_chars]}\n\n"
            "## 任务\n"
            "1. 识别候选人姓名，填入 name；确实无法识别时填空字符串。\n"
            "2. 判断这份简历应聘的是哪个岗位，把该岗位的 id 填入 position_id。\n"
            "   判断标准（务必从严）：\n"
            "   · 简历里如果直接写了应聘/期望岗位，以它为准，在列表里找对应的那个；\n"
            "   · 否则只有在一份简历的技术方向**明显对应**某个岗位时才选它；\n"
            "   · 如果方向只是沾边、或与所有岗位都不明显对应，position_id 一律填 null。"
            "**宁可不匹配，也不要硬凑一个最接近的岗位。**\n"
            '3. 匹配到岗位时，严格依据该岗位的 requirements 判断 result 为 "pass" 或 "fail"，'
            "并在 reason 中用不超过 120 字说明理由（未匹配岗位时 reason 说明为什么都不匹配）。\n"
            "4. 若该岗位带 extra 字段（额外硬性限制），必须同时满足 extra 才算 pass；"
            "只要违反 extra 中任何一条，一律判 fail，并在 reason 中指出违反了哪一条。"
        )

    strict_note = (
        "\n\n再强调一次：只输出一个 JSON 对象，result 只能是 \"pass\" 或 \"fail\"（英文），"
        "不要加任何解释文字或代码块标记。"
        if strict
        else ""
    )
    return job_part + strict_note


# ======================================================================
# 二、AI 回答的容错解析
# ======================================================================

# 各种「通过/淘汰」的说法 → 统一成 pass / fail
_PASS_WORDS = {"pass", "passed", "通过", "合格", "符合", "是", "yes", "y", "true", "t", "1", "1.0", "√", "对"}
_FAIL_WORDS = {"fail", "failed", "淘汰", "不合格", "不符合", "否", "no", "n", "false", "f", "0", "0.0", "×", "错"}

# 字段别名：AI 可能用中文键名或别的叫法
_NAME_KEYS = ("name", "姓名", "候选人姓名", "candidate", "candidate_name")
_RESULT_KEYS = ("result", "是否通过", "通过与否", "结论", "conclusion", "判断", "筛选结果", "pass")
_POS_KEYS = ("position_id", "positionid", "position", "岗位id", "岗位编号", "岗位", "pos_id", "job_id")
_REASON_KEYS = ("reason", "理由", "原因", "说明", "comment", "备注", "评价")


def _first_key(obj: dict, keys: tuple[str, ...]):
    """按顺序找第一个存在的键，返回 (键名, 值)；都没有返回 (None, None)。键名比对忽略大小写。"""
    lower = {str(k).lower(): k for k in obj.keys()}
    for k in keys:
        if k in obj:
            return k, obj[k]
        if k.lower() in lower:
            real = lower[k.lower()]
            return real, obj[real]
    return None, None


def extract_json(content: str) -> dict:
    """从 AI 回的文字里抠出 JSON 对象。

    对付三种不听话的回答：
      ① 用 ```json 包起来的  → 剥掉围栏
      ② 前面加了「好的，结果如下：」→ 从第一个 { 开始找
      ③ 后面还跟了废话        → 用「括号配对」精确找到对象结束的位置（不再抓到最后一个 }，那样会连带废话一起抓）
    """
    if not content or not content.strip():
        raise ValueError("AI 返回了空内容")
    text = content.strip()

    # ① 全局剥掉 markdown 代码围栏
    text = re.sub(r"```[a-zA-Z]*\n?|```", "", text).strip()

    # 先直接试
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
        raise ValueError("AI 返回的不是 JSON 对象")
    except json.JSONDecodeError:
        pass

    # ②③ 从第一个 { 起，按括号配对找完整的对象
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        pass
                    break  # 这个对象不合法，从下一个 { 再试
        start = text.find("{", start + 1)

    raise ValueError(f"没能从 AI 的回答里找到合法 JSON：{content[:200]}")


def normalize_result(raw) -> str | None:
    """把 AI 回的各种「通过/淘汰」写法统一成 'pass' / 'fail'；认不出返回 None。"""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return "pass" if raw else "fail"
    if isinstance(raw, (int, float)):
        if raw == 1:
            return "pass"
        if raw == 0:
            return "fail"
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    if s in _PASS_WORDS:
        return "pass"
    if s in _FAIL_WORDS:
        return "fail"
    # 含关键词的写法，例如 "pass（符合）"、"建议淘汰"、"3、通过"
    if any(w in s for w in ("pass", "通过", "合格", "符合要求")):
        return "pass"
    if any(w in s for w in ("fail", "淘汰", "不合格", "不符合")):
        return "fail"
    return None


def parse_position_id(raw) -> int | None:
    """把 AI 回的岗位编号/名称转成整数编号；转不出来返回 None。

    能处理：1、"1"、"1.0"、"id=1"、"岗位1"、"编号 1"、{"id":1}、"C++客户端开发工程师（初级）"
    """
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw) if raw.is_integer() else int(raw)
    if isinstance(raw, dict):  # {"id": 1}
        for k in ("id", "ID", "position_id", "岗位id", "编号"):
            if k in raw:
                return parse_position_id(raw[k])
        return None
    s = str(raw).strip()
    if not s:
        return None
    # 纯数字（含小数）
    m = re.fullmatch(r"(\d+)(?:\.0+)?", s)
    if m:
        return int(m.group(1))
    # 数字混在文字里：id=1 / 岗位1 / 编号 1 / 岗位编号：1
    m = re.search(r"(?:id|编号|岗位)\s*[:：=#]?\s*(\d+)", s, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # 任意位置出现的第一个整数
    m = re.search(r"(\d+)", s)
    if m:
        return int(m.group(1))
    return None


def pick_position(obj: dict, pos_map: dict[int, Position], fixed: Position | None = None) -> tuple[Position | None, str]:
    """决定这份简历该挂到哪个岗位。

    返回 (岗位对象或None, 用来说明的一句话)。
    规则：
      · 用户在界面指定了岗位（fixed）→ 直接用指定的，忽略 AI 的选择
      · 否则看 AI 回的 position_id；是数字就按编号找
      · 编号找不到 → 再按「岗位名称」精确匹配（同名取编号最小的那个）
      · 都不行 → None（未匹配）
    """
    if fixed is not None:
        return fixed, f"按指定岗位「{fixed.position_name}」建档"
        # 指定岗位模式：AI 返回什么岗位都不用管

    raw = _first_key(obj, _POS_KEYS)[1]
    pid = parse_position_id(raw)
    if pid is not None and pid in pos_map:
        return pos_map[pid], f"AI 匹配到岗位编号 {pid}"

    # 编号对不上，试试按名称匹配（有些模型习惯回岗位名）
    if isinstance(raw, str) and raw.strip():
        name = raw.strip()
        matches = [p for p in pos_map.values() if (p.position_name or "").strip() == name]
        if matches:
            target = min(matches, key=lambda p: p.id)  # 同名取编号最小的
            note = f"AI 按名称匹配到「{name}」" + ("（有同名岗位，取编号最小的）" if len(matches) > 1 else "")
            return target, note

    return None, "未匹配到在招岗位"


def parse_answer(content: str, pos_map: dict[int, Position], fixed: Position | None = None) -> dict:
    """把 AI 的回答一步到位翻译成程序要的东西。

    返回 {"name":..., "position":..., "result":..., "reason":..., "note":..., "obj":原始字典}
    其中 result 认不出时为 None（调用方据此判断要不要重试）。
    """
    obj = extract_json(content)
    name = str(_first_key(obj, _NAME_KEYS)[1] or "").strip()
    reason = str(_first_key(obj, _REASON_KEYS)[1] or "").strip()
    result = normalize_result(_first_key(obj, _RESULT_KEYS)[1])
    position, note = pick_position(obj, pos_map, fixed)
    return {"name": name, "position": position, "result": result, "reason": reason, "note": note, "obj": obj}
