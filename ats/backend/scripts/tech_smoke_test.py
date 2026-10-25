"""
阶段 7/8 自检：技术管理端

覆盖：
  1. 技术管理员登录 / HR 不能访问技术接口 / 技术管理员不能访问 HR 接口
  2. 运行概览结构
  3. 账号：创建 HR、登录、停用、重置密码、启用；不能停用自己；重复用户名 409
  4. AI 配置：创建 / 列表 / 启停 / 修改 / 删除
  5. AI 提示词：读取 / 保存 / 恢复原值
  6. 操作日志：分页与筛选
  7. 备份 ZIP：12 个 CSV + manifest.json

运行（后端已启动，且存在 tech/admin 账号）：
    .venv\\Scripts\\python -B scripts\\tech_smoke_test.py
"""
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import pymysql

BASE = os.getenv("ATS_BASE", "http://127.0.0.1:8001")
DB_PW = os.getenv("ATS_DB_PASSWORD", "your-password")
PASSED = 0
FAILED = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f"  [OK]   {label}")
    else:
        FAILED += 1
        print(f"  [FAIL] {label} {detail}")


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    tag = str(int(time.time()))
    hr_id = None
    new_id = None
    T = None
    cfg_ids: list[int] = []
    original_prompt = None
    try:
        # ---------- 1. 角色隔离 ----------
        r = c.post("/api/tech/auth/login", json={"username": "tech", "password": "admin"})
        check("技术管理员登录", r.status_code == 200, r.text[:150])
        T = {"Authorization": f"Bearer {r.json()['token']}"}
        check("技术端 /me", c.get("/api/tech/auth/me", headers=T).status_code == 200)

        hr_name = f"tech_hr_{tag}"
        r = c.post("/api/auth/register", json={"username": hr_name, "password": "secret123", "real_name": "测试HR", "phone": "139" + tag[-8:]})
        check("注册临时 HR", r.status_code == 201, r.text[:150])
        H = {"Authorization": f"Bearer {r.json()['token']}"}
        hr_id = r.json()["user"]["id"]
        check("HR 访问技术概览 403", c.get("/api/tech/overview", headers=H).status_code == 403)
        check("技术管理员访问 HR 接口 403", c.get("/api/candidates", headers=T).status_code == 403)
        check("技术概览无 token 401", c.get("/api/tech/overview").status_code == 401)

        # ---------- 2. 概览 ----------
        r = c.get("/api/tech/overview", headers=T)
        d = r.json()
        check("概览结构完整", r.status_code == 200 and {"users", "business", "system", "recent_logs"} <= set(d), str(d.keys()))
        check("概览含数据库体积", d["system"]["db_bytes"] > 0, str(d["system"]["db_bytes"]))

        # ---------- 3. 账号 ----------
        r = c.get("/api/tech/accounts", headers=T)
        check("账号列表 >= 2（测试库只有 tech + 临时 HR）", r.status_code == 200 and len(r.json()) >= 2, str(len(r.json())))
        r = c.post("/api/tech/accounts", headers=T, json={"role": "hr", "username": f"new_hr_{tag}", "password": "secret123", "real_name": "测试HR", "phone": "138" + tag[-8:]})
        check("创建 HR 账号", r.status_code == 201, r.text[:150])
        new_id = r.json()["id"]
        r = c.post("/api/auth/login", json={"username": f"new_hr_{tag}", "password": "secret123"})
        check("新 HR 可登录 HR 端", r.status_code == 200)
        check("重复用户名 409", c.post("/api/tech/accounts", headers=T, json={"role": "hr", "username": f"new_hr_{tag}", "phone": "138" + tag[-8:], "real_name": "测试HR"}).status_code == 409)
        r = c.put(f"/api/tech/accounts/{new_id}/status", headers=T, json={"is_active": False})
        check("停用账号", r.status_code == 200 and r.json()["is_active"] is False)
        check("停用后 HR 登录 403", c.post("/api/auth/login", json={"username": f"new_hr_{tag}", "password": "secret123"}).status_code == 403)
        r = c.put(f"/api/tech/accounts/{new_id}/reset-password", headers=T)
        check("重置密码", r.status_code == 200)
        r = c.put(f"/api/tech/accounts/{new_id}/status", headers=T, json={"is_active": True})
        check("重新启用", r.status_code == 200 and r.json()["is_active"] is True)
        r = c.post("/api/auth/login", json={"username": f"new_hr_{tag}", "password": "admin"})
        check("重置后默认密码可登录", r.status_code == 200, r.text[:100])

        me = c.get("/api/tech/auth/me", headers=T).json()
        check("不能停用自己", c.put(f"/api/tech/accounts/{me['id']}/status", headers=T, json={"is_active": False}).status_code == 400)

        # ---------- 4. AI 配置 ----------
        r = c.get("/api/tech/ai-configs", headers=T)
        check("AI 配置列表", r.status_code == 200)
        r = c.post("/api/tech/ai-configs", headers=T, json={"name": f"tech_cfg_{tag}", "base_url": "http://127.0.0.1:9/v1", "api_key": "k", "model": "m"})
        check("新建 AI 配置", r.status_code == 201, r.text[:150])
        k = r.json()["id"]; cfg_ids.append(k)
        check("启用配置", c.put(f"/api/tech/ai-configs/{k}/enable", headers=T).json()["is_enabled"] is True)
        check("停用配置", c.put(f"/api/tech/ai-configs/{k}/disable", headers=T).json()["is_enabled"] is False)
        check("修改配置", c.put(f"/api/tech/ai-configs/{k}", headers=T, json={"model": "m2"}).json()["model"] == "m2")

        # ---------- 5. 提示词 ----------
        r = c.get("/api/tech/ai-prompt", headers=T)
        original_prompt = r.json()
        check("读取系统提示词", r.status_code == 200 and "format_rules" in r.json())
        r = c.put("/api/tech/ai-prompt", headers=T, json={"rules": f"tech 测试规则 {tag}"})
        check("保存系统提示词", r.status_code == 200 and r.json()["is_custom"] is True)
        check("HR 不能改系统提示词", c.put("/api/tech/ai-prompt", headers=H, json={"rules": "x"}).status_code == 403)
        restore = original_prompt["rules"] if original_prompt["is_custom"] else ""
        r = c.put("/api/tech/ai-prompt", headers=T, json={"rules": restore})
        check("恢复原提示词", r.status_code == 200)

        # ---------- 6. 日志 ----------
        r = c.get("/api/tech/logs", headers=T, params={"page_size": 10})
        check("日志列表", r.status_code == 200 and r.json()["total"] > 0, r.text[:150])
        r = c.get("/api/tech/logs", headers=T, params={"action": "login", "role": "admin"})
        check("日志按动作/角色筛选", r.status_code == 200 and all(x["action"] == "login" and x["role"] == "admin" for x in r.json()["items"]))

        # ---------- 7. 备份 ----------
        r = c.get("/api/tech/backup/export", headers=T)
        check("备份下载 200", r.status_code == 200 and r.headers.get("content-type", "").startswith("application/zip"))
        z = zipfile.ZipFile(io.BytesIO(r.content))
        names = z.namelist()
        check("备份含 manifest.json", "manifest.json" in names)
        check("备份含 12 个 CSV", len([n for n in names if n.startswith("csv/")]) == 12, str(len(names)))
        manifest = json.loads(z.read("manifest.json"))
        check("manifest 记录 12 张表", len(manifest["tables"]) == 12)

    finally:
        # ---------- 清理：临时 HR、临时配置、恢复提示词 ----------
        try:
            if T is not None:
                for k in cfg_ids:
                    c.delete(f"/api/tech/ai-configs/{k}", headers=T)
                if original_prompt is not None:
                    restore = original_prompt["rules"] if original_prompt["is_custom"] else ""
                    c.put("/api/tech/ai-prompt", headers=T, json={"rules": restore})
        except Exception:
            pass
        try:
            conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=DB_PW, database=os.getenv("ATS_DB_NAME", "ats"))
            cur = conn.cursor()
            ids = [x for x in (hr_id, new_id) if x]
            if ids:
                cur.execute(f"DELETE FROM User WHERE ID IN ({','.join(map(str, ids))})")
            cur.execute("DELETE FROM Operation_Log")
            conn.commit()
            cur.execute("SELECT COUNT(*) FROM User")
            print(f"  cleanup User: {cur.fetchone()[0]} rows left")
            conn.close()
        except Exception as e:
            print(f"清理失败：{e}")
        c.close()

    print(f"\n结果：通过 {PASSED} 项，失败 {FAILED} 项")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
