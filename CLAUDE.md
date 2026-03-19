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
demo_app.py             - Streamlit demo app
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
python server_manager.py start-paddle    # Start PaddleOCR-VL
python server_manager.py start-gemma     # Start Gemma
python server_manager.py stop-paddle     # Stop PaddleOCR-VL
python server_manager.py stop-gemma      # Stop Gemma
python server_manager.py stop-all        # Stop cả 2
python server_manager.py switch paddle   # Switch sang PaddleOCR-VL
python server_manager.py switch gemma    # Switch sang Gemma
python server_manager.py status         # Xem status

# Tự động switch model khi chạy full pipeline
# (CLI tự động switch server khi cần)
```

### Streamlit Demo App
```bash
uv run streamlit run demo_app.py
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

- Git repo: Branch `refactor-1`, 2 commits
- Python version: 3.12.9
- Virtual environment: `.venv/` (đã cài dependencies)
- Refactor Progress: Phase 1 ✅, Phase 2 ✅, Phase 3 ⏸ (templates có nhưng chưa dùng), Phase 4 ⏸ (CLI dùng old style), Phase 5 ⏸ (batch processing refactor)

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

## 🔵 Phase 3: Templates & Exporters Integration (PENDING - 9 Tasks Total)

**Tasks:**
1. Fix duplicate `__all__` in core/__init__.py
2. Create renderer.py module (build_project_data, translate_page_data, render_page_blocks)
3. Deprecate process_project() in reconstructor.py

**Completed Items:**
| Item | Status | Date |
|------|--------|-------|
| Templates (base.html, page.html, styles.html, mathjax_config.html) | ✅ Done | 2026-02-20 |
| HTMLExporter with Jinja2 | ✅ Done | 2026-02-20 |

## 🔵 Phase 4: CLI Integration (PENDING)

**Tasks:**
4. Update translate() command use renderer
5. Update run() command use renderer
6. Update core/__init__.py exports

**Completed Items:**
| Item | Status |
|------|--------|
| CLI (parse, translate, run commands) | ✅ Done (uses old reconstructor) |

## 🔵 Phase 5: Batch Processing Rewrite - Concurrent Requests (PENDING)

**Approach:** ThreadPoolExecutor instead of asyncio (vLLM handles continuous batching automatically)

**Tasks:**
7. Add max_concurrent_requests to config (default: 32)
8. Update GemmaTranslator.__init__ use config
9. Rewrite translate_batch() use ThreadPoolExecutor

**Current Issues:**
- translate_batch() groups all texts into one request (incorrect)
- Complex response parsing is unreliable
- Does NOT utilize vLLM's concurrent requests
- max_tokens * len(non_empty) is too large

## 📝 Vấn đề còn lại

| Vấn đề | Mô tả | Priority | Phase |
|--------|---------|----------|-------|
| Duplicate `__all__` in core/__init__.py | Lines 4 & 6 duplicate | LOW | Phase 3 |
| reconstructor.py uses string concatenation | Not Jinja2 templates | HIGH | Phase 3 |
| Templates created but not used | base.html, page.html not called | HIGH | Phase 3 |
| CLI doesn't use HTMLExporter | Still uses process_project() | HIGH | Phase 4 |
| translate_batch() sends all in 1 request | Should be concurrent requests | HIGH | Phase 5 |
| Complex response parsing | Unreliable parsing | HIGH | Phase 5 |

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
| Phase 3: Templates & Exporters Integration | 🔵 Pending | 40% (2/5 items done, 3 tasks pending) |
| Phase 4: CLI Integration | 🔵 Pending | 33% (1/3 items done, 2 tasks pending) |
| Phase 5: Batch Processing Rewrite | 🔵 Pending | 0% (3 tasks pending) |
| Phase 6: Additional Features | 🔵 Pending | 0% |

### Next Steps (Session 2026-02-20 Refactor Plan)

**Bắt đầu từ đơn giản nhất:**

1. **Task #1** (Phase 3): Fix duplicate `__all__` in `core/__init__.py` - 2 lines change
2. **Task #2** (Phase 3): Create `renderer.py` module with build_project_data, translate_page_data, render_page_blocks
3. **Task #3** (Phase 3): Deprecate process_project() in reconstructor.py
4. **Task #4** (Phase 4): Update translate() command use renderer
5. **Task #5** (Phase 4): Update run() command use renderer
6. **Task #6** (Phase 4): Update core/__init__.py exports
7. **Task #7** (Phase 5): Add max_concurrent_requests to config
8. **Task #8** (Phase 5): Update GemmaTranslator.__init__ use config
9. **Task #9** (Phase 5): Rewrite translate_batch() use ThreadPoolExecutor

**See full details in:** `docs/CLAUDE.md`, `docs/PLANNING.md`, `docs/STATE.md`

---
**Cập nhật lần cuối:** 2026-02-20 (Refactor Plan Created)
