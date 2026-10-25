"""
【演示数据种子】三角色账号 + 岗位 + 表单 + 一份完整投递

用法（后端已启动）：
    .venv\\Scripts\\python -B scripts\\seed_demo.py            # 创建（已存在会提示）
    .venv\\Scripts\\python -B scripts\\seed_demo.py --reset    # 先清演示数据再创建

演示账号：
    HR        hr_demo / admin123
    候选人    13800138000 / admin
    技术管理  tech / admin（已由 create_user.py 创建）

说明：
  · 候选人简历由 HR 上传（PDF 自动生成）
  · 投递会临时停用 AI 配置，让它进入「待人工筛选」，保证演示结果稳定
  · --reset 会删除本脚本创建的演示数据，不影响其他真实数据
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz
import httpx
import pymysql

BASE = "http://127.0.0.1:8001"
# 数据库密码：读 .env 的 DATABASE_URL，或环境变量 ATS_DB_PASSWORD
import os
import re as _re

_env = Path(__file__).resolve().parents[1] / ".env"
_m = _re.search(r"://[^:]+:([^@]+)@", _env.read_text(encoding="utf-8")) if _env.exists() else None
DB_PW = os.getenv("ATS_DB_PASSWORD") or (_m.group(1) if _m else "")
HR_USERNAME = "hr_demo"
HR_PASSWORD = "admin123"
PHONE = "13800138000"
CANDIDATE_NAME = "陈晨"
POSITION_NAME = "Java 后端工程师（演示）"
PROFILE_FORM_NAME = "演示-候选人资料表"
POSITION_FORM_NAME = "演示-Java岗申请表"


def db():
    return pymysql.connect(host="127.0.0.1", port=3306, user="root", password=DB_PW, database=os.getenv("ATS_DB_NAME", "ats"))


def cleanup(conn):
    cur = conn.cursor()
    # 演示候选人相关
    cur.execute("SELECT ID FROM Candidate WHERE phone=%s", (PHONE,))
    cand_ids = [r[0] for r in cur.fetchall()]
    if cand_ids:
        ids = ",".join(map(str, cand_ids))
        cur.execute(f"SELECT ID FROM Application WHERE Can_ID IN ({ids})")
        app_ids = [r[0] for r in cur.fetchall()]
        if app_ids:
            apps = ",".join(map(str, app_ids))
            cur.execute(f"DELETE FROM Form_Answer WHERE Submission_ID IN (SELECT ID FROM Form_Submission WHERE Application_ID IN ({apps}))")
            cur.execute(f"DELETE FROM Form_Submission WHERE Application_ID IN ({apps})")
            cur.execute(f"DELETE FROM Application WHERE ID IN ({apps})")
        cur.execute(f"DELETE FROM Form_Answer WHERE Submission_ID IN (SELECT ID FROM Form_Submission WHERE Candidate_ID IN ({ids}))")
        cur.execute(f"DELETE FROM Form_Submission WHERE Candidate_ID IN ({ids})")
        cur.execute(f"DELETE FROM Candidate_File WHERE Candidate_ID IN ({ids})")
        cur.execute(f"DELETE FROM User WHERE candidate_id IN ({ids})")
        cur.execute(f"DELETE FROM Candidate WHERE ID IN ({ids})")

    # 演示岗位与表单
    cur.execute("SELECT ID FROM Position WHERE position_name=%s", (POSITION_NAME,))
    pos_ids = [r[0] for r in cur.fetchall()]
    if pos_ids:
        pids = ",".join(map(str, pos_ids))
        cur.execute(f"DELETE FROM Application WHERE Pos_ID IN ({pids})")
        cur.execute(f"DELETE FROM Position WHERE ID IN ({pids})")

    cur.execute("SELECT ID FROM Form_Template WHERE Name IN (%s,%s)", (PROFILE_FORM_NAME, POSITION_FORM_NAME))
    tpl_ids = [r[0] for r in cur.fetchall()]
    if tpl_ids:
        tids = ",".join(map(str, tpl_ids))
        cur.execute(f"DELETE FROM Form_Answer WHERE Submission_ID IN (SELECT ID FROM Form_Submission WHERE Template_ID IN ({tids}))")
        cur.execute(f"DELETE FROM Form_Submission WHERE Template_ID IN ({tids})")
        cur.execute(f"DELETE FROM Form_Field WHERE Template_ID IN ({tids})")
        cur.execute(f"DELETE FROM Form_Template WHERE ID IN ({tids})")

    # 演示 HR
    cur.execute("SELECT ID FROM User WHERE username=%s", (HR_USERNAME,))
    rows = cur.fetchall()
    for (uid,) in rows:
        cur.execute("DELETE FROM App_Setting WHERE User_ID=%s", (uid,))
        cur.execute("DELETE FROM AI_API_Config WHERE User_ID=%s", (uid,))
        cur.execute("DELETE FROM User WHERE ID=%s", (uid,))
    conn.commit()


def fill_answers(fields):
    answers = {}
    for f in fields:
        t = f.get("field_type")
        opts = f.get("options") or []
        if t == "checkbox":
            answers[f["field_key"]] = opts[:2]
        elif t in ("select", "radio"):
            answers[f["field_key"]] = opts[0] if opts else ""
        elif t == "number":
            answers[f["field_key"]] = "3"
        elif t == "date":
            answers[f["field_key"]] = "2026-11-01"
        elif t == "email":
            answers[f["field_key"]] = "demo@example.com"
        elif t == "phone":
            answers[f["field_key"]] = PHONE
        elif t == "textarea":
            answers[f["field_key"]] = "演示数据：三年 Java 后端经验，熟悉 Spring Boot 与 MySQL。"
        else:
            answers[f["field_key"]] = "演示"
    return answers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="先删除演示数据再创建")
    parser.add_argument("--clean", action="store_true", help="只删除演示数据，不创建")
    args = parser.parse_args()

    conn = db()
    if args.clean:
        cleanup(conn)
        conn.close()
        print("已清理演示数据")
        return 0
    if args.reset:
        cleanup(conn)
        print("已清理旧演示数据")
    c = httpx.Client(base_url=BASE, timeout=30)
    try:
        # HR
        r = c.post("/api/auth/login", json={"username": HR_USERNAME, "password": HR_PASSWORD})
        if r.status_code != 200:
            r = c.post("/api/auth/register", json={"username": HR_USERNAME, "password": HR_PASSWORD, "phone": "13912340001", "real_name": "演示HR"})
            r.raise_for_status()
            print(f"创建 HR：{HR_USERNAME} / {HR_PASSWORD}")
        else:
            print(f"复用 HR：{HR_USERNAME}")
        H = {"Authorization": f"Bearer {r.json()['token']}"}

        # 岗位
        positions = c.get("/api/positions", headers=H, params={"include_hidden": True}).json()
        pos = next((p for p in positions if p["position_name"] == POSITION_NAME), None)
        if pos is None:
            pos = c.post("/api/positions", headers=H, json={
                "position_name": POSITION_NAME, "owner": "王 HR",
                "position_requirements": "3 年以上 Java 开发经验；熟悉 Spring Boot、MySQL；有高并发项目经验优先。",
            }).json()
            print(f"创建岗位：{POSITION_NAME}")
        else:
            print(f"复用岗位：{POSITION_NAME}")

        # 候选人
        r = c.post("/api/candidates", headers=H, json={
            "name": CANDIDATE_NAME, "phone": PHONE, "email": "chenchen@example.com", "remark": "演示数据",
        })
        if r.status_code == 409:
            found = c.get("/api/candidates", headers=H, params={"phone": PHONE}).json()
            if not found:
                raise RuntimeError("候选人已存在但查不到，请先 --reset")
            cand = found[0]
        else:
            r.raise_for_status()
            cand = r.json()
        print(f"候选人：{cand['name']} / {PHONE} / admin")

        # 简历（HR 上传）
        doc = fitz.open(); page = doc.new_page()
        page.insert_text((72, 72), "Chen Chen. Java Spring Boot MySQL. Three years backend experience.", fontsize=11)
        pdf = doc.tobytes(); doc.close()
        files = c.get(f"/api/candidates/{cand['id']}/files", headers=H).json()
        if not any(f["category"] == "resume" and f["is_current"] for f in files):
            c.post(f"/api/candidates/{cand['id']}/files", headers=H,
                   files={"file": ("陈晨-简历.pdf", pdf, "application/pdf")}, data={"category": "resume"}).raise_for_status()
            print("已上传演示简历")

        # 登录候选人
        r = c.post("/api/portal/auth/login", json={"phone": PHONE, "password": "admin"})
        r.raise_for_status()
        C = {"Authorization": f"Bearer {r.json()['token']}"}

        # 个人资料表
        templates = c.get("/api/form-templates", headers=H).json()
        profile = next((t for t in templates if t["scope"] == "profile" and t["is_active"]), None)
        if profile is None:
            profile = c.post("/api/form-templates", headers=H, json={
                "name": PROFILE_FORM_NAME, "scope": "profile", "description": "请补充基本信息，方便 HR 了解你。",
                "fields": [
                    {"field_key": "name_cn", "label": "姓名", "field_type": "text", "required": True, "sort_order": 1},
                    {"field_key": "years", "label": "工作年限", "field_type": "number", "required": True, "sort_order": 2},
                    {"field_key": "education", "label": "最高学历", "field_type": "select", "required": True,
                     "options": ["大专", "本科", "硕士", "博士"], "sort_order": 3},
                    {"field_key": "intro", "label": "自我介绍", "field_type": "textarea", "required": False, "sort_order": 4},
                ],
            }).json()
            print(f"创建表单：{PROFILE_FORM_NAME}")
        detail = c.get(f"/api/form-templates/{profile['id']}", headers=H).json()
        c.put(f"/api/portal/forms/{profile['id']}", headers=C,
              json={"answers": fill_answers(detail["fields"]), "submit": True}).raise_for_status()

        # 投递（临时停用 AI，稳定进入待人工筛选）
        cur = conn.cursor()
        cur.execute("SELECT ID, is_enabled FROM AI_API_Config")
        prev = [(int(a), int(b)) for a, b in cur.fetchall()]
        cur.execute("UPDATE AI_API_Config SET is_enabled=0"); conn.commit()
        try:
            r = c.post("/api/portal/applications", headers=C, json={"pos_id": pos["id"]})
            if r.status_code == 409:
                print("演示投递已存在，跳过")
                app_id = None
            else:
                r.raise_for_status()
                app_id = r.json()["application"]["id"]
                print(f"已创建演示投递：#{app_id}（待人工筛选）")
        finally:
            for cid, enabled in prev:
                cur.execute("UPDATE AI_API_Config SET is_enabled=%s WHERE ID=%s", (enabled, cid))
            conn.commit()

        # 岗位申请表
        if app_id:
            t = next((x for x in c.get("/api/form-templates", headers=H).json()
                      if x["scope"] == "position" and x["position_id"] == pos["id"] and x["is_active"]), None)
            if t is None:
                t = c.post("/api/form-templates", headers=H, json={
                    "name": POSITION_FORM_NAME, "scope": "position", "position_id": pos["id"],
                    "description": "请说明你的应聘动机与期望薪资。",
                    "fields": [
                        {"field_key": "motivation", "label": "应聘动机", "field_type": "textarea", "required": True, "sort_order": 1},
                        {"field_key": "salary", "label": "期望薪资", "field_type": "select", "required": True,
                         "options": ["10-15k", "15-20k", "20-25k"], "sort_order": 2},
                    ],
                }).json()
                print(f"创建表单：{POSITION_FORM_NAME}")
            tdetail = c.get(f"/api/form-templates/{t['id']}", headers=H).json()
            c.put(f"/api/portal/forms/{t['id']}", headers=C, params={"application_id": app_id},
                  json={"answers": fill_answers(tdetail["fields"]), "submit": True}).raise_for_status()
            print("已提交岗位申请表")

        print("\n演示数据就绪：")
        print(f"  HR        {HR_USERNAME} / {HR_PASSWORD}   → http://127.0.0.1:5173/login")
        print(f"  候选人    {PHONE} / admin             → http://127.0.0.1:5173/portal/login")
        print("  技术管理  tech / admin（如未创建请先跑 create_user.py）")
        return 0
    finally:
        c.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
