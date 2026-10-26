"""
【这个文件是干什么的？】——用「假 AI」测试 AI 录入的成功路径
真正的 AI 要钱、要网、回答还不固定，没法用来做自动测试。
所以这里在本机 8009 端口起一个「假 AI 服务」（MockLLM）：它假装自己是大模型，
收到简历后按固定规则回答——简历里有 NOPOS 就说「没匹配的岗位」，有 FAILME 就说「不合格」，否则「合格」。

这样就能稳定地验证：识别姓名、匹配岗位、pass 自动推进、fail 标记淘汰、未匹配不建档、
重复不建档，以及「第一个 AI 配置坏了会自动换第二个」这个重试逻辑。

用法同 smoke_test.py。跑完自动清理。
"""
import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pymysql

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"
MOCK_PORT = 8009  # 假 AI 监听的端口
STAMP = str(int(time.time()))
PYMYSQL_PW = os.environ.get("ATS_DB_PASSWORD", "your-password")  # MySQL root 密码，可用环境变量 ATS_DB_PASSWORD 覆盖
calls = []  # 记下假 AI 被请求过的网址，用来验证「自动补 /chat/completions」
prev_configs = []  # 测试前库里的 AI 配置启用状态，结束时恢复


class MockLLM(BaseHTTPRequestHandler):
    """假 AI 服务：模仿 OpenAI 兼容接口的回答格式。"""

    def log_message(self, *a):
        pass  # 不打印访问日志，免得刷屏

    def do_POST(self):
        """收到 POST 请求时执行。读出提示词，按规则拼一个假回答。"""
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = body["messages"][1]["content"]  # messages[1] 是 user 那条（[0] 是 system 人设）
        calls.append(self.path)
        resume = prompt.split("## 简历内容", 1)[1]
        name = re.search(r"姓名[:：]\s*(\S+)", resume).group(1)  # 从「姓名：xxx」里抠出名字
        phone_m = re.search(r"手机号[:：]\s*(1[3-9]\d{9})", resume)
        phone = phone_m.group(1) if phone_m else ""
        pos_ids = [int(x) for x in re.findall(r'"id":\s*(\d+)', prompt.split("## 简历内容")[0])]  # 岗位列表里的编号
        if "NOPOS" in resume:
            out = {"name": name, "phone": phone, "position_id": None, "result": "fail", "reason": "简历方向与所有岗位无关"}
        else:
            out = {"name": name, "phone": phone, "position_id": pos_ids[0], "result": "fail" if "FAILME" in resume else "pass",
                   "reason": "mock 评估理由"}
        # 故意加 ```json 围栏，测试 parse_json_object 能不能剥掉
        content = "```json\n" + json.dumps(out, ensure_ascii=False) + "\n```"
        resp = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)


