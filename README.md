# ATS 招聘管理系统

> 2026 毕业设计 · 个人招聘流程管理系统 —— 一套本地运行、桌面优先的招聘全流程管理 Web 应用。

从候选人投递到发 offer，把整条招聘链路管起来：**候选人 / 岗位管理 → 7 阶段招聘管线状态流转 → AI 简历筛选 → 周报汇总与 Excel 导出**。

前端以「招聘管线」为主视觉，用一条由浅入深的阶段色阶表达「这个候选人走到第几关了」，密集表格里也能一眼扫出进度。

---

## 功能亮点

- **7 阶段招聘管线**：AI筛选 → 简历筛选 → 电话沟通 → 笔试 → 专业面 → HR面 → 终面，支持逐关**推进 / 撤回**，撤回可复活已淘汰、已录用的记录。
- **AI 简历筛选**：上传 PDF 简历，后端用 PyMuPDF 抽取文本，再调用你自配的 OpenAI 兼容 LLM 判断是否合格、识别候选人姓名与目标岗位；支持**多配置轮询分流 + 失败自动换配置重试**，回答解析做了中英文 / 布尔 / 数字写法容错。
- **阶段 × 岗位交叉汇总**：行 = 各招聘阶段，列 = 各岗位 + 总计，格子显示范围内「通过该关或正停在该关」的人数，**点数字可直接看该格的人员名单**。
- **招聘周报导出**：一键生成一个 Excel（含「阶段岗位汇总」+「进行中候选人」两个工作表），也可导出 CSV。
- **岗位「暂不招」一键隐藏**：隐藏后该岗位及其全部投递从统计 / 下拉 / 列表 / AI 筛选 / 导出中彻底排除，数据保留、改回即恢复。
- **投递改名纠错**：纠正 AI 认错的候选人姓名，重名会先提示确认。
- **面试评价模块**：把面试记录整理成结构化评价（见 `ats/backend/app/services/interview.py`）。
- **三档主题**：白天青碧 / 黑夜 / 护眼墨绿，同一色相家族，只换光换底不换调。

## 技术栈

| 层 | 技术 |
| :--- | :--- |
| 后端 | Python 3.11 · FastAPI 0.115 · SQLAlchemy 2 · Uvicorn |
| 数据库 | MySQL 8（utf8mb4），6 张表 |
| 前端 | Vue 3 · Element Plus · Vite · Vue Router · axios |
| 认证 | passlib(bcrypt) 哈希密码 + JWT（python-jose），除注册/登录/健康检查外全部接口需 `Authorization: Bearer <token>` |
| AI 筛选 | PyMuPDF 解析 PDF + httpx 调用用户自配的 OpenAI 兼容 LLM API |
| 导出 | openpyxl（xlsx）/ 内置 csv |
| 状态管理 | 轻量自写 store（Vue `ref` + `localStorage`），未引入 Pinia |

## 目录结构

```
1.0/
├── ats/                        # 招聘系统主体
│   ├── backend/                # FastAPI 后端
│   │   ├── app/
│   │   │   ├── core/           # 配置(.env)、数据库连接、登录依赖
│   │   │   ├── models/         # 6 张表的 ORM 模型
│   │   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   │   ├── routers/        # API 路由：auth·positions·candidates·applications·
│   │   │   │                   #   ai_screen·ai_configs·settings·stats·export·interview
│   │   │   ├── services/       # 业务逻辑：状态机、AI 筛选、提示词、统计汇总、导出、面试评价…
│   │   │   └── main.py         # FastAPI 入口，挂载各路由
│   │   ├── scripts/            # smoke_test.py（72 项断言）、mock_llm_test.py（本地假 AI）
│   │   ├── requirements.txt
│   │   └── .env.example        # 环境变量模板（复制为 .env 使用）
│   ├── frontend/               # Vue 3 前端
│   │   └── src/
│   │       ├── api/            # axios 实例（自动带 token / 401 跳登录）+ 接口封装
│   │       ├── stores/         # 登录状态（Vue ref + localStorage 持久化）
│   │       ├── router/         # 路由与登录守卫
│   │       ├── layouts/        # 后台布局（左菜单 + 顶栏速览）
│   │       ├── components/     # 阶段色标等公共组件
│   │       ├── views/          # 页面：登录/注册/岗位/候选人/投递/详情/汇总导出/设置/AI录入/面试
│   │       ├── styles/theme.css# 设计变量层：三主题 + 阶段色阶
│   │       └── constants.js    # 阶段/状态/结果中文名单（与后端数据字典一致）
│   ├── 启动.bat / 停止.bat      # Windows 一键启停脚本
│   └── README.md               # 更细的开发说明（结构约定、里程碑）
└── step/StepO/                 # 设计文档
    ├── 技术栈与开发计划.md      # 权威规格（v3.13）
    ├── 数据库字段说明文档.md    # 数据字典
    ├── 纠错日志.md              # 设计修订日志
    ├── crebas.sql              # MySQL 建表脚本
    ├── 招聘流程状态流转表.html  # 阶段流转表
    ├── ATS.cdm / ATS.pdm       # PowerDesigner 概念 / 物理模型
    └── recruit_flow_anime.jpg  # 招聘流程示意图
```

