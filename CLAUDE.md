# PP-DocLayout - Ghi chú cho session tiếp theo

## 📋 Tổng quan dự án
Pipeline dịch thuật tài liệu học thuật sang tiếng Việt với quy trình khép kín:
1. **Parse PDF** (Layout Analysis + OCR) → JSON + images
2. **Translate** (Gemma hoặc HY-MT) → Vietnamese
3. **Reconstruct** → HTML với MathJax

## 🏗 Cấu trúc codebase hiện tại

### Scripts cũ (đã có, có thể refactoring sau)
```
main.py                  - Parse PDF bằng PaddleOCR-VL
reconstruct_gemma.py     - Dịch + HTML với Gemma model
reconstruct_multi.py     - Dịch + HTML với HY-MT model
translator_engine.py     - Old translator wrapper (đã thay thế)
translator_engine_gemma.py - Old translator wrapper (đã thay thế)
base.py                  - Base class từ PaddleX
paddleocr_vl.py          - Wrapper PaddleOCR-VL
```

### Source code chính (src/pp_doclayout/) - Architecture mới
```
cli.py                   - Typer CLI với 3 commands: parse, translate, run
config.py                - Configuration (pydantic-settings)
policies/
  └─ translation_policy.py - Logic dịch/giữ/skip blocks
translators/
  ├─ base.py             - Abstract Base Translator
  ├─ gemma.py            - Google TranslateGemma (chất lượng cao)
  └─ hymt.py             - Tencent HY-MT (nhẹ & nhanh)
core/
  └─ reconstructor.py    - HTML rendering & reconstruction logic
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
engine: str = "gemma"
vllm_base_url: str = "http://127.0.0.1:8001/v1"
vllm_max_tokens: int = 16384
vllm_model_name: str = "Infomaniak-AI/vllm-translategemma-4b-it"
paddle_ocr_server_url: str = "http://127.0.0.1:8000/v1"
```

Có thể thay đổi qua env vars hoặc `.env` file.

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
- `pydantic-settings` - Configuration

