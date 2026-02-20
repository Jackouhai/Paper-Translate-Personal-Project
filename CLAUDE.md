# PP-DocLayout - Ghi chú cho session tiếp theo

## 📋 Tổng quan dự án
Pipeline dịch thuật tài liệu học thuật sang tiếng Việt với quy trình khép kín:
1. **Parse PDF** (Layout Analysis + OCR) → JSON + images
2. **Translate** (Gemma hoặc HY-MT) → Vietnamese
3. **Reconstruct** → HTML với MathJax

## 🏗 Cấu trúc codebase hiện tại

### Scripts cũ (legacy, vẫn hoạt động)
```
main.py                  - Parse PDF bằng PaddleOCR-VL
reconstruct_gemma.py     - Dịch + HTML với Gemma model
reconstruct_multi.py     - Dịch + HTML với HY-MT model
translator_engine.py     - Old translator wrapper (đã thay thế)
translator_engine_gemma.py - Old translator wrapper (đã thay thế)
base.py                  - Base class từ PaddleX
paddleocr_vl.py          - Wrapper PaddleOCR-VL
```

### Source code chính (src/pp_doclayout/) - Architecture mới ✅
```
__init__.py              - Version info
cli.py                   - Typer CLI với 3 commands: parse, translate, run
config.py                - Configuration (pydantic-settings) ✅
types.py                 - Type definitions (TypedDict) ✅

utils/                   # Utility functions ✅
  ├─ __init__.py
  ├─ file_utils.py       # find_image_file(), ensure_dir()
  └─ path_utils.py       # get_output_dir(), get_project_dir()

templates/               # Jinja2 HTML templates ✅
  ├─ base.html           # Base HTML template
  ├─ page.html           # Page template
  ├─ styles.html         # CSS styles
  └─ mathjax_config.html # MathJax configuration

policies/
  └─ translation_policy.py - Logic dịch/giữ/skip blocks

translators/
  ├─ __init__.py
  ├─ base.py             - Abstract Base Translator
  └─ gemma.py            - Google TranslateGemma (có translate_batch) ✅

exporters/               # Export handlers ✅
  ├─ __init__.py
  ├─ base.py             # BaseExporter (abstract)
  └─ html.py             # HTMLExporter với Jinja2

core/
  ├─ __init__.py
  ├─ reconstructor.py    # HTML rendering & reconstruction logic
  └─ batch_processor.py  # Batch processing for translation ✅
```

### Tests (tests/) ✅
```
test_config.py           # Tests for config.py
test_types.py            # Tests for types module
test_utils.py            # Tests for utils module
test_batch_processor.py  # Tests for batch_processor
test_exporters.py        # Tests for exporters
```

## 🚀 Cách sử dụng

### CLI mới (khuyến nghị)
```bash
# Parse PDF
uv run -m pp_doclayout.cli parse <path_to_pdf>

# Translate (cần vLLM server chạy trước)
uv run -m pp_doclayout.cli translate <output_dir>

# Full pipeline: parse + translate
uv run -m pp_doclayout.cli run <path_to_pdf>
```

### Scripts cũ
```bash
# Step 1: Parse
uv run main.py

# Step 2a: Dịch với Gemma
uv run reconstruct_gemma.py <project_dir>

# Step 2b: Dịch với HY-MT
uv run reconstruct_multi.py <project_dir>
```

## 🖥 Servers cần chạy

### vLLM Server (Gemma) - Port 8001
```bash
vllm serve Infomaniak-AI/vllm-translategemma-4b-it \
    --dtype bfloat16 \
    --max-model-len 32768 \
    --max-num-seqs 16 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.9 \
    --enforce-eager \
    --port 8001 \
    --optimization-level 0
```

### PaddleOCR-VL Server - Port 8000
```bash
vllm serve PaddlePaddle/PaddleOCR-VL-1.5 \
    --served-model-name PaddleOCR-VL-1.5-0.9B \
    --trust-remote-code \
    --max-num-batched-tokens 16384 \
    --max-num-seqs 3 \
    --max-model-len 32768 \
    --gpu-memory-utilization 0.6 \
    --no-enable-prefix-caching \
    --mm-processor-cache-gb 0 \
    --dtype bfloat16 \
    --tensor-parallel-size 1
```

### Khởi động cả 2 servers
```bash
./start_server.sh
```

