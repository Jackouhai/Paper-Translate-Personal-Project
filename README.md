# PP-DocLayout: Phân tích & Dịch thuật Tài liệu Khoa học

Dự án này cung cấp một quy trình khép kín để xử lý các tệp PDF học thuật, bao gồm: phân tích bố cục (Layout Analysis), nhận dạng ký tự (OCR), dịch thuật nội dung bằng LLM (Google TranslateGemma), và tái cấu trúc thành file HTML chuyên nghiệp giữ nguyên định dạng gốc.

## 🚀 Tính năng chính
- **Layout Analysis**: Nhận diện chính xác Tiêu đề, Abstract, Văn bản, Bảng biểu, Hình ảnh, Công thức.
- **OCR chuyên sâu**: Trích xuất nội dung bảng dưới dạng HTML và công thức dưới dạng LaTeX.
- **Dịch thuật thông minh**: Tích hợp mô hình LLM chuyên dụng dịch thuật (TranslateGemma 4B) chạy cục bộ trên GPU.
- **Translation Guard**: Logic bảo vệ thông minh - giữ nguyên Tiêu đề gốc, Tài liệu tham khảo, và Tên tác giả để đảm bảo tính chuyên nghiệp.
- **Reconstruction**: Tái tạo tài liệu dưới dạng HTML chuẩn SEO, hỗ trợ render công thức bằng MathJax.
- **CLI Tool**: Command-line interface dễ sử dụng với 3 commands: `parse`, `translate`, `run`.

## 💻 Tech Stack

### Core Framework
- **Python 3.10+** - Ngôn ngữ chính
- **uv** - Package manager siêu tốc

### Machine Learning & AI
- **vLLM** - High-throughput LLM inference engine
- **PaddlePaddle** - Deep learning framework cho OCR
- **PaddleOCR-VL** - Vision Language Model cho layout analysis
- **transformers** - Hugging Face model hub
- **tiktoken** - Token counting & estimation
- **sentencepiece** - Tokenizer cho Gemma models
- **bitsandbytes** - 8-bit quantization optimization
- **accelerate** - Distributed training/inference
- **protobuf** - Serialization cho model communication

### Web & Templates
- **Jinja2** - Modern template engine cho HTML rendering
- **MathJax** - Render công thức toán học LaTeX trong browser

### Configuration & CLI
- **Pydantic** - Type-safe data validation & settings management
- **Typer** - Modern CLI framework với auto-completion
- **python-dotenv** - Environment variables management

### GPU Acceleration
- **CUDA 12.8** - NVIDIA GPU support

---

## 🤖 AI Models

### 1. PaddleOCR-VL (Layout Analysis & OCR)
- **Model**: `PaddlePaddle/PaddleOCR-VL-1.5`
- **Served name**: `PaddleOCR-VL-1.5-0.9B`
- **Parameters**: ~0.9B
- **Function**:
  - Layout analysis (title, abstract, text, tables, images, formulas)
  - OCR cho text và tables
  - Table content extraction sang HTML
  - Formula extraction sang LaTeX
- **Server config**:
  - Port: 8000
  - GPU memory: 60% (~9.6GB)
  - Max model length: 32K tokens
  - Max sequences: 3
  - Dtype: bfloat16

### 2. TranslateGemma (Translation)
- **Model**: `Infomaniak-AI/vllm-translategemma-4b-it`
- **Parameters**: 4B
- **Function**:
  - English → Vietnamese translation
  - Batch processing với ThreadPoolExecutor
  - Context-aware translation
- **Server config**:
  - Port: 8001
  - GPU memory: 90% (~14.4GB)
  - Max model length: 32K tokens
  - Max sequences: 16
  - Dtype: bfloat16

### Resource Requirements (Combined)
- **Total GPU VRAM**: 16GB (NVIDIA RTX series)
- **GPU Memory Allocation**:
  - PaddleOCR-VL: ~9.6GB (60%)
  - TranslateGemma: ~14.4GB (90%)
- **Note**: Chạy 2 servers song song trên cùng GPU với memory sharing

---

