# CLAUDE - Session Notes

> **Mục đích:** Ghi chú cho session làm việc hiện tại

---

## 📌 Session Info

### Mode
**Learning Mode**
- Bạn tự code theo hướng dẫn/gợi ý của tôi
- Tôi chỉ kiểm tra lại sau khi bạn code xong
- Không auto-write code, chỉ gợi ý và review

### Session: 2026-02-20 - Refactor Plan Implementation

**Focus:** Hoàn thành refactor pipeline:
1. **Phase 3**: Templates & Exporters Integration (Jinja2)
2. **Phase 4**: CLI Integration (sử dụng HTMLExporter)
3. **Phase 5**: Batch Processing Rewrite (concurrent requests)

**Approach mới cho Phase 5:**
- Sử dụng `ThreadPoolExecutor` thay vì `asyncio`
- vLLM tự động handle continuous batching
- Mỗi request = 1 translation task

---

## 📋 Quick Links

### Documentation (3 files chính)
- [Planning](./PLANNING.md) - Tất cả plans (quá khứ → hiện tại → tương lai)
- [State](./STATE.md) - Tất cả progress tracking
- [CLAUDE (this file)](./CLAUDE.md) - Ghi chú session hiện tại

### Root files
- [Root CLAUDE.md](../CLAUDE.md) - Tổng quan dự án

---

## 🎯 Task Queue - Refactor Plan

### Phase 3: Templates & Exporters Integration

| # | Task | Status | Owner | File thay đổi | Date |
|---|-------|--------|---------------|-------|-------|
| 1 | Fix duplicate `__all__` in core/__init__.py | ✅ Done | User | `src/pp_doclayout/core/__init__.py` | 2026-02-24 |
| 2 | Create renderer.py module (build_project_data, translate_page_data, render_page_blocks) | ✅ Done | User | `src/pp_doclayout/core/renderer.py` (NEW) | 2026-02-24 |
| 3 | Deprecate process_project() in reconstructor.py | ✅ Done | User | `src/pp_doclayout/core/reconstructor.py` | 2026-02-24 |

### Phase 4: CLI Integration

| # | Task | Status | Owner | File thay đổi | Date |
|---|-------|--------|---------------|-------|-------|
| 4 | Update translate() command use renderer | ✅ Done | User | `src/pp_doclayout/cli.py` | 2026-02-27 |
| 5 | Update run() command use renderer | ✅ Done | User | `src/pp_doclayout/cli.py` | 2026-02-27 |
| 6 | Update core/__init__.py exports | ✅ Done | User | `src/pp_doclayout/core/__init__.py` | 2026-02-27 |

### Phase 5: Batch Processing Rewrite (Concurrent Requests)

| # | Task | Status | Owner | File thay đổi | Date |
|---|-------|--------|---------------|-------|-------|
| 7 | Add max_concurrent_requests to config | ✅ Done | User | `src/pp_doclayout/config.py` | 2026-02-27 |
| 8 | Update GemmaTranslator.__init__ use config | ✅ Done | User | `src/pp_doclayout/translators/gemma.py` | 2026-02-27 |
| 9 | Rewrite translate_batch() use ThreadPoolExecutor | ✅ Done | User | `src/pp_doclayout/translators/gemma.py` | 2026-02-27 |
| 10 | Fix translate_page_data() use translate_batch() | ✅ Done | User | `src/pp_doclayout/core/renderer.py` | 2026-02-27 |
| 11 | Remove duplicate translation from render_page_blocks() | ✅ Done | User | `src/pp_doclayout/core/renderer.py`, `src/pp_doclayout/cli.py` | 2026-02-27 |

---

## ⚙ Commands

### Test translate
```bash
# Parse PDF
uv run -m pp_doclayout.cli parse <path_to_pdf>

# Translate project
uv run -m pp_doclayout.cli translate <output_dir>

# Full pipeline
uv run -m pp_doclayout.cli run <path_to_pdf>
```

### Run tests
```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test files
uv run pytest tests/test_batch_processor.py -v
uv run pytest tests/test_exporters.py -v
```

### Check vLLM server
```bash
# Gemma server (port 8001)
curl http://127.0.0.1:8001/v1/models

# PaddleOCR server (port 8000)
curl http://127.0.0.1:8000/v1/models
```

---

## 📝 Development Notes

### Phase 3 - renderer.py module structure

