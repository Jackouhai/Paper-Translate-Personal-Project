import typer
from pathlib import Path
from typing import Optional

from pp_doclayout.translators import get_gemma
from pp_doclayout.config import settings

app = typer.Typer(
    name="ppdoc",
    help="Pipeline dịch paper học thuật sang tiếng Việt",
    add_completion=False,
)


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
    from paddleocr import PaddleOCRVL

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise typer.Exit(f"File không tồn tại: {pdf_path}", code=1)

    # Use custom output dir if provided, otherwise use config
    base_output = Path(output_dir) if output_dir else Path(settings.output_dir)
    project_dir = base_output / pdf_file.stem
    project_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"Parsing PDF: {pdf_path}")
    typer.echo(f"Output folder: {project_dir}")

    # Initialize PaddleOCR-VL
    pipeline = PaddleOCRVL(
        vl_rec_backend=settings.paddle_ocr_backend,
        vl_rec_server_url=settings.paddle_ocr_server_url,
    )

    # Process output
    output = pipeline.predict(str(pdf_path))
    for i, res in enumerate(output):
        typer.echo(f"--> Saving page {i + 1}/{len(output)}")
        try:
            res.save_to_json(save_path=str(project_dir))
            res.save_to_markdown(save_path=str(project_dir))
        except Exception as e:
            typer.echo(f"Lỗi lưu trang {i + 1}: {e}", err=True)
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
    export_format: str = typer.Option(
        "html",
        "--format",
        "-f",
        help="Định dạng export (default: html)",
    ),
):
    """Dịch project đã parse sang HTML.

    Sử dụng Gemma model để dịch:
    - Abstract
    - Nội dung text chính
    - Figure/table captions
    """
    from pp_doclayout.core import process_project

    translator = get_gemma()
    output_path = process_project(
        Path(project_dir), translator=translator, output_suffix=output_suffix
    )
    typer.echo(f"✓ HTML created: {output_path}")


@app.command()
def run(
    pdf_path: str,
    output_suffix: str = typer.Option(
        "translated",
        "--suffix",
        "-s",
        help="Hậu tố tên file output (default: translated)",
    ),
    export_format: str = typer.Option(
        "html",
        "--format",
        "-f",
        help="Định dạng export (default: html)",
    ),
):
    """Full pipeline: parse + translate.

    Chạy cả 2 bước:
    1. Parse PDF với PaddleOCR-VL
    2. Translate với Gemma model
    """
    # Step 1: Parsing
    typer.echo("=== Step 1: Parse PDF ===")
    from paddleocr import PaddleOCRVL

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise typer.Exit(f"File không tồn tại: {pdf_path}", code=1)

    project_dir = Path(settings.output_dir) / pdf_file.stem
    project_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"Parsing PDF: {pdf_path}")
    typer.echo(f"Output folder: {project_dir}")

    pipeline = PaddleOCRVL(
        vl_rec_backend=settings.paddle_ocr_backend,
        vl_rec_server_url=settings.paddle_ocr_server_url,
    )

    output = pipeline.predict(str(pdf_path))
    for i, res in enumerate(output):
        typer.echo(f"--> Saving page {i + 1}/{len(output)}")
        try:
            res.save_to_json(save_path=str(project_dir))
            res.save_to_markdown(save_path=str(project_dir))
        except Exception as e:
            typer.echo(f"Lỗi lưu trang {i + 1}: {e}", err=True)
    typer.echo(f"✓ Parse hoàn tất: {project_dir}")

    # Step 2: Translate
    typer.echo("\n=== Step 2: Translate ===")
    from pp_doclayout.core import process_project

    translator = get_gemma()
    output_path = process_project(
        project_dir, translator=translator, output_suffix=output_suffix
    )
    typer.echo(f"✓ HTML created: {output_path}")


if __name__ == "__main__":
    app()
