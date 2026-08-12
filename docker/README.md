# Docker demo

This package runs the two vLLM GPU servers, a long-lived Parse API that owns the
local PP-DocLayoutV3 helper model, and a pipeline client container. It is
intended for a Linux host, or Windows with
Docker Desktop configured for Linux containers, WSL2, and NVIDIA GPU support.
Native Windows containers are not supported.

## Prerequisites

- NVIDIA driver that works with the host CUDA runtime.
- Docker Engine with NVIDIA Container Toolkit on Linux, or Docker Desktop with
  WSL2 GPU support on Windows.
- At least the VRAM required by the current local configuration. The defaults
  match `scripts/start_paddle_ocr_vl.sh` and `scripts/start_translate_gemma.sh`.
- The local Docker profile uses `PARSE_API_DEVICE=auto`, so PP-DocLayoutV3 uses
  `gpu:0` when Paddle detects CUDA. The supplied 12 GB VPS profile sets it to
  `cpu` to preserve VRAM for the model servers. Run a representative PDF before
  a live demo; use the staged workflow below on 12 GB GPUs or lower.

Verify GPU pass-through before building the project:

```bash
docker run --rm --gpus all nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04 nvidia-smi
```

## RTX 3060 12 GB VPS profile

The default model profile targets the development GPU. For an RTX 3060 12 GB
VPS, create an untracked profile file from the supplied template:

```bash
cp .env.vps.example .env.vps
```

Use that file with every Docker Compose command on the VPS:

```bash
docker compose --env-file .env.vps build
docker compose --env-file .env.vps up -d paddle-ocr-vl translate-gemma parse-api web-api web-frontend
```

For the normal demo startup, use the sequential launcher instead. It waits for
TranslateGemma before loading PaddleOCR-VL, then starts the remaining services
and prints the temporary Cloudflare URL. Before loading either model, it runs
`nvidia-smi` in a CUDA container to verify Docker GPU pass-through:

```bash
chmod +x scripts/start_vps_demo.sh
./scripts/start_vps_demo.sh
```

Use `./scripts/start_vps_demo.sh --skip-build` for later restarts, or add
`--no-tunnel` to keep the demo private on the VPS.

For local development, use the dedicated wrapper. It uses the local `.env` and
Compose defaults, binds the frontend to `127.0.0.1:3100`, and starts the tunnel
unless `--no-tunnel` is supplied:

```bash
./scripts/start_local_demo.sh --skip-build
```

For a machine with about 24 GB VRAM, use the conservative 24 GB profile. The
wrapper creates the untracked `.env.24gb` from its example on first use:

```bash
./scripts/start_24gb_demo.sh --skip-build
```

The 24 GB profile is an initial operating point, not a benchmark result. If
the model logs show out-of-memory errors, lower `TRANSLATE_GEMMA_MAX_NUM_SEQS`
or `PADDLE_OCR_VL_MAX_NUM_SEQS` in `.env.24gb` before increasing concurrency.

The profile switches TranslateGemma to 4-bit BitsAndBytes, disables CUDA Graph
capture, lowers batch limits, and leaves VRAM headroom for PaddleOCR-VL. If
TranslateGemma still cannot start, change `TRANSLATE_GEMMA_CPU_OFFLOAD_GB=1` in
`.env.vps`; this shifts 1 GB of weights to system RAM and reduces throughput.

## Start and run

From the repository root, build the images once:

```bash
docker compose build
```

The Docker images configure `uv` with a five-minute HTTP read timeout, five
retries, and four concurrent downloads. This avoids most failures when large
CUDA dependency wheels are downloaded on a slower network. If a build still
fails due to a transient network error, rerun the same build command; Docker
uses a persistent BuildKit cache for `uv` downloads, so completed wheels do not
need to be downloaded again after a failed dependency layer.

On a GPU with 16 GB VRAM or higher, start both model servers and the Parse API.
The first start downloads model weights into the named Docker volumes
`pp-doclayout-hf-cache` and `pp-doclayout-paddlex-cache`, so it takes longer.

