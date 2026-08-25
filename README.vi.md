# PP-DocLayout

Pipeline dịch tài liệu học thuật PDF sang tiếng Việt, giữ nguyên layout gốc.

[README.md (English)](README.md)

---

## Key Features

- **Layout Analysis** — nhận diện tiêu đề, abstract, text, bảng, hình, công thức
- **OCR** — trích xuất text, bảng sang HTML, công thức sang LaTeX
- **Dịch thuật** — TranslateGemma 4B chạy locally trên GPU qua vLLM
- **Translation Policy** — giữ nguyên tiêu đề, references, công thức, chỉ dịch nội dung chính
- **HTML Output** — absolute positioning, MathJax render công thức
- **PDF Export** — xuất PDF qua headless Chrome (Playwright)
- **Browser Demo** — upload, theo dõi xử lý, và so sánh PDF song song

## Quick Start

> **Yêu cầu:** Linux | NVIDIA GPU | Python 3.10+ | [uv](https://docs.astral.sh/uv/)
>
> **VRAM:** ~4-8GB khi chạy từng bước. Docker profile local cho phép
> PP-DocLayoutV3 dùng `gpu:0` khi Paddle nhận CUDA. Profile VPS giữ model này ở
> CPU để dành VRAM cho hai vLLM server.

### PaddlePaddle Wheel

Trước khi cài, kiểm tra GPU và compute capability:

```bash
nvidia-smi
python3 -c "import subprocess; print(subprocess.check_output(['nvidia-smi', '--query-gpu=name,compute_cap', '--format=csv,noheader'], text=True))"
```

PaddlePaddle GPU yêu cầu compute capability lớn hơn 7.5. Nếu GPU không đạt yêu cầu này, cần dùng máy NVIDIA GPU/CUDA phù hợp khác trước khi chạy local pipeline.

`pyproject.toml` mặc định dùng `cu130`. Nếu máy cần wheel khác, sửa PaddlePaddle index trước khi chạy `uv sync`:

| CUDA wheel | PaddlePaddle index URL |
|------------|-------------------------|
| CUDA 13.0 | `https://www.paddlepaddle.org.cn/packages/stable/cu130/` |
| CUDA 12.9 | `https://www.paddlepaddle.org.cn/packages/stable/cu129/` |
| CUDA 12.6 | `https://www.paddlepaddle.org.cn/packages/stable/cu126/` |
| CUDA 11.8 | `https://www.paddlepaddle.org.cn/packages/stable/cu118/` |

```bash
# 1. Cài đặt
git clone <repo_url> && cd Paper-Translate-Personal-Project
uv sync
uv pip install -e .

# 2. Kiểm tra PaddlePaddle
uv run python scripts/check_paddle_env.py

# 3. Cài browser cho Playwright để xuất PDF
uv run playwright install chromium

# 4. Copy file cấu hình mẫu
cp .env.example .env

# Nếu không dùng được Chromium do Playwright quản lý, cài Google Chrome:
# wget -q -O /tmp/google-chrome.deb "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
# sudo apt install /tmp/google-chrome.deb
#
# Sau đó cấu hình PP-DocLayout sử dụng Chrome trên hệ thống:
# echo "PPDOCLAYOUT_PLAYWRIGHT_BROWSER_CHANNEL=chrome" >> .env

# 5. Khởi động PaddleOCR-VL server (Terminal 1, port 8000)
scripts/start_paddle_ocr_vl.sh

# 6. Khởi động TranslateGemma server (Terminal 2, port 8001)
scripts/start_translate_gemma.sh

# 7. Kiểm tra cả hai server (Terminal 3)
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models

# 8. Chạy
uv run -m pp_doclayout.cli run paper.pdf
```

Nếu kiểm tra PaddlePaddle fail, sửa Paddle/CUDA trước khi chạy `parse` hoặc `run`.

Lệnh mặc định xuất đồng thời `output/paper/translated_paper.html` và
`output/paper/translated_paper.pdf`.

Mặc định, các tiêu đề mục (`paragraph_title`) được giữ nguyên ngôn ngữ nguồn.
Chỉ bật dịch tiêu đề khi cần:

```bash
uv run -m pp_doclayout.cli run paper.pdf --translate-titles
```

Mặc định, PDF export dùng Chromium do Playwright quản lý. Để dùng browser đã
cài trên hệ thống, đặt browser channel trong `.env`:

```env
PPDOCLAYOUT_PLAYWRIGHT_BROWSER_CHANNEL=chrome
```

CSS dành cho chế độ in ánh xạ mỗi trang HTML đã parse thành một trang PDF,
đồng thời loại bỏ margin và shadow chỉ phục vụ giao diện xem trên màn hình.

## Triển khai Docker để demo

Dùng Docker khi demo trên máy Linux khác, hoặc Windows có Docker Desktop chạy
Linux containers qua WSL2 và hỗ trợ NVIDIA GPU. Docker đã đóng gói Python, CUDA
runtime, vLLM, PaddleOCR và Playwright; máy demo không cần cài môi trường `uv`
cục bộ.

Trước khi build, xác nhận Docker nhìn thấy GPU của máy host:

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04 nvidia-smi
```

Build image, khởi động hai model server và Parse API, đợi trạng thái `healthy`, rồi chạy
pipeline. Lần khởi động server đầu tiên sẽ tải model vào Docker volume.

```bash
docker compose build
docker compose up -d paddle-ocr-vl translate-gemma parse-api
docker compose ps
docker compose run --rm pipeline run input/PhoMT.pdf
```

`input/` và `output/` vẫn nằm trên máy host. Với GPU 12GB trở xuống, hãy chạy
từng bước và tắt model thứ nhất trước khi chạy model thứ hai:

```bash
docker compose up -d paddle-ocr-vl parse-api
docker compose run --rm --no-deps pipeline parse input/PhoMT.pdf
docker compose stop parse-api paddle-ocr-vl

docker compose up -d translate-gemma
docker compose run --rm --no-deps pipeline translate output/<thư_mục_parse>
docker compose stop translate-gemma
```

Dừng container nhưng giữ cache model đã tải:

```bash
docker compose down
```

### Browser demo

Khởi động giao diện xem lại một trang tại <http://localhost:3000>:

```bash
docker compose up -d paddle-ocr-vl translate-gemma parse-api web-api web-frontend
```

Cột trái dùng để upload PDF và chọn toàn bộ tài liệu hoặc một trang. PDF gốc
hiện ngay ở cột giữa; sau khi dịch xong, PDF dịch hiện ở cột phải. Điều khiển
zoom dùng chung cho cả hai tài liệu.
Nút "Dịch tiêu đề mục" mặc định tắt và tương ứng với option CLI ở trên.

Bước parse chạy tuần tự để model DocLayout ổn định. Mặc định chỉ một job được
dịch tại một thời điểm và job đó gửi tối đa bốn request đến TranslateGemma; đây
là cấu hình được chọn từ benchmark workload thật. Có thể chỉnh
`WEB_DEMO_TRANSLATION_WORKERS` và `WEB_DEMO_MAX_CONCURRENT_REQUESTS` trong môi
trường Compose, nhưng tích của hai giá trị không nên vượt bốn nếu dùng một GPU.

Để mở demo công khai trong thời gian ngắn, khởi động Cloudflare Quick Tunnel:

```bash
docker compose --profile tunnel up -d cloudflared
docker compose logs -f cloudflared
```

Trên VPS 12 GB, dùng `./scripts/start_vps_demo.sh` để build và khởi động các
service theo thứ tự: TranslateGemma sẵn sàng trước khi PaddleOCR-VL được nạp.

Chia sẻ URL `https://...trycloudflare.com` in trong log. URL thay đổi khi tunnel
khởi động lại và có thể truy cập công khai, nên hãy tắt tunnel sau phần demo.
Xem [docker/README.md](docker/README.md) để có hướng dẫn triển khai đầy đủ.

Nếu Quick Tunnel URL không resolve được, chỉ restart `cloudflared` để lấy URL
mới, không dừng hoặc nạp lại hai model GPU:

```bash
docker compose --env-file .env.vps --profile tunnel stop cloudflared
docker compose --env-file .env.vps --profile tunnel up -d cloudflared
docker compose --env-file .env.vps logs -f cloudflared
```

Nếu Docker báo `failed to set up container networking` kèm `network ... not
found`, container tunnel đã dừng đang giữ network cũ bị xóa bởi một lần
`docker compose down` trước đó. Chỉ tạo lại container này, không restart các
service GPU:

```bash
# Docker profile local
docker compose --profile tunnel rm -f cloudflared
docker compose --profile tunnel up -d cloudflared

# VPS profile
docker compose --env-file .env.vps --profile tunnel rm -f cloudflared
docker compose --env-file .env.vps --profile tunnel up -d cloudflared
```

Cấu hình Docker hiện tại dành cho NVIDIA GPU đời mới. Image đã được build và
smoke-test trên máy phát triển; RTX 3060 12 GB cần profile giảm bộ nhớ riêng
trước khi được xem là máy demo hỗ trợ chính thức. RTX 4060 8 GB phù hợp parse,
render hoặc làm client gọi server dịch từ máy khác. Quadro P3200 không được hỗ
trợ bởi stack vLLM/CUDA hiện tại. Xem hướng dẫn đầy đủ tại
[docker/README.md](docker/README.md).

---

## Hướng dẫn sử dụng

> Khuyến nghị chạy từng bước (`parse` rồi `translate`). Máy ít VRAM có thể tắt PaddleOCR-VL server sau khi parse xong để giải phóng VRAM cho TranslateGemma.

### Khởi động model servers

Mở ba terminal:

```bash
# Terminal 1: OCR/layout server
scripts/start_paddle_ocr_vl.sh

# Terminal 2: translation server
scripts/start_translate_gemma.sh

# Terminal 3: DocLayout worker và Parse API chạy lâu dài
scripts/start_parse_api.sh
```

Sau đó kiểm tra cả hai endpoint model tương thích OpenAI:

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
curl http://127.0.0.1:8082/health
```

`parse` và `run` gửi bước parse sang Parse API. Nếu API chưa chạy, chúng sẽ báo
lệnh `scripts/start_parse_api.sh`. `translate` vẫn kiểm tra trực tiếp server
TranslateGemma.

Mặc định, các model phụ local của PaddleOCR như `PP-DocLayoutV3` dùng:

```env
PPDOCLAYOUT_PADDLE_OCR_CLIENT_DEVICE=auto
```

`auto` sẽ chọn `gpu:0` nếu Paddle phát hiện CUDA GPU dùng được, nếu không sẽ
dùng `cpu`. Có thể ép device bằng cách đặt giá trị này thành `cpu` hoặc `gpu:0`
trong `.env`.

### Parse API chạy lâu dài

Khi có nhiều request parse, khởi động API một lần thay vì gọi CLI cho từng
request. API chỉ nạp một lần model phụ local `PP-DocLayoutV3`, xếp các PDF theo
hàng đợi FIFO, và giữ model trong VRAM đến khi API dừng.

Bắt buộc dùng đúng một Uvicorn worker. Nhiều worker là nhiều process Python
riêng, mỗi process sẽ nạp thêm một bản model layout local.

```bash
# PaddleOCR-VL server ở port 8000 phải đang chạy trước.
scripts/start_parse_api.sh

# Lệnh CLI tương đương
uv run -m pp_doclayout.cli serve
```

Gửi PDF, sau đó polling theo `job_id` nhận được:

```bash
curl -F "file=@input/PhoMT.pdf" http://127.0.0.1:8082/parse
curl http://127.0.0.1:8082/jobs/<job_id>
```

Trạng thái job là `queued`, `running`, `completed`, hoặc `failed`. Các lệnh CLI
giữ nguyên cú pháp, nhưng output của `parse` được lưu tại
`output/<tên_file>-<job-id>/`, do đó hai file cùng tên không ghi đè nhau. Không
dùng `--reload` khi demo ổn định vì reload sẽ tạo lại model worker.

### Bước 1: Parse PDF

Cần Parse API (port 8082); worker chạy lâu dài của API cần PaddleOCR-VL server
(port 8000).

```bash
uv run -m pp_doclayout.cli parse <file.pdf>

# Chỉ định thư mục output
uv run -m pp_doclayout.cli parse <file.pdf> -o ./ket_qua
```

Kết quả được lưu tại `output/<tên_file>-<job-id>/` (CLI sẽ in đúng đường dẫn):
- `*_res.json` — parsing results (tọa độ + nội dung từng block)
- `*_res.md` — markdown output
- `imgs/` — cropped images

### Bước 2: Translate

Cần TranslateGemma server (port 8001).

```bash
# Xuất cả HTML và PDF (mặc định)
uv run -m pp_doclayout.cli translate output/<thư_mục_parse>

# Chỉ xuất PDF
uv run -m pp_doclayout.cli translate output/<thư_mục_parse> -f pdf

# Hậu tố file tùy chỉnh
uv run -m pp_doclayout.cli translate output/<thư_mục_parse> --suffix vi
```

Mặc định tạo: `<thư_mục_parse>/translated_<tên_file>.html` và `.pdf`

### Full Pipeline

Chạy parse + translate trong 1 lệnh. Cần Parse API và TranslateGemma; Parse API
đến lượt nó cần PaddleOCR-VL.

```bash
# Xuất cả HTML và PDF (mặc định)
uv run -m pp_doclayout.cli run <file.pdf>

# Chỉ xuất PDF
uv run -m pp_doclayout.cli run <file.pdf> -f pdf
```

### Xem kết quả

```bash
xdg-open output/<tên_file>/translated_<tên_file>.html   # HTML
xdg-open output/<tên_file>/translated_<tên_file>.pdf    # PDF
```

## Models

Pipeline sử dụng 2 mô hình, mỗi mô hình chạy trên 1 vLLM server riêng:

| Model | Size | Port | Chức năng |
|-------|------|------|-----------|
| **PaddleOCR-VL** | 0.9B | 8000 | Phân tích layout, OCR, crop images |
| **TranslateGemma** | 4B (cấu hình vLLM FP8) | 8001 | Dịch Anh → Việt |

### Kiểm tra servers

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
```

### Benchmark với block PDF thật

Tạo JSONL từ các block mà pipeline thực sự dịch. Script dùng cùng translation
policy, prompt `<<<custom>>>` và giới hạn output với `GemmaTranslator`.

```bash
uv run scripts/build_translation_benchmark_dataset.py \
  output/PhoMT output/2306.00978v6 \
  --output bench_data/translation_blocks.jsonl \
  --max-samples 100
```

Sau khi TranslateGemma server đang chạy, chạy benchmark trong môi trường vLLM:

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

Không dùng `--skip-chat-template`: benchmark cần bọc user content bằng template
của TranslateGemma. Không dùng `--ignore-eos`: model tự kết thúc bản dịch như
pipeline thật.

## Translation Policy

| Action | Labels | Mô tả |
|--------|--------|-------|
| **Dịch** | `abstract`, `text`, `figure_title` | Nội dung chính |
| **Giữ nguyên** | `doc_title`, `paragraph_title`, `reference_content`, `footnote`, `display_formula`, `table`, `image`, `chart`, `formula_number`, `number` | Tiêu đề, references, công thức, số trang |
| **Bỏ qua** | `aside_text`, `header`, `footer`, `content` | Block nhiễu |

## Cấu trúc Project

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
│   └── translation_policy.py   # Logic dịch/giữ/skip
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
    ├── paddle_device.py        # Chọn device cho model phụ PaddleOCR
    ├── path_utils.py
    └── server_health.py        # Kiểm tra model servers tương thích OpenAI
```

## Troubleshooting

**Out of Memory (OOM):**
- Giảm `--max-model-len` hoặc `--gpu-memory-utilization` trong vLLM command
- Giảm `--max-num-seqs` để giảm batch size
- Chạy từng bước thay vì `run` để chỉ cần 1 server tại thời điểm

**ModuleNotFoundError:**
```bash
uv pip install -e .
```

**Servers không connect:**
```bash
nvidia-smi
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
```

## License

MIT License
