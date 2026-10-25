# ATS 招聘管理系统

> 2026 毕业设计 · 个人招聘流程管理系统 —— 一套本地运行、桌面优先的招聘全流程管理 Web 应用。

从候选人投递到发 offer，把整条招聘链路管起来：**候选人 / 岗位管理 → 7 阶段招聘管线状态流转 → AI 简历筛选 → 周报汇总与 Excel 导出**。

前端以「招聘管线」为主视觉，用一条由浅入深的阶段色阶表达「这个候选人走到第几关了」，密集表格里也能一眼扫出进度。

---

## 功能亮点

- **7 阶段招聘管线**：AI筛选 → 简历筛选 → 电话沟通 → 笔试 → 专业面 → HR面 → 终面，支持逐关**推进 / 撤回**，撤回可复活已淘汰、已录用的记录。
- **候选人端（移动优先）**：候选人用手机号登录 `/portal`，查看在招岗位、投递、看 7 关进度、填写可配置表单、查看 HR 上传的简历；简历只读，不需要自己上传。
- **三角色权限**：候选人 / HR / 技术管理员三套入口，接口级隔离；候选人只能看自己的投递。三端共用同一个登录页（身份页签切换），左侧为 7 关渐变管线视觉。
- **技术管理端**：入口 `/tech`，负责账号与权限、AI 接口配置与提示词、操作日志、数据备份与运行概览；不展示招聘业务数据。
- **可配置表单**：HR 定义个人资料表、岗位申请表与职业底色图（11 种字段、必填、选项、排序、分组标题、版本），候选人填写，HR 查看答卷。
- **AI 简历筛选**：上传 PDF 简历，后端用 PyMuPDF 抽取文本，再调用你自配的 OpenAI 兼容 LLM 判断是否合格、识别候选人姓名与目标岗位；支持**多配置轮询分流 + 失败自动换配置重试**，回答解析做了中英文 / 布尔 / 数字写法容错。
- **阶段 × 岗位交叉汇总**：行 = 各招聘阶段，列 = 各岗位 + 总计，格子显示范围内「通过该关或正停在该关」的人数，**点数字可直接看该格的人员名单**。
- **招聘周报导出**：一键生成一个 Excel（含「阶段岗位汇总」+「进行中候选人」两个工作表），也可导出 CSV。
- **岗位「暂不招」一键隐藏**：隐藏后该岗位及其全部投递从统计 / 下拉 / 列表 / AI 筛选 / 导出中彻底排除，数据保留、改回即恢复。
- **投递改名纠错**：纠正 AI 认错的候选人姓名，重名会先提示确认。
- **候选人通知**：通过电话沟通/笔试/专业面/HR面/终面及入职时，按 HR 配置的**富文本模板**自动生成草稿（候选人不可见），投递详情里逐人编辑、发送前预览（所见即候选人弹窗所得），正文自动附 Offer 文件清单；候选人没有手机号（未开通候选人端账号）时不能发送，补上后可重试。
- **Offer 文件与回传**：录用协议 / Offer / 背景调查三类文件 HR 上传、随通知发送后候选人才可见；候选人端按类型**回传签署件**（回传前有法律效力确认弹窗），HR 端标记「已回传」并可下载。
- **面试评价模块**：把面试记录整理成结构化评价（见 `ats/backend/app/services/interview.py`）。
- **三档主题**：白天青碧 / 黑夜 / 护眼墨绿，同一色相家族，只换光换底不换调。

## 技术栈

| 层 | 技术 |
| :--- | :--- |
| 后端 | Python 3.11 · FastAPI 0.115 · SQLAlchemy 2 · Uvicorn |
| 数据库 | MySQL 8（utf8mb4），14 张表（v3.15：三角色 + 文件 + 表单 + 日志；v3.16：候选人通知 + 阶段负责人） |
| 前端 | Vue 3 · Element Plus · Vite · Vue Router · axios |
| 认证 | passlib(bcrypt) 哈希密码 + JWT（python-jose）；三角色 `candidate / hr / admin`，候选人用手机号登录 |
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
│   │   │   ├── models/         # 12 张表的 ORM 模型
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
    ├── 技术栈与开发计划.md      # 权威规格（v3.16）
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

> v3.15 起候选人文件会存进 MySQL，请确认 `max_allowed_packet ≥ 16M`（MySQL 8 默认 64M 即可）。
> 已有 v3.14 数据库请执行 [migrate_v3.15_three_portal.sql](step/StepO/migrate_v3.15_three_portal.sql)，不要重跑 crebas。

