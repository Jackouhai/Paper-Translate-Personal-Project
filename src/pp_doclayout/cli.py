import typer
import os
from pathlib import Path
from typing import Optional

from pp_doclayout.translators import get_gemma
from pp_doclayout.config import settings
from pp_doclayout.core.parse_api_client import ParseAPIError, parse_pdf_via_api
from pp_doclayout.utils.paddle_device import resolve_paddle_device
from pp_doclayout.utils.server_health import check_server_health
from pp_doclayout.core.workflow import translate_and_export_project

app = typer.Typer(
    name="ppdoc",
    help="Pipeline dịch paper học thuật sang tiếng Việt",
    add_completion=False,
)

DEFAULT_EXPORT_FORMATS = "html,pdf"
SUPPORTED_EXPORT_FORMATS = frozenset({"html", "pdf"})

def _parse_export_formats(value: str) -> list[str]:
    formats = [
        export_format.strip().lower()
        for export_format in value.split(",")
        if export_format.strip()
    ]

    if not formats:
        raise typer.BadParameter(
            "Export format must contain html, pdf, or both."
        )

    invalid_formats = set(formats) - SUPPORTED_EXPORT_FORMATS
    if invalid_formats:
        invalid = ", ".join(sorted(invalid_formats))
        raise typer.BadParameter(f"Unsupported export format: {invalid}")

    return list(dict.fromkeys(formats))

def _export_project(
    project_data,
    project_dir: Path,
    output_suffix: str,
    export_formats: str,
) -> list[Path]:
    output_paths = []
    for export_format in _parse_export_formats(export_formats):
        if export_format == "html":
            from pp_doclayout.exporters.html import HTMLExporter

            exporter = HTMLExporter()
        else:
            from pp_doclayout.exporters.pdf import PDFExporter

            exporter = PDFExporter()

        output_path = (
            project_dir / f"{output_suffix}_{project_data['project_name']}.{export_format}"
        )
        exporter.export(project_data, output_path)
        output_paths.append(output_path)
    for output_path in output_paths:
        typer.echo(f"✓ {output_path.suffix[1:].upper()} created: {output_path}")
    return output_paths

def _create_paddle_ocr_pipeline(*, backend: str | None = None):
    """Create the PaddleOCR-VL pipeline with explicit device selection."""

    # PaddleX reads its model-host configuration while it is being imported.
    # Set these first so Colab can download official models from Hugging Face.
    os.environ["PADDLE_PDX_MODEL_SOURCE"] = settings.paddle_model_source
    if settings.paddle_huggingface_endpoint:
        os.environ["PADDLE_PDX_HUGGING_FACE_ENDPOINT"] = (
            settings.paddle_huggingface_endpoint
        )

    from paddleocr import PaddleOCRVL

    paddle_device = resolve_paddle_device(settings.paddle_ocr_client_device)
    typer.echo(f"PaddleOCR document layout analysis model on device: {paddle_device}")

    selected_backend = backend or settings.paddle_ocr_backend
    kwargs = dict(
        vl_rec_backend=selected_backend,
        format_block_content=settings.paddle_ocr_format_block_content,
        use_doc_unwarping=settings.paddle_ocr_use_doc_unwarping,
        use_chart_recognition=settings.paddle_ocr_use_chart_recognition,
        merge_layout_blocks=settings.paddle_ocr_merge_layout_blocks,
        use_ocr_for_image_block=settings.paddle_use_ocr_for_image_block,
        layout_detection_model_name=settings.paddle_ocr_layout_detection_model_name,
        use_layout_detection=settings.paddle_ocr_use_layout_detection,
        device=paddle_device,
    )
    if settings.paddle_ocr_vl_model_name:
        kwargs["vl_rec_model_name"] = settings.paddle_ocr_vl_model_name
    if selected_backend != "native":
        kwargs["vl_rec_server_url"] = settings.paddle_ocr_server_url
    return PaddleOCRVL(**kwargs)


def _require_server(name: str, base_url: str) -> None:
    """Exit early when a required OpenAI-compatible server is unavailable."""
    health = check_server_health(name=name, base_url=base_url)
    if health.available:
        return
    typer.echo(f"{name} server is not ready: {health.url}", err=True)
    typer.echo(f"  Reason: {health.message}", err=True)
    raise typer.Exit(code=1)


def _resolve_translation_backend() -> str:
    """Choose vLLM when ready, otherwise select the local fallback."""
    backend = settings.translation_backend.lower()
    if backend == "transformers":
        return backend
    if backend == "vllm":
        _require_server("TranslateGemma", settings.vllm_base_url)
        return backend

    health = check_server_health("TranslateGemma", settings.vllm_base_url)
    if health.available:
        return "vllm"
    typer.echo(
        "TranslateGemma vLLM server is unavailable; using local Transformers.",
        err=True,
    )
    return "transformers"


