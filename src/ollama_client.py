"""Gọi Ollama qua HTTP (không cần cài thư viện ollama)."""
import json
import sys

import requests

import config


def _post(path, payload, stream=False):
    try:
        r = requests.post(f"{config.OLLAMA_URL}{path}", json=payload,
                          stream=stream, timeout=600)
    except requests.ConnectionError:
        sys.exit(f"Không kết nối được Ollama tại {config.OLLAMA_URL}. "
                 "Hãy mở ứng dụng Ollama hoặc chạy lệnh: ollama serve")
    if r.status_code == 404:
        model = payload.get("model")
        sys.exit(f"Ollama chưa có model '{model}'. Chạy: ollama pull {model}")
    r.raise_for_status()
    return r


def embed(texts):
    """Trả về list vector, mỗi vector ứng với 1 đoạn văn bản."""
    r = _post("/api/embed", {"model": config.EMBED_MODEL, "input": texts})
    return r.json()["embeddings"]


def chat_stream(messages):
    """Gọi model chat, trả về từng mẩu chữ ngay khi model sinh ra."""
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "stream": True,
        "think": config.LLM_THINK,
        "options": {"temperature": config.LLM_TEMPERATURE, "num_ctx": config.LLM_NUM_CTX},
    }
    r = _post("/api/chat", payload, stream=True)
    for line in r.iter_lines():
        if not line:
            continue
        data = json.loads(line)
        piece = data.get("message", {}).get("content", "")
        if piece:
            yield piece
        if data.get("done"):
            break
