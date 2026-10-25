"""
阶段 4 自检：候选人岗位 + 投递 + AI 首筛 + 进度

覆盖：
  1. 无 AI 配置时投递仍成功 → pending_review
  2. 个人资料表未提交 → 400；提交后可投
  3. AI 通过 → 进入 resume；AI 不通过 → 已淘汰
  4. 重复投递 409
  5. 无简历 400；隐藏岗位列表不可见、详情/投递 404
  6. 候选人 B 不能看 A 的投递（404）
  7. 投递来源 source=portal
  8. 候选人响应不含 ai_comment / reason / evaluation
  9. 岗位申请表投递后补填，HR 能查看

运行（后端已启动）：
    .venv\\Scripts\\python -B scripts\\stage4_smoke_test.py
"""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import fitz  # noqa: E402
import httpx  # noqa: E402
import pymysql  # noqa: E402

BASE = os.getenv("ATS_BASE", "http://127.0.0.1:8001")
DB_PW = os.getenv("ATS_DB_PASSWORD", "your-password")
MOCK_PORT = 8011
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


def make_pdf(text: str) -> bytes:
    """生成一份带文本层的 PDF（ASCII，保证 PyMuPDF 能抽出来）。"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=11)
    data = doc.tobytes()
    doc.close()
    return data


class MockLLM(BaseHTTPRequestHandler):
    """假 AI：简历里含 FAILME 就回 fail，否则 pass。"""

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][1]["content"]
        resume = prompt.split("## 简历内容", 1)[1]
        out = {
            "name": "mock",
            "phone": "",
            "position_id": 1,
            "result": "fail" if "FAILME" in resume else "pass",
            "reason": "【mock】自动初筛理由",
        }
        content = "```json\n" + json.dumps(out, ensure_ascii=False) + "\n```"
        resp = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=60)
    tag = str(int(time.time()))
    base = int(time.time() * 1000) % 100000000
    ids = {"users": [], "candidates": [], "positions": [], "templates": [], "applications": [], "configs": []}
    prev_configs: list[tuple[int, int]] = []
    srv = None
    conn = None
    try:
        # 让测试 deterministic：先关掉库里已有的 AI 配置，结束时恢复
        conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=DB_PW, database=os.getenv("ATS_DB_NAME", "ats"))
        cur = conn.cursor()
        cur.execute("SELECT ID, is_enabled FROM AI_API_Config")
        prev_configs = [(int(a), int(b)) for a, b in cur.fetchall()]
        cur.execute("UPDATE AI_API_Config SET is_enabled=0")
        conn.commit()

        # ---------- 准备 ----------
        r = c.post("/api/auth/register", json={"username": f"stage4_hr_{tag}", "password": "secret123", "real_name": "测试HR", "phone": "139" + tag[-8:]})
        check("注册 HR", r.status_code == 201, r.text[:150])
        H = {"Authorization": f"Bearer {r.json()['token']}"}
        ids["users"].append(r.json()["user"]["id"])

        r = c.post("/api/positions", headers=H, json={"position_name": f"阶段4岗位_{tag}", "position_requirements": "3年Java"})
        pos = r.json()["id"]
        ids["positions"].append(pos)

        def new_candidate(name: str, offset: int):
            phone = f"136{(base + offset) % 100000000:08d}"
            rr = c.post("/api/candidates", headers=H, json={"name": name, "phone": phone})
            cid = rr.json()["id"]
            ids["candidates"].append(cid)
            lr = c.post("/api/portal/auth/login", json={"phone": phone, "password": "admin"})
            return cid, {"Authorization": f"Bearer {lr.json()['token']}"}

        cand_a, A = new_candidate(f"阶段4甲{tag}", 1)
        cand_b, B = new_candidate(f"阶段4乙{tag}", 2)
        cand_c, C = new_candidate(f"阶段4丙{tag}", 3)
        cand_d, D = new_candidate(f"阶段4丁{tag}", 4)

        def upload(cid, text: str, name: str):
            """简历由 HR 上传，候选人只读。"""
            r = c.post(
                f"/api/candidates/{cid}/files",
                headers=H,
                files={"file": (name, make_pdf(text), "application/pdf")},
                data={"category": "resume"},
            )
            return r

        check("HR 上传甲简历", upload(cand_a, "Candidate A. Java Spring MySQL. Five years experience.", "甲.pdf").status_code == 201)
        check("HR 上传乙简历（FAILME）", upload(cand_b, "Candidate B. FAILME. Junior developer with little experience.", "乙.pdf").status_code == 201)
        check("HR 上传丙简历", upload(cand_c, "Candidate C. Java backend developer. Three years.", "丙.pdf").status_code == 201)

        # ---------- 1. 无 AI 配置：降级 ----------
        r = c.post("/api/portal/applications", headers=C, json={"pos_id": pos})
        check("无 AI 配置投递仍成功", r.status_code == 201, r.text[:300])
        check("降级为 pending_review", r.json()["screening"] == "pending_review", str(r.json().get("screening")))
        check("停在 ai / 进行中", r.json()["application"]["current_stage"] == "ai" and r.json()["application"]["overall_status"] == "pending")
        c_app = r.json()["application"]["id"]
        ids["applications"].append(c_app)
        r = c.post("/api/portal/applications", headers=C, json={"pos_id": pos})
        check("重复投递 409", r.status_code == 409, f"{r.status_code}")

        # ---------- 2. 个人资料表 ----------
        r = c.post("/api/form-templates", headers=H, json={
            "name": f"资料表4_{tag}", "scope": "profile",
            "fields": [{"field_key": "name_cn", "label": "姓名", "field_type": "text", "required": True}],
        })
        t_profile = r.json()["id"]
        ids["templates"].append(t_profile)

        r = c.post("/api/portal/applications", headers=A, json={"pos_id": pos})
        check("资料表未提交投递 400", r.status_code == 400, f"{r.status_code} {r.text[:150]}")

        for token in (A, B):
            r = c.put(f"/api/portal/forms/{t_profile}", headers=token, json={"answers": {"name_cn": "张三"}, "submit": True})
            check("提交个人资料表", r.status_code == 200 and r.json()["status"] == "submitted", r.text[:150])

        # ---------- 3. AI 通过 / 不通过 ----------
        ra = c.post("/api/tech/auth/login", json={"username": "tech", "password": "admin"})
        check("技术管理员登录", ra.status_code == 200, ra.text[:150])
        TECH = {"Authorization": f"Bearer {ra.json()['token']}"}
        srv = HTTPServer(("127.0.0.1", MOCK_PORT), MockLLM)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        # 表单可见阶段默认 pro 起（v3.16），测试要在投递后就能填，先改成 ai 起
        c.put("/api/settings/portal-form-stage", headers=H, json={"position": "ai", "assessment": "ai"})

        r = c.post("/api/tech/ai-configs", headers=TECH, json={
            "name": "stage4-mock", "base_url": f"http://127.0.0.1:{MOCK_PORT}/v1",
            "api_key": "k", "model": "m", "is_enabled": True,
        })
        check("创建 mock AI 配置", r.status_code == 201, r.text[:150])
        cfg_id = r.json()["id"]
        ids["configs"].append(cfg_id)

        r = c.post("/api/portal/applications", headers=A, json={"pos_id": pos})
        check("甲投递成功", r.status_code == 201, r.text[:300])
        check("AI 通过 → ai_pass", r.json()["screening"] == "ai_pass", str(r.json().get("screening")))
        check("通过后进入 resume", r.json()["application"]["current_stage"] == "resume", str(r.json()["application"].get("current_stage")))
        a_app = r.json()["application"]["id"]
        ids["applications"].append(a_app)

        r = c.post("/api/portal/applications", headers=B, json={"pos_id": pos})
        check("乙投递成功", r.status_code == 201, r.text[:300])
        check("AI 不通过 → ai_fail", r.json()["screening"] == "ai_fail", str(r.json().get("screening")))
        check("不通过 → 已淘汰", r.json()["application"]["overall_status"] == "fail", str(r.json()["application"].get("overall_status")))
        b_app = r.json()["application"]["id"]
        ids["applications"].append(b_app)

        # ---------- 4. 来源 / 白名单 / 时间线 ----------
        r = c.get("/api/applications", headers=H, params={"can_id": cand_a, "pos_id": pos})
        check("HR 看到来源 portal", r.status_code == 200 and r.json()[0]["source"] == "portal", str(r.json()[:1]))
        check("HR 能看到 AI 结果", r.json()[0]["ai_result"] == "pass", str(r.json()[:1]))

        r = c.get(f"/api/portal/applications/{a_app}", headers=A)
        detail = r.json()
        check("甲投递详情 200", r.status_code == 200, r.text[:200])
        check("时间线 7 关", len(detail["timeline"]) == 7, str(len(detail.get("timeline", []))))
        check("AI 关 passed", detail["timeline"][0]["state"] == "passed", str(detail["timeline"][0]))
        check("简历筛选为当前关", detail["timeline"][1]["state"] == "current", str(detail["timeline"][1]))
        raw = json.dumps(detail, ensure_ascii=False)
        for key in ("ai_comment", "reason", "evaluation", "remark"):
            check(f"候选人响应不含 {key}", key not in raw, key)

        r = c.get(f"/api/portal/applications/{a_app}", headers=B)
        check("乙看甲的投递 404", r.status_code == 404, f"{r.status_code}")

        # ---------- 5. 岗位申请表：投递后补填 ----------
        r = c.post("/api/form-templates", headers=H, json={
            "name": f"岗位表4_{tag}", "scope": "position", "position_id": pos,
            "fields": [{"field_key": "motivation", "label": "应聘动机", "field_type": "textarea", "required": True}],
        })
        t_pos = r.json()["id"]
        ids["templates"].append(t_pos)

        r = c.get("/api/portal/forms", headers=A, params={"application_id": a_app})
        forms_ = r.json() if r.status_code == 200 else []
        check(
            "投递后可见岗位表",
            r.status_code == 200
            and any(x["scope"] == "profile" and x["id"] == t_profile for x in forms_)
            and any(x["scope"] == "position" and x["id"] == t_pos for x in forms_),
            r.text[:200],
        )
        r = c.get(f"/api/portal/applications/{a_app}", headers=A)
        check("详情显示岗位表待填", r.json()["form_status"]["position"] == "none", str(r.json().get("form_status")))

        r = c.put(
            f"/api/portal/forms/{t_pos}", headers=A, params={"application_id": a_app},
            json={"answers": {"motivation": "希望做后端"}, "submit": True},
        )
        check("提交岗位申请表", r.status_code == 200 and r.json()["status"] == "submitted", r.text[:200])
        r = c.get(f"/api/applications/{a_app}/forms", headers=H)
        check("HR 查看岗位答卷", r.status_code == 200 and len(r.json()) == 1, r.text[:200])

        # ---------- 6. 隐藏岗位 / 无简历 ----------
        r = c.put(f"/api/positions/{pos}", headers=H, json={"is_hidden": True})
        check("HR 设为暂不招", r.status_code == 200 and r.json()["is_hidden"] is True, r.text[:150])
        r = c.get("/api/portal/positions", headers=A)
        check("候选人列表不含隐藏岗位", all(x["id"] != pos for x in r.json()), str([x["id"] for x in r.json()]))
        r = c.get(f"/api/portal/positions/{pos}", headers=A)
        check("隐藏岗位详情 404", r.status_code == 404, f"{r.status_code}")
        r = c.post("/api/portal/applications", headers=D, json={"pos_id": pos})
        check("隐藏岗位投递 404", r.status_code == 404, f"{r.status_code}")

        r = c.put(f"/api/positions/{pos}", headers=H, json={"is_hidden": False})
        check("恢复在招", r.status_code == 200)
        r = c.post("/api/portal/applications", headers=D, json={"pos_id": pos})
        check("无简历投递 400", r.status_code == 400, f"{r.status_code} {r.text[:150]}")

        # ---------- 7. 列表 ----------
        r = c.get("/api/portal/applications", headers=A)
        check("甲的投递列表 1 条", r.status_code == 200 and len(r.json()) == 1, r.text[:200])
        check("列表带职位与阶段", r.json()[0]["position"]["id"] == pos and r.json()[0]["current_stage"] == "resume")

    finally:
        if srv is not None:
            srv.shutdown()
        try:
            if conn is None:
                conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=DB_PW, database=os.getenv("ATS_DB_NAME", "ats"))
            cur = conn.cursor()
            cand_ids = ",".join(map(str, ids["candidates"])) or "0"
            app_ids = ",".join(map(str, ids["applications"])) or "0"
            tpl_ids = ",".join(map(str, ids["templates"])) or "0"
            user_ids = ",".join(map(str, ids["users"])) or "0"
            pos_ids = ",".join(map(str, ids["positions"])) or "0"
            cfg_ids = ",".join(map(str, ids["configs"])) or "0"
            cur.execute(f"DELETE FROM Form_Answer WHERE Submission_ID IN (SELECT ID FROM Form_Submission WHERE Candidate_ID IN ({cand_ids}) OR Application_ID IN ({app_ids}))")
            cur.execute(f"DELETE FROM Form_Submission WHERE Candidate_ID IN ({cand_ids}) OR Application_ID IN ({app_ids})")
            cur.execute(f"DELETE FROM Candidate_File WHERE Candidate_ID IN ({cand_ids})")
            cur.execute(f"DELETE FROM Application WHERE Can_ID IN ({cand_ids}) OR ID IN ({app_ids})")
            cur.execute(f"DELETE FROM AI_API_Config WHERE ID IN ({cfg_ids})")
            cur.execute(f"DELETE FROM User WHERE candidate_id IN ({cand_ids}) OR ID IN ({user_ids})")
            cur.execute(f"DELETE FROM Candidate WHERE ID IN ({cand_ids})")
            cur.execute(f"DELETE FROM Form_Field WHERE Template_ID IN ({tpl_ids})")
            cur.execute(f"DELETE FROM Form_Template WHERE ID IN ({tpl_ids})")
            cur.execute(f"DELETE FROM Position WHERE ID IN ({pos_ids})")
            for cid, enabled in prev_configs:
                cur.execute("UPDATE AI_API_Config SET is_enabled=%s WHERE ID=%s", (enabled, cid))
            conn.commit()
            for t in ("Candidate_File", "Form_Submission", "Candidate", "Application", "Form_Template", "AI_API_Config", "Position"):
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
