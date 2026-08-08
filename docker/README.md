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
- The default Parse API runs PP-DocLayoutV3 on CPU to preserve GPU memory.
  All three services have been startup-tested on an RTX 5060 Ti 16 GB. Run a
  representative PDF before a live demo; use the staged workflow below on
  12 GB GPUs or lower.

Verify GPU pass-through before building the project:

```bash
docker run --rm --gpus all nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04 nvidia-smi
```

## Start and run

From the repository root, build the images once:

```bash
docker compose build
```

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

To remove the downloaded model cache as well:

```bash
docker volume rm pp-doclayout-hf-cache
```
