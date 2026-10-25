# ATS 招聘管理系统

> 项目总览、功能亮点与快速上手指南见仓库根目录的 [README.md](../README.md)；本文件偏后端/前端开发细节。

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
.venv\Scripts\python scripts\smoke_test.py http://127.0.0.1:8000      # 全接口 + 状态机，上百项断言
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
  core/       config（.env）、database（engine/session）、deps（三角色门卫：hr / candidate / admin）
  models/     12 张表 ORM，字段照 crebas.sql
  schemas/    Pydantic 请求/响应
  routers/    auth / portal_auth / portal_positions / portal_applications / portal_files / portal_forms / candidate_files / forms / tech_auth / tech_accounts / tech_config / tech_overview / tech_logs / tech_backup / positions / candidates / applications / ai_screen / settings / stats / export
  services/   security（bcrypt+JWT）、state_machine（7 阶段推进/撤回）、pdf、llm、prompt（提示词与回答容错）、ai_screen（录入编排）、summary（阶段×岗位交叉表）、positions（暂不招岗位统一排除）、export、views、settings、accounts（候选人手机号账号）、phone、ratelimit、log_service、file_service（文件校验/入库）、form_service（表单模板/答卷）、portal_apply（候选人投递 AI 首筛）、portal_views（候选人白名单序列化）、backup_service（ZIP 备份）
```

约定（详见设计文档 v3.5）：
- 枚举值照数据字典；`ai` 阶段在表里没有时间字段，只记结果与 AI 理由
- 撤回：已淘汰/已录用 → 清当前阶段结果、原地恢复进行中；进行中 → 退回上一阶段并清上一阶段结果；指定 `toStage` → 清该阶段及之后全部数据
- AI 录入不保存 PDF 与简历文本，只写 `ai_result` / `ai_comment`；同名视为同一候选人
- AI 录入的岗位可在弹窗整批指定（默认「自动识别」）；指定后 AI 只判断是否符合该岗位
- AI 筛选提示词：规则可自定义（存 App_Setting 表，按用户隔离），回答格式由系统锁定不可改
- AI 回答解析容错：result 兼容中英文/布尔/数字写法，position_id 兼容 "1"/"1.0"/"岗位1" 等
- 删除候选人 = 级联删除其名下投递（应用层实现）；岗位有投递时仍拒删（外键 restrict）
- 汇总导出页的「阶段×岗位汇总」：行=简历筛选/电话沟通/笔试/面试，列=各岗位+总计，格子=范围内「通过该关或正停在该关」的人数（在此关淘汰不算；**面试除外**：专业面/HR面/终面任一关在范围内即计入，面过被淘汰的也算）；岗位名自动缩写、同名岗位补负责人；范围可切本周/上周/本月/全部/自定义；**点数字可看该格人员名单**；可一键导出 Excel
- 汇总导出页的「进行中的候选人所处阶段」：列出范围内有动作且仍进行中的人（岗位/候选人/阶段），**支持按阶段多选筛选**，阶段自动生成且可逐条手动改写（存 App_Setting，不改业务数据），范围与交叉表联动
- 导出「招聘周报」= 一个 Excel 两个工作表（阶段岗位汇总 + 进行中候选人）
- 候选人管理页：搜索栏（姓名/备注/投递情况组合筛选）+ 点姓名或详情打开抽屉查看其名下全部投递（可跳投递详情）
- 岗位「暂不招」：岗位管理页行内开关一键隐藏；隐藏后该岗位及其全部投递从统计、下拉、列表、AI 筛选与导出中彻底不体现（数据保留，改回即恢复）；services/positions.py 是统一排除出口
- 投递详情「改姓名」：纠正 AI 认错的候选人姓名；重名会先提示（带对方投递数）确认后允许；改名不影响该候选人的任何投递记录
- 各关「结果原因 / 面试评价」：推进（通过/淘汰）仍是一键、不弹窗；出过结果的关随时可改，**正在进行的当前关也能先写**（面试完当下就记评价，之后再定通过/淘汰），都在投递详情页「各关记录」分区编辑；简历筛选/笔试只记原因（通过、淘汰都能写），电话沟通/专业面/HR面/终面另有面试评价，评价可贴逐字稿用「面试评价」功能 AI 生成后润色；撤回某关时该关原因与评价一并清空；AI 筛选理由仍是只读的 ai_comment

## 前端设计约定（v3.12）

- **主视觉是「招聘管线」**：7 关唯一高调处，其余安静；避开看板脸、多色标签、卡片堆
- **阶段色阶**：`--ats-stage-1..8` 浅→深，越靠后越深 = 走得越远；未到达用空心圆
- **三主题同色相家族**：白天青碧 / 黑夜提亮 / 护眼墨绿，只换光换底不换调
- **数字一律等宽**（`tabular-nums`），列可竖着扫读
- **内容用 `.panel` 分区**，不再每个区块一张卡片；弹窗宽度统一三档
- **只做桌面**（本机办公工具，表格宽），保证 1440 宽无横向溢出
- 交叉表「面试人数」：专业面/HR面/终面任一关在范围内即计入（面过即计入、含被淘汰），同一人只计一次；判定逻辑集中在 `summary.row_membership()`，计数与名单共用

## 前端结构

```
frontend/src/
  main.js        总开关：Element Plus、图标、路由、主题
  App.vue        根组件：el-config-provider 中文语言
  api/http.js    HR 端 axios：自动带 token、401 跳 /login、错误统一弹中文
  api/portalHttp.js 候选人端 axios：独立 token、401 跳 /portal/login
  api/techHttp.js   技术端 axios：独立 token、401 跳 /tech/login
  api/index.js   HR 端接口封装；api/portal.js 候选人端接口封装；api/tech.js 技术端接口封装
  stores/auth.js HR 登录状态；portalAuth.js 候选人；techAuth.js 技术管理员（三套 token 分开存）
  router/index.js 路由 + 三端守卫：HR / 候选人 / 技术管理员各走各的登录页
  layouts/AdminLayout.vue HR 后台布局；PortalLayout.vue 候选人端（移动优先 + 底部导航）；TechLayout.vue 技术管理端
  views/         HR 页面（候选人抽屉含文件/表单/投递；投递列表带来源；表单模板页）；views/portal/ 候选人端页面；views/tech/ 技术端页面
  theme.js + styles/theme.css  三档主题：白天 / 黑夜(Element dark) / 护眼(米黄)，localStorage 保持
  styles/portal.css  候选人端卡片、时间线、表单操作栏等移动端样式
  constants.js   7 阶段 / 状态 / 结果的中文名单 + 阶段色阶映射（照后端数据字典）
  components/StageTag.vue HR 阶段色标；PortalStageBar.vue 候选人进度条；PortalFormRenderer.vue 通用表单渲染
