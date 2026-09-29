"""
【这个文件是干什么的？】——整个后端的「总开关」
运行命令 uvicorn app.main:app 时，就是从这里启动的。

它做的事很简单：
  1. 造一个 FastAPI 应用（app），写上名字和说明
  2. 允许前端网页（跑在 5173 端口）来访问（CORS）
  3. 把 routers/ 里 8 组接口全部挂上去
  4. 再加两个自己的小接口：首页说明、健康检查

自己不干业务活，只负责「把大家组装起来」。
"""
import inspect

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text

from app.core.database import engine
from app.routers import (
    ai_configs,
    ai_screen,
    applications,
    auth,
    candidates,
    export,
    interview,
    positions,
    settings,
    stats,
)

# /docs 文档页上每个分组的中文说明
TAGS = [
    {"name": "auth", "description": "认证：注册 / 登录 / 当前用户 / 个人信息"},
    {"name": "positions", "description": "岗位管理"},
    {"name": "candidates", "description": "候选人管理"},
    {"name": "applications", "description": "投递与 7 阶段流程（推进 / 撤回 / 各关原因与面试评价）"},
    {"name": "ai-configs", "description": "AI 接口配置（按登录用户隔离）"},
    {"name": "ai-screen", "description": "AI 智能录入（PDF / 纯文本 → 自动建档）"},
    {"name": "interview", "description": "面试评价（逐字稿 → 按固定模板出评价）"},
    {"name": "settings", "description": "系统设置（AI 筛选提示词）"},
    {"name": "stats", "description": "统计总览"},
    {"name": "export", "description": "汇总导出（xlsx / csv）"},
]

app = FastAPI(
    title="ATS 招聘管理系统",
    version="0.2.0",
    # docs_url=None：关掉 FastAPI 自带的 /docs 页面，下面用我们自己的（带中英对照翻译）替换它
    docs_url=None,
    redoc_url=None,
    description="""个人招聘管理系统的后端接口，全中文说明。**先读下面的上手指南，再往下点接口。**

## 🚀 三步上手

1. **注册**：展开「auth → POST /api/auth/register」→ 点 **Try it out** → 填用户名密码 → 点 **Execute** → 在最下面的 Response 里复制 `token` 那一串（引号不要带）。
2. **贴通行证**：点右上角灰色 **Authorize** 按钮 → 把 token 粘进去 → 点 Authorize → Close。全程只需做一次。
3. **随便试**：之后每个接口都能 Try it out 了。填好参数点 Execute，往下看 Server response 就是返回结果。

## 🎯 招聘流程：一条投递要闯 7 关

```
ai AI筛选 → resume 简历筛选 → phone 电话沟通
→ test 笔试 → pro 专业面 → hr HR面 → final 终面
```

- 每一关打一个分：**pass**（通过，进入下一关）或 **fail**（淘汰，流程结束）
- 最后一关 final 打 pass = **已录用** 🎉
- 打错分了？调「撤回」接口反悔；AI 筛选的理由记在 `ai_comment` 里

## ⚠️ 常见错误码（返回出错时看 detail 里的中文提示）

| 码 | 意思 | 怎么办 |
| :- | :--- | :--- |
| 400 | 参数不对 | 看 detail 说明，改成合法值 |
| 401 | 没登录 / token 过期 | 重新 login，重新 Authorize |
| 404 | 编号不存在 | 检查 id 是不是抄错了 |
| 409 | 冲突：重复注册 / 重复投递 / 手快点了两次 | 正常现象，换个操作 |
| 422 | 格式不对：必填没填、字数超限 | 看 details 里指出的字段 |

## 📚 想读懂代码？

打开 `backend/代码导读.md`，有 7 站阅读路线；每个 `.py` 文件开头都写着「这个文件是干什么的」。
""",
    openapi_tags=TAGS,
)

# CORS（跨域）：浏览器有个安全规矩——网页在 5173 端口，默认不许它去请求 8000 端口的接口。
# 这里明确告诉浏览器：这两个地址来的请求我认，放行。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],  # 只放行本机前端开发服务器
    allow_credentials=True,
    allow_methods=["*"],  # GET / POST / PUT / DELETE 都行
    allow_headers=["*"],  # 请求头随便带（Authorization 就在里面）
    expose_headers=["Content-Disposition", "X-Row-Count"],  # 允许前端读到这两个回应头（下载文件名、导出行数）
)

