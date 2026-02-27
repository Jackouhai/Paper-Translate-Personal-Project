from pathlib import Path

from pp_doclayout.config import settings


def get_output_dir() -> Path:
    """Get the base output directory from config.

    Returns:
        Path to output directory
    """
    return Path(settings.output_dir)


def get_project_dir(pdf_name: str) -> Path:
    """Get project directory for a specific PDF.

    Args:
        pdf_name: Name of the PDF file (with or without .pdf extension)

    Returns:
        Path to the project directory: output/<pdf_name>/
    """
    # Remove .pdf extension if present
    name = pdf_name.removesuffix(".pdf")
    return get_output_dir() / name
