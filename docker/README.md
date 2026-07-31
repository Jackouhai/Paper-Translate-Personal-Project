# Docker demo

This package runs the same two GPU servers as the local setup and executes the
pipeline in a third container. It is intended for a Linux host, or Windows with
Docker Desktop configured for Linux containers, WSL2, and NVIDIA GPU support.
Native Windows containers are not supported.

## Prerequisites

- NVIDIA driver that works with the host CUDA runtime.
- Docker Engine with NVIDIA Container Toolkit on Linux, or Docker Desktop with
  WSL2 GPU support on Windows.
- At least the VRAM required by the current local configuration. The defaults
  match `scripts/start_paddle_ocr_vl.sh` and `scripts/start_translate_gemma.sh`.

Verify GPU pass-through before building the project:

```bash
docker run --rm --gpus all nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04 nvidia-smi
```

## Start and run

From the repository root, build the images once:

```bash
docker compose build
```

Start both model servers. The first start downloads model weights into the
named Docker volume `pp-doclayout-hf-cache`, so it takes longer.

```bash
docker compose up -d paddle-ocr-vl translate-gemma
docker compose ps
```

Wait until both services show `healthy`, then run the full pipeline. Files in
`input/` and `output/` stay on the host machine.

```bash
docker compose run --rm pipeline run input/PhoMT.pdf
```

The command creates both HTML and PDF by the project's current defaults. For
separate stages:

```bash
docker compose run --rm pipeline parse input/PhoMT.pdf
docker compose run --rm pipeline translate output/PhoMT
```

Useful checks:

```bash
curl http://localhost:8000/v1/models
curl http://localhost:8001/v1/models
docker compose logs -f paddle-ocr-vl
docker compose logs -f translate-gemma
```

Stop the model servers without deleting downloaded weights:

```bash
docker compose down
```

To remove the downloaded model cache as well:

```bash
docker volume rm pp-doclayout-hf-cache
```
