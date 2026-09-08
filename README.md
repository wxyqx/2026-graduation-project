# ATS 招聘管理系统

个人招聘流程管理系统：候选人管理、岗位管理、8 阶段招聘状态流转（AI筛选 → … → 终面）、AI 简历筛选与汇总导出。

设计文档见 `../step/StepO/`（建表脚本 crebas.sql、数据字典、技术栈与开发计划）。

## 技术栈

- 后端：Python 3.11 / FastAPI / SQLAlchemy 2 / MySQL 8
- 前端：Vue3 / Element Plus / Vite
- 认证：passlib(bcrypt) + JWT（python-jose），除 `/api/auth/*` 与 `/api/health` 外全部接口需要 `Authorization: Bearer <token>`
- AI 筛选：PyMuPDF 提取 PDF 文本 → 用户自配的 OpenAI 兼容 LLM API（多配置轮询、失败换配置重试）
- 导出：openpyxl xlsx / csv

## 本地启动

### 0. 数据库

本机 MySQL 运行中（`D:\mysql\start_mysql.bat` 可启停，账号 root，库 ats）。
新机器：先安装 MySQL 8，执行设计文档中的 crebas.sql 建表。

### 1. 后端（127.0.0.1:8000）

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
copy .env.example .env   # 改数据库密码，并把 SECRET_KEY 换成随机值
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

接口文档：http://127.0.0.1:8000/docs

后端自检（需服务已启动，会自动清理测试数据）：

```bash
.venv\Scripts\python scripts\smoke_test.py http://127.0.0.1:8000      # 全接口 + 状态机，72 项断言
.venv\Scripts\python scripts\mock_llm_test.py http://127.0.0.1:8000   # 本地 mock LLM 验证 AI 录入成功路径
```

### 2. 前端（127.0.0.1:5173）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5173，点「检测后端与数据库」看到绿色成功即部署完成。

## 后端结构

```
backend/app/
  core/       config（.env）、database（engine/session）、deps（get_current_user）
  models/     5 张表 ORM，字段照 crebas.sql
  schemas/    Pydantic 请求/响应
  routers/    auth / positions / candidates / applications / ai_configs / ai_screen / stats / export
  services/   security（bcrypt+JWT）、state_machine（8 阶段推进/撤回）、pdf、llm、ai_screen（录入编排）、export、views
```

约定（详见设计文档 v3.1）：
- 枚举值照数据字典；`contact` 阶段在表里没有结果/时间字段，只作为流程节点
- 撤回：已淘汰/已录用 → 清当前阶段结果、原地恢复进行中；进行中 → 退回上一阶段并清上一阶段结果；指定 `toStage` → 清该阶段及之后全部数据
- AI 录入不保存 PDF 与简历文本，只写 `ai_result` / `ai_comment`；同名视为同一候选人

## 进度

- [x] M1 环境 + 项目骨架
- [x] M2 后端：认证 + CRUD + 状态机 + AI 录入 + 统计/导出（2026-09-08）
- [ ] M3 前端骨架：登录/注册 + 导航布局 + 主题
- [ ] M4 前端功能页
- [ ] M5 收尾打包