# 把 8 组接口全部挂上。每个 routers/xxx.py 里都有一个 router 变量
for r in (auth, positions, candidates, applications, ai_configs, ai_screen, interview, settings, stats, export):
    app.include_router(r.router)

# 把各接口的中文 docstring 提升为 /docs 里的摘要与描述
# （FastAPI 默认不会用函数第一行的文字做「标题」，这里手动补一下，/docs 才能一眼看到中文）
for route in app.routes:
    if not getattr(route, "include_in_schema", False) or getattr(route, "summary", None):
        continue
    doc = inspect.getdoc(getattr(route, "endpoint", None)) if hasattr(route, "endpoint") else None
    if doc:
        route.summary = doc.strip().splitlines()[0].strip().rstrip("。")
        route.description = doc.strip()


# ======================================================================
# 一、参数填错（422）时，把英文报错翻成中英对照
# ======================================================================
# FastAPI 发现你传的参数不合规（太短、没填、类型不对…）时，默认回一段英文 JSON。
# 这里接管它：英文原样保留（type / loc / msg），每条再加一个 msg_cn 中文解释。

# 字段英文名 → 中文名
FIELD_CN = {
    "username": "用户名",
    "password": "密码",
    "position_name": "岗位名称",
    "owner": "负责人",
    "position_requirements": "岗位要求",
    "name": "姓名 / 配置名称",
    "remark": "备注",
    "can_id": "候选人编号 can_id",
    "pos_id": "岗位编号 pos_id",
    "fromStage": "当前关卡 fromStage",
    "from_stage": "当前关卡 fromStage",
    "result": "本关结果 result",
    "toStage": "退回关卡 toStage",
    "to_stage": "退回关卡 toStage",
    "base_url": "接口网址 base_url",
    "api_key": "密钥 api_key",
    "model": "模型名 model",
    "is_enabled": "是否启用 is_enabled",
    "filters": "筛选条件 filters",
    "fields": "导出列 fields",
    "format": "文件格式 format",
    "start_date": "开始日期",
    "end_date": "结束日期",
    "stage": "关卡 stage",
    "status": "状态 status",
    "files": "上传文件 files",
    "texts": "简历文本 texts",
}


def _reason_cn(err: dict) -> str:
    """把 pydantic 的错误类型（英文代号）翻成一句中文。ctx 里有具体的数字（比如最少几个字）。"""
    t = err.get("type", "")
    ctx = err.get("ctx") or {}
    if t == "string_too_short":
        return f"太短了：至少要 {ctx.get('min_length')} 个字"
    if t == "string_too_long":
        return f"太长了：最多 {ctx.get('max_length')} 个字"
    if t == "missing":
        return "这是必填项，但你没有填"
    if t == "string_type":
        return "要填文字（加引号的字符串），不能是数字 / true / false"
    if t in ("int_parsing", "int_type"):
        return "要填一个整数（数字，不加引号）"
    if t == "bool_type" or t == "bool_parsing":
        return "只能填 true 或 false（不加引号）"
    if t == "date_from_datetime_parsing" or t.startswith("date_"):
        return "日期格式要像 2026-09-08 这样"
    if t == "json_invalid":
        return "JSON 格式写错了：检查引号、逗号、大括号是不是成对"
    if t == "model_attributes_type" or t == "dict_type":
        return "整体要传一个 JSON 对象——用花括号 { } 包起来的「键: 值」"
    if t == "list_type":
        return "要传一个列表——用方括号 [ ] 包起来"
    if t == "greater_than_equal":
        return f"不能小于 {ctx.get('ge')}"
    if t == "less_than_equal":
        return f"不能大于 {ctx.get('le')}"
    if t == "enum" or t == "literal_error":
        return f"只能填这几个值之一：{ctx.get('expected')}"
    return "没通过检查，请对照网页上这个字段旁边的中文说明"


