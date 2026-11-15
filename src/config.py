"""Cấu hình chung. Đổi model ở đây, không cần sửa code chỗ khác."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- Ollama (chạy local, mặc định cổng 11434) ---
OLLAMA_URL = "http://localhost:11434"

# Model sinh câu trả lời. Chọn theo cấu hình máy (xem README, mục "Chọn model").
LLM_MODEL = "qwen3:8b"
# Qwen3 có chế độ "suy nghĩ" (thinking) làm câu trả lời chậm hơn nhiều.
# Với tra cứu tài liệu thì tắt đi là đủ.
LLM_THINK = False
LLM_TEMPERATURE = 0.2  # thấp để bám sát tài liệu, ít "sáng tác"
LLM_NUM_CTX = 8192     # độ dài ngữ cảnh (token) gửi cho model

# Model embedding: biến văn bản thành vector để tìm kiếm.
# bge-m3 hỗ trợ tiếng Việt tốt và có sẵn trên Ollama.
EMBED_MODEL = "bge-m3"

# --- Tìm kiếm ---
TOP_K = 5             # số đoạn tài liệu đưa vào prompt mỗi lần hỏi
MIN_SCORE = 0.30      # dưới ngưỡng này coi như không liên quan (chỉnh lại sau khi xem điểm bằng --debug)
HISTORY_TURNS = 3     # số lượt hỏi-đáp gần nhất giữ lại để nhớ ngữ cảnh

# --- Đường dẫn ---
CHUNKS_DIR = ROOT / "data" / "chunks"
INDEX_DIR = ROOT / "index"
SYSTEM_PROMPT_FILE = ROOT / "prompts" / "system_prompt.txt"