### Kiểm tra servers
```bash
curl http://127.0.0.1:8001/v1/models    # Gemma
curl http://127.0.0.1:8000/v1/models    # PaddleOCR
```

## ⚙ Cấu hình (src/pp_doclayout/config.py)

```python
# Engine
engine: str = "gemma"

# vLLM/Gemma Server
vllm_base_url: str = "http://127.0.0.1:8001/v1"
vllm_max_tokens: int = 16384
vllm_model_name: str = "Infomaniak-AI/vllm-translategemma-4b-it"

# PaddleOCR-VL Server
paddle_ocr_server_url: str = "http://127.0.0.1:8000/v1"
paddle_ocr_backend: str = "vllm-server"

# Batch Processing
batch_size_small: int = 16    # <100 tokens
batch_size_medium: int = 8    # 100-500 tokens
batch_size_large: int = 4     # >500 tokens

# Paths
output_dir: str = "output"

# Export
export_formats_raw: str = "html,pdf"  # comma-separated
```

Có thể thay đổi qua env vars với prefix `PPDOCLAYOUT_` hoặc `.env` file.

## 📝 Translation Policy

| Action | Labels | Mô tả |
|--------|--------|-------|
| **translate** | `abstract`, `text`, `figure_title`, `table_caption` | Nội dung chính |
| **keep** | `doc_title`, `paragraph_title`, `reference_content`, `footnote`, `display_formula`, `table`, `image`, `chart` | Tiêu đề, references, công thức |
| **skip** | `aside_text`, `header`, `footer`, `number`, `content` | Nhiễu, số trang |

## 📦 Dependencies chính

- `paddlepaddle-gpu` + `paddleocr` + `paddleocrvl` - OCR
- `vllm` - Inference engine
- `openai` - API client cho vLLM
- `typer` - CLI framework
- `pydantic-settings` - Configuration ✅
- `jinja2` - Templates ✅
- `tiktoken` - Token estimation ✅

Cài đặt:
```bash
uv pip install transformers accelerate bitsandbytes sentencepiece protobuf paddlepaddle-gpu paddleocr paddleocrvl pydantic-settings jinja2 tiktoken
```

## 📂 Output

Tất cả kết quả lưu trong `output/<pdf_name>/`:
- JSON files: `*_res.json` - parsing results
- Images: `imgs/` - cropped images
- HTML: `translated_<project_name>.html` - final result

## 🔍 Status hiện tại

- Git repo: Chưa có commit nào (all files untracked)
- Python version: 3.10+
- Virtual environment: `.venv/` (đã cài dependencies)

---

# 🎯 KẾ HOẠCH REFACTOR

## 📌 Config máy của bạn
```
GPU: NVIDIA GeForce RTX 5060 Ti (16GB VRAM)
CPU: 16 cores
RAM: 31GB total, 19GB available
Python: 3.12.9
Package Manager: uv 0.8.18
OS: Linux 6.17.0-14-generic
```

## 📋 Vấn đề cần refactor

| Vấn đề | Mô tả | Trạng thái |
|--------|-------|-----------|
| Code duplication | `find_image_file()` xuất hiện 3 lần | ✅ Fixed (utils/file_utils.py) |
| Hardcoded values | Paths, URLs được hardcode | ✅ Fixed (config.py + .env) |
| File quá lớn | `reconstructor.py` 386 lines | ⏳ Partial (batch_processor extracted) |
| No templates | HTML render bằng string concatenation | ✅ Fixed (Jinja2 templates) |
| No tests | Không có unit tests | ✅ Fixed (5 test files) |

## 🎯 Mục tiêu refactor

1. ✅ Tách code thành modules nhỏ, dễ quản lý
2. ✅ Dùng config file (.env) thay vì hardcode
3. ✅ Dùng Jinja2 templates cho HTML
4. ✅ Thêm tests
5. ⏳ Thêm PDF export (beyond HTML) - pending
6. ✅ Xử lý song song nhiều projects (BatchProcessor)

## 📁 Cấu trúc hiện tại (đã hoàn thành大部分)

