from pathlib import Path
from typing import Optional

from pp_doclayout.config import settings


def ensure_dir(path: Path | str) -> Path:
    """Ensure a directory exists, create if not.

    Args:
        path: Directory path to ensure exists

    Returns:
        Path object for the directory
    """
    dir_path = Path(path)
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def find_image_file(
    imgs_dir: Path, output_dir: Path, bbox: list, label: str
) -> Optional[str]:
    """Find image file based on bbox coordinates.

    PaddleOCR-VL saves cropped images with bbox as filename:
    `{x1}_{y1}_{x2}_{y2}.jpg`

    Args:
        imgs_dir: Directory containing cropped images
        output_dir: Base output directory (for relative path)
        bbox: Bounding box [x1, y1, x2, y2]
        label: Block label (for logging, unused in search)

    Returns:
        Relative path to image file, or None if not found
    """
    x1, y1, x2, y2 = (int(v) for v in bbox)
    pattern = f"*{x1}_{y1}_{x2}_{y2}.jpg"
    files = list(imgs_dir.glob(pattern))
    if files:
        return str(files[0].relative_to(output_dir))
    return None
