"""Gọi Ollama qua HTTP (không cần cài thư viện ollama)."""
import json

import requests

import config


class OllamaError(Exception):
    """Lỗi khi gọi Ollama, kèm thông báo tiếng Việt dễ hiểu."""


def _post(path, payload, stream=False):
    try:
        r = requests.post(f"{config.OLLAMA_URL}{path}", json=payload,
                          stream=stream, timeout=(10, 900))
    except requests.ConnectionError:
        raise OllamaError(f"Không kết nối được Ollama tại {config.OLLAMA_URL}. "
                          "Hãy mở ứng dụng Ollama hoặc chạy lệnh: ollama serve")
    except requests.Timeout:
        raise OllamaError("Ollama phản hồi quá lâu. Máy có thể đang quá tải, "
                          "hãy thử model nhỏ hơn trong src/config.py")
    if r.status_code == 404:
        model = payload.get("model")
        raise OllamaError(f"Ollama chưa có model '{model}'. Chạy: ollama pull {model}")
    if r.status_code >= 400:
        try:
            detail = r.json().get("error", r.text)
        except ValueError:
            detail = r.text
        raise OllamaError(f"Ollama báo lỗi: {detail}")
    return r


def get_version():
    """Trả về (phiên bản dạng chuỗi, tuple số) hoặc (None, None) nếu không đọc được."""
    try:
        v = requests.get(f"{config.OLLAMA_URL}/api/version", timeout=5).json()["version"]
        nums = tuple(int(x) for x in v.split("-")[0].split(".")[:3])
        return v, nums
    except Exception:
        return None, None


def version_warning():
    """Câu cảnh báo nếu Ollama quá cũ, ngược lại trả về None."""
    v, nums = get_version()
    if v is None:
        return None
    if nums < config.MIN_OLLAMA_VERSION:
        need = ".".join(map(str, config.MIN_OLLAMA_VERSION))
        return (f"Ollama đang là bản {v}, đã cũ (cần {need} trở lên) nên model sẽ trả lời rất chậm. "
                "Hãy tải bản mới tại https://ollama.com/download và cài đè lên.")
    return None


def embed(texts):
    """Trả về list vector, mỗi vector ứng với 1 đoạn văn bản."""
    r = _post("/api/embed", {"model": config.EMBED_MODEL, "input": texts,
                             "keep_alive": config.LLM_KEEP_ALIVE})
    return r.json()["embeddings"]


def chat_stream(messages):
    """
    Gọi model chat. Sinh ra các cặp (loại, nội dung):
      ("thinking", "") – model đang "suy nghĩ" (phần này không hiển thị cho người dùng)
      ("text", "...")  – một mẩu câu trả lời
    """
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "stream": True,
        "think": config.LLM_THINK,
        "keep_alive": config.LLM_KEEP_ALIVE,
        "options": {"temperature": config.LLM_TEMPERATURE, "num_ctx": config.LLM_NUM_CTX},
    }
    r = _post("/api/chat", payload, stream=True)

    # Ollama bản cũ trả phần suy nghĩ lẫn trong nội dung, kẹp giữa <think> ... </think>.
    # Lọc bỏ phần đó, chỉ báo trạng thái "đang suy nghĩ".
    buf, in_think = "", False
    for line in r.iter_lines():
        if not line:
            continue
        data = json.loads(line)
        if data.get("error"):
            raise OllamaError(f"Ollama báo lỗi: {data['error']}")
        msg = data.get("message", {})
        if msg.get("thinking"):
            yield ("thinking", "")
        buf += msg.get("content", "")

        while buf:
            if in_think:
                end = buf.find("</think>")
                if end < 0:
                    buf = buf[-(len("</think>") - 1):]  # giữ phần cuối phòng thẻ bị cắt đôi
                    yield ("thinking", "")
                    break
                buf, in_think = buf[end + len("</think>"):].lstrip(), False
            else:
                start = buf.find("<think>")
                if start >= 0:
                    if buf[:start].strip():
                        yield ("text", buf[:start])
                    buf, in_think = buf[start + len("<think>"):], True
                    continue
                # Thẻ <think> có thể đang bị cắt ở cuối: giữ lại vài ký tự cuối
                keep = next((k for k in range(min(len(buf), 6), 0, -1)
                             if "<think>".startswith(buf[-k:])), 0)
                if len(buf) > keep:
                    yield ("text", buf[:len(buf) - keep])
                buf = buf[len(buf) - keep:]
                break

        if data.get("done"):
            break
    if buf and not in_think:
        yield ("text", buf)
