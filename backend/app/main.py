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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text

from app.core.database import engine
from app.routers import ai_configs, ai_screen, applications, auth, candidates, export, positions, stats

# /docs 文档页上每个分组的中文说明
TAGS = [
    {"name": "auth", "description": "认证：注册 / 登录 / 当前用户"},
    {"name": "positions", "description": "岗位管理"},
    {"name": "candidates", "description": "候选人管理"},
    {"name": "applications", "description": "投递与 8 阶段流程（推进 / 撤回）"},
    {"name": "ai-configs", "description": "AI 接口配置（按登录用户隔离）"},
    {"name": "ai-screen", "description": "AI 智能录入（PDF / 纯文本 → 自动建档）"},
    {"name": "stats", "description": "统计总览"},
    {"name": "export", "description": "汇总导出（xlsx / csv）"},
]

app = FastAPI(
    title="ATS 招聘管理系统",
    version="0.2.0",
    description="""个人招聘管理系统的后端接口，全中文说明。**先读下面的上手指南，再往下点接口。**

## 🚀 三步上手

1. **注册**：展开「auth → POST /api/auth/register」→ 点 **Try it out** → 填用户名密码 → 点 **Execute** → 在最下面的 Response 里复制 `token` 那一串（引号不要带）。
2. **贴通行证**：点右上角灰色 **Authorize** 按钮 → 把 token 粘进去 → 点 Authorize → Close。全程只需做一次。
3. **随便试**：之后每个接口都能 Try it out 了。填好参数点 Execute，往下看 Server response 就是返回结果。

## 🎯 招聘流程：一条投递要闯 8 关

```
ai AI筛选 → resume 简历筛选 → contact 联系候选人 → phone 电话沟通
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
for r in (auth, positions, candidates, applications, ai_configs, ai_screen, stats, export):
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
<p>管理招聘：某个<b>候选人</b>投了某个<b>岗位</b>，生成一条<b>投递记录</b>，然后闯下面 8 关：</p>
<div class="flow">AI筛选 → 简历筛选 → 联系候选人 → 电话沟通 → 笔试 → 专业面 → HR面 → 终面<br>
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


@app.get("/api/health", tags=["auth"])
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