### 2. 启动后端（127.0.0.1:8000）

```bash
cd ats/backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env        # 然后编辑 .env：改数据库密码，并把 SECRET_KEY 换成随机值
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>（每个接口都有中文说明）。

首次部署用脚本创建技术管理员（技术管理端 `/tech` 用）：

```bash
.venv\Scripts\python scripts\create_user.py --role admin --username tech --password admin
```

### 3. 启动前端（127.0.0.1:5173）

```bash
cd ats/frontend
npm install
npm run dev
```

浏览器打开 <http://127.0.0.1:5173>：HR 先**注册一个账号**再进入后台；候选人端在 <http://127.0.0.1:5173/portal>（手机号需由 HR 先录入，默认密码 `admin`）；技术管理端在 <http://127.0.0.1:5173/tech>（默认 `tech` / `admin`，部署后请修改）。三个登录地址都会打开同一个登录界面，只是预选身份不同。

### 一键启动（Windows，可选）

配好数据库与后端虚拟环境后，双击 `ats\启动.bat`：脚本会自动检查 / 拉起 MySQL、启动后端与前端、并打开浏览器；要停止服务双击 `ats\停止.bat`。

### 自检脚本

服务启动后，可跑一遍自动化体检（脚本会自动清理测试数据）：

```bash
**一键全量测试（推荐）**：自动重建独立测试库 `ats_test`（**完全不碰真实库**）、起独立测试服务（8001 端口）、依次跑全部脚本：

```bash
cd ats/backend
.venv\Scripts\python scriptsun_all_tests.py    # 汇总 7 套脚本结果，退出码 0=全绿
```

push / PR 到 main 会自动触发 GitHub Actions 跑同一套测试（.github/workflows/tests.yml）。

也可以单独跑某一套（默认连 8001 端口的测试服务；数据库用环境变量 `ATS_DB_NAME` 指定）：

```bash
cd ats/backend
.venv\Scripts\python scripts\smoke_test.py http://127.0.0.1:8001       # HR 全接口 + 状态机
.venv\Scripts\python scripts\stage1_role_test.py                      # 三角色权限矩阵（30 项）
.venv\Scripts\python scripts\portal_smoke_test.py                     # 候选人账号/登录（31 项）
.venv\Scripts\python scripts\stage3_smoke_test.py                     # 文件 + 表单（45 项）
.venv\Scripts\python scripts\stage4_smoke_test.py                     # 候选人投递 + AI 首筛（42 项）
.venv\Scripts\python scripts\tech_smoke_test.py                       # 技术管理端（33 项）
.venv\Scripts\python scripts\mock_llm_test.py http://127.0.0.1:8000    # 本地 Mock LLM 验证 AI 录入（15 项）
```

> 脚本会直连 MySQL 做数据清理，默认读环境变量 `ATS_DB_PASSWORD` 作为数据库密码（可先在命令行 `set ATS_DB_PASSWORD=你的密码` 再运行）。
> 演示数据：`python scripts\seed_demo.py --reset` 创建，`--clean` 清理。

## 数据库设计

14 张表（v3.15 三角色 + 文件 + 表单 + 日志；v3.16 增候选人通知与阶段负责人）：

| 表 | 说明 |
| :--- | :--- |
| `Candidate` | 候选人基础信息；`phone` 是候选人端登录账号；`owner_id` 负责人 HR（能编辑全部关卡） |
| `Position` | 招聘岗位（含「暂不招」隐藏标记 `is_hidden`） |
| `Application` | 核心业务表：投递关系，记录 7 阶段结果与时间戳；`source` 标记来源 |
| `User` | 三角色账号：`candidate` 候选人 / `hr` HR / `admin` 技术管理员；HR/管理员实名与手机号必填，含头像 LONGBLOB |
| `AI_API_Config` | LLM API 配置，可多个同时启用 |
| `App_Setting` | 键值对设置项（AI 提示词、周报阶段文案、通知模板、表单可见阶段） |
| `Candidate_File` | 候选人文件（HR 上传、候选人只读，BLOB 入库） |
| `Candidate_Notice` | 候选人通知（通过关卡/入职按模板生成草稿，Send_Time 为空=未发送） |
| `Form_Template` | 可配置表单模板（个人资料表 / 岗位申请表 / 职业底色图，可不绑岗位=通用） |
| `Form_Field` | 表单字段（11 种类型、必填、选项、排序、分组标题、红蓝绿底色） |
| `Form_Submission` | 表单答卷（草稿 / 已提交） |
| `Form_Answer` | 表单答案（一个字段一行） |
| `Operation_Log` | 操作日志（登录、账号、配置、导出、备份） |
| `Stage_Owner` | 投递的阶段负责人（首次编辑该关的 HR 自动认领，只能编辑本关） |