## 快速开始

### 环境要求

| 依赖 | 版本 |
| :--- | :--- |
| Python | 3.11 |
| MySQL | 8.x（字符集 utf8mb4） |
| Node.js | 18+ |

### 1. 初始化数据库

在 MySQL 中新建数据库 `ats`，然后执行建表脚本：

```bash
mysql -u root -p ats < step/StepO/crebas.sql
```

（也可用 Navicat 等工具打开并执行 `crebas.sql`。）

### 2. 启动后端（127.0.0.1:8000）

```bash
cd ats/backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # 然后编辑 .env：改数据库密码，并把 SECRET_KEY 换成随机值
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>（每个接口都有中文说明）。

### 3. 启动前端（127.0.0.1:5173）

```bash
cd ats/frontend
npm install
npm run dev
```

浏览器打开 <http://127.0.0.1:5173>，先**注册一个账号**再进入后台使用。

### 一键启动（Windows，可选）

配好数据库与后端虚拟环境后，双击 `ats\启动.bat`：脚本会自动检查 / 拉起 MySQL、启动后端与前端、并打开浏览器；要停止服务双击 `ats\停止.bat`。

### 自检脚本

服务启动后，可跑一遍自动化体检（脚本会自动清理测试数据）：

```bash
cd ats/backend
.venv\Scripts\python scripts\smoke_test.py http://127.0.0.1:8000      # 全接口 + 状态机，上百项断言
.venv\Scripts\python scripts\mock_llm_test.py http://127.0.0.1:8000   # 用本地 Mock LLM 验证 AI 录入
```

> 两个脚本会直连 MySQL 做数据清理，默认读环境变量 `ATS_DB_PASSWORD` 作为数据库密码（可先在命令行 `set ATS_DB_PASSWORD=你的密码` 再运行）。

## 数据库设计

6 张表：

| 表 | 说明 |
| :--- | :--- |
| `Candidate` | 候选人基础信息 |
| `Position` | 招聘岗位（含「暂不招」隐藏标记 `is_hidden`） |
| `Application` | 核心业务表：候选人与岗位的投递关系，记录 7 阶段各自的结果与时间戳 |
| `User` | 登录用户（单用户自用场景，无角色权限） |
| `AI_API_Config` | LLM API 配置，可多个同时启用，批量筛选时轮询分流 |
| `App_Setting` | 键值对设置项（当前存 AI 筛选提示词） |

**7 阶段枚举**（`current_stage`）：`ai` AI筛选 → `resume` 简历筛选 → `phone` 电话沟通 → `test` 笔试 → `pro` 专业面 → `hr` HR面 → `final` 终面。
**每关结果**（`result`）：`pass` 通过 / `fail` 淘汰。**全局状态**（`overall_status`）：`pending` 进行中 / `pass` 已录用 / `fail` 已淘汰。

> 字段、约束、索引与枚举的完整定义见 [数据库字段说明文档](step/StepO/数据库字段说明文档.md)。

## 设计文档

| 文档 | 内容 |
| :--- | :--- |
| [技术栈与开发计划.md](step/StepO/技术栈与开发计划.md) | 权威规格（v3.13）：技术栈、UI 规范、页面清单、接口清单、里程碑 |
| [数据库字段说明文档.md](step/StepO/数据库字段说明文档.md) | 六表数据字典 + 约束索引 + 枚举 |
| [招聘流程状态流转表.html](step/StepO/招聘流程状态流转表.html) | 各阶段推进/撤回的流转规则表 |
| [纠错日志.md](step/StepO/纠错日志.md) | 设计修订日志（v3.2 → v3.13） |
| [crebas.sql](step/StepO/crebas.sql) | MySQL 建表脚本 |
| [代码导读.md](ats/backend/代码导读.md) | **新手向**：按顺序读懂后端代码（一次请求怎么走完、推荐阅读路线） |

## 开发进度

- [x] M1 环境 + 项目骨架
- [x] M2 后端：认证 + CRUD + 状态机 + AI 录入 + 统计/导出
- [x] M3 前端骨架：登录/注册 + 路由守卫 + 左菜单 + 顶栏 + 三档主题 + 各管理页
- [x] M4 前端功能：汇总导出页、系统设置（AI 配置 + 提示词）、AI 录入弹窗、导出下载
- [x] 后续增强：候选人级联删除、筛选记忆、一键启停脚本、AI 岗位手选与提示词、回答容错
- [x] 周报增强：阶段×岗位交叉汇总（格子可点看名单）、进行中候选人清单、招聘周报双表导出
- [x] 岗位「暂不招」隐藏、投递改名纠错
- [x] 前端视觉大改版：管线主视觉 + 阶段色标 + 阶段轨筛选 + 三主题
- [ ] M5 收尾打包

## 说明

- 本项目为**本地自用工具**，仅监听 `127.0.0.1`，面向桌面浏览器（表格较宽），定位是个人招聘流程管理而非多租户 SaaS。
- 仓库**不包含**任何密钥：数据库密码与 JWT 密钥放在本地 `.env`（已 gitignore），AI API 密钥运行时存于数据库，不落仓库。
- 用例中的面试评价样例等含个人隐私的材料不入库。
- 仅供学习交流使用。
