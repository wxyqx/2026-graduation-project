"""
【这个文件是干什么的？】——后端的「体检单」
写好代码后怎么知道它真的能用？一个个手点太累，所以写一个脚本自动跑一遍：
注册 → 登录 → 建岗位 → 建候选人 → 建投递 → 一关关推进、撤回 → AI 配置 → 导出……
每一步都「断言」（assert）结果必须是我们预期的，不对就立刻报错停下。

这种「把主要功能快速跑一遍」的测试叫「冒烟测试」（比喻：机器一开机先看冒不冒烟）。
以后改了代码，跑一遍这个脚本，72 项全绿就说明没改坏。

用法：先起服务，再 `python scripts/smoke_test.py [服务地址]`，默认 http://127.0.0.1:8001。
测试完自动清理本次创建的数据（直连数据库删除，因为投递/候选人/用户没有删除接口）。
"""
import io
import sys
import time

import fitz
import httpx
import pymysql
from openpyxl import load_workbook

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"  # 服务地址，可以从命令行传
STAMP = str(int(time.time()))  # 当前时间戳，拼进用户名/岗位名，保证每次跑都不重名
created = {"users": [], "positions": [], "candidates": [], "applications": [], "configs": []}  # 记下建了什么，最后好删
passed = 0  # 通过了几项


def check(cond, msg):
    """检查一件事：cond 为真就打一行 ok，为假就报错停下。整个脚本就是几十个 check 串起来。"""
    global passed
    if not cond:
        raise AssertionError(msg)
    passed += 1
    print(f"  ok  {msg}")


