"""
【mock_llm_server.py】本地假 AI 服务，专供前端联调 AI 录入用（不跑测试断言）。
在 8009 端口起一个 OpenAI 兼容的 /chat/completions，规则见下方 do_POST。
用法：python scripts/mock_llm_server.py   （Ctrl+C 停止）
"""
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer


class MockLLM(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(length))
        prompt = body["messages"][1]["content"]  # user 消息（岗位列表 + 简历）
        parts = prompt.split("## 简历内容", 1)
        pos_text, resume = parts[0], parts[1]

        name_m = re.search(r"姓名[:：]\s*(\S+)", resume)
        name = name_m.group(1) if name_m else ""
        pos_ids = [int(x) for x in re.findall(r'"id":\s*(\d+)', pos_text)]

        # 简历里带这些标记 → 模拟不同情况，方便联调
        if "NOPOS" in resume:
            out = {"name": name, "position_id": None, "result": "", "reason": "简历方向与在招岗位不相关"}
        else:
            # 如果岗位带 extra（附加条件），模拟 AI「因不满足附加条件而判 fail」，便于验证功能
            has_extra = '"extra"' in pos_text
            if "FAILME" in resume:
                result, reason = "fail", "【mock】简历与岗位要求差距较大，不建议继续"
            elif has_extra:
                result, reason = "fail", "【mock】该岗位设有附加条件，候选人不满足，故淘汰"
            else:
                result, reason = "pass", "【mock】简历与岗位要求基本吻合，建议进入下一环节"
            out = {"name": name, "position_id": pos_ids[0] if pos_ids else None, "result": result, "reason": reason}
        content = "```json\n" + json.dumps(out, ensure_ascii=False) + "\n```"
        resp = json.dumps({"choices": [{"message": {"role": "assistant", "content": content}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)


if __name__ == "__main__":
    print("mock LLM 服务运行在 http://127.0.0.1:8009/v1/chat/completions  (Ctrl+C 停止)")
    HTTPServer(("127.0.0.1", 8009), MockLLM).serve_forever()
