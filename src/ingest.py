"""
Nạp tài liệu vào kho tìm kiếm (index).

Đọc mọi file .jsonl trong data/chunks/, tạo vector cho từng đoạn bằng model embedding
của Ollama, rồi lưu vào thư mục index/. Chạy lại mỗi khi thêm/sửa tài liệu
hoặc đổi EMBED_MODEL.

    python src/ingest.py
"""
import json
import sys

import numpy as np

import config
from ollama_client import OllamaError, embed

BATCH = 16


def load_chunks():
    files = sorted(config.CHUNKS_DIR.glob("*.jsonl"))
    if not files:
        sys.exit(f"Không thấy file .jsonl nào trong {config.CHUNKS_DIR}")
    chunks, seen = [], set()
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            c = json.loads(line)
            if c["id"] in seen:
                sys.exit(f"Trùng id chunk: {c['id']} (file {f.name})")
            seen.add(c["id"])
            chunks.append(c)
        print(f"  {f.name}")
    return chunks


def main():
    print("Đọc tài liệu:")
    chunks = load_chunks()
    print(f"Tổng {len(chunks)} đoạn. Đang tạo vector bằng '{config.EMBED_MODEL}'...")

    vecs = []
    try:
        for i in range(0, len(chunks), BATCH):
            vecs.extend(embed([c["text"] for c in chunks[i:i + BATCH]]))
            print(f"  {min(i + BATCH, len(chunks))}/{len(chunks)}")
    except OllamaError as e:
        sys.exit(str(e))

    mat = np.asarray(vecs, dtype=np.float32)
    mat /= np.linalg.norm(mat, axis=1, keepdims=True)  # chuẩn hoá để dùng cosine

    config.INDEX_DIR.mkdir(exist_ok=True)
    np.save(config.INDEX_DIR / "vectors.npy", mat)
    (config.INDEX_DIR / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    (config.INDEX_DIR / "info.json").write_text(
        json.dumps({"embed_model": config.EMBED_MODEL, "count": len(chunks),
                    "dim": int(mat.shape[1])}, ensure_ascii=False), encoding="utf-8")
    print(f"Xong. Đã lưu index vào {config.INDEX_DIR}")


if __name__ == "__main__":
    main()