```

## 进度

- [x] M1 环境 + 项目骨架
- [x] M2 后端：认证 + CRUD + 状态机 + AI 录入 + 统计/导出（2026-09-08）
- [x] M3 前端骨架：登录/注册 + 路由守卫 + 左菜单 + 顶部状态栏 + 三档主题 + 岗位/候选人/投递/详情页（2026-09-09）
- [x] M4 前端功能：汇总导出页、系统设置（AI 配置管理 + AI 筛选提示词）、AI 录入简历弹窗（岗位手选）、导出下载（2026-09-09）
- [x] 后续增强：候选人级联删除、表格样式、筛选记忆、一键启停脚本、AI 岗位手选与提示词、回答容错（2026-09-15）
- [x] 周报增强：阶段×岗位交叉汇总表（口径=通过该关或正停在该关，格子可点看名单）、进行中候选人所处阶段清单（阶段多选筛选+手动改写）、招聘周报双表导出、候选人搜索与详情（2026-09-17）
- [x] 岗位「暂不招」隐藏：行内开关 + 显示筛选，隐藏后岗位及其投递从统计/列表/AI/导出彻底排除（2026-09-17）
- [x] 投递详情可改候选人姓名（纠正 AI 认错的名字，重名需确认，不影响投递进度）（2026-09-17）
- [x] v3.15 候选人端：三角色权限、手机号登录、只读简历、可配置表单、投递 + AI 首筛、移动优先界面（2026-10-24）
- [x] v3.15 HR 适配 + 技术管理端：文件/表单/来源、表单模板、账号、AI 配置、日志、备份、概览（2026-10-24）
- [x] v3.15 测试与文档：367 项断言、部署/备份恢复文档、seed_demo（2026-10-24）
- [x] v3.16 表单链路顺手化：候选人端文件页直列表单点行即达填写页；HR 模板去「用途」单选 + 只读预览；注册页对齐候选人登录视觉（2026-10-24）
- [x] v3.16 Offer 文件与候选人回传：三类文件上传→随通知发送后可见，候选人回传签署件（法律效力确认），HR 标记「已回传」（2026-10-25）
- [x] v3.16 候选人通知：通过关卡/入职按富文本模板生成草稿，逐人编辑 + 发送前预览，正文自动附 Offer 文件清单；候选人没手机号不能发送（前端提醒失败 + 后端 400 拦截），补上后可重试（2026-10-25）
- [x] v3.16 体验顺手化：个人信息改弹窗、三端头像、各关记录滑动选关就地编辑、投递详情标签页、通用申请表、表单可见阶段设置（2026-10-25）
- [x] 前端视觉大改版：管线主视觉 + 阶段色标 + 阶段轨筛选 + 招聘漏斗 + 设计变量层与三主题（2026-09-21）
- [ ] M5 收尾打包