> 老库升级：先执行 [migrate_v3.15_three_portal.sql](step/StepO/migrate_v3.15_three_portal.sql)，再按文件名顺序执行 v3.16 的九个增量脚本（`migrate_v3.16_*.sql`：候选人通知、简历摘录字段、通知草稿、Offer 发送时间、头像、HR 手机号、HR 实名、销号恢复时间、阶段负责人）；回滚见 [rollback_v3.15_three_portal.sql](step/StepO/rollback_v3.15_three_portal.sql)。

**7 阶段枚举**（`current_stage`）：`ai` AI筛选 → `resume` 简历筛选 → `phone` 电话沟通 → `test` 笔试 → `pro` 专业面 → `hr` HR面 → `final` 终面。
**每关结果**（`result`）：`pass` 通过 / `fail` 淘汰。**全局状态**（`overall_status`）：`pending` 进行中 / `pass` 已录用 / `fail` 已淘汰。

> 字段、约束、索引与枚举的完整定义见 [数据库字段说明文档](step/StepO/数据库字段说明文档.md)。

## 设计文档

| 文档 | 内容 |
| :--- | :--- |
| [技术栈与开发计划.md](step/StepO/技术栈与开发计划.md) | 权威规格（v3.16 增补）：技术栈、UI 规范、页面清单、接口清单、里程碑 |
| [候选人端与管理端方案.md](step/StepO/候选人端与管理端方案.md) | v3.15 三角色方案：候选人端 / HR 端 / 技术管理端、数据模型、接口与阶段计划 |
| [部署与备份恢复.md](step/StepO/部署与备份恢复.md) | 部署检查、老库升级、备份 ZIP、手工恢复步骤 |
| [数据库字段说明文档.md](step/StepO/数据库字段说明文档.md) | 12 张表数据字典 + 约束索引 + 枚举 |
| [招聘流程状态流转表.html](step/StepO/招聘流程状态流转表.html) | 各阶段推进/撤回的流转规则表 |
| [纠错日志.md](step/StepO/纠错日志.md) | 设计修订日志（v3.2 → v3.16） |
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
- [x] v3.15 三角色：候选人手机号登录 / 只读简历 / 可配置表单 / 自主投递与 AI 首筛 / 移动优先界面
- [x] v3.15 HR 适配：文件与表单答卷、投递来源、表单模板管理
- [x] v3.15 技术管理端：账号、AI 配置与提示词、操作日志、全库备份、运行概览
- [x] v3.15 测试与文档：382 项自动化断言（含 Mock LLM 15 项）、部署/备份恢复文档、演示种子数据
- [x] v3.16 表单链路顺手化：候选人端文件页直列表单、模板只读预览、通用申请表（不绑岗位）、表单可见阶段设置
- [x] v3.16 Offer 文件与候选人回传（法律效力确认）、个人信息弹窗、三端头像、各关记录就地编辑
- [x] v3.16 候选人通知：通过关卡/入职富文本模板、发送前预览、Offer 文件清单随附；没手机号不能发送（前端提醒 + 后端拦截）
- [x] v3.16 HR 手机号强制：注册 / 个人信息 / 技术端建号必填手机号，存量账号与候选人已批量补编并开通登录
- [x] v3.16 HR 实名强制：同三处必填实名，顶栏优先显示实名；存量 HR 已编占位姓名
- [x] v3.16 淘汰通知与销号：淘汰即按模板发通知，2 天保留期内登录弹窗可见，超期登录被拦（拦截信息含淘汰说明）并销号
- [x] v3.16 销号数据保存 3 个月：销号只停用不删数据，技术管理端保存期内可一键恢复账号（超期不可恢复）
- [x] v3.16 HR 负责人体系：候选人负责人（默认建档/录简历 HR）管全局，阶段负责人只管本关，技术管理端可单个/批量变更负责人
- [ ] M5 收尾打包（可选：Docker / 单文件启动）

## 说明

- 本项目为**本地自用工具**，仅监听 `127.0.0.1`，面向桌面浏览器（表格较宽），定位是个人招聘流程管理而非多租户 SaaS。
- 仓库**不包含**任何密钥：数据库密码与 JWT 密钥放在本地 `.env`（已 gitignore），AI API 密钥运行时存于数据库，不落仓库。
- 用例中的面试评价样例等含个人隐私的材料不入库。
- 仅供学习交流使用。
