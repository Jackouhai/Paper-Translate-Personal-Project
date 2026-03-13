# Planning - PP-DocLayout

> **Mục đích:** Tất cả plans của dự án (quá khứ, hiện tại, tương lai)

---

## 📌 Config máy

```
GPU: NVIDIA GeForce RTX 5060 Ti (16GB VRAM)
CPU: 16 cores
RAM: 31GB total, 19GB available
Python: 3.12.9
Package Manager: uv 0.8.18
OS: Linux 6.17.0-14-generic
```

---

## 📋 Vấn đề cần refactor

| Vấn đề | Mô tả | Priority |
|--------|---------|----------|
| Code duplication | `find_image_file()` xuất hiện 3 lần, HTML styles lặp lại | MEDIUM |
| Hardcoded values | Paths, URLs được hardcode (`/home/bocchi/...`) | MEDIUM |
| File quá lớn | `reconstructor.py` 403 lines, làm nhiều việc | HIGH |
| No templates | HTML được render bằng string concatenation | HIGH |
| No tests | Không có unit tests đủ | MEDIUM |
| **Batch processing KHÔNG tận dụng vLLM** | Gửi TẤT CÀ vào 1 request thay vì concurrent | **HIGH** |
| Duplicate `__all__` | core/__init__.py có 2 dòng __all__ (lines 4 & 6) | LOW |

---

## 🎯 Mục tiêu refactor

1. ✅ Tách code thành modules nhỏ, dễ quản lý
2. ✅ Dùng config file (.env) thay vì hardcode
3. 🔵 Dùng Jinja2 templates cho HTML (templates có, chưa dùng)
4. ✅ Thêm tests
5. 🔵 Thêm PDF export (beyond HTML)
6. 🔵 Xử lý song song nhiều projects

---

## 📁 Cấu trúc codebase sau refactor

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
│   │   ├── file_utils.py
│   │   └── path_utils.py
│   │
│   ├── templates/               # Jinja2 HTML templates ✅
│   │   ├── base.html
│   │   ├── page.html
│   │   ├── mathjax_config.html
│   │   └── styles.html
│   │
│   ├── policies/
│   │   └── translation_policy.py ✅
│   │
│   ├── exporters/               # Export handlers ✅
│   │   ├── base.py
│   │   ├── html.py
│   │   └── pdf.py (🔵)
│   │
│   ├── translators/
│   │   ├── base.py ✅
│   │   ├── gemma.py ✅
│   │   └── hymt.py (🔵)
│   │
│   └── core/                    # Core business logic
│       ├── batch_processor.py   ✅
│       ├── reconstructor.py     🔵 Need refactor
│       └── renderer.py         🔵 NEW - will be created
│
├── tests/                     # Unit tests ✅
├── docs/                      # Documentation ✅
│   ├── CLAUDE.md
│   ├── STATE.md
│   └── PLANNING.md
├── pyproject.toml
├── .env.example
└── .env
```

---

# ============================================
# PHASE 1: Foundation - DONE ✅
# ============================================

## ✅ Phase 1: Foundation - Configuration & Utilities

| Step | Tên | Trạng thái |
|------|-----|-----------|
| 1 | Cài pydantic-settings | ✅ Done |
| 2 | Tạo .env.example | ✅ Done |
| 3 | Tạo types.py | ✅ Done |
| 4 | Tạo utils module | ✅ Done |
| 5 | Update config.py | ✅ Done |
| 6 | Test verification | ✅ Done |

**Completion:** 100% ✅

---

# ============================================
# PHASE 2: Core Logic - DONE ✅
# ============================================

## ✅ Phase 2: Core Logic & Batch Processing

| Task | Trạng thái | Notes |
|------|-----------|------|
| BatchProcessor | ✅ Done | - |
| GemmaTranslator.translate_batch() | ✅ Done | Incorrect implementation (groups all texts into 1 request) |
| Translation Policy | ✅ Done | - |
| Utils (file_utils, path_utils) | ✅ Done | - |

**Completion:** 100% ✅

---

# ============================================
# PHASE 3: Templates & Exporters Integration - DONE ✅
# ============================================

## ✅ Phase 3: Templates & Exporters Integration

### Vấn đề (đã giải quyết)

- `reconstructor.py` sử dụng string concatenation thay vì Jinja2 templates
- Templates đã được tạo (base.html, page.html, styles.html, mathjax_config.html) nhưng chưa được sử dụng
- `HTMLExporter` đã được tạo nhưng chưa được dùng bởi CLI

### Tasks

| # | Task | Status | Priority | Date | Notes |
|---|-------|----------|----------|-------|-------|
| 1 | Fix duplicate `__all__` in core/__init__.py | ✅ Done | LOW | 2026-02-24 | Removed duplicate line 6 |
| 2 | Create renderer.py module | ✅ Done | HIGH | 2026-02-24 | New file with build_project_data, translate_page_data, render_page_blocks |
| 3 | Deprecate process_project() in reconstructor.py | ✅ Done | MEDIUM | 2026-02-24 | Added DeprecationWarning |

### Completed Items

| Item | Status | Date |
|------|--------|-------|
| Templates (base.html, page.html, styles.html, mathjax_config.html) | ✅ Done | 2026-02-20 |
| HTMLExporter with Jinja2 | ✅ Done | 2026-02-20 |
| renderer.py module (3 main functions) | ✅ Done | 2026-02-24 |
| Deprecation warning for process_project() | ✅ Done | 2026-02-24 |

### Implementation Details

#### Task 2: renderer.py module structure

```python
# src/pp_doclayout/core/renderer.py

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..policies.translation_policy import should_translate
from ..types import Block, PageData, ProjectData, BlockLabel

