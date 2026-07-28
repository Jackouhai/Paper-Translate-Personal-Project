# PaperTranslate AppImage Release Test

## Release Summary

* Package type: AppImage
* Architecture: x86_64
* AppImage filename: `PaperTranslate-x86_64.AppImage`
* Approximate size: 6.7 GB
* Bundled Python: CPython 3.10.20
* Test environment: Ubuntu with NVIDIA GeForce RTX 3060 12 GB
* Branch: `thai-bundled-python-runtime`
* Runtime strategy: staged OCR and translation because both models cannot run concurrently within 12 GB VRAM

## Build Result

The AppImage was generated successfully using `appimagetool`.

```text
Success
Final AppImage build: PASS
```

The generated AppImage contains the Tauri desktop application, frontend assets, FastAPI backend, bundled Python runtime, and required Python dependencies.

## End-to-End Test Results

The following checks passed:

* [x] The graphical interface opened correctly.
* [x] The bundled FastAPI backend started automatically.
* [x] PaddleOCR-VL was detected.
* [x] PDF parsing returned HTTP 200.
* [x] OCR JSON output was created.
* [x] OCR Markdown output was created.
* [x] TranslateGemma was detected after switching models.
* [x] Translation returned HTTP 200.
* [x] Translated Vietnamese HTML was created.
* [x] Generated files could be downloaded from the interface.
* [x] The backend stopped automatically when the application was closed.
* [x] Port 8002 was released after application shutdown.

## Service Ports

| Service                | Port |
| ---------------------- | ---: |
| PaddleOCR-VL           | 8000 |
| TranslateGemma         | 8001 |
| PaperTranslate backend | 8002 |

## Runtime Locations

Bundled Python executable:

```text
/usr/lib/PaperTranslate/runtime/python/cpython-3.10.20-linux-x86_64-gnu/bin/python3.10
```

Inside the mounted AppImage, the runtime is resolved under a temporary mount directory:

```text
/tmp/.mount_*/usr/lib/PaperTranslate/runtime/python/cpython-3.10.20-linux-x86_64-gnu/bin/python3.10
```

Python site-packages:

```text
/usr/lib/PaperTranslate/runtime/venv/lib/python3.10/site-packages
```

Backend application:

```text
/usr/lib/PaperTranslate/backend-app
```

Application data:

```text
~/.local/share/com.jackouhai.papertranslate
```

## Backend Startup

The AppImage started the backend using the bundled relocatable Python runtime.

Example startup log:

```text
Starting backend with Python: /tmp/.mount_*/usr/lib/PaperTranslate/runtime/python/cpython-3.10.20-linux-x86_64-gnu/bin/python3.10
Python home: /tmp/.mount_*/usr/lib/PaperTranslate/runtime/python/cpython-3.10.20-linux-x86_64-gnu
Python site-packages: /tmp/.mount_*/usr/lib/PaperTranslate/runtime/venv/lib/python3.10/site-packages
Backend script: /tmp/.mount_*/usr/lib/PaperTranslate/backend-app/run_backend.py
Application startup complete.
Uvicorn running on http://127.0.0.1:8002
```

## Staged Model Workflow

The target computer has an NVIDIA RTX 3060 with 12 GB VRAM. PaddleOCR-VL and TranslateGemma cannot run concurrently within the available GPU memory, so the test used the following staged workflow:

1. Start PaddleOCR-VL on port 8000.
2. Open the AppImage.
3. Upload a scientific PDF.
4. Parse the PDF and generate OCR and layout outputs.
5. Stop PaddleOCR-VL after parsing completes.
6. Start TranslateGemma on port 8001.
7. Wait for the frontend to detect the translator.
8. Translate and reconstruct the document.
9. Download the generated results from the interface.

## Model Status Endpoint

The backend model-status endpoint responded successfully:

```http
GET http://127.0.0.1:8002/pipeline/model-status
```

Example response when both model servers were stopped:

```json
{
  "ocr_ready": false,
  "translator_ready": false
}
```

Expected response while PaddleOCR-VL is running:

```json
{
  "ocr_ready": true,
  "translator_ready": false
}
```

Expected response while TranslateGemma is running:

```json
{
  "ocr_ready": false,
  "translator_ready": true
}
```

## Generated Outputs

The end-to-end pipeline successfully generated:

* OCR layout JSON
* OCR Markdown
* Translated Vietnamese HTML
* Downloadable output files through the graphical interface

The generated files were stored under the PaperTranslate application data directory:

```text
~/.local/share/com.jackouhai.papertranslate
```

## Backend Lifecycle

Before the application was closed, bundled Python listened on port 8002.

After the AppImage was closed:

```text
Final AppImage lifecycle: PASS
```

No backend process remained, and port 8002 was released.

## Packaging Notes

The following optional components were removed because they are not required for the NVIDIA single-GPU workflow:

* NVSHMEM MPI bootstrap
* NVSHMEM OpenSHMEM bootstrap
* NVSHMEM libfabric transport
* NVSHMEM UCX transport
* bitsandbytes ROCm backends

CUDA libraries, NVSHMEM core libraries, and the main Python runtime components were retained.

## Build Automation

The AppImage packaging workflow is automated through:

```text
scripts/package_appimage.sh
scripts/prune_appimage_runtime.sh
```

The packaging script:

1. Builds the frontend.
2. Builds the production Tauri binary.
3. Copies the binary into the existing AppDir.
4. Removes unsupported optional runtime components.
5. Verifies bundled Python and site-packages.
6. Creates the final AppImage with `appimagetool`.

## Conclusion

The PaperTranslate AppImage passed the complete local English-to-Vietnamese scientific PDF translation workflow.

```text
Release candidate status: PASS
```