Cài đặt:
```bash
uv pip install transformers accelerate bitsandbytes sentencepiece protobuf paddlepaddle-gpu paddleocr paddleocrvl
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

# 🎯 KẾ HOẠCH REFACTOR (ĐANG LÀM)

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

| Vấn đề | Mô tả | Tại sao cần fix? |
|--------|---------|-----------------|
| Code duplication | `find_image_file()` xuất hiện 3 lần, HTML styles lặp lại | Hard maintain |
| Hardcoded values | Paths, URLs được hardcode (`/home/bocchi/...`) | Không portable |
| File quá lớn | `reconstructor.py` 386 lines, làm nhiều việc | Difficult test |
| No templates | HTML được render bằng string concatenation | Hard customize |
| No tests | Không có unit tests | Risky khi refactor |

## 🎯 Mục tiêu refactor

1. ✅ Tách code thành modules nhỏ, dễ quản lý
2. ✅ Dùng config file (.env) thay vì hardcode
3. ✅ Dùng Jinja2 templates cho HTML
4. ✅ Thêm tests
5. ✅ Thêm PDF export (beyond HTML)
6. ✅ Xử lý song song nhiều projects

## 📁 Cấu trúc mới sau refactor

```
PP_DocLayout/
├── src/pp_doclayout/
│   ├── __init__.py
│   ├── cli.py                   # CLI commands
│   ├── config.py                # Configuration (Pydantic Settings)
│   ├── types.py                 # Type definitions
│   │
│   ├── utils/                   # Utility functions
│   │   ├── __init__.py
│   │   ├── file_utils.py        # find_image_file(), ensure_dir()
│   │   └── path_utils.py        # get_output_dir(), get_project_dir()
│   │
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── page.html
│   │   ├── mathjax_config.html
│   │   └── styles.html
│   │
│   ├── policies/
│   │   └── translation_policy.py
│   │
│   ├── exporters/               # Export handlers
│   │   ├── base.py
│   │   ├── html.py
│   │   └── pdf.py
│   │
│   ├── translators/
│   │   ├── base.py
│   │   └── gemma.py
│   │
│   └── core/                    # Core business logic
│       ├── block_processor.py
│       ├── page_processor.py
│       ├── batch_processor.py   # NEW! Parallel processing
│       ├── project_processor.py
│       └── html_renderer.py
│
├── tests/                       # Unit tests
├── pyproject.toml
├── .env.example
└── .env
```

## 🚀 PHASE 1: Foundation - Configuration & Utilities

### Step 1: ✅ Cài pydantic-settings
```bash
uv pip install pydantic-settings
```

### Step 2: ✅ Tạo .env.example
File `.env.example` với đầy đủ config:
- PPDOCLAYOUT_PADDLE_OCR_SERVER_URL
- PPDOCLAYOUT_VLLM_BASE_URL
- PPDOCLAYOUT_VLLM_MAX_TOKENS
- PPDOCLAYOUT_VLLM_MODEL_NAME
- PPDOCLAYOUT_BATCH_SIZE_SMALL/MEDIUM/LARGE
- PPDOCLAYOUT_OUTPUT_DIR
- PPDOCLAYOUT_EXPORT_FORMATS

### Step 3: Tạo types.py
File `src/pp_doclayout/types.py` với:
- `TranslateAction = Literal["translate", "keep", "skip"]`
- `BlockLabel` với tất cả labels từ PaddleOCR-VL
- `Block`, `PageData`, `ProjectData` TypedDict classes

### Step 4: Tạo utils module
Directory `src/pp_doclayout/utils/` với:
- `__init__.py`
- `file_utils.py` - `find_image_file()`, `ensure_dir()`
- `path_utils.py` - `get_output_dir()`, `get_project_dir()`

### Step 5: Update config.py
Update `src/pp_doclayout/config.py` với Pydantic Settings:
- Use `BaseSettings`, `SettingsConfigDict`, `Field`
- Define tất cả config fields
- Use `env_prefix="PPDOCLAYOUT_"`

### Step 6: Test verification
```bash
# Test config
uv run python -c "from pp_doclayout.config import settings; print(settings)"

# Test utils
uv run python -c "from pp_doclayout.utils import find_image_file; print('OK')"
```

## 🚀 PHASE 2: Refactor Core Logic

### Step 1: Tạo BatchProcessor
File `src/pp_doclayout/core/batch_processor.py`:
- Class `BatchProcessor`
- Method `process_document()` - filter, group by length, batch translate
- Group blocks: small (<100 tokens), medium (100-500), large (>500)

### Step 2: Update GemmaTranslator
Thêm method `translate_batch()` vào `src/pp_doclayout/translators/gemma.py`:
- Accept list of texts
- Return list of translations
- Use vLLM's batch processing

## 🚀 PHASE 3-6: (chi tiết trong file plan)
- Phase 3: Templates & Exporters (Jinja2)
- Phase 4: Remove HY-MT & Simplify
- Phase 5: CLI Enhancements
- Phase 6: Testing Infrastructure

## 📌 Session hiện tại

- **Mode**: Learning mode - bạn tự code, tôi chỉ hướng dẫn
- **Phase đang làm**: Phase 1 - Foundation
- **Bước tiếp theo**: Step 3 - Tạo types.py

### Phase 1 Progress (2/6 steps)

| Step | Tên | Trạng thái |
|------|-----|-----------|
| 1 | Cài pydantic-settings | ✅ Done |
| 2 | Tạo .env.example | ✅ Done |
| 3 | Tạo types.py | ⏳ Next |
| 4 | Tạo utils module | ⏳ Pending |
| 5 | Update config.py | ⏳ Pending |
| 6 | Test verification | ⏳ Pending |

---
**Cập nhật lần cuối:** 2026-02-16