if TYPE_CHECKING:
    from ..translators.base import BaseTranslator

# Reuse constants from reconstructor.py
LABEL_TO_TAG = {...}
CENTERED_LABELS = frozenset({...})
VISUAL_LABELS = frozenset({...})
CAPTION_LABELS = frozenset({...})
REFERENCE_KEYWORDS = frozenset({...})

# Reuse functions from reconstructor.py
def group_blocks(blocks: list[dict]) -> list[dict]:
    """Figure grouping logic (lines 119-173 in reconstructor.py)"""
    ...

def render_figure_group(...) -> str:
    """Figure rendering (lines 216-264 in reconstructor.py)"""
    ...

def render_visual(...) -> str:
    """Visual rendering (lines 195-213 in reconstructor.py)"""
    ...

def find_image_file(...) -> str | None:
    """Image file detection (lines 44-57 in reconstructor.py)"""
    ...

def build_project_data(project_dir: Path) -> ProjectData:
    """Load JSON files and build ProjectData structure.

    Returns:
        ProjectData with pages list and project_name
    """
    ...

def translate_page_data(page: PageData, translator: BaseTranslator) -> PageData:
    """Translate blocks in a page.

    Returns:
        PageData with translated blocks
    """
    ...

def render_page_blocks(
    page: PageData,
    imgs_dir: Path,
    output_dir: Path,
    translator: BaseTranslator,
) -> str:
    """Render blocks to HTML (reuse grouping logic from reconstructor.py).

    Returns:
        HTML string for page blocks
    """
    ...
```

**Completion:** 100% ✅

---

# ============================================
# PHASE 4: CLI Integration - DONE ✅
# ============================================

## ✅ Phase 4: CLI Integration

### Vấn đề (đã giải quyết)

- `cli.py` sử dụng `process_project()` từ `reconstructor.py` (old style)
- Chưa sử dụng `build_project_data()` và `HTMLExporter`

### Tasks

| # | Task | Status | Priority | Date | Notes |
|---|-------|----------|----------|-------|-------|
| 4 | Update translate() command use renderer | ✅ Done | HIGH | 2026-02-27 | Replace process_project() with new pipeline |
| 5 | Update run() command use renderer | ✅ Done | HIGH | 2026-02-27 | Replace process_project() with new pipeline |
| 6 | Update core/__init__.py exports | ✅ Done | MEDIUM | 2026-02-27 | Add build_project_data, translate_page_data, render_page_blocks |

### Completed Items

| Item | Status | Date |
|------|--------|-------|
| CLI (parse, translate, run commands) | ✅ Done | 2026-02-27 |
| translate() command updated | ✅ Done | 2026-02-27 |
| run() command updated | ✅ Done | 2026-02-27 |
| core/__init__.py exports updated | ✅ Done | 2026-02-27 |

### Implementation Details

#### Task 4 & 5: Update CLI commands

**Before:**
```python
from pp_doclayout.core import process_project

def translate(project_dir, output_suffix="translated"):
    translator = get_gemma()
    output_path = process_project(
        Path(project_dir), translator=translator, output_suffix=output_suffix
    )
```

**After:**
```python
from pp_doclayout.core.renderer import build_project_data, translate_page_data, render_page_blocks
from pp_doclayout.exporters import HTMLExporter