```python
# src/pp_doclayout/core/renderer.py

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..policies.translation_policy import should_translate

# Reuse constants and functions from reconstructor.py
LABEL_TO_TAG = {...}
CENTERED_LABELS = frozenset({...})
VISUAL_LABELS = frozenset({...})
CAPTION_LABELS = frozenset({...})
REFERENCE_KEYWORDS = frozenset({...})

def group_blocks(blocks: list[dict]) -> list[dict]:
    """Reuse from reconstructor.py (lines 119-173)"""
    ...

def render_figure_group(...) -> str:
    """Reuse from reconstructor.py (lines 216-264)"""
    ...

def render_visual(...) -> str:
    """Reuse from reconstructor.py (lines 195-213)"""
    ...

def find_image_file(...) -> str | None:
    """Reuse from reconstructor.py (lines 44-57)"""
    ...

def build_project_data(project_dir: Path) -> ProjectData:
    """Load JSON files and build ProjectData structure."""
    ...

def translate_page_data(page: PageData, translator: BaseTranslator) -> PageData:
    """Translate blocks in a page."""
    ...

def render_page_blocks(
    page: PageData,
    imgs_dir: Path,
    output_dir: Path,
    translator: BaseTranslator,
) -> str:
    """Render blocks to HTML (reuse grouping logic)."""
    ...
```

### Phase 5 - ThreadPoolExecutor approach

**Vấn đề hiện tại:**
```python
# SAI - Gửi TẤT CẢ vào 1 request
messages = [{
    "role": "user",
    "content": "\n".join(
        f"[{idx}] <<<source>>>en<<<target>>>vi<<<text>>>{text}"
        for idx, (_, text) in enumerate(non_empty)
    )
}]
```

**Cách làm đúng (ThreadPoolExecutor):**
```python
# ĐÚNG - Gửi N requests song song với ThreadPoolExecutor
from concurrent.futures import ThreadPoolExecutor, as_completed

def translate_batch(self, texts, source_lang="en", target_lang="vi"):
    max_workers = min(self.max_concurrent_requests, len(texts))
    results = [None] * len(texts)

    def translate_one(idx, text):
        return (idx, self.translate(text, source_lang, target_lang))

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
- vLLM tự động handle continuous batching
- Không cần parse response phức tạp
- Mỗi request có max_tokens riêng
- Error handling tốt hơn per request

---

## ✅ Checklist trước khi hoàn thành task

Khi hoàn thành 1 task:
1. [ ] Task hoàn thành theo plan
2. [ ] Update [STATE.md](./STATE.md) - đánh ✅ task tương ứng
3. [ ] Tests passing (nếu có)
4. [ ] Code review (tôi sẽ giúp)

---

## 📞 Workflow

1. **Chọn task** từ Task Queue ở trên (bắt đầu từ Task #1 - đơn giản nhất)
2. **Làm task** - bạn code theo hướng dẫn
3. **Xong task** → update STATE.md
4. **Tiếp task tiếp** hoặc nghỉ

---

## 🔗 Session History

### 2026-02-27 (late evening)
- **Fixed duplicate translation bug!** Removed translation from render functions:
  - Task #10: Fixed translate_page_data() to use translate_batch() (was using translate() per block)
  - Task #11: Removed duplicate translation from render_page_blocks(), _render_caption(), render_figure_group()
  - Updated CLI to not pass translator to render functions

### 2026-02-27 (evening)
- **Phase 5 Completed!** All 3 tasks done:
  - Task #7: Added max_concurrent_requests to config (default: 32)
  - Task #8: Updated GemmaTranslator.__init__ use config
  - Task #9: Rewrote translate_batch() use ThreadPoolExecutor

### 2026-02-27 (morning)
- **Phase 4 Completed!** All 3 tasks done:
  - Task #4: Updated translate() command to use renderer and HTMLExporter
  - Task #5: Updated run() command to use renderer and HTMLExporter
  - Task #6: Updated core/__init__.py exports with renderer functions

### 2026-02-24
- **Phase 3 Completed!** All 3 tasks done:
  - Task #1: Fixed duplicate `__all__` in core/__init__.py
  - Task #2: Created renderer.py module with 3 main functions
  - Task #3: Added deprecation warning to process_project()

### 2026-02-20
- Đã tạo comprehensive refactor plan với 3 phases
- Quyết định sử dụng ThreadPoolExecutor thay vì asyncio cho concurrent requests
- Tạo 9 tasks cụ thể cần làm
- Chưa bắt đầu implement tasks (đợi user code)

---

**Session started:** 2026-02-20
**Last updated:** 2026-02-27