def make_pdf(text: str) -> bytes:
    """用 PyMuPDF 在内存里造一个带文字的小 PDF，模拟用户上传的简历。fontname="china-s" 是内置的中文字体。"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11, fontname="china-s")
    data = doc.tobytes()
    doc.close()
    return data


def run():
    c = httpx.Client(base_url=BASE, timeout=30)  # httpx 是发网络请求的工具，像一个程序版的浏览器

    print("== health / auth")
    check(c.get("/api/health").json()["database"] == "up", "health ok")
    ua, pw = f"smoke_{STAMP}", "secret123"
    r = c.post("/api/auth/register", json={"username": ua, "password": pw})
    check(r.status_code == 201 and r.json()["token"], "register 201 + token")
    created["users"].append(r.json()["user"]["id"])
    check(c.post("/api/auth/register", json={"username": ua, "password": pw}).status_code == 409, "重名 409")
    check(c.post("/api/auth/register", json={"username": "a", "password": pw}).status_code == 422, "用户名过短 422")
    check(c.post("/api/auth/login", json={"username": ua, "password": "wrong"}).status_code == 401, "密码错误 401")
    r = c.post("/api/auth/login", json={"username": ua, "password": pw})
    check(r.status_code == 200, "login 200")
    token = r.json()["token"]
    H = {"Authorization": f"Bearer {token}"}  # 以后每个请求都带这个「通行证」请求头，模拟已登录
    check(c.get("/api/auth/me", headers=H).json()["username"] == ua, "me 返回当前用户")
    check(c.get("/api/auth/me").status_code == 401, "无 token 401")
    check(c.get("/api/positions", headers={"Authorization": "Bearer bad.token"}).status_code == 401, "坏 token 401")
    check(c.get("/api/applications").status_code == 401, "业务接口无 token 401")

    print("== positions")
    r = c.post("/api/positions", headers=H, json={"position_name": f"Java工程师_{STAMP}", "owner": "HR-A",
                                                  "position_requirements": "3年以上Java，熟悉Spring Boot/MySQL"})
    check(r.status_code == 201, "创建岗位 201")
    p1 = r.json()["id"]; created["positions"].append(p1)
    r = c.post("/api/positions", headers=H, json={"position_name": f"前端工程师_{STAMP}", "position_requirements": "Vue3"})
    p2 = r.json()["id"]; created["positions"].append(p2)
    check(c.post("/api/positions", headers=H, json={"owner": "x"}).status_code == 422, "岗位缺名称 422")
    r = c.put(f"/api/positions/{p2}", headers=H, json={"owner": "HR-B"})
    check(r.json()["owner"] == "HR-B" and r.json()["position_name"].startswith("前端"), "更新岗位仅改 owner")
    check(any(p["id"] == p1 for p in c.get("/api/positions", headers=H).json()), "岗位列表包含新建")
    check(c.get("/api/positions/999999", headers=H).status_code == 404, "岗位不存在 404")

    print("== candidates")
    r = c.post("/api/candidates", headers=H, json={"name": f"张三_{STAMP}", "remark": "内推"})
    check(r.status_code == 201, "创建候选人 201")
    c1 = r.json()["id"]; created["candidates"].append(c1)
    r = c.post("/api/candidates", headers=H, json={"name": f"李四_{STAMP}"})
    c2 = r.json()["id"]; created["candidates"].append(c2)
    names = [x["name"] for x in c.get("/api/candidates", headers=H, params={"name": f"张三_{STAMP}"}).json()]
    check(names == [f"张三_{STAMP}"], "姓名模糊查询")
    check(len(c.get("/api/candidates", headers=H, params={"remark": "内推"}).json()) >= 1, "备注模糊查询")
    check(len(c.get("/api/candidates", headers=H, params={"name": f"张三_{STAMP}", "remark": "内推"}).json()) == 1, "姓名+备注组合筛选")
    check(all(x["application_count"] >= 0 for x in c.get("/api/candidates", headers=H, params={"has_application": "yes"}).json()), "按有无投递筛选(有)")
    check(c.get("/api/candidates", headers=H, params={"has_application": "no"}).status_code == 200, "按有无投递筛选(无)")
    check(c.put(f"/api/candidates/{c1}", headers=H, json={"remark": "改备注"}).json()["remark"] == "改备注", "更新备注")

    print("== applications + 状态机")
    r = c.post("/api/applications", headers=H, json={"can_id": c1, "pos_id": p1})
    check(r.status_code == 201, "创建投递 201")
    a1 = r.json()["id"]; created["applications"].append(a1)
    d = r.json()
    check(d["current_stage"] == "ai" and d["overall_status"] == "pending" and len(d["stages"]) == 8, "初始 ai/pending/8 阶段")
    check(c.post("/api/applications", headers=H, json={"can_id": c1, "pos_id": p1}).status_code == 409, "重复投递 409")
    check(c.post("/api/applications", headers=H, json={"can_id": 999999, "pos_id": p1}).status_code == 404, "候选人不存在 404")
    r = c.post("/api/applications", headers=H, json={"can_id": c2, "pos_id": p2})
    a2 = r.json()["id"]; created["applications"].append(a2)
    lst = c.get("/api/applications", headers=H, params={"pos_id": p1}).json()
    check([x["id"] for x in lst] == [a1] and lst[0]["candidate_name"] == f"张三_{STAMP}", "按岗位筛选 + 带候选人名")
    check(c.get("/api/applications", headers=H, params={"stage": "xxx"}).status_code == 400, "非法 stage 400")
    by_can = c.get("/api/applications", headers=H, params={"can_id": c1}).json()
    check(by_can == [] or all(x["can_id"] == c1 for x in by_can), "按候选人编号筛选投递")
    check(c.get("/api/applications", headers=H, params={"status": "pending"}).status_code == 200, "按状态筛选")

    # 两个小快捷函数：adv = 推进某一关，rev = 撤回。lambda 是「一行写完的小函数」
    adv = lambda aid, fs, res: c.post(f"/api/applications/{aid}/advance", headers=H, json={"fromStage": fs, "result": res})
    rev = lambda aid, to=None: c.post(f"/api/applications/{aid}/revert", headers=H, json={"toStage": to} if to else {})

    check(adv(a1, "resume", "pass").status_code == 409, "fromStage 不匹配 409")
    check(adv(a1, "ai", "maybe").status_code == 400, "result 非法 400")
    check(rev(a1).status_code == 400, "ai 阶段 pending 不可撤回 400")
    d = adv(a1, "ai", "pass").json()
    check(d["current_stage"] == "resume" and d["ai_result"] == "pass", "ai pass → resume")
    d = adv(a1, "resume", "pass").json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["current_stage"] == "contact" and st["resume"]["result"] == "pass" and st["resume"]["time"], "resume pass 写结果+时间 → contact")
    d = adv(a1, "contact", "pass").json()
    check(d["current_stage"] == "phone", "contact（无字段）pass → phone")
    d = adv(a1, "phone", "fail").json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["overall_status"] == "fail" and d["current_stage"] == "phone" and st["phone"]["result"] == "fail", "phone fail → 已淘汰")
    check(adv(a1, "phone", "pass").status_code == 409, "已淘汰不可再推进 409")
    d = rev(a1).json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["overall_status"] == "pending" and d["current_stage"] == "phone" and st["phone"]["result"] is None, "淘汰撤回 → phone pending，结果清空")
    d = rev(a1).json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["current_stage"] == "contact", "进行中撤回 → 退回 contact")
    d = rev(a1).json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["current_stage"] == "resume" and st["resume"]["result"] is None and st["resume"]["time"] is None, "再撤回 → resume 且 resume 结果/时间清空")
    d = adv(a1, "resume", "pass").json(); d = adv(a1, "contact", "pass").json(); d = adv(a1, "phone", "pass").json()
    d = rev(a1, "ai").json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["current_stage"] == "ai" and all(s["result"] is None for s in d["stages"]) and d["ai_comment"] is None, "指定 toStage=ai 清空全部")
    check(rev(a1, "final").status_code == 400, "toStage 晚于当前 400")
    for fs in ["ai", "resume", "contact", "phone", "test", "pro", "hr"]:
        d = adv(a1, fs, "pass").json()
    check(d["current_stage"] == "final" and d["overall_status"] == "pending", "一路推进到 final")
    d = adv(a1, "final", "pass").json()
    check(d["overall_status"] == "pass" and d["current_stage"] == "final", "终面通过 → 已录用")
    d = rev(a1).json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["overall_status"] == "pending" and d["current_stage"] == "final" and st["final"]["result"] is None, "录用撤回 → final pending")
    d = adv(a1, "final", "pass").json()
    detail = c.get(f"/api/applications/{a1}", headers=H).json()
    check(detail["position"]["id"] == p1 and detail["candidate"]["id"] == c1, "详情含候选人+岗位")

    print("== 岗位删除限制")
    check(c.delete(f"/api/positions/{p1}", headers=H).status_code == 409, "有投递的岗位删除 409")
    r = c.post("/api/positions", headers=H, json={"position_name": f"临时岗_{STAMP}"})
    check(c.delete(f"/api/positions/{r.json()['id']}", headers=H).status_code == 204, "空岗位删除 204")

    print("== ai-configs（用户隔离）")
    check(c.post("/api/ai-screen/intake", headers=H, data={"texts": ["x" * 50]}).status_code == 400, "无启用配置 intake 400")
    r = c.post("/api/ai-configs", headers=H, json={"name": "cfgA", "base_url": "http://127.0.0.1:9/v1", "api_key": "k", "model": "m"})
    check(r.status_code == 201 and r.json()["is_enabled"] is False, "创建配置默认停用")
    k1 = r.json()["id"]; created["configs"].append(k1)
    r = c.post("/api/ai-configs", headers=H, json={"name": "cfgB", "base_url": "http://127.0.0.1:9/v1/", "api_key": "k", "model": "m", "is_enabled": True})
    k2 = r.json()["id"]; created["configs"].append(k2)
    check(c.put(f"/api/ai-configs/{k1}/enable", headers=H).json()["is_enabled"] is True, "enable")
    check(c.put(f"/api/ai-configs/{k1}/disable", headers=H).json()["is_enabled"] is False, "disable")
    check(c.put(f"/api/ai-configs/{k1}", headers=H, json={"model": "glm-4-flash"}).json()["model"] == "glm-4-flash", "更新 model")
    check(len(c.get("/api/ai-configs", headers=H).json()) == 2, "列表 2 条")
    ub = f"smoke_b_{STAMP}"
    r = c.post("/api/auth/register", json={"username": ub, "password": pw}); created["users"].append(r.json()["user"]["id"])
    HB = {"Authorization": f"Bearer {r.json()['token']}"}
    check(c.get("/api/ai-configs", headers=HB).json() == [], "用户 B 看不到 A 的配置")
    check(c.put(f"/api/ai-configs/{k1}", headers=HB, json={"model": "x"}).status_code == 404, "用户 B 改 A 的配置 404")
    check(c.delete(f"/api/ai-configs/{k1}", headers=HB).status_code == 404, "用户 B 删 A 的配置 404")

    print("== ai-screen intake（配置不可达，验证提取与错误路径）")
    c.put(f"/api/ai-configs/{k1}/enable", headers=H)
    good_pdf = make_pdf("姓名：王五\n应聘：Java工程师\n5年Java开发经验，精通Spring Boot、MySQL、Redis，主导过电商系统重构。")
    blank_pdf = fitz.open(); blank_pdf.new_page(); blank = blank_pdf.tobytes(); blank_pdf.close()
    before = len(c.get("/api/candidates", headers=H).json())
    r = c.post("/api/ai-screen/intake", headers=H,
               files=[("files", ("wangwu.pdf", good_pdf, "application/pdf")),
                      ("files", ("scan.pdf", blank, "application/pdf")),
                      ("files", ("note.txt", b"hello", "text/plain"))],
               data={"texts": ["太短", "李四，8年前端经验，精通 Vue3 / TypeScript / Vite，负责过大型后台系统。" * 2]})
    check(r.status_code == 200, "intake 200")
    res = r.json()["results"]
    check(r.json()["total"] == 5 and len(res) == 5, "5 条逐条返回")
    check(res[0]["status"] == "error" and "无法识别" in res[0]["message"], "有效 PDF → LLM 不可达 error（已重试）")
    check(res[1]["status"] == "extract_failed" and "无法提取文本" in res[1]["message"], "空白 PDF → extract_failed（扫描件）")
    check(res[2]["status"] == "extract_failed" and "仅支持 PDF" in res[2]["message"], "非 PDF → extract_failed")
    check(res[3]["status"] == "extract_failed" and "过短" in res[3]["message"], "短文本 → extract_failed")
    check(res[4]["status"] == "error", "有效文本 → LLM 不可达 error")
    check(len(c.get("/api/candidates", headers=H).json()) == before, "失败条目不建档")
    check(c.post("/api/ai-screen/intake", headers=H).status_code == 400, "空请求 400")

    print("== stats / export")
    s = c.get("/api/stats/overview", headers=H).json()
    check(s["position_count"] >= 2 and s["pass_count"] >= 1 and s["pending_count"] >= 1, "统计计数")
    check(len(s["stage_counts"]) == 8 and s["ai_pending_count"] >= 1, "8 阶段分布 + 待 AI 筛选数")
    check(any(bp["pos_id"] == p1 and bp["pass"] == 1 for bp in s["by_position"]), "按岗位分组")
    check(s["month_hired"] >= 1 and s["week_in_progress"] >= 1, "本月录用/本周进行")
    fields = c.get("/api/export/fields", headers=H).json()
    check(len(fields) == 21, "导出字段 21 个")
    r = c.post("/api/export", headers=H, json={"filters": {"pos_id": p1}, "fields": ["id", "candidate_name", "position_name", "overall_status", "final_time"], "format": "xlsx"})
    check(r.status_code == 200 and "spreadsheetml" in r.headers["content-type"] and r.headers["x-row-count"] == "1", "导出 xlsx 1 行")
    ws = load_workbook(io.BytesIO(r.content)).active
    rows = list(ws.iter_rows(values_only=True))
    check(rows[0] == ("投递编号", "候选人姓名", "岗位名称", "全局状态", "终面时间") and rows[1][3] == "已录用", "xlsx 表头中文 + 状态中文")
    r = c.post("/api/export", headers=H, json={"filters": {}, "format": "csv"})
    check(r.status_code == 200 and r.content.startswith("\ufeff".encode("utf-8")) and r.content.decode("utf-8-sig").splitlines()[0].startswith("投递编号,候选人姓名"), "csv utf-8-sig 全字段")
    check(c.post("/api/export", headers=H, json={"fields": ["hacker"]}).status_code == 400, "非法字段 400")
    check(c.post("/api/export", headers=H, json={"filters": {"stage": "zzz"}}).status_code == 400, "非法 stage 400")

    print("== 系统设置：AI 提示词 ==")
    check(c.get("/api/settings/ai-prompt").status_code == 401, "提示词接口未登录 401")
    d = c.get("/api/settings/ai-prompt", headers=H).json()
    check(d["is_custom"] is False and len(d["rules"]) > 0, "初始为系统默认规则")
    check("只能是一个 JSON 对象" in d["format_rules"] and "pass" in d["format_rules"], "格式说明锁定并含关键约束")
    check(len(d["default_rules"]) > 0, "返回默认规则供恢复用")
    d = c.put("/api/settings/ai-prompt", headers=H, json={"rules": "冒烟测试规则：只招博士"}).json()
    check(d["is_custom"] is True and d["rules"] == "冒烟测试规则：只招博士", "保存自定义规则")
    check(c.get("/api/settings/ai-prompt", headers=H).json()["rules"] == "冒烟测试规则：只招博士", "自定义规则已持久化")
    d = c.put("/api/settings/ai-prompt", headers=H, json={"rules": ""}).json()
    check(d["is_custom"] is False and d["rules"] == d["default_rules"], "传空恢复系统默认")

    print("== AI 录入：指定岗位 / 参数校验 ==")
    r = c.post("/api/ai-screen/intake", headers=H, data={"texts": ["x" * 50], "pos_id": "999999"})
    check(r.status_code == 400, "不存在的 pos_id 400")
    check(c.post("/api/ai-screen/intake", headers=H).status_code == 400, "intake 空请求 400")

    print("== 阶段 × 岗位 交叉汇总表 ==")
    d = c.get("/api/stats/matrix", headers=H, params={"range": "week"}).json()
    check(d["range"] == "week" and d["range_label"] == "本周", "matrix 默认本周")
    check(len(d["rows"]) == 4 and [r["label"] for r in d["rows"]] == ["简历筛选数", "电话沟通人数", "笔试人数", "面试人数"], "matrix 4 行且顺序正确")
    check(len(d["positions"]) == len(d["col_totals"]) and len(d["col_totals"]) == len(d["rows"][0]["cells"]), "列数一致")
    check(d["grand_total"] == sum(d["col_totals"]) == sum(d["row_totals"]), "总计自洽（列合计=行合计=总和）")
    check(any(p["label"] and p["id"] for p in d["positions"]), "岗位列含 label 与 id")
    for rng in ("last_week", "month", "all"):
        check(c.get("/api/stats/matrix", headers=H, params={"range": rng}).status_code == 200, f"range={rng} 正常")
    check(c.get("/api/stats/matrix", headers=H, params={"range": "custom", "start_date": "2026-09-01", "end_date": "2026-09-17"}).status_code == 200, "自定义范围正常")
    check(c.get("/api/stats/matrix", headers=H, params={"range": "custom", "start_date": "2026-09-20", "end_date": "2026-09-01"}).status_code == 400, "起止日期颠倒 400")
    r = c.post("/api/export", headers=H, json={"mode": "matrix", "range": "week", "format": "xlsx"})
    check(r.status_code == 200 and "spreadsheetml" in r.headers["content-type"], "导出矩阵 xlsx")
    ws = load_workbook(io.BytesIO(r.content)).active
    mrows = list(ws.iter_rows(values_only=True))
    check(mrows[0][0] == "阶段" and mrows[0][-1] == "总计", "矩阵表头 阶段…总计")
    check(mrows[-1][0] == "总计" and mrows[-1][-1] == d["grand_total"], "矩阵末行为总计且与接口一致")
    check(c.post("/api/export", headers=H, json={"mode": "bad"}).status_code == 400, "非法 mode 400")

    print("== 进行中的候选人所处阶段 清单 ==")
    d = c.get("/api/stats/in-progress", headers=H, params={"range": "week"}).json()
    check("groups" in d and "total" in d, "in-progress 返回结构")
    check(d["range_label"] == "本周", "in-progress 默认本周")
    flat = [x for g in d["groups"] for x in g["candidates"]]
    check(d["total"] == len(flat), "total 与明细条数一致")
    for rng in ("last_week", "month", "all"):
        check(c.get("/api/stats/in-progress", headers=H, params={"range": rng}).status_code == 200, f"in-progress range={rng} 正常")
    check(c.get("/api/stats/in-progress", headers=H, params={"range": "custom", "start_date": "2026-09-20", "end_date": "2026-09-01"}).status_code == 400, "in-progress 日期颠倒 400")

    print("== 阶段文案手动改写 ==")
    d = c.get("/api/stats/in-progress", headers=H, params={"range": "all"}).json()
    flat = [x for g in d["groups"] for x in g["candidates"]]
    if flat:
        target = flat[0]
        r = c.put("/api/settings/stage-note", headers=H, json={"app_id": target["app_id"], "note": "待offer回传"}).json()
        check(r["notes"].get(str(target["app_id"])) == "待offer回传", "保存手动文案")
        d2 = c.get("/api/stats/in-progress", headers=H, params={"range": "all"}).json()
        row = [x for g in d2["groups"] for x in g["candidates"] if x["app_id"] == target["app_id"]][0]
        check(row["stage_text"] == "待offer回传" and row["is_custom"] is True, "清单显示手动文案并标 is_custom")
        check(row["auto_text"] != "待offer回传", "同时返回自动文案供恢复")
        c.put("/api/settings/stage-note", headers=H, json={"app_id": target["app_id"], "note": ""})
        d3 = c.get("/api/stats/in-progress", headers=H, params={"range": "all"}).json()
        row3 = [x for g in d3["groups"] for x in g["candidates"] if x["app_id"] == target["app_id"]][0]
        check(row3["is_custom"] is False and row3["stage_text"] == row3["auto_text"], "传空恢复自动")

    print("== 导出招聘周报（两个工作表）==")
    r = c.post("/api/export", headers=H, json={"mode": "report", "range": "week", "format": "xlsx"})
    check(r.status_code == 200 and "spreadsheetml" in r.headers["content-type"], "导出 report xlsx")
    wb = load_workbook(io.BytesIO(r.content))
    check(wb.sheetnames == ["阶段岗位汇总", "进行中候选人"], f"两个工作表：{wb.sheetnames}")
    check(list(wb["阶段岗位汇总"].iter_rows(values_only=True))[0][0] == "阶段", "表1=阶段岗位汇总")
    check([x.value for x in wb["进行中候选人"][1]] == ["岗位", "候选人", "阶段"], "表2 表头 岗位/候选人/阶段")
    r = c.post("/api/export", headers=H, json={"mode": "report", "range": "week", "format": "csv"})
    check(r.status_code == 200 and "csv" in r.headers["content-type"], "report+csv 退化为单表")


    print(f"\n全部通过：{passed} 项断言")


def cleanup():
    """把这次测试建的数据全删掉，让数据库恢复干净。删除顺序有讲究：先删「引用别人的」（投递），再删「被引用的」（候选人、岗位）。"""
    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password="your-password", database="ats")
    cur = conn.cursor()
    def dele(table, ids):
        if ids:
            cur.execute(f"DELETE FROM `{table}` WHERE ID IN ({','.join(map(str, ids))})")
    dele("Application", created["applications"])
    if created["users"]:
        cur.execute(f"DELETE FROM AI_API_Config WHERE User_ID IN ({','.join(map(str, created['users']))})")
        cur.execute(f"DELETE FROM App_Setting WHERE User_ID IN ({','.join(map(str, created['users']))})")
    dele("Candidate", created["candidates"])
    dele("Position", created["positions"])
    dele("User", created["users"])
    conn.commit()
    for t in ("Application", "Candidate", "Position", "AI_API_Config", "User"):
        cur.execute(f"SELECT COUNT(*) FROM `{t}`")
        print(f"  cleanup {t}: {cur.fetchone()[0]} rows left")
    conn.close()


if __name__ == "__main__":
    # try/finally：不管测试中途成功还是失败，finally 里的清理都一定会执行，不留垃圾数据
    try:
        run()
    finally:
        print("== cleanup")
        cleanup()