def _parse_via_service(pdf_file: Path, output_dir: str | None = None) -> Path:
    """Use the Parse API when available, otherwise run PaddleOCR-VL locally."""

    backend = settings.parsing_backend.lower()
    if backend not in {"auto", "api", "local"}:
        typer.echo(
            "Invalid PPDOCLAYOUT_PARSING_BACKEND; use auto, api, or local.",
            err=True,
        )
        raise typer.Exit(code=1)

    if backend == "local":
        return _parse_locally(pdf_file, output_dir)

    try:
        return parse_pdf_via_api(
            pdf_path=pdf_file,
            base_url=settings.parse_api_base_url,
            output_dir=Path(output_dir) if output_dir else None,
        )
    except ParseAPIError as error:
        if backend == "auto":
            typer.echo(
                "Parse API is unavailable; using local PaddleOCR-VL (native backend).",
                err=True,
            )
            return _parse_locally(pdf_file, output_dir)
        typer.echo(f"Parse API error: {error}", err=True)
        raise typer.Exit(code=1) from error


_local_paddle_pipeline = None


def _parse_locally(pdf_file: Path, output_dir: str | None = None) -> Path:
    """Parse one PDF without a Parse API or vLLM server."""
    global _local_paddle_pipeline
    if _local_paddle_pipeline is None:
        _local_paddle_pipeline = _create_paddle_ocr_pipeline(backend="native")

    base_output = Path(output_dir) if output_dir else Path(settings.output_dir)
    project_dir = base_output / pdf_file.stem
    project_dir.mkdir(parents=True, exist_ok=True)
    for result in _local_paddle_pipeline.predict(str(pdf_file)):
        result.save_to_json(save_path=str(project_dir))
        result.save_to_markdown(save_path=str(project_dir))
    return project_dir

@app.command()
def parse(
    pdf_path: str,
    output_dir: Optional[str] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Thư mục output (default: từ config)",
    ),
):
    """Phân tích PDF (Layout & OCR).

    Sử dụng PaddleOCR-VL để:
    - Phát hiện layout (tiêu đề, đoạn văn, hình ảnh, bảng, công thức...)
    - OCR cho text
    - Lưu kết quả vào JSON và markdown
    """

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise typer.Exit(f"File không tồn tại: {pdf_path}", code=1)

    typer.echo(f"Parsing PDF: {pdf_path}")
    project_dir = _parse_via_service(pdf_file, output_dir)
    typer.echo(f"✓ Parse hoàn tất: {project_dir}")


@app.command()
def translate(
    project_dir: str,
    output_suffix: str = typer.Option(
        "translated",
        "--suffix",
        "-s",
        help="Hậu tố tên file output (default: translated)",
    ),
    export_formats: str = typer.Option(
        DEFAULT_EXPORT_FORMATS,
        "--format",
        "-f",
        help="Định dạng export, phân tách bằng dấu phẩy (default: html,pdf)",
    ),
):
    """Dịch project đã parse và export artifact đã chọn.

    Sử dụng Gemma model để dịch:
    - Abstract
    - Nội dung text chính
    - Figure/table captions
    """
    # Check the translation server before creating the translator.
    translator = get_gemma(backend=_resolve_translation_backend())

    project_dir = Path(project_dir)
    output_paths = translate_and_export_project(
        project_dir,
        translator,
        output_suffix=output_suffix,
        export_formats=_parse_export_formats(export_formats),
    )
    for output_path in output_paths:
        typer.echo(f"✓ {output_path.suffix[1:].upper()} created: {output_path}")


@app.command()
def run(
    pdf_path: str,
    output_suffix: str = typer.Option(
        "translated",
        "--suffix",
        "-s",
        help="Hậu tố tên file output (default: translated)",
    ),
    export_formats: str = typer.Option(
        DEFAULT_EXPORT_FORMATS,
        "--format",
        "-f",
        help="Định dạng export, phân tách bằng dấu phẩy (default: html,pdf)",
    ),
):
    """Full pipeline: parse + translate.

    Chạy cả 2 bước:
    1. Parse PDF với PaddleOCR-VL
    2. Translate với Gemma model
    """
    # Step 1: Parsing
    typer.echo("=== Step 1: Parse PDF ===")

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise typer.Exit(f"File không tồn tại: {pdf_path}", code=1)

    translation_backend = _resolve_translation_backend()

    typer.echo(f"Parsing PDF: {pdf_path}")
    project_dir = _parse_via_service(pdf_file)
    typer.echo(f"✓ Parse hoàn tất: {project_dir}")

    # Step 2: Translate
    typer.echo("\n=== Step 2: Translate ===")
    translator = get_gemma(backend=translation_backend)
    output_paths = translate_and_export_project(
        project_dir,
        translator,
        output_suffix=output_suffix,
        export_formats=_parse_export_formats(export_formats),
    )
    for output_path in output_paths:
        typer.echo(f"✓ {output_path.suffix[1:].upper()} created: {output_path}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8082, "--port"),
):
    """Start the long-lived Parse API with exactly one worker process."""

    import uvicorn

    typer.echo(f"Starting Parse API on http://{host}:{port}")
    uvicorn.run(
        "pp_doclayout.api:app",
        host=host,
        port=port,
        workers=1,
    )

def main():
    app()


if __name__ == "__main__":
    main()