def _jsonable(v):
    """把报错里可能出现的奇怪对象（上传文件、异常对象…）转成能放进 JSON 的普通值。"""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    return str(v)


@app.exception_handler(RequestValidationError)
async def validation_error_cn(request: Request, exc: RequestValidationError):
    """接管所有 422 参数错误，输出中英对照。"""
    detail = []
    for e in exc.errors():
        e = _jsonable(dict(e))
        e.pop("url", None)  # pydantic 附带的英文文档链接，对学习没帮助，去掉
        loc = list(e.get("loc", []))  # 位置，例：["body", "password"] = 请求内容里的 password
        where = loc[0] if loc else ""
        field = str(loc[-1]) if len(loc) > 1 else (str(loc[0]) if loc else "")
        prefix = {"body": "", "query": "网址参数 ", "path": "网址路径 "}.get(where, "")
        e["msg_cn"] = f"{prefix}{FIELD_CN.get(field, field)}：{_reason_cn(e)}"
        detail.append(e)
    return JSONResponse(
        status_code=422,
        content={
            "message": (
                "422 参数没填对。下面每条错误都是中英对照：msg 是英文原文，msg_cn 是中文解释，"
                "loc 告诉你是哪个字段（body = 请求内容里的），input 是你实际填的值"
            ),
            "count": len(detail),
            "detail": detail,
        },
    )


# ======================================================================
# 二、接口文档的「响应说明」区：OK / Created / Validation Error 翻成中英对照
# ======================================================================
RESPONSE_DESC_CN = {
    "OK": "OK 成功",
    "Created": "Created 创建成功",
    "No Content": "No Content 成功（没有内容要返回）",
    "Validation Error": "Validation Error 参数没填对（返回里每条都有 msg_cn 中文解释）",
    "Successful Response": "Successful Response 成功",
}


def custom_openapi():
    """生成接口文档的数据（/openapi.json），顺手把默认的英文响应说明改成中英对照。"""
    if app.openapi_schema:
        return app.openapi_schema
    spec = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=TAGS,
    )
    for path_item in spec.get("paths", {}).values():
        for op in path_item.values():
            for resp in op.get("responses", {}).values():
                d = resp.get("description")
                if d in RESPONSE_DESC_CN:
                    resp["description"] = RESPONSE_DESC_CN[d]
    app.openapi_schema = spec
    return spec


app.openapi = custom_openapi


# ======================================================================
# 三、自己的 /docs 页面：在官方 Swagger 页面上叠一层「中英对照」翻译
# ======================================================================
# Swagger UI 本身是英文的、没有中文包。做法：页面加载后，用一小段 JS 找到那些固定的英文词
# （Execute、Responses、Server response…），在后面补上中文。英文保留，方便对照学习。
DOCS_BANNER = """
<div style="font-family:'Microsoft YaHei',sans-serif;background:#ecf5ff;border-bottom:2px solid #409eff;
padding:10px 24px;font-size:14px;line-height:1.8;color:#333">
💡 <b>中文提示</b>：点接口名展开 → <b>Try it out 试一试</b> → 填参数（已有示例）→ <b>Execute 执行</b> → 往下看 <b>Server response 服务器实际返回</b>。
出错时先看返回里的 <b>msg_cn</b>（中文解释）；<b>msg</b> 是英文原文。页面上所有英文按钮、区块名都已配上中文对照。
</div>
"""

