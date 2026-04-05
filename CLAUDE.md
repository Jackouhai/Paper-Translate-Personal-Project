# PP-DocLayout - Claude Code Session

## 📋 Tổng quan dự án

**Mục tiêu:** Pipeline dịch thuật tài liệu học thuật (PDF) sang tiếng Việt

**Pipeline:**
```
PDF → [PaddleOCR-VL parse] → JSON + Images → [Gemma translate] → Vietnamese → [HTML render] → Final HTML
```

**Server cần chạy:**
- Gemma vLLM: `http://127.0.0.1:8001/v1` (port 8001)
- PaddleOCR-VL: `http://127.0.0.1:8000/v1` (port 8000)

---

## 🏗 Cấu trúc Code (src/pp_doclayout/)

| File/Dir | Mô tả |
|----------|-------|
| `__init__.py` | Package init (version, __all__) |
| `cli.py` | Typer CLI - 3 commands: parse, translate, run |
| `config.py` | Pydantic Settings (env: PPDOCLAYOUT_*) |
| `types.py` | TypedDict definitions |
| **core/** | |
| `renderer.py` | Build/translate/render page → HTML |
| **exporters/** | |
| `base.py` | Abstract BaseExporter |
| `html.py` | HTMLExporter (Jinja2 templates) |
| **policies/** | |
| `translation_policy.py` | should_translate() - translate/keep/skip rules |
| **templates/** | Jinja2 HTML templates |
| `base.html` | Main HTML structure |
| `page.html` | Single page template |
| `styles.html` | CSS styles |
| `mathjax_config.html` | MathJax config |
| `dynamic_font_size.html` | Dynamic font sizing |
| **translators/** | |
| `base.py` | Abstract BaseTranslator |
| `gemma.py` | GemmaTranslator (vLLM API) |
| **utils/** | File/path utilities |

**demo/** - Old scripts (có bugs, không khuyến khích dùng)

---

## 🖥 Frontend (frontend_project/)

React + TypeScript + Vite + Tailwind CSS v4

| File | Mô tả |
|------|-------|
| `src/App.tsx` | Main component - Landing + Workspace views |
| `src/main.tsx` | React entry point |
| `src/index.css` | Global styles (Tailwind) |
| `vite.config.ts` | Vite config (port 3000) |
| `package.json` | Dependencies (React 19, Motion, Lucide icons) |

**UI Features:**
- Landing page: drag & drop upload zone, animated hero
- Workspace: sidebar navigation, zoom controls, HTML/PDF view toggle
- Hiện tại dùng **mock data** (setTimeout simulation)
- Chưa có API calls thật

**Dependencies cần lưu ý:**
- `@google/genai` → **sẽ xóa** (không dùng)
- `lucide-react` → icons
- `motion` → animations

---

## ⚙️ Config (PPDOCLAYOUT_* env vars hoặc .env)

```bash
# vLLM/Gemma
PPDOCLAYOUT_VLLM_BASE_URL=http://127.0.0.1:8001/v1
PPDOCLAYOUT_VLLM_MODEL_NAME=Infomaniak-AI/vllm-translategemma-4b-it
PPDOCLAYOUT_VLLM_MAX_TOKENS=16384
PPDOCLAYOUT_MAX_CONCURRENT_REQUESTS=32

# PaddleOCR-VL
PPDOCLAYOUT_PADDLE_OCR_SERVER_URL=http://127.0.0.1:8000/v1
PPDOCLAYOUT_PADDLE_OCR_BACKEND=vllm-server

# Batch Processing
PPDOCLAYOUT_BATCH_SIZE_SMALL=16   # < 100 tokens
PPDOCLAYOUT_BATCH_SIZE_MEDIUM=8   # 100-500 tokens
PPDOCLAYOUT_BATCH_SIZE_LARGE=4    # > 500 tokens

# Paths
PPDOCLAYOUT_OUTPUT_DIR=output
```

---

## 📝 Translation Policy

| Action | Labels |
|--------|--------|
| **translate** | `abstract`, `text`, `figure_title`, `table_caption` |
| **keep** | `doc_title`, `paragraph_title`, `reference_content`, `footnote`, `display_formula`, `table`, `image` |
| **skip** | `aside_text`, `header`, `footer`, `number`, `content` |

**Special cases:**
- `text` < 6 words, no `@` → keep
- `text` contains `@` (email) → keep
- `paragraph_title` = "contents" → skip
- In reference section: `text` → keep

---

## 🚀 CLI Usage

```bash
# Parse PDF (PaddleOCR-VL)
uv run -m pp_doclayout.cli parse <pdf_path>

# Translate JSON → HTML
uv run -m pp_doclayout.cli translate <output_dir>

# Full pipeline: parse + translate
uv run -m pp_doclayout.cli run <pdf_path>
```

---

## ✅ REFACTOR PROGRESS (2026-04-05)

| # | Task | Status | Date | Notes |
|---|------|--------|------|-------|
| 1 | Fix circular import (translators/__init__.py) | ✅ Done | 2026-04-05 | Removed `settings` from exports |
| 2 | BatchProcessor not used | ✅ Done | 2026-04-05 | Xóa batch_processor.py, giữ nguyên translate_batch() vì vLLM continuous batching đã tối ưu |
| 3 | Duplicate find_image_file | ✅ Done | 2026-04-05 | renderer.py import từ utils; fix absolute imports trong utils |
| 4 | Hardcoded page dimensions | ✅ Skip | 2026-04-05 | Low priority, JSON ưu tiên, fallback là defensive |
| 5 | Missing __all__ in root | ✅ Done | 2026-04-05 | Thêm __all__ = ["__version__"] |
| 6 | pyproject.toml empty dependencies | ⏸ Pending | - | User tạm hoãn |

---

## 🔴 Issues còn lại

| # | Issue | Priority | Notes |
|---|-------|----------|-------|
| 6 | pyproject.toml empty dependencies | High | User tạm hoãn |

---

## 📌 Architecture Notes

### translate_batch() flow
```
translate_page_data()
    │
    └── translator.translate_batch([texts])
              │
              └── ThreadPoolExecutor(max_workers=32)
                        │
                        └── Gửi N requests đồng thời đến vLLM
                                  │
                                  └── vLLM continuous batching tự động
```

### Translation decisions
- vLLM continuous batching hoạt động tự động khi có nhiều requests đồng thời
- BatchProcessor không cần thiết vì translate_batch() đã gửi 1 request/text
- 1 request = 1 block text → vLLM batch được tự nhiên

---

## 📌 Learning Mode

**Mode:** User codes, tôi kiểm tra

### Quy tắc:
1. Tôi chỉ gợi ý + hướng dẫn, **KHÔNG** tự code
2. User tự code theo hướng dẫn
3. Xong → báo tôi kiểm tra
4. Q&A: hỏi bất kỳ lúc nào

### Verify Commands:
```bash
python -c "from src.pp_doclayout.core.renderer import *; print('OK')"
python -c "from src.pp_doclayout import *; print('OK')"
```

---

## 🔍 Verify Commands

```bash
# Core module
python -c "from src.pp_doclayout.core.renderer import *; print('OK')"

# Full package
python -c "from src.pp_doclayout import *; print('OK')"

# CLI
python -c "from src.pp_doclayout.cli import *; print('OK')"
```

---

## 📦 Dependencies (cần install thủ công)

```bash
# Core (GPU)
uv pip install paddlepaddle-gpu paddleocr paddleocrvl openai vllm

# Project
uv pip install typer pydantic-settings jinja2 tiktoken

# API Layer (cho frontend integration)
uv pip install fastapi uvicorn[standard] python-multipart

# Dev
uv pip install pytest
```

---

## 🌐 Frontend Integration Plan (PLAN.md)

**Mục tiêu:** Thêm web UI → upload PDF, theo dõi tiến trình, xem kết quả dịch

**Architecture:**
```
Browser (React:3000) ──proxy──> FastAPI (:5000) ──> PaddleOCR-VL (:8000)
                                        │                + Gemma vLLM (:8001)
                                        │
                                   background task (parse + translate)
```

**8 bước implementation:**
1. API skeleton (`api.py` + health check)
2. Upload endpoint (POST /api/documents/upload)
3. Background processing + Status endpoint
4. Result + file serving
5. Frontend API client (`api.ts`)
6. Frontend upload flow (real file upload)
7. Frontend progress + result viewer
8. Production build (1 server)

**Chi tiết đầy đủ:** xem `PLAN.md`

---

## 📌 Learning Mode

**Mode:** User codes, tôi kiểm tra

### Quy tắc:
1. Tôi chỉ gợi ý + hướng dẫn, **KHÔNG** tự code
2. User tự code theo hướng dẫn
3. Xong → báo tôi kiểm tra
4. Q&A: hỏi bất kỳ lúc nào

---

**Cập nhật:** 2026-04-05
