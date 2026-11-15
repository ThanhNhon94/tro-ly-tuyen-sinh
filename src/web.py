"""
Giao diện chat trên trình duyệt cho Trợ lý tuyển sinh.

    python src/web.py              # mở http://localhost:8000
    python src/web.py --port 8080
    python src/web.py --host 0.0.0.0   # cho máy khác trong cùng mạng LAN truy cập

Chỉ dùng thư viện chuẩn của Python, không cần cài thêm gì ngoài requirements.txt.
"""
import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import config
from ollama_client import OllamaError
from rag import Retriever, answer, load_system_prompt

WEB_DIR = config.ROOT / "web"
MAX_QUESTION_CHARS = 1000

retriever = None
system_prompt = None


def source_label(chunk):
    m = chunk["metadata"]
    if m.get("dieu"):
        return f"Điều {m['dieu']}. {m.get('tieu_de', '')} – {m.get('truong', '')} ({m.get('so_van_ban', '')})"
    return f"{m.get('phan', 'Văn bản')} – {m.get('truong', '')} ({m.get('so_van_ban', '')})"


def clean_history(raw):
    """Chỉ giữ các tin nhắn hợp lệ do trình duyệt gửi lên."""
    out = []
    for msg in raw if isinstance(raw, list) else []:
        if isinstance(msg, dict) and msg.get("role") in ("user", "assistant") \
                and isinstance(msg.get("content"), str):
            out.append({"role": msg["role"], "content": msg["content"][:4000]})
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # gọn log
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, (WEB_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/health":
            self._send(200, json.dumps({"ok": True, "model": config.LLM_MODEL}), "application/json")
        else:
            self._send(404, "Không tìm thấy", "text/plain; charset=utf-8")

    def do_POST(self):
        if self.path != "/api/chat":
            return self._send(404, "Không tìm thấy", "text/plain; charset=utf-8")
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            question = str(body.get("question", "")).strip()[:MAX_QUESTION_CHARS]
            history = clean_history(body.get("history"))
        except (ValueError, json.JSONDecodeError):
            return self._send(400, "Dữ liệu không hợp lệ", "text/plain; charset=utf-8")
        if not question:
            return self._send(400, "Câu hỏi trống", "text/plain; charset=utf-8")

        # Trả về dạng NDJSON: mỗi dòng là 1 sự kiện JSON, trình duyệt đọc dần để hiện chữ ngay
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def emit(obj):
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()

        try:
            stream, hits = answer(retriever, system_prompt, history, question)
            emit({"type": "sources", "items": [
                {"label": source_label(c), "score": round(s, 3)} for c, s in hits]})
            for piece in stream:
                emit({"type": "delta", "text": piece})
            emit({"type": "done"})
        except OllamaError as e:
            emit({"type": "error", "message": str(e)})
        except (BrokenPipeError, ConnectionResetError):
            pass  # người dùng đóng trang giữa chừng
        except Exception as e:  # không để lỗi lạ làm treo giao diện
            emit({"type": "error", "message": f"Lỗi hệ thống: {e}"})


def main():
    global retriever, system_prompt
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    retriever = Retriever()
    system_prompt = load_system_prompt()

    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    print(f"Trợ lý tuyển sinh đang chạy tại {url}  (Ctrl+C để dừng)")
    if not args.no_browser:
        webbrowser.open(url)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
