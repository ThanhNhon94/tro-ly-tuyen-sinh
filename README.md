# Trợ lý tuyển sinh

Trợ lý ảo chạy **local** trên máy tính, giúp học sinh THPT và phụ huynh tra cứu thông tin tuyển sinh đại học.
Hướng tiếp cận: **Generative AI + RAG** (Retrieval-Augmented Generation).

## Cách hệ thống hoạt động

```
                ┌──────────── NẠP TÀI LIỆU (chạy 1 lần / khi có tài liệu mới) ────────────┐
 PDF quy chế ──► chunk_quyche.py ──► data/chunks/*.jsonl ──► ingest.py ──► index/ (vector)
                └─────────────────────────────────────────────────────────────────────────┘

                ┌──────────────────────────── KHI NGƯỜI DÙNG HỎI ──────────────────────────┐
 Câu hỏi ──► tạo vector ──► tìm 5 đoạn gần nhất trong index ──► ghép vào prompt
         ──► model LLM (Ollama) trả lời theo prompts/system_prompt.txt, có dẫn Điều khoản
                └─────────────────────────────────────────────────────────────────────────┘
```

**RAG không "train" model.** Model giữ nguyên; kiến thức nằm trong `index/`.
Thêm trường mới hay cập nhật năm mới chỉ cần nạp thêm tài liệu và chạy lại `ingest.py`.

## Cấu trúc thư mục

| Đường dẫn | Nội dung |
|---|---|
| `data/raw/` | Tài liệu gốc (PDF) |
| `data/chunks/` | Tài liệu đã cắt thành đoạn, mỗi trường/văn bản một file `.jsonl` |
| `prompts/system_prompt.txt` | Bộ quy tắc trả lời (xưng hô, lịch sự, dẫn nguồn, không bịa số liệu) |
| `docs/test_cases.md` | Câu hỏi kiểm thử và kết quả kỳ vọng |
| `src/config.py` | Chọn model, số đoạn tìm kiếm, ngưỡng điểm... |
| `src/chunk_quyche.py` | Cắt PDF quy chế theo Chương / Mục / Điều |
| `src/ingest.py` | Tạo vector và lưu index |
| `src/chat.py` | Chat trên cửa sổ dòng lệnh |
| `index/` | Sinh ra khi chạy `ingest.py` (không đưa lên git) |

## Cài đặt và chạy

1. Cài **Python 3.10+** và **Ollama** (https://ollama.com).
2. Tải model:
   ```bash
   ollama pull qwen3:8b     # model trả lời
   ollama pull bge-m3       # model embedding (tìm kiếm)
   ```
3. Cài thư viện:
   ```bash
   pip install -r requirements.txt
   ```
4. Tạo index rồi chat:
   ```bash
   python src/ingest.py
   python src/chat.py --debug
   ```
   `--debug` in ra các đoạn tài liệu tìm được kèm điểm tương đồng, giúp kiểm tra tìm kiếm có đúng không.

## Thêm tài liệu mới

```bash
python src/chunk_quyche.py data/raw/<file>.pdf --truong "<Tên trường>" --nam 2026 \
    --so-van-ban "<số văn bản>" --ngay "dd/mm/yyyy" -o data/chunks/<ten-file>.jsonl
python src/ingest.py
```

`chunk_quyche.py` dùng cho văn bản dạng **Quy chế** (chia theo Điều). Văn bản **Thông tin tuyển sinh**
có nhiều bảng (ngành, tổ hợp, chỉ tiêu, điểm) sẽ cần script cắt riêng cho bảng.

## Chọn model

| Cấu hình máy | Model trả lời (`LLM_MODEL`) | Ghi chú |
|---|---|---|
| Chỉ CPU, RAM 8 GB | `qwen3:4b` | Chậm, chất lượng tạm được |
| RAM 16 GB hoặc GPU 6–8 GB | `qwen3:8b` *(mặc định)* | Cân bằng tốt cho tiếng Việt |
| GPU 16–24 GB | `qwen3:14b` hoặc lớn hơn | Trả lời mượt và chính xác hơn |

- Đổi model: sửa `LLM_MODEL` trong `src/config.py`, rồi `ollama pull <tên model>`. Không cần chạy lại `ingest.py`.
- Embedding: mặc định `bge-m3`. Nếu đổi `EMBED_MODEL` thì **phải** chạy lại `ingest.py`.
- Sau mỗi lần đổi model, chạy lại các câu trong `docs/test_cases.md` để so sánh.

## Lộ trình

- [x] Cắt quy chế ĐHBK Hà Nội 2026 theo Điều
- [x] Bộ quy tắc trả lời lịch sự
- [x] Pipeline RAG local (Ollama + tìm kiếm vector)
- [ ] Nạp Thông tin tuyển sinh (bảng ngành, tổ hợp, điểm chuẩn)
- [ ] Thêm trường khác, lọc theo trường khi câu hỏi nêu tên trường
- [ ] Tìm kiếm kết hợp từ khoá (BM25) cho viết tắt như XTTN, ĐGTD
- [ ] Giao diện web (Streamlit/Gradio)
- [ ] Script chấm tự động bộ câu hỏi kiểm thử