## 📊 Pipeline Workflow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              PP-DocLayout Pipeline                               │
└─────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│      INPUT PDF       │
│   (Academic Paper)   │
└──────────┬───────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              STEP 1: PARSE                                       │
│                              (PaddleOCR-VL)                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  1. Layout Analysis                                                            │
│     - Detect titles, abstract, text, tables, images, formulas                  │
│     - Assign labels to each block                                               │
│                                                                                 │
│  2. OCR Processing                                                              │
│     - Extract text content                                                      │
│     - Table content → HTML                                                      │
│     - Formulas → LaTeX                                                          │
│     - Crop visual elements (images, charts, tables)                             │
│                                                                                 │
│  3. Save Output                                                                 │
│     ├─ *_res.json      (Parsing results with coordinates & content)           │
│     ├─ *_res.md        (Markdown output)                                       │
│     └─ imgs/           (Cropped images: {x1}_{y1}_{x2}_{y2}.jpg)              │
└─────────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          STEP 2: BUILD PROJECT DATA                            │
│                          (renderer.py)                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  • Load all *_res.json files                                                    │
│  • Sort by page number                                                          │
│  • Build ProjectData structure:                                                │
│    {                                                                             │
│      "project_name": "<filename>",                                             │
│      "pages": [                                                                 │
│        {                                                                        │
│          "width": 1224,                                                         │
│          "height": 1584,                                                        │
│          "parsing_res_list": [...]                                             │
│        },                                                                        │
│        ...                                                                       │
│      ]                                                                           │
│    }                                                                             │
└─────────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         STEP 3: TRANSLATE                                       │
│                         (TranslateGemma + Translation Policy)                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  For each page:                                                                 │
│                                                                                 │
│  1. Translation Policy Filter                                                  │
│     ┌──────────────────────────────────────────────────────────────────────┐  │
│     │  TRANSLATE  │  KEEP  │  SKIP                                          │  │
│     ├──────────────────────────────────────────────────────────────────────┤  │
│     │  abstract   │ doc_title     │ aside_text                            │  │
│     │  text       │ paragraph_title│ header                                │  │
│     │  figure_title│ reference_content │ footer                             │  │
│     │             │ footnote      │ number                                │  │
│     │             │ display_formula │                                      │  │
│     │             │ table         │                                      │  │
│     │             │ image         │                                      │  │
│     │             │ chart         │                                      │  │
│     │             │ formula_number│                                      │  │
│     └──────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  2. Special Cases                                                              │
│     • paragraph_title with "contents" → SKIP                                  │
│     • text < 6 words and no @ → KEEP                                          │
│     • text contains @ (email) → KEEP                                          │
│     • In reference section: text → reference_content → KEEP                   │
│                                                                                 │
│  3. Batch Translation (ThreadPoolExecutor)                                      │
│     • Group blocks by token count:                                             │
│       - Small (<100 tokens)   → batch size: 16                                │
│       - Medium (100-500)     → batch size: 8                                 │
│       - Large (>500 tokens)   → batch size: 4                                 │
│     • Translate batches concurrently with Gemma                               │
│     • Update block_content with translations                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          STEP 4: RENDER HTML                                   │
│                          (renderer.py)                                          │
├─────────────────────────────────────────────────────────────────────────────────┤
│  For each page:                                                                 │
│                                                                                 │
│  1. Sort blocks by block_id (maintain reading order)                           │
│                                                                                 │
│  2. Build HTML blocks with absolute positioning:                               │
│     ┌──────────────────────────────────────────────────────────────────────┐  │
│     │ <div class="block {label} auto-fit"                                  │  │
│     │      style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;">          │  │
│     │   {content}                                                          │  │
│     │ </div>                                                               │  │
│     └──────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  3. Visual blocks (image, chart, table):                                       │
│     • Image/Chart: <img src="imgs/{bbox}.jpg">                                │
│     • Table: <div class="table-container">{HTML table}</div>                   │
│                                                                                 │
│  4. Wrap in page container:                                                    │
│     ┌──────────────────────────────────────────────────────────────────────┐  │
│     │ <div class="page-container">                                       │  │
│     │   <div class="page" style="width:1224px;height:1584px;">             │  │
│     │     {all blocks}                                                    │  │
│     │   </div>                                                            │  │
│     │ </div>                                                              │  │
│     └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      STEP 5: EXPORT TO HTML                                     │
│                      (HTMLExporter + Jinja2)                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  1. Use Jinja2 Templates:                                                       │
│     • base.html          - HTML structure, MathJax config, CSS                 │
│     • page.html          - Page content template                              │
│     • styles.html        - CSS styles for positioning & formatting             │
│     • mathjax_config.html - MathJax configuration for LaTeX rendering         │
│                                                                                 │
│  2. Template Structure:                                                         │
│     ┌──────────────────────────────────────────────────────────────────────┐  │
│     │ <!DOCTYPE html>                                                      │  │
│     │ <html>                                                               │  │
│     │   <head>                                                             │  │
│     │     <title>{project_name}</title>                                    │  │
│     │     {MathJax config}                                                 │  │
│     │     {CSS styles}                                                     │  │
│     │   </head>                                                            │  │
│     │   <body>                                                             │  │
│     │     {page_html for each page}                                        │  │
│     │   </body>                                                            │  │
│     │ </html>                                                              │  │
│     └──────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  3. Save final HTML:                                                            │
│     output/{project_name}/translated_{project_name}.html                      │
└─────────────────────────────────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────┐
│      OUTPUT HTML      │
│  • SEO-friendly       │
│  • MathJax formulas   │
│  • Absolute positioning│
│  • Original layout    │
└──────────────────────┘