```bash
docker compose up -d paddle-ocr-vl translate-gemma parse-api
docker compose ps
```

Wait until all three services show `healthy`, then run the full pipeline. Files in
`input/` and `output/` stay on the host machine.

```bash
docker compose run --rm pipeline run input/PhoMT.pdf
```

The command creates both HTML and PDF by the project's current defaults. On a
12 GB GPU or lower, use separate stages instead:

```bash
docker compose up -d paddle-ocr-vl parse-api
docker compose run --rm --no-deps pipeline parse input/PhoMT.pdf
docker compose stop parse-api paddle-ocr-vl

docker compose up -d translate-gemma
docker compose run --rm --no-deps pipeline translate output/<parse-output-dir>
```

`parse` prints its output directory. It contains a job ID to prevent concurrent
uploads with the same filename from overwriting each other.

Useful checks:

```bash
curl http://localhost:8000/v1/models
curl http://localhost:8001/v1/models
docker compose exec parse-api python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8082/health')"
docker compose logs -f paddle-ocr-vl
docker compose logs -f translate-gemma
docker compose logs -f parse-api
```

Stop the model servers without deleting downloaded weights:

```bash
docker compose down
```

## Browser demo and Cloudflare Quick Tunnel

The browser demo is a single three-column workspace. The left column uploads a
PDF and selects all pages or one page; the original PDF appears in the middle
as soon as the upload is accepted; the translated PDF appears in the right
column when the job completes. One shared zoom control applies to both PDF
viewers.

The parse stage is intentionally serialized. The local profile allows five
completed parse jobs to translate concurrently, with up to four block requests
per job sent to TranslateGemma. This is job-level concurrency; vLLM remains one
model server and batches the requests continuously. The queue accepts ten jobs.
For a 12 GB VPS, `.env.vps` reduces translation to one job at a time.

Override the local limits only after measuring GPU headroom:

```bash
WEB_DEMO_TRANSLATION_WORKERS=3 WEB_DEMO_MAX_CONCURRENT_REQUESTS=3 \
  docker compose up -d web-api
```

Start the complete demo locally at <http://localhost:3000>:

```bash
docker compose up -d paddle-ocr-vl translate-gemma parse-api web-api web-frontend
docker compose ps
```

To expose only that frontend for a short presentation, include the optional
Cloudflare Quick Tunnel profile:

```bash
docker compose --profile tunnel up -d
docker compose logs -f cloudflared
```

Copy the `https://...trycloudflare.com` URL printed by `cloudflared` and share
it with the council. The URL changes after the tunnel restarts. Quick Tunnel is
public and does not support Cloudflare Access, so do not publish it outside the
presentation and stop the stack when the session ends:

```bash
docker compose down
```

If the temporary URL does not resolve, restart only the tunnel. This obtains a
new URL without stopping or reloading the GPU model containers:

```bash
docker compose --env-file .env.vps --profile tunnel stop cloudflared
docker compose --env-file .env.vps --profile tunnel up -d cloudflared
docker compose --env-file .env.vps logs -f cloudflared
```

If restarting only `cloudflared` reports `failed to set up container networking`
with `network ... not found`, its stopped container still references a Docker
network removed by an earlier `docker compose down`. Recreate only that
container; GPU model containers stay running:

```bash
# Local Docker profile
docker compose --profile tunnel rm -f cloudflared
docker compose --profile tunnel up -d cloudflared

# VPS profile
docker compose --env-file .env.vps --profile tunnel rm -f cloudflared
docker compose --env-file .env.vps --profile tunnel up -d cloudflared
```

The tunnel reaches `web-frontend` only. PaddleOCR-VL, TranslateGemma, Parse API
and Web API remain internal to the Docker network from the tunnel's perspective.

To remove the downloaded model cache as well:

```bash
docker volume rm pp-doclayout-hf-cache
```
