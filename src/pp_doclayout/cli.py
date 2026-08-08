import typer
from pathlib import Path
from typing import Optional

from pp_doclayout.translators import get_gemma
from pp_doclayout.config import settings
from pp_doclayout.core.parse_api_client import ParseAPIError, parse_pdf_via_api
from pp_doclayout.utils.paddle_device import resolve_paddle_device
from pp_doclayout.utils.server_health import check_server_health

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
        typer.echo(f"✓ {export_format.upper()} created: {output_path}")

    return output_paths

def _create_paddle_ocr_pipeline():
    """Create the PaddleOCR-VL pipeline with explicit device selection."""

    from paddleocr import PaddleOCRVL

    paddle_device = resolve_paddle_device(settings.paddle_ocr_client_device)
    typer.echo(f"PaddleOCR document layout analysis model on device: {paddle_device}")

    return PaddleOCRVL(
        vl_rec_backend=settings.paddle_ocr_backend,
        vl_rec_server_url=settings.paddle_ocr_server_url,
        format_block_content=settings.paddle_ocr_format_block_content,
        use_doc_unwarping=settings.paddle_ocr_use_doc_unwarping,
        use_chart_recognition=settings.paddle_ocr_use_chart_recognition,
        merge_layout_blocks=settings.paddle_ocr_merge_layout_blocks,
        use_ocr_for_image_block=settings.paddle_use_ocr_for_image_block,
        layout_detection_model_name=settings.paddle_ocr_layout_detection_model_name,
        use_layout_detection=settings.paddle_ocr_use_layout_detection,
        device=paddle_device,
    )


def _require_server(name: str, base_url: str) -> None:
    """Exit early when a required OpenAI-compatible server is unavailable."""
    health = check_server_health(name=name, base_url=base_url)
    if health.available:
        return
    typer.echo(f"{name} server is not ready: {health.url}", err=True)
    typer.echo(f"  Reason: {health.message}", err=True)
    raise typer.Exit(code=1)


def _parse_via_service(pdf_file: Path, output_dir: str | None = None) -> Path:
    """Submit a CLI parse request to the long-lived local Parse API."""

    try:
        return parse_pdf_via_api(
            pdf_path=pdf_file,
            base_url=settings.parse_api_base_url,
            output_dir=Path(output_dir) if output_dir else None,
        )
    except ParseAPIError as error:
        typer.echo(f"Parse API error: {error}", err=True)
        raise typer.Exit(code=1) from error

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
    from pp_doclayout.core.renderer import build_project_data, translate_page_data, render_page_blocks

    # Check the translation server before creating the translator.
    _require_server("TranslateGemma", settings.vllm_base_url)
    translator = get_gemma()

    # 1. Build project data from JSON files
    project_dir = Path(project_dir)
    project_data = build_project_data(project_dir)

    # 2. Translate all pages
    translated_pages = []
    for page in project_data["pages"]:
        translated_page = translate_page_data(page, translator)

        # 3. Render page blocks to HTML
        imgs_dir = project_dir / "imgs"
        blocks_html = render_page_blocks(translated_page, imgs_dir, project_dir)
        translated_page["html_content"] = blocks_html

        translated_pages.append(translated_page)

    project_data["pages"] = translated_pages

    # 4. Export
    _export_project(
        project_data,
        project_dir,
        output_suffix,
        export_formats,
    )


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

    _require_server("TranslateGemma", settings.vllm_base_url)

    typer.echo(f"Parsing PDF: {pdf_path}")
    project_dir = _parse_via_service(pdf_file)
    typer.echo(f"✓ Parse hoàn tất: {project_dir}")

    # Step 2: Translate
    typer.echo("\n=== Step 2: Translate ===")
    from pp_doclayout.core.renderer import build_project_data, translate_page_data, render_page_blocks
    translator = get_gemma()

    # 1. Build project data from JSON files
    project_data = build_project_data(project_dir)

    # 2. Translate all pages
    translated_pages = []
    for page in project_data["pages"]:
        translated_page = translate_page_data(page, translator)

        # 3. Render page blocks to HTML
        imgs_dir = project_dir / "imgs"
        blocks_html = render_page_blocks(translated_page, imgs_dir, project_dir)
        translated_page["html_content"] = blocks_html

        translated_pages.append(translated_page)

    project_data["pages"] = translated_pages

    # 4. Export
    _export_project(
        project_data,
        project_dir,
        output_suffix,
        export_formats,
    )


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
