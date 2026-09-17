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

浏览器打开 http://127.0.0.1:5173，先注册一个账号，再进后台使用（首页“检测后端与数据库”仅在 M1 验证用）。

## 后端结构

```
backend/app/
  core/       config（.env）、database（engine/session）、deps（get_current_user）
  models/     6 张表 ORM，字段照 crebas.sql
  schemas/    Pydantic 请求/响应
  routers/    auth / positions / candidates / applications / ai_configs / ai_screen / settings / stats / export
  services/   security（bcrypt+JWT）、state_machine（8 阶段推进/撤回）、pdf、llm、prompt（提示词与回答容错）、ai_screen（录入编排）、summary（阶段×岗位交叉表）、positions（暂不招岗位统一排除）、export、views、settings
```

约定（详见设计文档 v3.5）：
- 枚举值照数据字典；`contact` 阶段在表里没有结果/时间字段，只作为流程节点
- 撤回：已淘汰/已录用 → 清当前阶段结果、原地恢复进行中；进行中 → 退回上一阶段并清上一阶段结果；指定 `toStage` → 清该阶段及之后全部数据
- AI 录入不保存 PDF 与简历文本，只写 `ai_result` / `ai_comment`；同名视为同一候选人
- AI 录入的岗位可在弹窗整批指定（默认「自动识别」）；指定后 AI 只判断是否符合该岗位
- AI 筛选提示词：规则可自定义（存 App_Setting 表，按用户隔离），回答格式由系统锁定不可改
- AI 回答解析容错：result 兼容中英文/布尔/数字写法，position_id 兼容 "1"/"1.0"/"岗位1" 等
- 删除候选人 = 级联删除其名下投递（应用层实现）；岗位有投递时仍拒删（外键 restrict）
- 汇总导出页的「阶段×岗位汇总」：行=简历筛选/电话沟通/笔试/面试，列=各岗位+总计，格子=范围内「通过该关或正停在该关」的人数（在此关淘汰不算；面试只判专业面）；岗位名自动缩写、同名岗位补负责人；范围可切本周/上周/本月/全部/自定义；**点数字可看该格人员名单**；可一键导出 Excel
- 汇总导出页的「进行中的候选人所处阶段」：列出范围内有动作且仍进行中的人（岗位/候选人/阶段），**支持按阶段多选筛选**，阶段自动生成且可逐条手动改写（存 App_Setting，不改业务数据），范围与交叉表联动
- 导出「招聘周报」= 一个 Excel 两个工作表（阶段岗位汇总 + 进行中候选人）
- 候选人管理页：搜索栏（姓名/备注/投递情况组合筛选）+ 点姓名或详情打开抽屉查看其名下全部投递（可跳投递详情）
- 岗位「暂不招」：岗位管理页行内开关一键隐藏；隐藏后该岗位及其全部投递从统计、下拉、列表、AI 筛选与导出中彻底不体现（数据保留，改回即恢复）；services/positions.py 是统一排除出口

## 前端结构

```
frontend/src/
  main.js        总开关：Element Plus、图标、路由、主题
  App.vue        根组件：el-config-provider 中文语言
  api/http.js    axios 实例：自动带 token、401 自动跳登录、错误统一弹中文提示
  api/index.js   每个后端接口包成一个函数
  stores/auth.js 登录状态（token + 用户），localStorage 持久化
  router/index.js 路由 + 守卫：未登录访问后台 → /login
  layouts/AdminLayout.vue 后台布局：左菜单 + 顶栏（5 个速览数字 + 主题切换）
  views/         登录 / 注册 / 岗位管理 / 候选人管理 / 投递列表 / 投递详情 / 汇总导出 / 系统设置 / AI录入弹窗
  theme.js + styles/theme.css  三档主题：白天 / 黑夜(Element dark) / 护眼(米黄)，localStorage 保持
  constants.js   8 阶段 / 状态 / 结果的中文名单（照后端数据字典）
```

## 进度

- [x] M1 环境 + 项目骨架
- [x] M2 后端：认证 + CRUD + 状态机 + AI 录入 + 统计/导出（2026-09-08）
- [x] M3 前端骨架：登录/注册 + 路由守卫 + 左菜单 + 顶部状态栏 + 三档主题 + 岗位/候选人/投递/详情页（2026-09-09）
- [x] M4 前端功能：汇总导出页、系统设置（AI 配置管理 + AI 筛选提示词）、AI 录入简历弹窗（岗位手选）、导出下载（2026-09-09）
- [x] 后续增强：候选人级联删除、表格样式、筛选记忆、一键启停脚本、AI 岗位手选与提示词、回答容错（2026-09-15）
- [x] 周报增强：阶段×岗位交叉汇总表（口径=通过该关或正停在该关，格子可点看名单）、进行中候选人所处阶段清单（阶段多选筛选+手动改写）、招聘周报双表导出、候选人搜索与详情（2026-09-17）
- [x] 岗位「暂不招」隐藏：行内开关 + 显示筛选，隐藏后岗位及其投递从统计/列表/AI/导出彻底排除（2026-09-17）
- [ ] M5 收尾打包
