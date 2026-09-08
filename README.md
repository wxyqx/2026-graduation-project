# ATS 招聘管理系统

个人招聘流程管理系统：候选人管理、岗位管理、8 阶段招聘状态流转（AI筛选 → … → 终面）、AI 简历筛选与汇总导出。

设计文档见 `../step/StepO/`（建表脚本 crebas.sql、数据字典、技术栈与开发计划）。

## 技术栈

- 后端：Python 3.11 / FastAPI / SQLAlchemy 2 / MySQL 8
- 前端：Vue3 / Element Plus / Vite
- 认证：JWT（M2 实现）

## 本地启动

### 0. 数据库

本机 MySQL 运行中（`D:\mysql\start_mysql.bat` 可启停，账号 root，库 ats）。
新机器：先安装 MySQL 8，执行设计文档中的 crebas.sql 建表。

### 1. 后端（127.0.0.1:8000）

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
copy .env.example .env   # 按需改数据库密码
.venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. 前端（127.0.0.1:5173）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5173，点「检测后端与数据库」看到绿色成功即部署完成。

## 进度

- [x] M1 环境 + 项目骨架（本仓库初始状态）
- [ ] M2 后端：认证 + CRUD + 状态机 + AI 筛选 + 导出
- [ ] M3 前端骨架：登录/注册 + 导航布局 + 主题
- [ ] M4 前端功能页
- [ ] M5 收尾打包