═══════════════════════════════════════════════════════════════════════════════════════

                            FULL PIPELINE (run command)

    PDF → Parse → Build → Translate → Render → Export → HTML
         (Step 1)  (Step 2) (Step 3)     (Step 4) (Step 5)

                            STEP-BY-STEP OPTIONS

    Option 1: parse        PDF → Parse → JSON/MD/Images
    Option 2: translate    JSON → Build → Translate → Render → Export → HTML
```

---

## 🛠 Yêu cầu hệ thống
- **OS**: Linux (Khuyên dùng)
- **GPU**: NVIDIA RTX với **16GB VRAM** (cho PaddleOCR-VL + Gemma song song)
- **Môi trường**: Python 3.10+, CUDA 12.8
- **Công cụ quản lý**: `uv` (Khuyên dùng)

## 📦 Cài đặt

### 1. Cài đặt dependencies
```bash
uv pip install transformers accelerate bitsandbytes sentencepiece protobuf paddlepaddle-gpu paddleocr paddleocrvl jinja2 tiktoken
```

### 2. Cấu hình (tùy chọn)
Tạo file `.env` để override config mặc định:
```bash
cp .env.example .env
# Chỉnh sửa các giá trị trong .env nếu cần
```

## 🚀 Khởi động vLLM Servers

Trước khi chạy, cần khởi động 2 vLLM servers:

### Terminal 1 - PaddleOCR-VL Server (Port 8000)
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

### Terminal 2 - Gemma Server (Port 8001)
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

### Kiểm tra servers
```bash
# Kiểm tra Gemma server
curl http://127.0.0.1:8001/v1/models

# Kiểm tra PaddleOCR server
curl http://127.0.0.1:8000/v1/models
```

## 📖 Hướng dẫn sử dụng (CLI)

### ⚠️ QUAN TRỌNG: Sử dụng CLI mới

**Lưu ý:** Các script cũ trong folder `demo/` là script thử nghiệm nhanh:

| Script | Trạng thái | Vấn đề |
|--------|-----------|--------|
| `render_project.py` | ❌ BUG | Dịch cả doc_title, paragraph_title, display_formula, v.v. |
| `vp2_render_project.py` | ❌ BUG | Dịch cả doc_title, paragraph_title, display_formula, v.v. |
| `reconstruct_gemma.py` | ⚠️ Old style | Logic đúng nhưng dùng API cũ |
| `reconstruct_multi.py` | ⚠️ Old style | Logic đúng nhưng dùng HY-MT (không dùng nữa) |

**Vui lòng sử dụng CLI mới với translation policy chính xác:**
```bash
uv run -m pp_doclayout.cli <command>
```

### Option 1: Full Pipeline (Parse + Translate)
Quy trình hoàn tất trong 1 command:
```bash
uv run -m pp_doclayout.cli run <path_to_pdf>

# Ví dụ:
uv run -m pp_doclayout.cli run /path/to/paper.pdf
```

### Option 2: Từng bước

#### Bước 1: Phân tích PDF (Parse)
```bash
uv run -m pp_doclayout.cli parse <path_to_pdf>

# Với output tùy chỉnh:
uv run -m pp_doclayout.cli parse <path_to_pdf> --output-dir /custom/output
```

Kết quả sẽ được lưu vào `output/<tên_file>/`:
- `*_res.json` - Parsing results (tọa độ + nội dung)
- `*_res.md` - Markdown output
- `imgs/` - Cropped images

#### Bước 2: Dịch thuật (Translate)
```bash
uv run -m pp_doclayout.cli translate <output_dir>

# Với hậu tố file tùy chỉnh:
uv run -m pp_doclayout.cli translate <output_dir> --suffix translated

