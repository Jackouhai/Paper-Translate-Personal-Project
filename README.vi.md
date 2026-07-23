# PP-DocLayout

Pipeline dịch tài liệu học thuật PDF sang tiếng Việt, giữ nguyên layout gốc.

[README.md (English)](README.md)

---

## Key Features

- **Layout Analysis** — nhận diện tiêu đề, abstract, text, bảng, hình, công thức
- **OCR** — trích xuất text, bảng sang HTML, công thức sang LaTeX
- **Dịch thuật** — TranslateGemma 4B chạy locally trên GPU qua vLLM
- **Translation Policy** — giữ nguyên tiêu đề, references, công thức, chỉ dịch nội dung chính
- **HTML Output** — absolute positioning, MathJax render công thức
- **PDF Export** — xuất PDF qua headless Chrome (Playwright)

## Quick Start

> **Yêu cầu:** Linux | NVIDIA GPU | Python 3.10+ | [uv](https://docs.astral.sh/uv/)
>
> **VRAM:** ~4-8GB chạy từng bước, ~16GB cho full pipeline (cả 2 servers cùng lúc)

### PaddlePaddle Wheel

Trước khi cài, kiểm tra GPU và compute capability:

```bash
nvidia-smi
python3 -c "import subprocess; print(subprocess.check_output(['nvidia-smi', '--query-gpu=name,compute_cap', '--format=csv,noheader'], text=True))"
```

PaddlePaddle GPU yêu cầu compute capability lớn hơn 7.5. Nếu GPU không đạt yêu cầu này, cần dùng máy NVIDIA GPU/CUDA phù hợp khác trước khi chạy local pipeline.

`pyproject.toml` mặc định dùng `cu130`. Nếu máy cần wheel khác, sửa PaddlePaddle index trước khi chạy `uv sync`:

| CUDA wheel | PaddlePaddle index URL |
|------------|-------------------------|
| CUDA 13.0 | `https://www.paddlepaddle.org.cn/packages/stable/cu130/` |
| CUDA 12.9 | `https://www.paddlepaddle.org.cn/packages/stable/cu129/` |
| CUDA 12.6 | `https://www.paddlepaddle.org.cn/packages/stable/cu126/` |
| CUDA 11.8 | `https://www.paddlepaddle.org.cn/packages/stable/cu118/` |

```bash
# 1. Cài đặt
git clone <repo_url> && cd Paper-Translate-Personal-Project
uv sync
uv pip install -e .

# 2. Kiểm tra PaddlePaddle
uv run python scripts/check_paddle_env.py

# 3. Cài browser cho Playwright để xuất PDF
uv run playwright install chromium

# 4. Copy file cấu hình mẫu
cp .env.example .env

# Nếu không dùng được Chromium do Playwright quản lý, cài Google Chrome:
# wget -q -O /tmp/google-chrome.deb "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
# sudo apt install /tmp/google-chrome.deb
#
# Sau đó cấu hình PP-DocLayout sử dụng Chrome trên hệ thống:
# echo "PPDOCLAYOUT_PLAYWRIGHT_BROWSER_CHANNEL=chrome" >> .env

# 5. Khởi động PaddleOCR-VL server (Terminal 1, port 8000)
scripts/start_paddle_ocr_vl.sh

# 6. Khởi động TranslateGemma server (Terminal 2, port 8001)
scripts/start_translate_gemma.sh

# 7. Kiểm tra cả hai server (Terminal 3)
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models

# 8. Chạy
uv run -m pp_doclayout.cli run paper.pdf
```

Nếu kiểm tra PaddlePaddle fail, sửa Paddle/CUDA trước khi chạy `parse` hoặc `run`.

Output: `output/paper/translated_paper.html`

```bash
# Xuất PDF thay vì HTML
uv run -m pp_doclayout.cli run paper.pdf -f pdf

# Hoặc dịch dữ liệu đã parse sang PDF
uv run -m pp_doclayout.cli translate output/paper -f pdf
```

Output: `output/paper/translated_paper.pdf`

Mặc định, PDF export dùng Chromium do Playwright quản lý. Để dùng browser đã
cài trên hệ thống, đặt browser channel trong `.env`:

```env
PPDOCLAYOUT_PLAYWRIGHT_BROWSER_CHANNEL=chrome
```

CSS dành cho chế độ in ánh xạ mỗi trang HTML đã parse thành một trang PDF,
đồng thời loại bỏ margin và shadow chỉ phục vụ giao diện xem trên màn hình.

---

## Hướng dẫn sử dụng

> Khuyến nghị chạy từng bước (`parse` rồi `translate`). Máy ít VRAM có thể tắt PaddleOCR-VL server sau khi parse xong để giải phóng VRAM cho TranslateGemma.

### Khởi động model servers

Mở hai terminal:

```bash
# Terminal 1: OCR/layout server
scripts/start_paddle_ocr_vl.sh

# Terminal 2: translation server
scripts/start_translate_gemma.sh
```

Sau đó kiểm tra cả hai endpoint model tương thích OpenAI:

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
```

CLI sẽ kiểm tra các endpoint này trước khi chạy `parse`, `translate`, hoặc
`run`. Nếu thiếu server bắt buộc, command sẽ dừng sớm và in ra URL server cùng
lý do lỗi.

Mặc định, các model phụ local của PaddleOCR như `PP-DocLayoutV3` dùng:

```env
PPDOCLAYOUT_PADDLE_OCR_CLIENT_DEVICE=auto
```

`auto` sẽ chọn `gpu:0` nếu Paddle phát hiện CUDA GPU dùng được, nếu không sẽ
dùng `cpu`. Có thể ép device bằng cách đặt giá trị này thành `cpu` hoặc `gpu:0`
trong `.env`.

### Bước 1: Parse PDF

Chỉ cần PaddleOCR-VL server (port 8000).

```bash
uv run -m pp_doclayout.cli parse <file.pdf>

# Chỉ định thư mục output
uv run -m pp_doclayout.cli parse <file.pdf> -o ./ket_qua
```

Kết quả lưu tại `output/<tên_file>/`:
- `*_res.json` — parsing results (tọa độ + nội dung từng block)
- `*_res.md` — markdown output
- `imgs/` — cropped images

### Bước 2: Translate

Cần TranslateGemma server (port 8001).

```bash
# Xuất HTML (mặc định)
uv run -m pp_doclayout.cli translate output/<tên_file>

# Xuất PDF
uv run -m pp_doclayout.cli translate output/<tên_file> -f pdf

# Hậu tố file tùy chỉnh
uv run -m pp_doclayout.cli translate output/<tên_file> --suffix vi
```

Kết quả: `output/<tên_file>/translated_<tên_file>.html` hoặc `.pdf`

### Full Pipeline

Chạy parse + translate trong 1 lệnh. Cần cả 2 servers chạy cùng lúc.

```bash
# Xuất HTML (mặc định)
uv run -m pp_doclayout.cli run <file.pdf>

# Xuất PDF
uv run -m pp_doclayout.cli run <file.pdf> -f pdf
```

### Xem kết quả

```bash
xdg-open output/<tên_file>/translated_<tên_file>.html   # HTML
xdg-open output/<tên_file>/translated_<tên_file>.pdf    # PDF
```

## Models

Pipeline sử dụng 2 mô hình, mỗi mô hình chạy trên 1 vLLM server riêng:

| Model | Size | Port | Chức năng |
|-------|------|------|-----------|
| **PaddleOCR-VL** | 0.9B | 8000 | Phân tích layout, OCR, crop images |
| **TranslateGemma** | 4B (bitsandbytes quantized) | 8001 | Dịch Anh → Việt |

### Kiểm tra servers

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
```

## Translation Policy

| Action | Labels | Mô tả |
|--------|--------|-------|
| **Dịch** | `abstract`, `text`, `figure_title` | Nội dung chính |
| **Giữ nguyên** | `doc_title`, `paragraph_title`, `reference_content`, `footnote`, `display_formula`, `table`, `image`, `chart`, `formula_number` | Tiêu đề, references, công thức |
| **Bỏ qua** | `aside_text`, `header`, `footer`, `number` | Nhiễu, số trang |

## Cấu trúc Project

```
src/pp_doclayout/
├── cli.py                      # CLI (parse, translate, run)
├── config.py                   # Pydantic Settings
├── types.py                    # TypedDict definitions
├── core/
│   └── renderer.py             # Build/translate/render → HTML
├── exporters/
│   ├── base.py                 # Abstract BaseExporter
│   ├── html.py                 # HTMLExporter (Jinja2)
│   └── pdf.py                  # PDFExporter (Playwright)
├── policies/
│   └── translation_policy.py   # Logic dịch/giữ/skip
├── translators/
│   ├── base.py                 # Abstract BaseTranslator
│   └── gemma.py                # GemmaTranslator (vLLM API)
├── templates/                  # Jinja2 HTML templates
│   ├── base.html
│   ├── page.html
│   ├── styles.html
│   ├── mathjax_config.html
│   └── dynamic_font_size.html
└── utils/
    ├── file_utils.py
    ├── paddle_device.py        # Chọn device cho model phụ PaddleOCR
    ├── path_utils.py
    └── server_health.py        # Kiểm tra model servers tương thích OpenAI
```

## Troubleshooting

**Out of Memory (OOM):**
- Giảm `--max-model-len` hoặc `--gpu-memory-utilization` trong vLLM command
- Giảm `--max-num-seqs` để giảm batch size
- Chạy từng bước thay vì `run` để chỉ cần 1 server tại thời điểm

**ModuleNotFoundError:**
```bash
uv pip install -e .
```

**Servers không connect:**
```bash
nvidia-smi
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
```

## License

MIT License
