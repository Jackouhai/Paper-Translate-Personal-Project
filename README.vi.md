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

## Quick Start

> **Yêu cầu:** Linux | NVIDIA GPU | Python 3.10+ | [uv](https://docs.astral.sh/uv/)
>
> **VRAM:** ~4-8GB chạy từng bước, ~16GB cho full pipeline (cả 2 servers cùng lúc)

```bash
# 1. Cài đặt
git clone <repo_url> && cd Paper-Translate-Personal-Project
uv sync
uv pip install -e .

# 2. Khởi động PaddleOCR-VL (Terminal 1, port 8000)
vllm serve PaddlePaddle/PaddleOCR-VL-1.5 \
    --served-model-name PaddleOCR-VL-1.5-0.9B \
    --trust-remote-code \
    --dtype bfloat16 \
    --max-model-len 16384 \
    --max-num-seqs 30 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.2 \
    --enforce-eager \
    --no-enable-prefix-caching \
    --mm-processor-cache-gb 0

# 3. Khởi động TranslateGemma (Terminal 2, port 8001)
vllm serve Infomaniak-AI/vllm-translategemma-4b-it \
    --dtype bfloat16 \
    --quantization bitsandbytes \
    --load-format bitsandbytes \
    --max-model-len 32768 \
    --max-num-seqs 30 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.5 \
    --kv-cache-dtype fp8 \
    --enforce-eager \
    --port 8001

# 4. Chạy
uv run -m pp_doclayout.cli run paper.pdf
```

Output: `output/paper/translated_paper.html`

---

## Hướng dẫn sử dụng

> Khuyến nghị chạy từng bước (`parse` rồi `translate`). Máy ít VRAM có thể tắt PaddleOCR-VL server sau khi parse xong để giải phóng VRAM cho TranslateGemma.

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
uv run -m pp_doclayout.cli translate output/<tên_file>

# Hậu tố file tùy chỉnh
uv run -m pp_doclayout.cli translate output/<tên_file> --suffix vi
```

Kết quả: `output/<tên_file>/translated_<tên_file>.html`

### Full Pipeline

Chạy parse + translate trong 1 lệnh. Cần cả 2 servers chạy cùng lúc.

```bash
uv run -m pp_doclayout.cli run <file.pdf>
```

### Xem kết quả

```bash
xdg-open output/<tên_file>/translated_<tên_file>.html
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
│   └── html.py                 # HTMLExporter (Jinja2)
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
    └── path_utils.py
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
