"""Phần lõi RAG: tìm đoạn tài liệu liên quan và ghép prompt cho model."""
import json
import sys

import numpy as np

import config
from ollama_client import chat_stream, embed


class Retriever:
    def __init__(self):
        info_file = config.INDEX_DIR / "info.json"
        if not info_file.exists():
            sys.exit("Chưa có index. Hãy chạy trước: python src/ingest.py")
        info = json.loads(info_file.read_text(encoding="utf-8"))
        if info["embed_model"] != config.EMBED_MODEL:
            sys.exit(f"Index được tạo bằng '{info['embed_model']}' nhưng config đang dùng "
                     f"'{config.EMBED_MODEL}'. Hãy chạy lại: python src/ingest.py")
        self.vectors = np.load(config.INDEX_DIR / "vectors.npy")
        self.chunks = json.loads((config.INDEX_DIR / "chunks.json").read_text(encoding="utf-8"))

    def search(self, query, k=config.TOP_K, truong=None):
        q = np.asarray(embed([query])[0], dtype=np.float32)
        q /= np.linalg.norm(q)
        scores = self.vectors @ q
        if truong:  # lọc theo trường nếu biết người dùng hỏi trường nào
            mask = np.array([c["metadata"].get("truong") == truong for c in self.chunks])
            scores = np.where(mask, scores, -1.0)
        top = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in top if scores[i] >= config.MIN_SCORE]


def load_system_prompt():
    return config.SYSTEM_PROMPT_FILE.read_text(encoding="utf-8")


def build_user_message(question, hits):
    if hits:
        docs = "\n\n".join(f"[{i}] {c['text']}" for i, (c, _) in enumerate(hits, 1))
    else:
        docs = "(Không tìm thấy đoạn tài liệu nào liên quan đến câu hỏi.)"
    return (f"<tai_lieu>\n{docs}\n</tai_lieu>\n\n"
            f"Câu hỏi của người dùng: {question}\n\n"
            "Hãy trả lời theo đúng các quy tắc đã được giao, chỉ dựa trên <tai_lieu>.")


def build_messages(system_prompt, history, question, hits):
    """history: list các {"role", "content"} đã hỏi-đáp trước đó (chỉ câu hỏi gốc, không kèm tài liệu)."""
    return [
        {"role": "system", "content": system_prompt},
        *history[-config.HISTORY_TURNS * 2:],
        {"role": "user", "content": build_user_message(question, hits)},
    ]


def answer(retriever, system_prompt, history, question):
    """Trả về (generator chữ trả lời, danh sách đoạn tài liệu đã dùng)."""
    hits = retriever.search(question)
    messages = build_messages(system_prompt, history, question, hits)
    return chat_stream(messages), hits