```
PP_DocLayout/
├── src/pp_doclayout/
│   ├── __init__.py
│   ├── cli.py                   # CLI commands
│   ├── config.py                # Configuration (Pydantic Settings) ✅
│   ├── types.py                 # Type definitions ✅
│   │
│   ├── utils/                   # Utility functions ✅
│   │   ├── __init__.py
│   │   ├── file_utils.py        # find_image_file(), ensure_dir()
│   │   └── path_utils.py        # get_output_dir(), get_project_dir()
│   │
│   ├── templates/               # Jinja2 HTML templates ✅
│   │   ├── base.html
│   │   ├── page.html
│   │   ├── mathjax_config.html
│   │   └── styles.html
│   │
│   ├── policies/
│   │   └── translation_policy.py
│   │
│   ├── exporters/               # Export handlers ✅
│   │   ├── base.py              # BaseExporter (abstract)
│   │   ├── html.py              # HTMLExporter
│   │   └── pdf.py               # TODO: PDFExporter
│   │
│   ├── translators/
│   │   ├── base.py              # BaseTranslator (abstract)
│   │   └── gemma.py             # GemmaTranslator + translate_batch()
│   │
│   └── core/
│       ├── reconstructor.py     # Main reconstruction logic
│       └── batch_processor.py   # Batch processing ✅
│
├── tests/                       # Unit tests ✅
│   ├── test_config.py
│   ├── test_types.py
│   ├── test_utils.py
│   ├── test_batch_processor.py
│   └── test_exporters.py
│
├── pyproject.toml
├── .env.example                 ✅
└── .env
```

---

## 📊 PROGRESS TRACKING

### ✅ Phase 1: Foundation - Configuration & Utilities (HOÀN THÀNH)

| Step | Tên | Trạng thái |
|------|-----|-----------|
| 1 | Cài pydantic-settings | ✅ Done |
| 2 | Tạo .env.example | ✅ Done |
| 3 | Tạo types.py | ✅ Done |
| 4 | Tạo utils module | ✅ Done |
| 5 | Update config.py | ✅ Done |
| 6 | Test verification | ✅ Done |

### ✅ Phase 2: Refactor Core Logic (HOÀN THÀNH)

| Step | Tên | Trạng thái |
|------|-----|-----------|
| 1 | Tạo BatchProcessor | ✅ Done |
| 2 | Update GemmaTranslator.translate_batch() | ✅ Done |

### ✅ Phase 3: Templates & Exporters (HOÀN THÀNH)

| Step | Tên | Trạng thái |
|------|-----|-----------|
| 1 | Tạo Jinja2 templates | ✅ Done |
| 2 | Tạo BaseExporter | ✅ Done |
| 3 | Tạo HTMLExporter | ✅ Done |
| 4 | Tests for exporters | ✅ Done |

### ⏳ Phase 4: Cleanup & Optimization (PENDING)

| Step | Tên | Trạng thái |
|------|-----|-----------|
| 1 | Remove HY-MT support (hoặc tách riêng) | ⏳ Pending |
| 2 | Fix duplicate `__all__` in core/__init__.py | ⏳ Pending |
| 3 | Integrate HTMLExporter into reconstructor | ⏳ Pending |
| 4 | Add PDFExporter | ⏳ Pending |

### ⏳ Phase 5: CLI Enhancements (PENDING)

| Step | Tên | Trạng thái |
|------|-----|-----------|
| 1 | Add --format option to CLI | ⏳ Pending |
| 2 | Add --batch-size option | ⏳ Pending |
| 3 | Progress bar for translation | ⏳ Pending |

### ⏳ Phase 6: Testing & Documentation (PENDING)

| Step | Tên | Trạng thái |
|------|-----|-----------|
| 1 | Integration tests | ⏳ Pending |
| 2 | Update README.md | ⏳ Pending |
| 3 | Add docstrings | ⏳ Pending |

---

## 📌 Session hiện tại

- **Mode**: Learning mode
  - **Bạn tự code** theo hướng dẫn/gợi ý của tôi
  - Tôi **chỉ kiểm tra** lại sau khi bạn code xong
  - Không auto-write code, chỉ gợi ý và review
- **Phase đã hoàn thành**: Phase 1, 2, 3
- **Phase tiếp theo**: Phase 4 - Cleanup & Optimization

## 🐛 Known Issues

1. **core/__init__.py** có duplicate `__all__` definition (line 4 and 6)
2. **reconstructor.py** vẫn còn duplicate `find_image_file()` function (line 44-57) - nên dùng từ utils
3. **HY-MT support** vẫn còn trong codebase (reconstruct_multi.py) - cần quyết định keep hay remove

---
**Cập nhật lần cuối:** 2026-02-20