def translate(project_dir, output_suffix="translated"):
    translator = get_gemma()

    # Build project data from JSON files
    project_dir = Path(project_dir)
    project_data = build_project_data(project_dir)

    # Translate all pages
    translated_pages = []
    for page in project_data["pages"]:
        translated_page = translate_page_data(page, translator)

        # Render page blocks to HTML
        imgs_dir = project_dir / "imgs"
        blocks_html = render_page_blocks(translated_page, imgs_dir, project_dir, translator)
        translated_page["html_content"] = blocks_html

        translated_pages.append(translated_page)

    project_data["pages"] = translated_pages

    # Export to HTML
    exporter = HTMLExporter()
    output_path = project_dir / f"{output_suffix}_{project_data['project_name']}.html"
    exporter.export(project_data, output_path)
```

**Completion:** 100% ✅

---

# ============================================
# PHASE 5: Batch Processing Rewrite - DONE ✅
# ============================================

## ✅ Phase 5: Batch Processing Rewrite (Concurrent Requests)

### Vấn đề hiện tại

```python
# SAI - Gửi TẤT CẢ vào 1 request
def translate_batch(self, texts, source_lang="en", target_lang="vi"):
    messages = [{
        "role": "user",
        "content": "\n".join(
            f"[{idx}] <<<source>>>{source_lang}<<<target>>>{target_lang}<<<text>>>{text}"
            for idx, (_, text) in enumerate(non_empty)
        ),
    }]

    response = self.client.chat.completions.create(
        model=self.model_name,
        messages=messages,
        max_tokens=self.max_tokens * len(non_empty),  # QUÁ LỚN!
        temperature=0,
    )
    # ... complex response parsing ...
```

**Vấn đề:**
1. ❌ Gemma model KHÔNG hiểu format phức tạp
2. ❌ Parsing response unreliable
3. ❌ **KHÔNG tận dụng vLLM's concurrent requests**
4. ❌ `max_tokens * len(non_empty)` quá lớn, có thể gây memory issues

### Cách làm ĐÚNG - ThreadPoolExecutor

```python
# ĐÚNG - Gửi N requests song song với ThreadPoolExecutor
from concurrent.futures import ThreadPoolExecutor, as_completed

def translate_batch(
    self,
    texts: list[str],
    source_lang: str = "en",
    target_lang: str = "vi",
) -> list[str | None]:
    """Translate multiple texts using concurrent requests.

    vLLM will automatically batch these requests via continuous batching.

    Args:
        texts: List of texts to translate
        source_lang: Source language code
        target_lang: Target language code

    Returns:
        List of translations (None if failed for a particular text)
    """
    if not texts:
        return []

    # Use ThreadPoolExecutor for concurrent requests
    max_workers = min(self.max_concurrent_requests, len(texts))
    results = [None] * len(texts)

    def translate_one(idx: int, text: str) -> tuple[int, str]:
        """Translate a single text."""
        translated = self.translate(text, source_lang, target_lang)
        return (idx, translated)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(translate_one, i, text): i
            for i, text in enumerate(texts)
            if text and text.strip()
        }

        for future in as_completed(futures):
            idx, translated = future.result()
            results[idx] = translated

    return results
```

**Lợi ích:**
- ✅ vLLM tự động handle continuous batching
- ✅ Không cần parse response phức tạp
- ✅ Mỗi request có `max_tokens` riêng (đúng value)
- ✅ Error handling tốt hơn per request
- ✅ Code đơn giản, dễ maintain

### Tasks

| # | Task | Status | Priority | Date | Notes |
|---|-------|----------|----------|-------|-------|
| 7 | Add max_concurrent_requests to config | ✅ Done | HIGH | 2026-02-27 | Default: 32 |
| 8 | Update GemmaTranslator.__init__ use config | ✅ Done | HIGH | 2026-02-27 | Add parameter |
| 9 | Rewrite translate_batch() use ThreadPoolExecutor | ✅ Done | HIGH | 2026-02-27 | Core refactor |

### Implementation Details

#### Task 7: Add to config

```python
# src/pp_doclayout/config.py

class Settings(BaseSettings):
    ...

    # ===== Concurrent Request Settings =====
    max_concurrent_requests: int = Field(
        default=32,
        description="Max concurrent translation requests"
    )
```

#### Task 8: Update GemmaTranslator.__init__

```python
# src/pp_doclayout/translators/gemma.py