def main():
    srv = HTTPServer(("127.0.0.1", MOCK_PORT), MockLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    c = httpx.Client(base_url=BASE, timeout=60)
    ids = {"users": [], "positions": [], "configs": []}
    ok = 0

    def check(cond, msg, detail=""):
        nonlocal ok
        assert cond, f"{msg} {detail}"
        ok += 1
        print(f"  ok  {msg}")

    try:
        r = c.post("/api/auth/register", json={"username": f"mock_{STAMP}", "password": "secret123", "real_name": "测试HR", "phone": "139" + STAMP[-8:]})
        ids["users"].append(r.json()["user"]["id"])
        H = {"Authorization": f"Bearer {r.json()['token']}"}
        # v3.15：AI 配置是系统级的，由技术管理员维护
        ra = c.post("/api/tech/auth/login", json={"username": "tech", "password": "admin"})
        T = {"Authorization": f"Bearer {ra.json()['token']}"}
        conn0 = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=PYMYSQL_PW, database=os.getenv("ATS_DB_NAME", "ats"))
        cur0 = conn0.cursor()
        cur0.execute("SELECT ID, is_enabled FROM ai_api_config")
        prev_configs.extend((int(a), int(b)) for a, b in cur0.fetchall())
        cur0.execute("UPDATE ai_api_config SET is_enabled=0")
        conn0.commit(); conn0.close()

        r = c.post("/api/positions", headers=H, json={"position_name": f"Java工程师_{STAMP}", "position_requirements": "3年Java"})
        p1 = r.json()["id"]; ids["positions"].append(p1)
        # 配置 1 指向死端口，配置 2 指向 mock；轮询下第 0 条先撞死配置再换 mock
        r = c.post("/api/tech/ai-configs", headers=T, json={"name": "dead", "base_url": "http://127.0.0.1:9/v1", "api_key": "k", "model": "m", "is_enabled": True})
        ids["configs"].append(r.json()["id"])
        r = c.post("/api/tech/ai-configs", headers=T, json={"name": "mock", "base_url": f"http://127.0.0.1:{MOCK_PORT}/v1", "api_key": "k", "model": "m", "is_enabled": True})
        ids["configs"].append(r.json()["id"])

        ai_phone = "139" + STAMP[-8:]
        nopos_text = f"姓名：孙七_{STAMP}\nNOPOS 资深厨师，擅长川菜粤菜，十年后厨管理经验。"
        texts = [
            f"姓名：王五_{STAMP}\n5年Java开发经验，精通Spring Boot、MySQL，主导过电商系统重构。",
            f"姓名：赵六_{STAMP}\nFAILME 应届生，仅了解Java基础语法，无项目经验。",
            f"姓名：周八_{STAMP}\n手机号：{ai_phone}\n3年Java开发经验，熟悉Spring Cloud。",
        ]
        r = c.post("/api/ai-screen/intake", headers=H, data={"texts": texts, "pos_id": p1})
        check(r.status_code == 200, "intake 200")
        res = r.json()["results"]
        check(res[0]["status"] == "ok" and res[0]["ai_result"] == "pass" and res[0]["config_used"] == "mock", f"第 0 条：死配置失败后换 mock 成功（重试生效） {res[0]}")
        check(res[0]["candidate_name"] == f"王五_{STAMP}" and res[0]["position_id"] == p1 and res[0]["application_id"], "识别姓名 + 匹配岗位 + 建档")
        d = c.get(f"/api/applications/{res[0]['application_id']}", headers=H).json()
        check(d["current_stage"] == "resume" and d["overall_status"] == "pending" and d["ai_result"] == "pass" and d["ai_comment"] == "mock 评估理由", "pass 自动推进到 resume 并写 ai_comment")
        check(res[1]["status"] == "ok" and res[1]["ai_result"] == "fail", "第 1 条：fail 建档")
        check("人工复核" in res[1]["message"], "fail 不自动淘汰，提示待人工复核")
        d = c.get(f"/api/applications/{res[1]['application_id']}", headers=H).json()
        check(d["current_stage"] == "ai" and d["overall_status"] == "pending" and d["ai_result"] == "fail", "fail → 停在 ai、待人工复核（不自动淘汰，v3.17 P0-2）")
        check(res[2]["status"] == "ok" and res[2]["phone"] == ai_phone, "第 2 条：AI 识别出手机号")
        cands = c.get("/api/candidates", headers=H, params={"name": STAMP}).json()
        check(sorted(x["name"] for x in cands) == sorted([f"王五_{STAMP}", f"赵六_{STAMP}", f"周八_{STAMP}"]), "只为建档条目创建候选人，备注 AI录入")
        check(all(x["remark"] == "AI录入" for x in cands), "候选人备注 AI录入")
        zhou = next(x for x in cands if x["name"] == f"周八_{STAMP}")
        check(zhou["phone"] == ai_phone and zhou["has_account"] is True, "手机号写入候选人并自动开通账号")
        r = c.post("/api/portal/auth/login", json={"phone": ai_phone, "password": "admin"})
        check(r.status_code == 200 and r.json()["candidate"]["id"] == zhou["id"], "AI 建档的候选人可直接用手机号登录")
        check(all(p.endswith("/v1/chat/completions") for p in calls), "base_url 自动补 /chat/completions")

        # 自动识别模式：AI 说都不匹配 → 不建档
        r = c.post("/api/ai-screen/intake", headers=H, data={"texts": [nopos_text]})
        check(r.json()["results"][0]["status"] == "no_position", "自动模式未匹配岗位 → 不建档", str(r.json()["results"][0]))

        r = c.post("/api/ai-screen/intake", headers=H, data={"texts": [texts[0]], "pos_id": p1})
        check(r.json()["results"][0]["status"] == "duplicate", "同人同岗再次录入 → duplicate 不重复建档")
        check(len(c.get("/api/applications", headers=H, params={"pos_id": p1}).json()) == 3, "投递仍为 3 条")
        print(f"\n全部通过：{ok} 项断言")
    finally:
        conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=PYMYSQL_PW, database=os.getenv("ATS_DB_NAME", "ats"))
        cur = conn.cursor()
        cur.execute(f"DELETE FROM application WHERE Pos_ID IN ({','.join(map(str, ids['positions'])) or 0})")
        cur.execute(f"DELETE FROM user WHERE role='candidate' AND candidate_id IN (SELECT ID FROM candidate WHERE name LIKE '%{STAMP}%')")
        cur.execute(f"DELETE FROM candidate WHERE name LIKE '%{STAMP}'")
        cur.execute(f"DELETE FROM ai_api_config WHERE ID IN ({','.join(map(str, ids['configs'])) or 0})")
        for cid, enabled in prev_configs:
            cur.execute("UPDATE ai_api_config SET is_enabled=%s WHERE ID=%s", (enabled, cid))
        cur.execute(f"DELETE FROM position WHERE ID IN ({','.join(map(str, ids['positions'])) or 0})")
        cur.execute(f"DELETE FROM user WHERE ID IN ({','.join(map(str, ids['users'])) or 0})")
        conn.commit()
        for t in ("application", "candidate", "position", "ai_api_config", "user"):
            cur.execute(f"SELECT COUNT(*) FROM `{t}`"); print(f"  cleanup {t}: {cur.fetchone()[0]} rows left")
        conn.close()
        srv.shutdown()


if __name__ == "__main__":
    main()
