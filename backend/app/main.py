from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text

from app.core.database import engine
from app.routers import ai_configs, ai_screen, applications, auth, candidates, export, positions, stats

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
    description=(
        "个人招聘管理系统后端。**除「认证」下的注册/登录与健康检查外，"
        "所有接口都需要先登录拿 token**：点右上角 Authorize，"
        "把 /api/auth/login 返回的 token 值粘进去即可。"
    ),
    openapi_tags=TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Row-Count"],
)

for r in (auth, positions, candidates, applications, ai_configs, ai_screen, stats, export):
    app.include_router(r.router)

# 把各接口的中文 docstring 提升为 /docs 里的摘要与描述
import inspect

for route in app.routes:
    if not getattr(route, "include_in_schema", False) or getattr(route, "summary", None):
        continue
    doc = inspect.getdoc(getattr(route, "endpoint", None)) if hasattr(route, "endpoint") else None
    if doc:
        route.summary = doc.strip().splitlines()[0].strip().rstrip("。")
        route.description = doc.strip()


@app.get("/", include_in_schema=False)
def home():
    return HTMLResponse(
        """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>ATS 招聘管理系统</title>
<style>body{font-family:"Microsoft YaHei",sans-serif;max-width:640px;margin:80px auto;padding:0 20px;color:#333;line-height:1.9}
h1{font-size:22px}.tip{background:#f0f9eb;border:1px solid #b3e19d;border-radius:8px;padding:12px 16px}
a{color:#409eff}code{background:#f4f4f5;padding:2px 6px;border-radius:4px}</style></head><body>
<h1>ATS 招聘管理系统 · 后端服务运行中 ✔</h1>
<p>数据库连接正常，接口就绪。</p>
<div class="tip">
<p><b>你现在看到的不是系统界面。</b>本系统是「前后端分离」结构：</p>
<p>① 后端接口（本页 + <a href="/docs">/docs 接口文档</a>）——已完成，/docs 每个接口都带中文说明，
点右上角 <code>Authorize</code> 粘贴登录返回的 token 就能直接试；</p>
<p>② 前端操作界面（岗位管理、投递列表、AI 录入等中文页面）——属于开发计划里的 M3/M4，尚未开始。</p>
</div>
<p>想现在就开始做中文前端界面的话，直接说「开始 M3」即可。</p>
</body></html>"""
    )


@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "up"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error", "database": "down"})
