# PP-DocLayout - Ghi chú cho session tiếp theo

## 📋 Tổng quan dự án
Pipeline dịch thuật tài liệu học thuật sang tiếng Việt với quy trình khép kín:
1. **Parse PDF** (Layout Analysis + OCR) → JSON + images
2. **Translate** (Gemma) → Vietnamese
3. **Reconstruct** → HTML với MathJax

## 🏗 Cấu trúc codebase hiện tại

### Scripts cũ (đã có, vẫn hoạt động)
```
main.py                  - Parse PDF bằng PaddleOCR-VL (hardcoded paths)
reconstruct_gemma.py     - Dịch + HTML với Gemma model (old style)
reconstruct_multi.py     - Dịch + HTML với HY-MT model (old style)
translator_engine.py     - Old translator wrapper (Tencent HY-MT)
translator_engine_gemma.py - Old translator wrapper (Gemma)
base.py                  - Base class từ PaddleX
paddleocr_vl.py          - Wrapper PaddleOCR-VL
server_manager.py        - Quản lý 2 servers với model switching
start_server.sh          - Script khởi động 2 servers
```

### Source code chính (src/pp_doclayout/) - Architecture mới (đã refactor)
```
__init__.py              - Version 0.1.0
cli.py                   - Typer CLI với 3 commands: parse, translate, run
config.py                - Configuration (Pydantic Settings) ✅
types.py                 - Type definitions (TypedDict) ✅

utils/                   # Utility functions ✅
  ├─ __init__.py
  ├─ file_utils.py        - find_image_file(), ensure_dir()
  └─ path_utils.py        - get_output_dir(), get_project_dir()

templates/               # Jinja2 HTML templates ✅
  ├─ base.html           - Base HTML structure
  ├─ page.html           - Single page template
  ├─ styles.html         - CSS styles
  └─ mathjax_config.html - MathJax config

policies/
  ├─ __init__.py
  └─ translation_policy.py - Logic dịch/giữ/skip blocks ✅

exporters/               # Export handlers ✅
  ├─ __init__.py
  ├─ base.py             - Abstract Base Exporter
  └─ html.py            - HTMLExporter với Jinja2

translators/             # Translator implementations ✅
  ├─ __init__.py
  ├─ base.py             - Abstract Base Translator
  └─ gemma.py            - Google TranslateGemma (với translate_batch())

core/                    # Core business logic
  ├─ __init__.py         - Export process_project, BatchProcessor
  ├─ batch_processor.py   - Batch processing logic ✅
  └─ reconstructor.py    - HTML rendering & reconstruction (old style)
```

### Tests ✅
```
tests/
  ├─ test_config.py
  ├─ test_types.py
  ├─ test_utils.py
  ├─ test_batch_processor.py
  └─ test_exporters.py
```

### File cấu hình ✅
```
pyproject.toml            - Project metadata (version 0.1.0)
.env.example              - Environment variables mẫu
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

### Server Manager CLI
```bash
# Quản lý servers
python demo/server_manager.py start-paddle    # Start PaddleOCR-VL
python demo/server_manager.py start-gemma     # Start Gemma
python demo/server_manager.py stop-paddle     # Stop PaddleOCR-VL
python demo/server_manager.py stop-gemma      # Stop Gemma
python demo/server_manager.py stop-all        # Stop cả 2
python demo/server_manager.py switch paddle   # Switch sang PaddleOCR-VL
python demo/server_manager.py switch gemma    # Switch sang Gemma
python demo/server_manager.py status         # Xem status

# Tự động switch model khi chạy full pipeline
# (CLI tự động switch server khi cần)
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
# Engine Settings
engine: str = "gemma"

# vLLM/Gemma Server Settings
vllm_base_url: str = "http://127.0.0.1:8001/v1"
vllm_max_tokens: int = 16384
vllm_model_name: str = "Infomaniak-AI/vllm-translategemma-4b-it"

# PaddleOCR-VL Server Settings
paddle_ocr_server_url: str = "http://127.0.0.1:8000/v1"
paddle_ocr_backend: str = "vllm-server"

# Batch Processing Settings
batch_size_small: int = 16   # < 100 tokens
batch_size_medium: int = 8   # 100-500 tokens
batch_size_large: int = 4    # > 500 tokens

# Path Settings
output_dir: str = "output"

