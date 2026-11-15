"""
Cắt văn bản quy chế tuyển sinh (PDF) thành các đoạn (chunk) theo Chương / Mục / Điều
để nạp vào vector database cho hệ thống RAG.

Cách dùng:
    pip install pdfplumber
    python src/chunk_quyche.py data/raw/dhbk-2026-quy-che-tuyen-sinh-4740.pdf --truong "ĐHBK Hà Nội" --nam 2026 \
        --so-van-ban "4740/QĐ-ĐHBK" --ngay "06/05/2026" -o data/chunks/dhbk-2026-quy-che.jsonl

Kết quả: mỗi dòng trong chunks.jsonl là 1 chunk dạng
    {"id": ..., "text": ..., "metadata": {...}}
"text" đã gắn sẵn tiêu đề ngữ cảnh (trường, văn bản, chương, điều) để khi tìm kiếm
và khi đưa vào prompt, model luôn biết đoạn đó thuộc trường nào, điều nào.
"""

import argparse
import json
import re
import unicodedata
import pdfplumber

MAX_CHARS = 1500  # Điều dài hơn ngưỡng này sẽ được cắt tiếp theo từng khoản

RE_PAGE_NUM = re.compile(r"^\s*\d{1,3}\s*$")
RE_CHUONG = re.compile(r"^\s*Chương\s+([IVXLC]+)\s*$")
RE_MUC = re.compile(r"^\s*Mục\s+(\d+)\s*$")
RE_DIEU = re.compile(r"^\s*Điều\s+(\d+)\.\s*(.*)$")
RE_KHOAN = re.compile(r"^\s*\d+(\.\d+)?\.?\s")
# Dòng bắt đầu một ý mới (không nối vào dòng trước)
RE_NEW_PARA = re.compile(r"^\s*(\d+\.\s|\d+\.\d+\.?\s|[a-zđ]\)\s|Bước\s+\d+|-\s|Điều\s+\d+\.)")


def read_lines(pdf_path):
    """Trả về danh sách (số trang, dòng) đã bỏ số trang và dòng trống."""
    # pdfplumber giữ đúng dấu tiếng Việt (pypdf hay tách chữ kiểu "giá tr ị")
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            for line in (page.extract_text() or "").splitlines():
                if not line.strip() or RE_PAGE_NUM.match(line):
                    continue
                out.append((pno, line.strip()))
    return out


def join_paragraphs(lines):
    """Nối các dòng bị ngắt giữa câu thành đoạn văn hoàn chỉnh."""
    paras = []
    for line in lines:
        if paras and not RE_NEW_PARA.match(line):
            paras[-1] += " " + line.strip()
        else:
            paras.append(line.strip())
    return [re.sub(r"\s+", " ", p) for p in paras]


def split_long(paras, max_chars):
    """Cắt 1 Điều dài thành nhiều phần, mỗi phần gồm trọn vẹn các khoản."""
    parts, cur = [], []
    for p in paras:
        if cur and RE_KHOAN.match(p) and sum(len(x) for x in cur) + len(p) > max_chars:
            parts.append(cur)
            cur = []
        cur.append(p)
    if cur:
        parts.append(cur)
    return parts


