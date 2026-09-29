"""
【这个文件是干什么的？】——后端的「体检单」
写好代码后怎么知道它真的能用？一个个手点太累，所以写一个脚本自动跑一遍：
注册 → 登录 → 建岗位 → 建候选人 → 建投递 → 一关关推进、撤回 → AI 配置 → 导出……
每一步都「断言」（assert）结果必须是我们预期的，不对就立刻报错停下。

这种「把主要功能快速跑一遍」的测试叫「冒烟测试」（比喻：机器一开机先看冒不冒烟）。
以后改了代码，跑一遍这个脚本，上百项断言全绿就说明没改坏。

用法：先起服务，再 `python scripts/smoke_test.py [服务地址]`，默认 http://127.0.0.1:8001。
测试完自动清理本次创建的数据（直连数据库删除，因为投递/候选人/用户没有删除接口）。
"""
import io
import os
import sys
import time

import fitz
import httpx
import pymysql
from openpyxl import load_workbook

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8001"  # 服务地址，可以从命令行传
STAMP = str(int(time.time()))  # 当前时间戳，拼进用户名/岗位名，保证每次跑都不重名
PYMYSQL_PW = os.environ.get("ATS_DB_PASSWORD", "your-password")  # MySQL root 密码，可用环境变量 ATS_DB_PASSWORD 覆盖
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

    print("== 个人信息（改用户名 / 改密码）")
    check(c.put("/api/auth/profile", json={"username": "x"}).status_code == 401, "改个人信息未登录 401")
    # 先造一个「别人」，用来验证改成别人用户名会 409
    other = f"smoke_other_{STAMP}"
    ro = c.post("/api/auth/register", json={"username": other, "password": pw})
    created["users"].append(ro.json()["user"]["id"])
    # 改用户名：成功后返回新 token，用新 token 问「我是谁」应看到新名字
    new_name = f"{ua}_new"
    check(c.put("/api/auth/profile", headers=H, json={"username": new_name}).status_code == 200, "改用户名 200")
    check(c.put("/api/auth/profile", headers=H, json={"username": other}).status_code == 409, "改成别人用户名 409")
    check(c.put("/api/auth/profile", headers=H, json={"username": "a"}).status_code == 422, "用户名过短 422")
    token2 = c.put("/api/auth/profile", headers=H, json={"username": new_name}).json()["token"]
    H = {"Authorization": f"Bearer {token2}"}
    check(c.get("/api/auth/me", headers=H).json()["username"] == new_name, "新 token 反映新用户名")
    # 改回原名，免得影响后面用例里用过的 ua
    token = c.put("/api/auth/profile", headers=H, json={"username": ua}).json()["token"]
    H = {"Authorization": f"Bearer {token}"}
    check(c.get("/api/auth/me", headers=H).json()["username"] == ua, "改回原名")
    # 改密码：当前密码不对 / 不填当前密码，都拒绝（400）
    check(c.put("/api/auth/profile", headers=H, json={"username": ua, "current_password": "wrong", "new_password": "newsecret456"}).status_code == 400, "当前密码错 400")
    check(c.put("/api/auth/profile", headers=H, json={"username": ua, "new_password": "newsecret456"}).status_code == 400, "缺当前密码 400")
    # 正常改密码：旧密码失效、新密码可登录
    check(c.put("/api/auth/profile", headers=H, json={"username": ua, "current_password": pw, "new_password": "newsecret456"}).status_code == 200, "改密码 200")
    check(c.post("/api/auth/login", json={"username": ua, "password": pw}).status_code == 401, "旧密码失效 401")
    check(c.post("/api/auth/login", json={"username": ua, "password": "newsecret456"}).status_code == 200, "新密码可登录")

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
    check(d["current_stage"] == "ai" and d["overall_status"] == "pending" and len(d["stages"]) == 7, "初始 ai/pending/7 阶段")
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
    check(d["current_stage"] == "phone" and st["resume"]["result"] == "pass" and st["resume"]["time"], "resume pass 写结果+时间 → phone")
    d = adv(a1, "phone", "fail").json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["overall_status"] == "fail" and d["current_stage"] == "phone" and st["phone"]["result"] == "fail", "phone fail → 已淘汰")
    check(adv(a1, "phone", "pass").status_code == 409, "已淘汰不可再推进 409")
    d = rev(a1).json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["overall_status"] == "pending" and d["current_stage"] == "phone" and st["phone"]["result"] is None, "淘汰撤回 → phone pending，结果清空")
    d = rev(a1).json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["current_stage"] == "resume" and st["resume"]["result"] is None and st["resume"]["time"] is None, "进行中撤回 → 退回 resume 且 resume 结果/时间清空")
    d = adv(a1, "resume", "pass").json(); d = adv(a1, "phone", "pass").json()
    d = rev(a1, "ai").json()
    st = {s["stage"]: s for s in d["stages"]}
    check(d["current_stage"] == "ai" and all(s["result"] is None for s in d["stages"]) and d["ai_comment"] is None, "指定 toStage=ai 清空全部")
    check(rev(a1, "final").status_code == 400, "toStage 晚于当前 400")
    for fs in ["ai", "resume", "phone", "test", "pro", "hr"]:
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

    print("== 各关记录：结果原因 / 面试评价（详情页编辑，不改流程）==")
    # 此时 a1 已走完全部 6 个人工关，正好逐个写记录。sn = 写某关记录
    sn = lambda aid, stg, **kw: c.put(f"/api/applications/{aid}/stage-note", headers=H, json={"stage": stg, **kw})
    check("reason" in detail["stages"][1] and "evaluation" in detail["stages"][1], "时间线含 reason/evaluation 键")
    st = {s["stage"]: s for s in detail["stages"]}
    check(sn(a1, "resume", reason="本科3年，符合岗位要求").json()["stages"][1]["reason"] == "本科3年，符合岗位要求", "简历筛选·写通过原因")
    # 电话沟通：原因 + 面试评价
    r = sn(a1, "phone", reason="沟通顺畅，接受厦门", evaluation="电话沟通评价全文")
    st = {s["stage"]: s for s in r.json()["stages"]}
    check(st["phone"]["reason"] == "沟通顺畅，接受厦门" and st["phone"]["evaluation"] == "电话沟通评价全文", "电话沟通·原因+面试评价")
    check(sn(a1, "test", reason="笔试 86 分").json()["stages"][3]["reason"] == "笔试 86 分", "笔试·写通过原因")
    # 专业面 / HR面：原因 + 面试评价
    st = {s["stage"]: s for s in sn(a1, "pro", reason="技术扎实", evaluation="专业面评价").json()["stages"]}
    check(st["pro"]["reason"] == "技术扎实" and st["pro"]["evaluation"] == "专业面评价", "专业面·原因+面试评价")
    check(sn(a1, "hr", reason="稳定性好", evaluation="HR面评价").json()["stages"][5]["evaluation"] == "HR面评价", "HR面·原因+面试评价")
    check(sn(a1, "final", reason="团队匹配度好", evaluation="终面评价").json()["stages"][6]["evaluation"] == "终面评价", "终面·原因+面试评价")
    # 清空：传空字符串
    check(sn(a1, "final", reason="").json()["stages"][6]["reason"] is None, "传空串 = 清空该项")
    sn(a1, "final", reason="团队匹配度好")  # 写回去，供导出/统计用例
    # 错误路径
    check(sn(a1, "resume", reason="r", evaluation="e").status_code == 400, "简历筛选传面试评价 400")
    check(sn(a1, "test", reason="r", evaluation="e").status_code == 400, "笔试传面试评价 400")
    check(sn(a1, "ai", reason="x").status_code == 400, "ai 关不可手写 400")
    check(sn(a1, "nope", reason="x").status_code == 400, "非法 stage 400")
    check(sn(a2, "resume", reason="x").status_code == 400, "未进行阶段写记录 400")
    check(c.put(f"/api/applications/{a1}/stage-note", json={"stage": "pro", "reason": "x"}).status_code == 401, "未登录写记录 401")

    # 进行中的当前关也能先写（还没打分），但更靠后的关仍不可写
    r = c.post("/api/candidates", headers=H, json={"name": f"进行中记录_{STAMP}"})
    nc = r.json()["id"]; created["candidates"].append(nc)
    r = c.post("/api/applications", headers=H, json={"can_id": nc, "pos_id": p2})
    na = r.json()["id"]; created["applications"].append(na)
    d = adv(na, "ai", "pass").json()  # ai pass → 当前关 resume，且 resume 未打分
    check(d["current_stage"] == "resume" and {s["stage"]: s for s in d["stages"]}["resume"]["result"] is None, "新投递推进后停在 resume（未打分）")
    r = sn(na, "resume", reason="进行中先记一笔，面试完再定")
    check(r.status_code == 200 and r.json()["stages"][1]["reason"] == "进行中先记一笔，面试完再定", "进行中的当前关可先写原因")
    check(sn(na, "phone", reason="x").status_code == 400, "更靠后的未到达关仍不可写 400")
    check(sn(na, "ai", reason="x").status_code == 400, "进行中时 ai 关仍不可写 400")
    # 进行中写下的记录，在打 pass 后保留（不会因推进而丢）
    d = adv(na, "resume", "pass").json()
    check({s["stage"]: s for s in d["stages"]}["resume"]["reason"] == "进行中先记一笔，面试完再定", "推进后进行中写的记录保留")
    # 但撤回该关会把它清掉
    d = rev(na).json()
    check({s["stage"]: s for s in d["stages"]}["resume"]["reason"] is None, "撤回后清掉（含进行中写下的）")
    # 撤回该关 → 原因与面试评价一并清空
    d = rev(a1).json()  # a1 现为 final/pass(已录用)，撤回 → final/pending，清 final 记录
    st = {s["stage"]: s for s in d["stages"]}
    check(st["final"]["reason"] is None and st["final"]["evaluation"] is None, "撤回该关 → 原因与面试评价清空")
    d = adv(a1, "final", "pass").json()  # 再通过终面，恢复「已录用」状态，供后面用例

    print("== 岗位删除限制")
    check(c.delete(f"/api/positions/{p1}", headers=H).status_code == 409, "有投递的岗位删除 409")
    r = c.post("/api/positions", headers=H, json={"position_name": f"临时岗_{STAMP}"})
    check(c.delete(f"/api/positions/{r.json()['id']}", headers=H).status_code == 204, "空岗位删除 204")

    print("== 改候选人姓名（人工纠正 AI 认错的名字）==")
    r = c.put(f"/api/candidates/{c1}", headers=H, json={"name": f"张三改名_{STAMP}"})
    check(r.status_code == 200 and r.json()["name"] == f"张三改名_{STAMP}", "改名成功")
    # 关键：改名不影响投递进度
    before = c.get(f"/api/applications/{a1}", headers=H).json()
    c.put(f"/api/candidates/{c1}", headers=H, json={"name": f"再次改名_{STAMP}"})
    after = c.get(f"/api/applications/{a1}", headers=H).json()
    check(after["candidate_name"] == f"再次改名_{STAMP}", "投递详情显示新名字")
    check(after["current_stage"] == before["current_stage"] and after["overall_status"] == before["overall_status"], "改名不影响投递阶段与状态")
    check([s_["result"] for s_ in after["stages"]] == [s_["result"] for s_ in before["stages"]], "改名不影响各关结果")
    check(c.put(f"/api/candidates/{c1}", headers=H, json={"name": "   "}).status_code == 400, "改名为空 400")
    r = c.put(f"/api/candidates/{c1}", headers=H, json={"name": f"李四_{STAMP}"})
    check(r.status_code == 409 and "同名" in r.json()["detail"], "改成与已有候选人同名 409")
    r = c.put(f"/api/candidates/{c1}", headers=H, json={"name": f"李四_{STAMP}", "confirm_duplicate": True})
    check(r.status_code == 200 and r.json()["name"] == f"李四_{STAMP}", "带确认后允许同名")
    check(c.put("/api/candidates/999999", headers=H, json={"name": "x"}).status_code == 404, "改不存在的候选人 404")
    # 改回自己的名字，避免影响后续断言（重名会让后续按姓名/岗位的统计前提变化）
    c.put(f"/api/candidates/{c1}", headers=H, json={"name": f"张三改名_{STAMP}", "confirm_duplicate": True})
    check(c.get(f"/api/applications/{a1}", headers=H).json()["candidate_name"] == f"张三改名_{STAMP}", "改回名字成功")

    print("== 岗位「暂不招」隐藏 ==")
    check("is_hidden" in c.get("/api/positions", headers=H).json()[0], "岗位返回含 is_hidden")
    # 注意：默认列表只含「在招」，include_hidden=true 才是全部。两者要分开记，否则当库里本来就有隐藏岗位时会误判
    before_visible = len(c.get("/api/positions", headers=H).json())
    before_total = len(c.get("/api/positions", headers=H, params={"include_hidden": "true"}).json())
    before_apps = len(c.get("/api/applications", headers=H).json())
    before_ov = c.get("/api/stats/overview", headers=H).json()
    before_mx = c.get("/api/stats/matrix", headers=H, params={"range": "all"}).json()
    check(c.put(f"/api/positions/{p1}", headers=H, json={"is_hidden": True}).json()["is_hidden"] is True, "设为暂不招")
    check(len(c.get("/api/positions", headers=H).json()) == before_visible - 1, "岗位列表默认少 1 个")
    check(len(c.get("/api/positions", headers=H, params={"include_hidden": "true"}).json()) == before_total, "include_hidden=true 总数不变")
    check(len(c.get("/api/applications", headers=H).json()) < before_apps, "投递列表排除了暂不招岗位的投递")
    after_ov = c.get("/api/stats/overview", headers=H).json()
    check(after_ov["position_count"] == before_ov["position_count"] - 1, "在招岗位数 -1")
    check(not any(x["pos_id"] == p1 for x in after_ov["by_position"]), "按岗位统计不含暂不招岗位")
    after_mx = c.get("/api/stats/matrix", headers=H, params={"range": "all"}).json()
    check(len(after_mx["positions"]) == len(before_mx["positions"]) - 1, "交叉表少一列")
    check(c.post("/api/applications", headers=H, json={"can_id": c1, "pos_id": p1}).status_code == 400, "往暂不招岗位建投递 400")
    check(c.get("/api/stats/matrix/cell", headers=H, params={"row": "test", "pos_id": p1}).status_code == 400, "暂不招岗位的格子 400")
    check(c.put(f"/api/positions/{p1}", headers=H, json={"is_hidden": False}).json()["is_hidden"] is False, "恢复在招")
    check(len(c.get("/api/positions", headers=H).json()) == before_visible, "恢复后岗位数回来")
    check(c.get("/api/stats/overview", headers=H).json()["position_count"] == before_ov["position_count"], "恢复后在招岗位数回来")


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
    check(len(s["stage_counts"]) == 7 and s["ai_pending_count"] >= 1, "7 阶段分布 + 待 AI 筛选数")
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

    print("== 交叉表格子名单 / 阶段多选 ==")
    mc = c.get("/api/stats/matrix", headers=H, params={"range": "all"}).json()
    # 找一个非零格子，核对名单人数与格子数字一致
    found = False
    for r in mc["rows"]:
        for i, n in enumerate(r["cells"]):
            if n > 0:
                pos_id = mc["positions"][i]["id"]
                cell = c.get("/api/stats/matrix/cell", headers=H,
                             params={"row": r["key"], "pos_id": pos_id, "range": "all"}).json()
                check(cell["count"] == n, f"格子名单人数({cell['count']}) == 格子数字({n}) [{r['label']}×{cell['position_label']}]")
                check(all("passed" in p and "stage_text" in p for p in cell["people"]), "名单每项含 已通过标记/阶段文案")
                found = True
                break
        if found:
            break
    check(found, "至少找到一个非零格子")
    check(c.get("/api/stats/matrix/cell", headers=H, params={"row": "zzz", "pos_id": 1}).status_code == 400, "非法 row 400")
    check(c.get("/api/stats/matrix/cell", headers=H, params={"row": "test", "pos_id": 999999}).status_code == 400, "岗位不存在 400")

    print("== 面试行口径：三关任一在范围内 + 面过被淘汰也计入 ==")
    # 造三个人，验证新口径（用直连 SQL 回拨时间戳，构造「跨时间范围」场景）
    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=PYMYSQL_PW, database="ats")
    cur = conn.cursor()

    def new_cand_app(name, pos_id):
        """临时建候选人 + 投递，返回 (cand_id, app_id)。"""
        can = c.post("/api/candidates", headers=H, json={"name": name}).json()
        created["candidates"].append(can["id"])
        ap = c.post("/api/applications", headers=H, json={"can_id": can["id"], "pos_id": pos_id}).json()
        created["applications"].append(ap["id"])
        return can["id"], ap["id"]

    def push(app_id, stages, results):
        """把投递按给定阶段/结果推进。stages=['ai','resume',...]，results 与之对应（默认全 pass）。"""
        for st, res in zip(stages, results):
            r = c.post(f"/api/applications/{app_id}/advance", headers=H, json={"fromStage": st, "result": res})
            assert r.status_code == 200, f"推进 {st} 失败：{r.text}"

    def interview_cell(pos_id, rng="week"):
        m = c.get("/api/stats/matrix", headers=H, params={"range": rng}).json()
        row = next(r for r in m["rows"] if r["key"] == "interview")
        idx = next(i for i, p in enumerate(m["positions"]) if p["id"] == pos_id)
        return row["cells"][idx], m

    LAST_YEAR = "2025-03-01 10:00:00"

    # ① 面试环节被淘汰 → 计入面试行，且 state=rejected
    _, ap_rej = new_cand_app(f"面试淘汰_{STAMP}", p2)
    push(ap_rej, ["ai", "resume", "phone", "test", "pro"], ["pass"] * 4 + ["fail"])
    cell = c.get("/api/stats/matrix/cell", headers=H, params={"row": "interview", "pos_id": p2, "range": "week"}).json()
    me = next((x for x in cell["people"] if x["app_id"] == ap_rej), None)
    check(me is not None and me["state"] == "rejected", "面试环节淘汰 → 面试行计入且 state=rejected")

    # ② 跨时间范围：专业面通过（回拨到去年）+ HR面本周被淘汰 → 本周仍计入（旧口径只看专业面，不会计入）
    #    用 HR 面淘汰（而非通过）来避开"停在终面等待"带来的干扰（等待也会用 update_time 计入本周）
    _, ap_cross = new_cand_app(f"跨范围_{STAMP}", p2)
    push(ap_cross, ["ai", "resume", "phone", "test", "pro", "hr"], ["pass"] * 5 + ["fail"])
    cur.execute("UPDATE Application SET pro_time=%s WHERE ID=%s", (LAST_YEAR, ap_cross))
    conn.commit()
    cell2 = c.get("/api/stats/matrix/cell", headers=H, params={"row": "interview", "pos_id": p2, "range": "week"}).json()
    hit2 = next((x for x in cell2["people"] if x["app_id"] == ap_cross), None)
    check(hit2 is not None, "专业面在去年、HR面在本周 → 本周面试行仍计入他（旧口径不会）")
    check(hit2 and hit2["state"] == "rejected", "该人 state=rejected（HR面被淘汰）")
    # 再把 hr_time 也回拨 → 本周不计入，全部范围仍计入
    cur.execute("UPDATE Application SET hr_time=%s WHERE ID=%s", (LAST_YEAR, ap_cross))
    conn.commit()
    cell3 = c.get("/api/stats/matrix/cell", headers=H, params={"row": "interview", "pos_id": p2, "range": "week"}).json()
    check(not any(x["app_id"] == ap_cross for x in cell3["people"]), "两关都回拨到去年 → 本周不计入")
    cell4 = c.get("/api/stats/matrix/cell", headers=H, params={"row": "interview", "pos_id": p2, "range": "all"}).json()
    check(any(x["app_id"] == ap_cross for x in cell4["people"]), "全部范围 → 仍计入")

    # ③ 同人三关都命中只算一次：按格子数字核对（本人只贡献 1）
    base_all, _ = interview_cell(p2, "all")
    _, ap_multi = new_cand_app(f"三关_{STAMP}", p2)
    push(ap_multi, ["ai", "resume", "phone", "test", "pro", "hr", "final"], ["pass"] * 7)
    after_all, _ = interview_cell(p2, "all")
    check(after_all - base_all == 1, f"三关都命中只 +1（{base_all} → {after_all}）")

    # ④ 对照组：笔试环节淘汰 **不**计入笔试行
    _, ap_test_fail = new_cand_app(f"笔试淘汰_{STAMP}", p2)
    push(ap_test_fail, ["ai", "resume", "phone", "test"], ["pass"] * 3 + ["fail"])
    m_all = c.get("/api/stats/matrix", headers=H, params={"range": "all"}).json()
    trow = next(r for r in m_all["rows"] if r["key"] == "test")
    tidx = next(i for i, p in enumerate(m_all["positions"]) if p["id"] == p2)
    tcell = c.get("/api/stats/matrix/cell", headers=H, params={"row": "test", "pos_id": p2, "range": "all"}).json()
    check(not any(x["app_id"] == ap_test_fail for x in tcell["people"]), "笔试淘汰 → 笔试行不计入（面试行才含淘汰）")

    # ⑤ 面试行每个非零格子的名单人数 == 格子数字，且每人都有 state
    m_iv = c.get("/api/stats/matrix", headers=H, params={"range": "all"}).json()
    ivrow = next(r for r in m_iv["rows"] if r["key"] == "interview")
    for i, n in enumerate(ivrow["cells"]):
        if n > 0:
            pid = m_iv["positions"][i]["id"]
            cc = c.get("/api/stats/matrix/cell", headers=H, params={"row": "interview", "pos_id": pid, "range": "all"}).json()
            check(cc["count"] == n, f"面试名单人数({cc['count']}) == 格子数字({n})")
            check(all("state" in x for x in cc["people"]), "面试名单每人含 state")
            break
    cur.close()
    conn.close()

    d_all = c.get("/api/stats/in-progress", headers=H, params={"range": "all"}).json()
    stage_of = {}
    for g in d_all["groups"]:
        for x in g["candidates"]:
            stage_of[x["app_id"]] = x["stage_key"]
    if stage_of:
        one_stage = sorted(set(stage_of.values()))[0]
        d_one = c.get("/api/stats/in-progress", headers=H, params=[("range", "all"), ("stages", one_stage)]).json()
        flat_one = [x for g in d_one["groups"] for x in g["candidates"]]
        check(all(x["stage_key"] == one_stage for x in flat_one), f"stages={one_stage} 只返回该阶段的人")
        check(d_one["total"] <= d_all["total"], "筛选后人数不多于全部")
    check(c.get("/api/stats/in-progress", headers=H, params={"range": "all", "stages": "zzz"}).status_code == 400, "非法 stages 400")

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
    conn = pymysql.connect(host="127.0.0.1", port=3306, user="root", password=PYMYSQL_PW, database="ats")
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
