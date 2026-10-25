"""
阶段 3 自检：文件 + 可配置表单

覆盖：
  1. HR 上传/替换/删除文件；候选人只读列表/下载；越权 404
  2. 文件类型、空文件、10MB 上限、413
  3. HR 建个人资料表（9 种字段）、重复启用拦截、字段校验
  4. 候选人保存草稿 → 提交；必填缺失 400；HR 查看答卷
  5. 改字段版本 +1，历史答案保留
  6. 岗位申请表：建投递 → 候选人填写 → HR 查看；他人投递 404
  7. 候选人 token 访问 HR 表单接口 403

运行（后端已启动）：
    .venv\\Scripts\\python -B scripts\\stage3_smoke_test.py
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
import pymysql  # noqa: E402

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
    c = httpx.Client(base_url=BASE, timeout=30)
    tag = str(int(time.time()))
    ids = {"users": [], "candidates": [], "positions": [], "templates": [], "applications": []}
    try:
        # ---------- 准备 ----------
        r = c.post("/api/auth/register", json={"username": f"stage3_hr_{tag}", "password": "secret123"})
        check("注册 HR", r.status_code == 201, r.text[:150])
        H = {"Authorization": f"Bearer {r.json()['token']}"}
        ids["users"].append(r.json()["user"]["id"])

        r = c.post("/api/positions", headers=H, json={"position_name": f"阶段3岗位_{tag}", "position_requirements": "3年开发"})
        check("建岗位", r.status_code == 201, r.text[:150])
        pos = r.json()["id"]
        ids["positions"].append(pos)

        phone1 = f"138{int(time.time() * 1000) % 100000000:08d}"
        r = c.post("/api/candidates", headers=H, json={"name": f"阶段3甲{tag}", "phone": phone1})
        check("建候选人甲", r.status_code == 201, r.text[:150])
        cand1 = r.json()["id"]
        ids["candidates"].append(cand1)
        r = c.post("/api/portal/auth/login", json={"phone": phone1, "password": "admin"})
        check("候选人甲登录", r.status_code == 200, r.text[:150])
        C1 = {"Authorization": f"Bearer {r.json()['token']}"}

        phone2 = f"137{int(time.time() * 1000) % 100000000:08d}"
        r = c.post("/api/candidates", headers=H, json={"name": f"阶段3乙{tag}", "phone": phone2})
        cand2 = r.json()["id"]
        ids["candidates"].append(cand2)
        r = c.post("/api/portal/auth/login", json={"phone": phone2, "password": "admin"})
        C2 = {"Authorization": f"Bearer {r.json()['token']}"}

        # ---------- 文件（HR 上传，候选人只读） ----------
        pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
        r = c.post(
            f"/api/candidates/{cand1}/files",
            headers=H,
            files={"file": ("我的简历.pdf", pdf, "application/pdf")},
            data={"category": "resume"},
        )
        check("HR 上传简历 201", r.status_code == 201, r.text[:200])
        f1 = r.json()
        check("首份简历为当前版本", f1.get("is_current") is True, str(f1))

        r = c.get("/api/portal/files", headers=C1)
        check("候选人文件列表 1 条（只读）", r.status_code == 200 and len(r.json()) == 1, r.text[:150])

        r = c.get(f"/api/portal/files/{f1['id']}/download", headers=C1)
        check("候选人下载内容一致", r.status_code == 200 and r.content == pdf, f"{r.status_code} {len(r.content)}")

        r = c.post(
            "/api/portal/files",
            headers=C1,
            files={"file": ("候选人想上传.pdf", pdf, "application/pdf")},
            data={"category": "resume"},
        )
        check("候选人不能上传文件（405）", r.status_code == 405, f"{r.status_code}")
        r = c.delete(f"/api/portal/files/{f1['id']}", headers=C1)
        check("候选人不能删除文件（404/405）", r.status_code in (404, 405), f"{r.status_code}")

        r = c.post(
            f"/api/candidates/{cand1}/files",
            headers=H,
            files={"file": ("简历v2.pdf", pdf, "application/pdf")},
            data={"category": "resume"},
        )
        check("HR 上传第二份简历", r.status_code == 201, r.text[:150])
        f2 = r.json()
        r = c.get("/api/portal/files", headers=C1, params={"category": "resume"})
        rows = r.json()
        check("只有一份 current 简历", sum(1 for x in rows if x["is_current"]) == 1, str([(x["id"], x["is_current"]) for x in rows]))
        check("旧简历 is_current=false", any(x["id"] == f1["id"] and not x["is_current"] for x in rows))

        r = c.get(f"/api/candidates/{cand1}/files", headers=H)
        check("HR 看候选人文件（2 份简历）", r.status_code == 200 and len(r.json()) == 2, r.text[:150])
        r = c.get(f"/api/files/{f1['id']}/download", headers=H)
        check("HR 下载旧简历", r.status_code == 200 and r.content == pdf)

        r = c.get(f"/api/portal/files/{f1['id']}/download", headers=C2)
        check("候选人乙下载甲的文件 404", r.status_code == 404, f"{r.status_code}")

        r = c.post(f"/api/candidates/{cand1}/files", headers=H, files={"file": ("bad.exe", b"MZ", "application/octet-stream")})
        check("不支持的类型 400", r.status_code == 400, f"{r.status_code}")
        r = c.post(f"/api/candidates/{cand1}/files", headers=H, files={"file": ("empty.pdf", b"", "application/pdf")})
        check("空文件 400", r.status_code == 400, f"{r.status_code}")
        big = b"x" * (10 * 1024 * 1024 + 1)
        r = c.post(f"/api/candidates/{cand1}/files", headers=H, files={"file": ("big.pdf", big, "application/pdf")})
        check("超过 10MB 返回 413", r.status_code == 413, f"{r.status_code}")

        r = c.post(
            f"/api/candidates/{cand1}/files",
            headers=H,
            files={"file": ("HR上传证书.pdf", pdf, "application/pdf")},
            data={"category": "certificate"},
        )
        check("HR 上传证书", r.status_code == 201, r.text[:150])
        f_hr = r.json()
        r = c.delete(f"/api/files/{f2['id']}", headers=H)
        check("HR 删除文件 204", r.status_code == 204, f"{r.status_code}")

        # ---------- 个人资料表 ----------
        fields = [
            {"field_key": "name_cn", "label": "姓名", "field_type": "text", "required": True, "sort_order": 1},
            {"field_key": "intro", "label": "自我介绍", "field_type": "textarea", "required": False, "sort_order": 2},
            {"field_key": "years", "label": "工作年限", "field_type": "number", "required": True, "sort_order": 3},
            {"field_key": "available_date", "label": "可入职日期", "field_type": "date", "required": False, "sort_order": 4},
            {"field_key": "education", "label": "最高学历", "field_type": "select", "required": True,
             "options": ["大专", "本科", "硕士"], "sort_order": 5},
            {"field_key": "gender", "label": "性别", "field_type": "radio", "required": False,
             "options": ["男", "女"], "sort_order": 6},
            {"field_key": "skills", "label": "技能", "field_type": "checkbox", "required": False,
             "options": ["Java", "Python", "Go"], "sort_order": 7},
            {"field_key": "email", "label": "邮箱", "field_type": "email", "required": False, "sort_order": 8},
            {"field_key": "contact_phone", "label": "联系电话", "field_type": "phone", "required": False, "sort_order": 9},
        ]
        r = c.post(
            "/api/form-templates",
            headers=H,
            json={"name": f"资料表_{tag}", "scope": "profile", "description": "请完善", "fields": fields},
        )
        check("建个人资料表（9 字段）", r.status_code == 201, r.text[:300])
        t1 = r.json()
        ids["templates"].append(t1["id"])
        check("字段数 = 9", t1["field_count"] == 9, str(t1.get("field_count")))

        r = c.post("/api/form-templates", headers=H, json={"name": f"重复_{tag}", "scope": "profile", "fields": []})
        check("同范围再建启用模板 400", r.status_code == 400, f"{r.status_code}")

        r = c.post(
            "/api/form-templates", headers=H,
            json={"name": f"坏字段_{tag}", "scope": "profile", "fields": [
                {"field_key": "x", "label": "X", "field_type": "select", "required": True}
            ]},
        )
        check("select 缺选项 400", r.status_code == 400, f"{r.status_code}")

        r = c.get("/api/portal/forms", headers=C1)
        forms_ = r.json() if r.status_code == 200 else []
        mine = next((x for x in forms_ if x["scope"] == "profile" and x["id"] == t1["id"]), None)
        check("候选人可填列表含资料表", r.status_code == 200 and mine is not None and mine["my_status"] == "none", r.text[:200])

        r = c.get(f"/api/portal/forms/{t1['id']}", headers=C1)
        check("候选人拿到 9 个字段", r.status_code == 200 and len(r.json()["template"]["fields"]) == 9, r.text[:200])

        r = c.put(f"/api/portal/forms/{t1['id']}", headers=C1, json={"answers": {"name_cn": "张三"}, "submit": False})
        check("保存草稿", r.status_code == 200 and r.json()["status"] == "draft", r.text[:200])

        r = c.put(f"/api/portal/forms/{t1['id']}", headers=C1, json={"answers": {"name_cn": "", "years": "3"}, "submit": True})
        check("必填缺失 400", r.status_code == 400, f"{r.status_code} {r.text[:150]}")

        valid = {
            "name_cn": "张三", "intro": "五年开发经验", "years": "5", "available_date": "2026-11-01",
            "education": "本科", "gender": "男", "skills": ["Java", "Python"],
            "email": "zhangsan@example.com", "contact_phone": "13800138000",
        }
        r = c.put(f"/api/portal/forms/{t1['id']}", headers=C1, json={"answers": valid, "submit": True})
        check("提交答卷", r.status_code == 200 and r.json()["status"] == "submitted", r.text[:300])
        check("多选值以数组返回", r.json()["answers"].get("skills") == ["Java", "Python"], str(r.json().get("answers")))

        r = c.get(f"/api/candidates/{cand1}/forms", headers=H)
        check("HR 查看候选人答卷", r.status_code == 200 and len(r.json()) == 1, r.text[:300])
        check("HR 答卷带候选人姓名", r.json()[0]["candidate_name"] == f"阶段3甲{tag}", str(r.json()[0].get("candidate_name")))
        check("HR 答卷带中文标签 items", len(r.json()[0]["items"]) == 9, str(len(r.json()[0]["items"])))

        # 改字段：去掉 intro，加 wechat，版本 +1
        fields2 = [f for f in fields if f["field_key"] != "intro"]
        fields2.append({"field_key": "wechat", "label": "微信", "field_type": "text", "required": False, "sort_order": 10})
        r = c.put(f"/api/form-templates/{t1['id']}/fields", headers=H, json={"fields": fields2})
        check("保存字段版本 +1", r.status_code == 200 and r.json()["version"] == 2, r.text[:200])
        r = c.get(f"/api/candidates/{cand1}/forms", headers=H)
        intro_item = next((x for x in r.json()[0]["items"] if x["field_key"] == "intro"), None)
        check("软删除字段的历史答案保留", intro_item is not None and intro_item["is_active"] is False, str(intro_item))

        # ---------- 岗位申请表 ----------
        pos_fields = [
            {"field_key": "motivation", "label": "应聘动机", "field_type": "textarea", "required": True, "sort_order": 1},
            {"field_key": "salary", "label": "期望薪资", "field_type": "select", "required": True,
             "options": ["10-15k", "15-20k"], "sort_order": 2},
        ]
        r = c.post(
            "/api/form-templates",
            headers=H,
            json={"name": f"岗位表_{tag}", "scope": "position", "position_id": pos, "fields": pos_fields},
        )
        check("建岗位申请表", r.status_code == 201, r.text[:200])
        t2 = r.json()
        ids["templates"].append(t2["id"])

        r = c.post("/api/applications", headers=H, json={"can_id": cand1, "pos_id": pos})
        check("建投递", r.status_code == 201, r.text[:200])
        app_id = r.json()["id"]
        ids["applications"].append(app_id)

        r = c.get("/api/portal/forms", headers=C1, params={"application_id": app_id})
        forms_ = r.json() if r.status_code == 200 else []
        has_profile = any(x["scope"] == "profile" and x["id"] == t1["id"] for x in forms_)
        has_position = any(x["scope"] == "position" and x["id"] == t2["id"] for x in forms_)
        check("候选人可填列表含岗位表", r.status_code == 200 and has_profile and has_position, r.text[:200])

        r = c.get(f"/api/portal/forms/{t2['id']}", headers=C1, params={"application_id": app_id})
        check("岗位表字段 2 个", r.status_code == 200 and len(r.json()["template"]["fields"]) == 2, r.text[:200])

        r = c.put(
            f"/api/portal/forms/{t2['id']}",
            headers=C1,
            params={"application_id": app_id},
            json={"answers": {"motivation": "看好这个岗位", "salary": "15-20k"}, "submit": True},
        )
        check("提交岗位申请表", r.status_code == 200 and r.json()["status"] == "submitted", r.text[:200])

        r = c.get(f"/api/applications/{app_id}/forms", headers=H)
        check("HR 查看投递的岗位答卷", r.status_code == 200 and len(r.json()) == 1, r.text[:200])

        r = c.get(f"/api/portal/forms/{t2['id']}", headers=C2, params={"application_id": app_id})
        check("他人投递的岗位表 404", r.status_code == 404, f"{r.status_code}")
        r = c.put(
            f"/api/portal/forms/{t2['id']}",
            headers=C2,
            params={"application_id": app_id},
            json={"answers": {"motivation": "x", "salary": "10-15k"}, "submit": True},
        )
        check("他人不能提交 404", r.status_code == 404, f"{r.status_code}")

        r = c.get("/api/form-templates", headers=C1)
        check("候选人 token 访问 HR 表单接口 403", r.status_code == 403, f"{r.status_code}")

    finally:
        # 数据库清理：按依赖顺序删
        try:
            conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=DB_PW, database="ats")
            cur = conn.cursor()
            cand_ids = ",".join(map(str, ids["candidates"])) or "0"
            tpl_ids = ",".join(map(str, ids["templates"])) or "0"
            app_ids = ",".join(map(str, ids["applications"])) or "0"
            user_ids = ",".join(map(str, ids["users"])) or "0"
            pos_ids = ",".join(map(str, ids["positions"])) or "0"
            cur.execute(f"DELETE FROM Form_Answer WHERE Submission_ID IN (SELECT ID FROM Form_Submission WHERE Candidate_ID IN ({cand_ids}) OR Application_ID IN ({app_ids}))")
            cur.execute(f"DELETE FROM Form_Submission WHERE Candidate_ID IN ({cand_ids}) OR Application_ID IN ({app_ids})")
            cur.execute(f"DELETE FROM Candidate_File WHERE Candidate_ID IN ({cand_ids})")
            cur.execute(f"DELETE FROM Application WHERE Can_ID IN ({cand_ids}) OR ID IN ({app_ids})")
            cur.execute(f"DELETE FROM User WHERE candidate_id IN ({cand_ids}) OR ID IN ({user_ids})")
            cur.execute(f"DELETE FROM Candidate WHERE ID IN ({cand_ids})")
            cur.execute(f"DELETE FROM Form_Field WHERE Template_ID IN ({tpl_ids})")
            cur.execute(f"DELETE FROM Form_Template WHERE ID IN ({tpl_ids})")
            cur.execute(f"DELETE FROM Position WHERE ID IN ({pos_ids})")
            conn.commit()
            for t in ("Candidate_File", "Form_Answer", "Form_Submission", "Form_Template", "Candidate", "Application", "Position"):
                cur.execute(f"SELECT COUNT(*) FROM `{t}`")
                print(f"  cleanup {t}: {cur.fetchone()[0]} rows left")
            conn.close()
        except Exception as e:  # noqa: BLE001
            print(f"清理失败：{e}")
        c.close()

    print(f"\n结果：通过 {PASSED} 项，失败 {FAILED} 项")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