def build_chunks(pdf_path, truong, nam, so_van_ban, ngay):
    lines = read_lines(pdf_path)
    text_all = [l for _, l in lines]

    # 1) Phần Quyết định ban hành (trước mục lục): giữ làm 1 chunk về hiệu lực văn bản
    end_qd = next(i for i, l in enumerate(text_all) if "Nơi nhận" in l)
    chunks = []
    base_meta = {"truong": truong, "nam": nam, "so_van_ban": so_van_ban,
                 "ngay_ban_hanh": ngay, "nguon": pdf_path.split("/")[-1]}

    qd_paras = join_paragraphs(text_all[:end_qd])
    chunks.append({
        "header": f"[{truong}] Quyết định {so_van_ban} ngày {ngay} – ban hành Quy chế tuyển sinh đại học {nam}",
        "paras": qd_paras,
        "meta": {**base_meta, "phan": "Quyết định ban hành", "trang": lines[0][0]},
    })

    # 2) Bỏ qua mục lục: phần quy chế bắt đầu từ dòng "(Kèm theo Quyết định..."
    start = next(i for i, l in enumerate(text_all) if "Kèm theo Quyết định" in l)
    chuong = chuong_ten = muc = muc_ten = None
    cur = None  # Điều đang đọc
    i = start
    while i < len(lines):
        pno, line = lines[i]
        if m := RE_CHUONG.match(line):
            chuong = f"Chương {m.group(1)}"
            # Tên chương có thể kéo dài nhiều dòng (viết hoa) cho tới khi gặp Mục/Điều
            ten = []
            while i + 1 < len(lines) and not (RE_MUC.match(lines[i + 1][1]) or RE_DIEU.match(lines[i + 1][1])):
                i += 1
                ten.append(lines[i][1].strip())
            chuong_ten, muc, muc_ten = " ".join(ten), None, None
        elif m := RE_MUC.match(line):
            muc = f"Mục {m.group(1)}"
            i += 1
            muc_ten = lines[i][1].strip()
        elif m := RE_DIEU.match(line):
            if cur:
                chunks.append(cur)
            dieu_so, ten = m.group(1), m.group(2).strip()
            # Tên điều có thể xuống dòng (vd Điều 20, 21, 22): dòng sau bắt đầu bằng chữ thường
            # hoặc là một dòng rất ngắn (vd "ĐHCQ")
            while i + 1 < len(lines) and not RE_NEW_PARA.match(lines[i + 1][1]) \
                    and (lines[i + 1][1][:1].islower() or len(lines[i + 1][1]) < 20):
                i += 1
                ten += " " + lines[i][1].strip()
            cur = {
                "dieu": f"Điều {dieu_so}", "ten": ten, "lines": [],
                "meta": {**base_meta, "chuong": f"{chuong}. {chuong_ten}" if chuong else None,
                         "muc": f"{muc}. {muc_ten}" if muc else None,
                         "dieu": int(dieu_so), "tieu_de": ten, "trang": pno},
            }
        elif cur:
            cur["lines"].append(line)
        i += 1
    if cur:
        chunks.append(cur)

    # 3) Gắn tiêu đề ngữ cảnh + cắt Điều dài
    out = []
    for c in chunks:
        if "paras" in c:  # chunk Quyết định
            out.append(("qd", c["header"], c["paras"], c["meta"]))
            continue
        paras = join_paragraphs(c["lines"])
        parts = split_long(paras, MAX_CHARS)
        for k, part in enumerate(parts, start=1):
            loc = " > ".join(x for x in [c["meta"]["chuong"], c["meta"]["muc"]] if x)
            suffix = f" (phần {k}/{len(parts)})" if len(parts) > 1 else ""
            header = (f"[{truong}] Quy chế tuyển sinh {nam} ({so_van_ban}) – {loc} > "
                      f"{c['dieu']}. {c['ten']}{suffix}")
            out.append((f"dieu{c['meta']['dieu']:02d}-{k}", header, part, c["meta"]))

    ascii_ = unicodedata.normalize("NFD", so_van_ban.replace("Đ", "D").replace("đ", "d"))
    ascii_ = "".join(ch for ch in ascii_ if unicodedata.category(ch) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")
    return [{
        "id": f"{slug}-{cid}",
        "text": header + "\n" + "\n".join(paras),
        "metadata": meta,
    } for cid, header, paras, meta in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--truong", required=True)
    ap.add_argument("--nam", type=int, required=True)
    ap.add_argument("--so-van-ban", required=True)
    ap.add_argument("--ngay", required=True)
    ap.add_argument("-o", "--output", default="chunks.jsonl")
    a = ap.parse_args()

    chunks = build_chunks(a.pdf, a.truong, a.nam, a.so_van_ban, a.ngay)
    with open(a.output, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"Đã tạo {len(chunks)} chunk -> {a.output}")


if __name__ == "__main__":
    main()