class GemmaTranslator(BaseTranslator):
    def __init__(
        self,
        base_url: str | None = None,
        model_name: str | None = None,
        max_tokens: int | None = None,
        max_concurrent_requests: int | None = None,
    ):
        from ..config import settings

        self.base_url = base_url or settings.vllm_base_url
        self.model_name = model_name or settings.vllm_model_name
        self.max_tokens = max_tokens or settings.vllm_max_tokens
        self.max_concurrent_requests = max_concurrent_requests or settings.max_concurrent_requests

        self.client = OpenAI(base_url=self.base_url, api_key="unused")
```

**Completion:** 100% ✅

### Additional Fixes (2026-02-27 late evening)

After implementing Phase 5, discovered and fixed critical bugs:

| Issue | Description | Fix |
|--------|-------------|------|
| translate_page_data() not using translate_batch() | Was calling translate() per block (sequential) | Changed to collect all texts and call translate_batch() |
| Duplicate translation | render_page_blocks() was re-translating blocks | Removed translation logic from render functions |
| Incorrect function signatures | render functions still had translator parameter | Removed translator parameter and related logic |

**Files changed:**
- `src/pp_doclayout/core/renderer.py` - translate_page_data(), render_page_blocks(), _render_caption(), render_figure_group()
- `src/pp_doclayout/cli.py` - Updated calls to render_page_blocks()

**Result:** Now properly uses concurrent requests via ThreadPoolExecutor and vLLM's continuous batching

### Additional Fixes (2026-03-06)

| Issue | Description | Fix |
|--------|-------------|------|
| doc_title heading markers | doc_title content had "#" prefix like "# Title" | Strip "#" for doc_title and paragraph_title |
| LaTeX escaping in display_formula | Double backslashes `\\` causing MathJax to fail | Replace `\\` with `\` before rendering |
| Header/footer blocks in output | Blocks with SKIP labels still appeared in output | Added should_translate() check to skip blocks |
| vision_footnote in output | OCR error text appearing as standalone block | Added "vision_footnote" to SKIP_LABELS |
| Figure grouping wrong | 8 visuals with 1 caption not showing caption | Fixed render_figure_group() logic for 1 caption case |
| table_caption label | PaddleOCR-VL doesn't produce "table_caption" label | Removed "table_caption" from all code |

**Files changed:**
- `src/pp_doclayout/core/renderer.py` - Fixed heading markers, LaTeX escaping, skip check, figure grouping, removed table_caption
- `src/pp_doclayout/policies/translation_policy.py` - Added vision_footnote to SKIP_LABELS, removed table_caption
- `src/pp_doclayout/config.py` - Added 2 new PaddleOCR-VL config fields
- `src/pp_doclayout/cli.py` - Added all PaddleOCR-VL config to both parse and run
- `.env.example` - Added all new config options

### PaddleOCR-VL Config Options (2026-03-06)

| Config field | Default | Description |
|--------------|---------|-------------|
| `paddle_ocr_format_block_content` | True | Format block content (LaTeX, math, table) |
| `paddle_ocr_use_doc_unwarping` | True | Use document unwarping (deskew, straighten) |
| `paddle_ocr_use_chart_recognition` | True | Parse charts separately |
| `paddle_ocr_merge_layout_blocks` | True | Merge related layout blocks |
| `paddle_ocr_layout_detection_model_name` | "PP-DocLayoutV3" | Layout detection model name |
| `paddle_ocr_use_layout_detection` | True | Use layout detection |
| `paddle_use_ocr_for_image_block` | True | OCR for images |

All options are configurable via environment variables (prefix: `PPDOCLAYOUT_`) or `.env` file.

---

# ============================================
# PHASE 6: Additional Features - 🔵 PENDING
# ============================================

## 🔵 Phase 6: Additional Features

| Task | Status | Priority |
|------|--------|----------|
| HY-MT translator in new architecture | 🔵 Pending | LOW |
| PDF exporter | 🔵 Pending | LOW |
| Parallel project processing | 🔵 Pending | LOW |

**Completion:** 0%

---

## 📝 Notes

### Session 2026-02-20 - Refactor Plan Created
- Created comprehensive refactor plan with 3 phases (9 tasks total)
- Decided to use **ThreadPoolExecutor** for concurrent requests instead of asyncio
- Focus: Templates integration, CLI updates, and batch processing rewrite
- Task list created in session documentation (docs/CLAUDE.md)

### Earlier sessions
- 2026-02-20: Reorganize docs structure to 3 files only
- 2026-02-20: Identified batch processing issue
- 2026-02-20: Created Phase 5 for batch processing refactor (originally using asyncio, now changed to ThreadPoolExecutor)

---

## 🔗 Related

- **State tracking:** `STATE.md`
- **CLAUDE notes:** `CLAUDE.md`

---

**Last updated:** 2026-03-06