DOCS_I18N_SCRIPT = """
<script>
(function () {
  // 英文原词 → 「英文 中文」对照。英文保留在前面，方便认识这些词
  var MAP = {
    "Authorize": "Authorize 授权登录（粘 token）", "Logout": "Logout 退出登录", "Available authorizations": "Available authorizations 可用的登录方式",
    "Try it out": "Try it out 试一试", "Execute": "Execute 执行", "Clear": "Clear 清空",
    "Close": "Close 关闭", "Cancel": "Cancel 取消", "Copy": "Copy 复制", "Download": "Download 下载文件",
    "Hide": "Hide 收起", "Show": "Show 展开", "Loading...": "Loading... 加载中…",
    "Parameters": "Parameters 参数", "No parameters": "No parameters 不需要参数",
    "Request body": "Request body 请求内容（要发给后端的数据）", "Responses": "Responses 响应说明",
    "Curl": "Curl 命令（复制到终端也能调这个接口）", "Request URL": "Request URL 请求地址",
    "Server response": "Server response 服务器实际返回", "Code": "Code 状态码", "Details": "Details 说明",
    "Response body": "Response body 返回内容", "Response headers": "Response headers 返回头（附加信息）",
    "Schema": "Schema 字段结构", "Example Value": "Example Value 示例", "Media type": "Media type 数据格式",
    "Controls Accept header.": "Controls Accept header. 告诉后端你想要什么格式",
    "Schemas": "Schemas 数据模型（各接口的表格模板）", "Models": "Models 数据模型",
    "Name": "Name 名称", "Description": "Description 说明", "Links": "Links 链接", "No links": "No links 无",
    "required": "required 必填", "string": "string 文字", "integer": "integer 整数", "boolean": "boolean 真/假",
    "array": "array 列表", "object": "object 对象",
    "OK": "OK 成功", "Created": "Created 创建成功", "No Content": "No Content 成功（无内容）",
    "Validation Error": "Validation Error 参数没填对",
    "Bad Request": "Bad Request 400 参数不对", "Unauthorized": "Unauthorized 401 没登录 / 登录过期",
    "Not Found": "Not Found 404 编号不存在", "Conflict": "Conflict 409 重复 / 冲突",
    "Unprocessable Entity": "Unprocessable Entity 422 参数没填对（看返回里的 msg_cn）",
    "Internal Server Error": "Internal Server Error 500 服务器内部出错",
    "Undocumented": "Undocumented 未在文档里声明的状态码"
  };
  // 数据模型的类名 → 中文
  var SCHEMA = {
    "RegisterIn": "注册请求", "LoginIn": "登录请求", "TokenOut": "登录返回（含 token）", "UserOut": "用户信息",
    "PositionIn": "新建岗位", "PositionUpdate": "编辑岗位", "PositionOut": "岗位信息",
    "CandidateIn": "新建候选人", "CandidateUpdate": "改备注", "CandidateOut": "候选人信息",
    "ApplicationCreate": "新建投递", "AdvanceIn": "推进一关", "RevertIn": "撤回",
    "AiConfigIn": "新建 AI 配置", "AiConfigUpdate": "编辑 AI 配置", "AiConfigOut": "AI 配置信息",
    "ExportFilters": "导出筛选条件", "ExportIn": "导出请求",
    "HTTPValidationError": "参数校验错误", "ValidationError": "单条校验错误",
    "Body_intake_api_ai_screen_intake_post": "AI 录入的上传表单"
  };
  function walk() {
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    var n;
    while ((n = w.nextNode())) {
      var s = n.nodeValue.trim();
      if (!s) continue;
      var m = MAP[s] || (SCHEMA[s] ? s + "　" + SCHEMA[s] : null);
      // 执行后的实时结果里，出错行写成「Error: Unprocessable Entity」这种带前缀的形式，也要认得
      if (!m && s.indexOf("Error: ") === 0 && MAP[s.slice(7)]) m = "Error 出错: " + MAP[s.slice(7)];
      if (m) n.nodeValue = n.nodeValue.replace(s, m);   // 替换后含中文，下次不会再匹配到，不会重复追加
    }
  }
  var timer = null;
  // Swagger 页面是动态生成的，每次内容变化（展开接口、点执行）后再翻译一遍
  new MutationObserver(function () { clearTimeout(timer); timer = setTimeout(walk, 120); })
    .observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  walk();
})();
</script>
"""


@app.get("/docs", include_in_schema=False)
async def docs_cn():
    """接口文档页（中英对照版）。用 FastAPI 自带的 Swagger 页面，再叠上翻译脚本和中文提示条。"""
    page = get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="ATS 接口文档（中英对照）",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
    )
    html = page.body.decode("utf-8")
    if '<div id="swagger-ui">' in html:
        html = html.replace('<div id="swagger-ui">', DOCS_BANNER + '<div id="swagger-ui">', 1)
    else:
        html = html.replace("<body>", "<body>" + DOCS_BANNER, 1)
    html = html.replace("</body>", DOCS_I18N_SCRIPT + "</body>", 1)
    return HTMLResponse(html)


