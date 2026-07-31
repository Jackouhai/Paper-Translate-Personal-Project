# Local vLLM Server

This project contains the isolated Python environment used to run the local
vLLM model servers for PP-DocLayout. It is separate from the main pipeline
environment because vLLM requires Python 3.11.

## Requirements

- Python 3.11
- `uv`
- NVIDIA GPU and a CUDA environment compatible with vLLM

## Install

From the repository root:

```bash
cd services/llm-server
uv sync
cd ../..
```

`uv sync` creates `services/llm-server/.venv`. This directory is local build
state and must not be committed.

## Start the model servers

Open two terminals from the repository root.

Terminal 1 starts the PaddleOCR-VL server on port 8000:

```bash
scripts/start_paddle_ocr_vl.sh
```

Terminal 2 starts the TranslateGemma server on port 8001:

```bash
scripts/start_translate_gemma.sh
```

## Verify the servers

```bash
curl http://127.0.0.1:8000/v1/models
curl http://127.0.0.1:8001/v1/models
```

The PP-DocLayout CLI runs the same checks before `parse`, `translate`, and
`run`.