# Export Settings
export_formats: list[str] = ["html", "pdf"]
```

Có thể thay đổi qua env vars (prefix `PPDOCLAYOUT_`) hoặc `.env` file.

## 📝 Translation Policy

| Action | Labels | Mô tả |
|--------|--------|-------|
| **translate** | `abstract`, `text`, `figure_title`, `table_caption` | Nội dung chính |
| **keep** | `doc_title`, `paragraph_title`, `reference_content`, `footnote`, `vision_footnote`, `display_formula`, `table`, `image`, `chart`, `formula_number` | Tiêu đề, references, công thức |
| **skip** | `aside_text`, `header`, `footer`, `number`, `content`, `paragraph_title` (when "contents") | Nhiễu, số trang, table of contents |

**Special cases:**
- `paragraph_title` with "contents" → skip
- `text` < 6 words and no @ → keep
- `text` contains @ (email) → keep
- In reference section: `text` → `reference_content` → keep

## 📦 Dependencies chính

- `paddlepaddle-gpu` + `paddleocr` + `paddleocrvl` - OCR
- `vllm` - Inference engine
- `openai` - API client cho vLLM
- `typer` - CLI framework
- `pydantic-settings` - Configuration
- `jinja2` - Template engine
- `tiktoken` - Token estimation

Cài đặt:
```bash
uv pip install transformers accelerate bitsandbytes sentencepiece protobuf paddlepaddle-gpu paddleocr paddleocrvl jinja2 tiktoken
```

## 📂 Output

Tất cả kết quả lưu trong `output/<pdf_name>/`:
- JSON files: `*_res.json` - parsing results
- Markdown: `*_res.md` - parsed markdown
- Images: `imgs/` - cropped images
- HTML: `translated_<project_name>.html` - final result

## 🔍 Status hiện tại

- Git repo: Branch `refactor-1`, multiple commits
- Python version: 3.12.9
- Virtual environment: `.venv/` (đã cài dependencies)
- Refactor Progress: Phase 1 ✅, Phase 2 ✅, Phase 3 ✅, Phase 4 ✅, Phase 5 ✅, Phase 6 🔵 (3 tasks, 0% done)
- Overall Progress: 86% (19/22 tasks complete)

---

# 🎯 REFACTOR PROGRESS (Session 2026-02-20)

## 📌 Config máy của bạn
```
GPU: NVIDIA GeForce RTX 5060 Ti (16GB VRAM)
CPU: 16 cores
RAM: 31GB total, 19GB available
Python: 3.12.9
Package Manager: uv 0.8.18
OS: Linux 6.17.0-14-generic
```

## ✅ Phase 1: Foundation - Configuration & Utilities (DONE)

| Step | Tên | Trạng thái |
|------|-----|-----------|
| 1 | Cài pydantic-settings | ✅ Done |
| 2 | Tạo .env.example | ✅ Done |
| 3 | Tạo types.py | ✅ Done |
| 4 | Tạo utils module | ✅ Done |
| 5 | Update config.py | ✅ Done |
| 6 | Test verification | ✅ Done |

## ✅ Phase 2: Refactor Core Logic (DONE)

| Item | Trạng thái |
|------|-----------|
| BatchProcessor | ✅ Done |
| GemmaTranslator.translate_batch() | ✅ Done (incorrect implementation) |
| Translation Policy | ✅ Done |
| Utils (file_utils, path_utils) | ✅ Done |

## ✅ Phase 3: Templates & Exporters Integration (DONE)

| Item | Status | Date |
|------|--------|-------|
| Templates (base.html, page.html, styles.html, mathjax_config.html) | ✅ Done | 2026-02-20 |
| HTMLExporter with Jinja2 | ✅ Done | 2026-02-20 |
| renderer.py module | ✅ Done | 2026-02-24 |
| Deprecate process_project() | ✅ Done | 2026-02-24 |

## ✅ Phase 4: CLI Integration (DONE)

| Item | Status | Date |
|------|--------|-------|
| CLI (parse, translate, run commands) | ✅ Done | 2026-02-27 |
| translate() command updated | ✅ Done | 2026-02-27 |
| run() command updated | ✅ Done | 2026-02-27 |
| core/__init__.py exports updated | ✅ Done | 2026-02-27 |

## ✅ Phase 5: Batch Processing Rewrite (DONE)

**Approach:** ThreadPoolExecutor instead of asyncio (vLLM handles continuous batching automatically)

| Item | Status | Date |
|------|--------|-------|
| max_concurrent_requests config added | ✅ Done | 2026-02-27 |
| GemmaTranslator.__init__ updated | ✅ Done | 2026-02-27 |
| translate_batch() rewritten with ThreadPoolExecutor | ✅ Done | 2026-02-27 |
| Fixed duplicate translation bug | ✅ Done | 2026-02-27 |

## 🔵 Phase 6: Additional Features (PENDING)

| Task | Description | Status | Priority |
|------|-------------|--------|----------|
| Clean up old scripts | Remove legacy scripts in root directory | 🔵 Pending | MEDIUM |
| PDF exporter | Export to PDF format | 🔵 Pending | LOW |
| Improve documentation | Update docs for Phase 1-5 | 🔵 Pending | LOW |

## 📝 Tất cả issues đã giải quyết ✅

Tất cả các vấn đề trong Phase 3-5 đã được giải quyết:
- ✅ Templates đang được sử dụng
- ✅ CLI đang dùng renderer và HTMLExporter
- ✅ translate_batch() đang dùng ThreadPoolExecutor
- ✅ Không có duplicate translation bug

## 📌 Session hiện tại

- **Mode**: Learning mode
  - **Bạn tự code** theo hướng dẫn/gợi ý của tôi
  - Tôi **chỉ kiểm tra** lại sau khi bạn code xong
  - Không auto-write code, chỉ gợi ý và review

### Phase Progress Summary

| Phase | Status | Completion |
|-------|--------|------------|
| Phase 1: Foundation | ✅ Done | 100% |
| Phase 2: Core Logic | ✅ Done | 100% |
| Phase 3: Templates & Exporters Integration | ✅ Done | 100% |
| Phase 4: CLI Integration | ✅ Done | 100% |
| Phase 5: Batch Processing Rewrite | ✅ Done | 100% |
| Phase 6: Additional Features | 🔵 Pending | 0% (3 tasks) |

### Next Steps (Session 2026-03-16)

**Phase 6 Tasks:**

1. **Clean up old scripts** (MEDIUM) - Remove legacy scripts in root directory
2. **PDF exporter** (LOW) - Export to PDF format
3. **Improve documentation** (LOW) - Update docs for Phase 1-5 ✅

**See full details in:** `docs/CLAUDE.md`, `docs/PLANNING.md`, `docs/STATE.md`

---
**Cập nhật lần cuối:** 2026-03-16 (Phase 6 Updated)
