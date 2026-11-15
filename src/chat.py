"""
Chat với Trợ lý tuyển sinh ngay trên cửa sổ dòng lệnh.

    python src/chat.py            # chat bình thường
    python src/chat.py --debug    # in thêm các đoạn tài liệu tìm được và điểm tương đồng
"""
import argparse

from ollama_client import OllamaError, version_warning
from rag import Retriever, answer, load_system_prompt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    if warn := version_warning():
        print(f"[Cảnh báo] {warn}\n")
    retriever = Retriever()
    system_prompt = load_system_prompt()
    history = []
    print("Trợ lý tuyển sinh đã sẵn sàng. Gõ câu hỏi (gõ 'thoat' để thoát, 'moi' để bắt đầu lại).\n")

    while True:
        try:
            q = input("Bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            continue
        if q.lower() in {"thoat", "thoát", "exit", "quit"}:
            break
        if q.lower() in {"moi", "mới"}:
            history = []
            print("(Đã xoá lịch sử hội thoại)\n")
            continue

        try:
            stream, hits = answer(retriever, system_prompt, history, q)
            if args.debug:
                print("--- Tài liệu tìm được ---")
                for c, s in hits:
                    print(f"  {s:.3f}  {c['id']}  {c['metadata'].get('tieu_de', '')}")
                print("------------------------")

            print("Trợ lý: ", end="", flush=True)
            reply = ""
            thinking_shown = False
            for kind, piece in stream:
                if kind == "thinking":
                    if not thinking_shown:
                        print("(đang suy nghĩ...) ", end="", flush=True)
                        thinking_shown = True
                    continue
                print(piece, end="", flush=True)
                reply += piece
            print("\n")
        except OllamaError as e:
            print(f"\n[Lỗi] {e}\n")
            continue
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": reply}]


if __name__ == "__main__":
    main()
