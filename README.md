# PP-DocLayout

Academic PDF translation pipeline — English to Vietnamese, preserving original layout.

[README.md (Tiếng Việt)](README.vi.md)

---

## Key Features

- **Layout Analysis** — detect titles, abstracts, text, tables, figures, formulas
- **OCR** — extract text, tables to HTML, formulas to LaTeX
- **Translation** — TranslateGemma 4B running locally on GPU via vLLM
- **Smart Policy** — preserve titles, references, formulas; only translate main content
- **HTML Output** — absolute positioning, MathJax formula rendering
- **PDF Export** — headless Chrome rendering via Playwright

## Quick Start

> **Requirements:** Linux | NVIDIA GPU | Python 3.10+ | [uv](https://docs.astral.sh/uv/)
>
> **VRAM:** ~4-8GB step-by-step, ~16GB for full pipeline (both servers at once)

### PaddlePaddle Wheel

Before installing, check the GPU and compute capability:

```bash
nvidia-smi
python3 -c "import subprocess; print(subprocess.check_output(['nvidia-smi', '--query-gpu=name,compute_cap', '--format=csv,noheader'], text=True))"
```

PaddlePaddle GPU requires compute capability greater than 7.5. If your GPU does not meet this requirement, use another NVIDIA GPU/CUDA machine before running the local pipeline.

`pyproject.toml` defaults to `cu130`. Change the PaddlePaddle index before `uv sync` if your machine needs another wheel:

| CUDA wheel | PaddlePaddle index URL |
|------------|-------------------------|
| CUDA 13.0 | `https://www.paddlepaddle.org.cn/packages/stable/cu130/` |
| CUDA 12.9 | `https://www.paddlepaddle.org.cn/packages/stable/cu129/` |
| CUDA 12.6 | `https://www.paddlepaddle.org.cn/packages/stable/cu126/` |
| CUDA 11.8 | `https://www.paddlepaddle.org.cn/packages/stable/cu118/` |

```bash
# 1. Install
git clone <repo_url> && cd Paper-Translate-Personal-Project
uv sync
uv pip install -e .

# 2. Verify PaddlePaddle
uv run python scripts/check_paddle_env.py

# 3. Install a browser for Playwright PDF export
uv run playwright install chromium

# If Playwright-managed Chromium is unavailable, install Google Chrome:
# wget -q -O /tmp/google-chrome.deb "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
# sudo apt install /tmp/google-chrome.deb
#
# Then configure PP-DocLayout to use the system Chrome channel:
# cp .env.example .env
# echo "PPDOCLAYOUT_PLAYWRIGHT_BROWSER_CHANNEL=chrome" >> .env

# 4. Start PaddleOCR-VL server (Terminal 1, port 8000)
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

# 5. Start TranslateGemma server (Terminal 2, port 8001)
vllm serve Infomaniak-AI/vllm-translategemma-4b-it \
    --dtype bfloat16 \
    --quantization bitsandbytes \
    --load-format bitsandbytes \
    --max-model-len 32768 \
    --max-num-seqs 15 \
    --max-num-batched-tokens 8192 \
    --gpu-memory-utilization 0.5 \
    --kv-cache-dtype fp8 \
    --enforce-eager \
    --port 8001

# 6. Run
uv run -m pp_doclayout.cli run paper.pdf
```

If PaddlePaddle verification fails, fix Paddle/CUDA before running `parse` or `run`.

Output: `output/paper/translated_paper.html`

```bash
# Export as PDF instead
uv run -m pp_doclayout.cli run paper.pdf -f pdf

# Or translate existing parsed data to PDF
uv run -m pp_doclayout.cli translate output/paper -f pdf
```

Output: `output/paper/translated_paper.pdf`

PDF export uses Playwright-managed Chromium by default. To use a
system-installed browser instead, set a Playwright browser channel in `.env`:

```env
PPDOCLAYOUT_PLAYWRIGHT_BROWSER_CHANNEL=chrome
```

The PDF print stylesheet maps each parsed HTML page to one PDF page and removes
screen-only margins and shadows during export.

---

## Usage

> Recommended: run step-by-step (`parse` then `translate`). On low VRAM machines, stop the PaddleOCR-VL server after parsing to free VRAM for TranslateGemma.

### Step 1: Parse PDF

Only needs PaddleOCR-VL server (port 8000).

```bash
uv run -m pp_doclayout.cli parse <file.pdf>

# Custom output directory
uv run -m pp_doclayout.cli parse <file.pdf> -o ./output
```

Output saved to `output/<filename>/`:
- `*_res.json` — parsing results (coordinates + content per block)
- `*_res.md` — markdown output
- `imgs/` — cropped images

### Step 2: Translate

Needs TranslateGemma server (port 8001).

```bash
# HTML output (default)
uv run -m pp_doclayout.cli translate output/<filename>

# PDF output
uv run -m pp_doclayout.cli translate output/<filename> -f pdf

# Custom output suffix
uv run -m pp_doclayout.cli translate output/<filename> --suffix vi
```

Output: `output/<filename>/translated_<filename>.html` or `.pdf`

### Full Pipeline

Parse + translate in one command. Requires both servers running.

```bash
# HTML output (default)
uv run -m pp_doclayout.cli run <file.pdf>

# PDF output
uv run -m pp_doclayout.cli run <file.pdf> -f pdf
```

### View result

```bash
xdg-open output/<filename>/translated_<filename>.html   # HTML
xdg-open output/<filename>/translated_<filename>.pdf    # PDF
```

## Models

The pipeline uses 2 models, each on a separate vLLM server:

| Model | Size | Port | Purpose |
|-------|------|------|---------|
| **PaddleOCR-VL** | 0.9B | 8000 | Layout analysis, OCR, crop images |
| **TranslateGemma** | 4B (bitsandbytes quantized) | 8001 | English → Vietnamese translation |

### Verify servers

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
```

## Translation Policy

| Action | Labels | Description |
|--------|--------|-------------|
| **Translate** | `abstract`, `text`, `figure_title` | Main content |
| **Keep** | `doc_title`, `paragraph_title`, `reference_content`, `footnote`, `display_formula`, `table`, `image`, `chart`, `formula_number` | Titles, references, formulas |
| **Skip** | `aside_text`, `header`, `footer`, `number` | Noise, page numbers |

## Project Structure

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
│   └── translation_policy.py   # Translate/keep/skip logic
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
- Reduce `--max-model-len` or `--gpu-memory-utilization` in vLLM command
- Reduce `--max-num-seqs` to lower batch size
- Run step-by-step instead of `run` to only need 1 server at a time

**ModuleNotFoundError:**
```bash
uv pip install -e .
```

**Servers not connecting:**
```bash
nvidia-smi
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
```

## License

MIT License