# Ví dụ:
uv run -m pp_doclayout.cli translate output/my_paper
```

Kết quả: `output/my_paper/translated_my_paper.html`

### Bước 3: Xem kết quả
Mở file HTML bằng trình duyệt:
```bash
xdg-open output/my_paper/translated_my_paper.html
```

## 🧠 Logic Dịch thuật (Translation Policy)

Để giữ tính học thuật, hệ thống được cấu hình:

| Action | Labels | Mô tả |
|--------|--------|-------|
| **Dịch** | `abstract`, `text`, `figure_title`, | Nội dung chính |
| **Giữ nguyên** | `doc_title`, `paragraph_title`, `reference_content`, `footnote`, `display_formula`, `table`, `image`, `chart`, `formula_number` | Tiêu đề, references, công thức |
| **Loại bỏ** | `aside_text`, `header`, `footer`, `number` | Nhiễu, số trang |

**Special cases:**
- `paragraph_title` chứa "contents" → bỏ qua
- `text` < 6 từ và không có @ → giữ nguyên
- `text` chứa @ (email) → giữ nguyên
- Trong reference section: `text` → `reference_content` → giữ nguyên

## 📁 Cấu trúc Project

```
PP_DocLayout/
├── src/pp_doclayout/
│   ├── __init__.py
│   ├── cli.py                   # CLI commands (parse, translate, run)
│   ├── config.py                # Configuration (Pydantic Settings)
│   ├── types.py                 # Type definitions
│   │
│   ├── utils/                   # Utility functions
│   │   ├── file_utils.py
│   │   └── path_utils.py
│   │
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── base.html
│   │   ├── page.html
│   │   ├── mathjax_config.html
│   │   └── styles.html
│   │
│   ├── policies/
│   │   └── translation_policy.py # Logic dịch/giữ/skip blocks
│   │
│   ├── exporters/               # Export handlers
│   │   ├── base.py
│   │   └── html.py            # HTMLExporter với Jinja2
│   │
│   ├── translators/             # Translator implementations
│   │   ├── base.py
│   │   └── gemma.py            # Google TranslateGemma (với translate_batch())
│   │
│   └── core/                    # Core business logic
│       ├── batch_processor.py   # Batch processing logic
│       ├── reconstructor.py     # HTML rendering & reconstruction (old style)
│       └── renderer.py         # New renderer (build, translate, render)
│
├── tests/                      # Unit tests
├── demo/                       # Experimental scripts (old style, not recommended)
│   ├── render_project.py        # Old renderer (has translation bugs)
│   ├── vp2_render_project.py   # Old renderer (has translation bugs)
│   ├── reconstruct_gemma.py     # Old translation script
│   ├── reconstruct_multi.py     # Old translation script (HY-MT)
│   ├── server_manager.py        # Server management tool
│   └── start_server.sh         # Start vLLM servers script
├── docs/                       # Documentation
│   ├── CLAUDE.md
│   ├── STATE.md
│   └── PLANNING.md
├── pyproject.toml
├── .env.example
└── README.md
```

## 🔧 Cấu hình (Environment Variables)

Các config có thể thay đổi qua `.env` file (prefix `PPDOCLAYOUT_`):

| Variable | Mặc định | Mô tả |
|----------|---------|-------|
| `PPDOCLAYOUT_ENGINE` | `gemma` | Engine dịch thuật |
| `PPDOCLAYOUT_VLLM_BASE_URL` | `http://127.0.0.1:8001/v1` | vLLM server URL (Gemma) |
| `PPDOCLAYOUT_VLLM_MAX_TOKENS` | `16384` | Max tokens per request |
| `PPDOCLAYOUT_VLLM_MODEL_NAME` | `Infomaniak-AI/vllm-translategemma-4b-it` | Model name |
| `PPDOCLAYOUT_PADDLE_OCR_SERVER_URL` | `http://127.0.0.1:8000/v1` | PaddleOCR server URL |
| `PPDOCLAYOUT_OUTPUT_DIR` | `output` | Output directory |

## 🐛 Troubleshooting

### Servers không chạy được
- Kiểm tra GPU memory: `nvidia-smi`
- Giảm `gpu-memory-utilization` nếu thiếu VRAM
- Đảm bảo đã cài `vllm`: `uv pip install vllm`

### Out of Memory (OOM)
- Giảm `max-model-len` trong vLLM server command
- Giảm `max-num-seqs` để giảm batch size

### Lỗi import
- Reinstall dependencies: `uv pip install -e .`
- Kiểm tra Python version: `python --version` (cần 3.10+)

## 📝 License
MIT License

## 🤝 Contributing
Pull requests are welcome!

---

**Last updated:** 2026-02-27