@app.get("/", include_in_schema=False)  # include_in_schema=False：这个页面不出现在 /docs 里
def home():
    """首页：一段中文说明，告诉打开的人「这是后端，不是系统界面」。"""
    return HTMLResponse(
        """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>ATS 招聘管理系统</title>
<style>body{font-family:"Microsoft YaHei",sans-serif;max-width:720px;margin:60px auto;padding:0 20px;color:#333;line-height:1.9}
h1{font-size:22px}h2{font-size:17px;margin-top:28px;border-left:4px solid #409eff;padding-left:10px}
.tip{background:#f0f9eb;border:1px solid #b3e19d;border-radius:8px;padding:12px 16px}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:6px 10px;font-size:14px;text-align:left}
a{color:#409eff}code{background:#f4f4f5;padding:2px 6px;border-radius:4px}
.flow{background:#f4f4f5;border-radius:8px;padding:10px 14px;font-family:monospace;font-size:14px}</style></head><body>
<h1>ATS 招聘管理系统 · 后端服务运行中 ✔</h1>
<p>数据库连接正常，接口就绪。</p>
<div class="tip"><b>提醒：你现在看到的不是系统界面。</b>这里是后端；能点能点的中文操作界面属于 M3/M4 前端，还没开始做。</div>

<h2>现在能干什么？</h2>
<p>打开 <a href="/docs">/docs 接口文档</a>——里面 28 个接口全部带中文教程：每个接口是干什么的、
参数每个格子填什么、返回什么、出错了是什么原因，照着填就能跑通。页面顶部还有「三步上手」指南。</p>

<h2>系统在管一件什么事？</h2>
<p>管理招聘：某个<b>候选人</b>投了某个<b>岗位</b>，生成一条<b>投递记录</b>，然后闯下面 7 关：</p>
<div class="flow">AI筛选 → 简历筛选 → 电话沟通 → 笔试 → 专业面 → HR面 → 终面<br>
（每关：pass 通过进下一关 / fail 淘汰结束；终面通过 = 已录用；打错可撤回）</div>

<h2>接口都有哪些？</h2>
<table>
<tr><th>分组</th><th>管什么</th></tr>
<tr><td>auth 认证</td><td>注册、登录、我是谁</td></tr>
<tr><td>positions 岗位</td><td>岗位的增删改查</td></tr>
<tr><td>candidates 候选人</td><td>候选人的新增、查询、改备注</td></tr>
<tr><td>applications 投递</td><td>投递列表、详情、推进一关、撤回</td></tr>
<tr><td>ai-configs AI 配置</td><td>添加/启用你自己的大模型接口</td></tr>
<tr><td>ai-screen AI 录入</td><td>传 PDF 简历，AI 识别姓名、匹配岗位、自动建档</td></tr>
<tr><td>stats 统计</td><td>各种计数（顶部状态栏、汇总页用）</td></tr>
<tr><td>export 导出</td><td>按条件导出 Excel / csv</td></tr>
</table>

<h2>想读懂代码？</h2>
<p>打开 <code>backend/代码导读.md</code>，有 7 站阅读路线；每个 <code>.py</code> 文件开头都写着「这个文件是干什么的」。</p>
</body></html>"""
    )


@app.get("/api/health", tags=["auth"], summary="健康检查：后端活着吗？数据库通吗？")
def health():
    """健康检查：后端活着吗？数据库通吗？

**干什么用**：前端一打开先问一声。不需要登录，随时可以点。

**返回什么**：
- 一切正常：`{"status": "ok", "database": "up"}`
- 数据库连不上：503，`{"status": "error", "database": "down"}` → 检查 MySQL 有没有启动、`.env` 里的密码对不对
"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # 最简单的 SQL，能跑通就说明数据库连着
        return {"status": "ok", "database": "up"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error", "database": "down"})  # 503 = 服务暂时不可用
