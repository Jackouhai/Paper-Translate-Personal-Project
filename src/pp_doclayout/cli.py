import typer
from pathlib import Path
from pp_doclayout.translators import get_gemma
from pp_doclayout.config import settings

app = typer.Typer(
    name="ppdoc",
    help="Pipeline dịch paper học thuật sang tiếng Việt",
)


@app.command()
def parse(pdf_path: str):
    """Phân tích PDF (Layout & OCR)"""
    from paddleocr import PaddleOCRVL

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise typer.Exit(f"File không tồn tại: {pdf_path}")

    # Create output folder
    project_dir = Path(settings.output_dir) / pdf_file.stem
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
            typer.echo(f"Lỗi lưu trang {i + 1}: {e}")
    typer.echo(f"Parse hoàn tất: {project_dir}")


@app.command()
def translate(project_dir: str, output_suffix: str = "translated"):
    """Dịch project đã parse vào html"""
    from pp_doclayout.core import process_project

    translator = get_gemma()
    output_path = process_project(
        Path(project_dir), translator=translator, output_suffix=output_suffix
    )
    typer.echo(f"HTML created: {output_path}")


@app.command()
def run(pdf_path: str, output_suffix: str = "translated"):
    """Full pipeline: parse + translate"""
    # Step 1: Parsing
    typer.echo("=== Step 1: Parse PDF ===")
    from paddleocr import PaddleOCRVL

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise typer.Exit(f"File không tồn tại: {pdf_file}")

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
            typer.echo(f"Lỗi lưu trang {i + 1}: {e}")
    typer.echo(f"Parse hoàn tất: {project_dir}")

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
