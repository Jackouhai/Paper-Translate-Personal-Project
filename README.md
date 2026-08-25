# PP-DocLayout

Academic PDF translation pipeline — English to Vietnamese, preserving original layout.

[README.vi.md (Tiếng Việt)](README.vi.md)

---

## Key Features

- **Layout Analysis** — detect titles, abstracts, text, tables, figures, formulas
- **OCR** — extract text, tables to HTML, formulas to LaTeX
- **Translation** — TranslateGemma 4B running locally on GPU via vLLM
- **Smart Policy** — preserve titles, references, formulas; only translate main content
- **HTML Output** — absolute positioning, MathJax formula rendering
- **PDF Export** — headless Chrome rendering via Playwright
- **Browser Demo** — upload, processing status, and side-by-side PDF review

## Quick Start

> **Requirements:** Linux | NVIDIA GPU | Python 3.10+ | [uv](https://docs.astral.sh/uv/)
>
> **VRAM:** ~4-8GB step-by-step. The local Docker profile lets PP-DocLayoutV3
> use `gpu:0` when Paddle detects CUDA. The VPS profile keeps it on CPU to
> reserve VRAM for the two vLLM servers.

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

# 4. Copy the example environment file
cp .env.example .env

# If Playwright-managed Chromium is unavailable, install Google Chrome:
# wget -q -O /tmp/google-chrome.deb "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
# sudo apt install /tmp/google-chrome.deb
#
# Then configure PP-DocLayout to use the system Chrome channel:
# echo "PPDOCLAYOUT_PLAYWRIGHT_BROWSER_CHANNEL=chrome" >> .env

# 5. Start PaddleOCR-VL server (Terminal 1, port 8000)
scripts/start_paddle_ocr_vl.sh

# 6. Start TranslateGemma server (Terminal 2, port 8001)
scripts/start_translate_gemma.sh

# 7. Verify both servers (Terminal 3)
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models

# 8. Run
uv run -m pp_doclayout.cli run paper.pdf
```

If PaddlePaddle verification fails, fix Paddle/CUDA before running `parse` or `run`.

The default command exports both `output/paper/translated_paper.html` and
`output/paper/translated_paper.pdf`.

Section titles (`paragraph_title`) remain in their source language by default.
Enable their translation explicitly when needed:

```bash
uv run -m pp_doclayout.cli run paper.pdf --translate-titles
```

PDF export uses Playwright-managed Chromium by default. To use a
system-installed browser instead, set a Playwright browser channel in `.env`:

```env
PPDOCLAYOUT_PLAYWRIGHT_BROWSER_CHANNEL=chrome
```

The PDF print stylesheet maps each parsed HTML page to one PDF page and removes
screen-only margins and shadows during export.

## Docker Demo Deployment

Use Docker when demonstrating on another Linux machine, or on Windows through
Docker Desktop with WSL2 and NVIDIA GPU support. Docker packages Python, CUDA
runtime, vLLM, PaddleOCR, and Playwright; the target machine does not need a
local `uv` environment.

Before building, verify that Docker can access the host GPU:

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04 nvidia-smi
```

Build the images, start the two model servers and Parse API, wait for `healthy`, then run the
pipeline. The first server start downloads model weights into a Docker volume.

```bash
docker compose build
docker compose up -d paddle-ocr-vl translate-gemma parse-api
docker compose ps
docker compose run --rm pipeline run input/PhoMT.pdf
```

`input/` and `output/` remain on the host machine. On 12GB or less, run the two
stages separately and stop the first model before starting the
second:

```bash
docker compose up -d paddle-ocr-vl parse-api
docker compose run --rm --no-deps pipeline parse input/PhoMT.pdf
docker compose stop parse-api paddle-ocr-vl

docker compose up -d translate-gemma
docker compose run --rm --no-deps pipeline translate output/<parse-output-dir>
docker compose stop translate-gemma
```

Stop containers while retaining downloaded weights:

```bash
docker compose down
```

### Browser demo

Start the one-page review interface at <http://localhost:3000>:

```bash
docker compose up -d paddle-ocr-vl translate-gemma parse-api web-api web-frontend
```

The left column uploads a PDF and selects all pages or one page. The source PDF
appears in the middle immediately; after translation, the translated PDF is
shown in the right column. The shared zoom control applies to both documents.
The "Dịch tiêu đề mục" switch is off by default and matches the CLI option.

The parse stage is serialized to keep the DocLayout model stable. By default,
one job translates at a time and sends at most four requests to TranslateGemma;
this is the configuration selected from the real-workload benchmark. Set
`WEB_DEMO_TRANSLATION_WORKERS` and `WEB_DEMO_MAX_CONCURRENT_REQUESTS` in the
Compose environment to tune these limits, but their product should not exceed
four for a single GPU.

For a short public demonstration, start the optional Cloudflare Quick Tunnel:

```bash
docker compose --profile tunnel up -d cloudflared
docker compose logs -f cloudflared
```

On a 12 GB VPS, use `./scripts/start_vps_demo.sh` to build and start the same
services sequentially, with TranslateGemma ready before PaddleOCR-VL loads.

Share the `https://...trycloudflare.com` URL printed in the logs. It changes
when the tunnel restarts and is public, so stop it when the presentation ends.
See [docker/README.md](docker/README.md) for the complete deployment guide.

If a Quick Tunnel URL does not resolve, restart only `cloudflared` to receive a
new URL without stopping or reloading either GPU model:

```bash
docker compose --env-file .env.vps --profile tunnel stop cloudflared
docker compose --env-file .env.vps --profile tunnel up -d cloudflared
docker compose --env-file .env.vps logs -f cloudflared
```

If Docker reports `failed to set up container networking` with `network ... not
found`, the stopped tunnel container references a network removed by an earlier
`docker compose down`. Recreate only that container; do not restart the GPU
services:

```bash
# Local Docker profile
docker compose --profile tunnel rm -f cloudflared
docker compose --profile tunnel up -d cloudflared

# VPS profile
docker compose --env-file .env.vps --profile tunnel rm -f cloudflared
docker compose --env-file .env.vps --profile tunnel up -d cloudflared
```

The current Docker configuration targets a modern NVIDIA GPU. It has been
built and smoke-tested on the development machine; RTX 3060 12 GB needs a
separate reduced-memory profile before it is a supported demo target. A typical
8 GB RTX 4060 should be used for parsing/rendering or as a client to a remote
translation server. Quadro P3200 is not supported by the current vLLM/CUDA
stack. See [docker/README.md](docker/README.md) for the full deployment guide.

---

## Usage

> Recommended: run step-by-step (`parse` then `translate`). On low VRAM machines, stop the PaddleOCR-VL server after parsing to free VRAM for TranslateGemma.

### Start model servers

Open three terminals:

```bash
# Terminal 1: OCR/layout server
scripts/start_paddle_ocr_vl.sh

# Terminal 2: translation server
scripts/start_translate_gemma.sh

# Terminal 3: persistent DocLayout worker and Parse API
scripts/start_parse_api.sh
```

Then verify both OpenAI-compatible model endpoints:

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
curl http://127.0.0.1:8082/health
```

`parse` and `run` submit their parse stage to the Parse API. If it is missing,
they exit with a command to start `scripts/start_parse_api.sh`. `translate`
still checks its TranslateGemma server directly.

By default, local PaddleOCR helper models such as `PP-DocLayoutV3` use:

```env
PPDOCLAYOUT_PADDLE_OCR_CLIENT_DEVICE=auto
```

`auto` selects `gpu:0` when Paddle detects a usable CUDA GPU, otherwise `cpu`.
You can force a device by setting this value to `cpu` or `gpu:0` in `.env`.

### Long-lived Parse API

For multiple parse requests, start the API once instead of invoking the CLI
per request. It loads the local `PP-DocLayoutV3` helper model once, queues PDF
jobs in FIFO order, and keeps that model in VRAM until the API stops.

Only use one Uvicorn worker. Multiple Uvicorn workers are separate Python
processes and each would load another copy of the local layout model.

```bash
# PaddleOCR-VL server on port 8000 must already be running.
scripts/start_parse_api.sh

# Equivalent CLI command
uv run -m pp_doclayout.cli serve
```

Submit a PDF, then poll its job ID:

```bash
curl -F "file=@input/PhoMT.pdf" http://127.0.0.1:8082/parse
curl http://127.0.0.1:8082/jobs/<job_id>
```

The API returns `queued`, `running`, `completed`, or `failed`. Existing CLI
commands keep their syntax, but `parse` output is now placed under
`output/<filename>-<job-id>/` so concurrent uploads with the same filename
cannot overwrite each other. Do not use `--reload` for a stable demo because a
reload recreates the model worker.

### Step 1: Parse PDF

Needs the Parse API (port 8082), whose long-lived worker requires
PaddleOCR-VL server (port 8000).

```bash
uv run -m pp_doclayout.cli parse <file.pdf>

# Custom output directory
uv run -m pp_doclayout.cli parse <file.pdf> -o ./output
```

Output is saved to `output/<filename>-<job-id>/` (the CLI prints the exact
path):
- `*_res.json` — parsing results (coordinates + content per block)
- `*_res.md` — markdown output
- `imgs/` — cropped images

### Step 2: Translate

Needs TranslateGemma server (port 8001).

```bash
# HTML and PDF output (default)
uv run -m pp_doclayout.cli translate output/<parse-output-dir>

# Export only PDF
uv run -m pp_doclayout.cli translate output/<parse-output-dir> -f pdf

# Custom output suffix
uv run -m pp_doclayout.cli translate output/<parse-output-dir> --suffix vi
```

Output by default: `<parse-output-dir>/translated_<filename>.html` and `.pdf`

### Full Pipeline

Parse + translate in one command. Requires Parse API and TranslateGemma; the
Parse API itself requires PaddleOCR-VL.

```bash
# HTML and PDF output (default)
uv run -m pp_doclayout.cli run <file.pdf>

# Export only PDF
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
| **TranslateGemma** | 4B (vLLM FP8 configuration) | 8001 | English → Vietnamese translation |

### Verify servers

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
```

### Benchmark with real PDF blocks

Create JSONL from the blocks the pipeline actually translates. The script uses
the same translation policy, `<<<custom>>>` prompt, and output limit as
`GemmaTranslator`.

```bash
uv run scripts/build_translation_benchmark_dataset.py \
  output/PhoMT output/2306.00978v6 \
  --output bench_data/translation_blocks.jsonl \
  --max-samples 100
```

With the TranslateGemma server running, benchmark it from the vLLM environment:

```bash
cd services/llm-server
UV_CACHE_DIR="$PWD/.uv-cache" uv run --no-sync vllm bench serve \
  --backend openai \
  --base-url http://127.0.0.1:8001 \
  --endpoint /v1/completions \
  --model Infomaniak-AI/vllm-translategemma-4b-it \
  --dataset-name custom \
  --dataset-path ../../bench_data/translation_blocks.jsonl \
  --no-oversample \
  --num-prompts 100 \
  --max-concurrency 4 \
  --num-warmups 3 \
  --temperature 0 \
  --save-result --save-detailed \
  --result-dir ../../logs/vllm-bench-real
```

Do not use `--skip-chat-template`: the benchmark must wrap the user content
with TranslateGemma's template. Do not use `--ignore-eos`: the model should
finish each translation naturally, as it does in the pipeline.

## Translation Policy

| Action | Labels | Description |
|--------|--------|-------------|
| **Translate** | `abstract`, `text`, `figure_title` | Main content |
| **Keep** | `doc_title`, `paragraph_title`, `reference_content`, `footnote`, `display_formula`, `table`, `image`, `chart`, `formula_number`, `number` | Titles, references, formulas, page numbers |
| **Skip** | `aside_text`, `header`, `footer`, `content` | Noise blocks |

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
    ├── paddle_device.py        # Resolve PaddleOCR helper model device
    ├── path_utils.py
    └── server_health.py        # Check OpenAI-compatible model servers
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
