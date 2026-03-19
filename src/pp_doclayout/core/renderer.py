"""Renderer module - Build, translate, and render page data."""

import json
import re
import html
from pathlib import Path
from typing import TYPE_CHECKING

from ..policies.translation_policy import should_translate
from ..types import Block, PageData, ProjectData, BlockLabel

if TYPE_CHECKING:
    from ..translators.base import BaseTranslator


# ============== Constants ==============
LABEL_TO_TAG = {
    "doc_title": "h1",
    "paragraph_title": "h2",
    "abstract": "div",
    "formula_number": "span",
}

TITLE_LABELS = frozenset({"doc_title", "paragraph_title"})
FOOTNOTE_LABELS = frozenset({"footnote"})
HTML_WRAPPER_LABELS = frozenset({
    "figure_title", "display_formula", "authors",
    "vision_footnote", "abstract", "table_caption"
})
ALGORITHM_LABELS = frozenset({
    "algorithm"
})

VISUAL_LABELS = frozenset({"image", "chart", "table"})
REFERENCE_KEYWORDS = frozenset({"reference", "references", "bibliography"})
PAGE_W = 1224
PAGE_H = 1584


# ============== Helper Functions ==============
def find_image_file(
    imgs_dir: Path, output_dir: Path, bbox: list, label: str
) -> str | None:
    """Image detection based on bbox."""
    x1, y1, x2, y2 = (int(v) for v in bbox)
    pattern = f"*{x1}_{y1}_{x2}_{y2}.jpg"
    files = list(imgs_dir.glob(pattern))
    if files:
        return str(files[0].relative_to(output_dir))
    return None


def escape_inner_html(content: str) -> str:
    """Escape inner HTML content while preserving outer tags."""
    m = re.match(r"(<[^>]+>)(.*?)(</[^>]+>)", content, re.DOTALL)
    if not m:
        return html.escape(content)

    start_tag, inner, end_tag = m.groups()
    inner_escaped = html.escape(inner)
    return f"{start_tag}{inner_escaped}{end_tag}"


def build_block(b: dict, imgs_dir: Path, output_dir: Path) -> str:
    """Build a single block div with absolute positioning.

    Args:
        b: Block data dictionary
        imgs_dir: Path to images directory
        output_dir: Path to output directory

    Returns:
        HTML string for block
    """
    bbox = b.get("block_bbox")
    x1, y1, x2, y2 = bbox

    left = int(x1)
    top = int(y1)
    width = int(x2 - x1)
    height = int(y2 - y1)

    label = b.get("block_label")
    tag = LABEL_TO_TAG.get(label, "div")

    if label in VISUAL_LABELS:
        return render_visual(b, imgs_dir, output_dir)

    content = b.get("block_content", "").strip()
    inner = ""

    if label in TITLE_LABELS:
        content = content.strip("#").strip()

    if label in FOOTNOTE_LABELS:
        inner = content
    elif label in HTML_WRAPPER_LABELS:
        inner = escape_inner_html(content)
    else:
        inner = html.escape(content)

    div = (
        f'<{tag} class="block {label} auto-fit" '
        f'style="left:{left}px;top:{top}px;width:{width}px;height:{height}px;">'
        f'{inner}'
        f'</{tag}>'
    )

    return div


def build_html(blocks: list[dict], imgs_dir: Path, output_dir: Path) -> str:
    """Build HTML from blocks using absolute positioning.

    Args:
        blocks: List of block dictionaries
        imgs_dir: Path to images directory
        output_dir: Path to output directory

    Returns:
        HTML string joining all block divs
    """
    new_blocks = []

    for b in blocks:
        div = build_block(b, imgs_dir, output_dir)
        new_blocks.append(div)

    return "\n".join(new_blocks)


def render_visual(block: dict, imgs_dir: Path, output_dir: Path) -> str:
    """Render visual block (image, chart, table) with absolute positioning."""
    label = block.get("block_label", "")
    bbox = block.get("block_bbox", [0, 0, 0, 0])
    content = block.get("block_content", "").strip()

    x1, y1, x2, y2 = bbox

    left = int(x1)
    top = int(y1)
    width = int(x2 - x1)
    height = int(y2 - y1)

    inner = ""

    if label in ("image", "chart"):
        img_path = find_image_file(imgs_dir, output_dir, bbox, label)

        if not img_path:
            alt_label = "chart" if label == "image" else "image"
            img_path = find_image_file(imgs_dir, output_dir, bbox, alt_label)

        if img_path:
            inner = f'<img src="{img_path}" alt="{label}">'

    elif label == "table":
        inner = f'<div class="table-container">{content}</div>'

    else:
        return ""

    div = (
        f'<div class="block {label}" '
        f'style="left:{left}px;top:{top}px;width:{width}px;height:{height}px;">'
        f'{inner}'
        f'</div>\n'
    )

    return div


# ============== Main Functions ==============
def build_project_data(project_dir: Path) -> ProjectData:
    """Load JSON files and build ProjectData structure.

    Returns:
        ProjectData with pages list and project_name
    """
    project_name = project_dir.name
    json_files = sorted(
        project_dir.glob("*_res.json"),
        key=lambda x: (lambda m: int(m.group(1)) if m else 0)(
            re.search(r"_(\d+)_res", x.name)
        ),
    )

    if not json_files:
        raise FileNotFoundError(f"No *_res.json files found in {project_dir}")

    pages = []
    for json_path in json_files:
        with open(json_path, "r", encoding="utf-8") as f:
            page_data: PageData = json.load(f)
            pages.append(page_data)

    return {"pages": pages, "project_name": project_name}


def translate_page_data(page: PageData, translator: "BaseTranslator") -> PageData:
    """Translate blocks in a page using batch translation.

    Args:
        page: PageData with blocks to translate
        translator: Translator instance with translate_batch() method

    Returns:
        PageData with translated blocks
    """
    result: PageData = dict(page)  # Copy

    # Collect blocks to translate with their prefixes
    blocks_info = []
    for idx, block in enumerate(result["parsing_res_list"]):
        label = block["block_label"]
        content = block["block_content"].strip()

        action = should_translate(label, content)
        if action == "translate":
            # Handle prefix preservation (e.g., "Abstract")
            prefix = ""
            text_to_translate = content

            if label == "abstract" and content.lower().startswith("abstract"):
                prefix = content[:8] + " "
                text_to_translate = content[8:]

            blocks_info.append({
                "idx": idx,
                "prefix": prefix,
                "text_to_translate": text_to_translate,
            })

    # Batch translate all texts
    if blocks_info:
        texts = [b["text_to_translate"] for b in blocks_info]
        translations = translator.translate_batch(texts)

        # Update blocks with translations
        for block_info, translated in zip(blocks_info, translations):
            if translated:
                # Add prefix back if needed
                full_translation = block_info["prefix"] + translated
                result["parsing_res_list"][block_info["idx"]]["block_content"] = full_translation

    return result


def render_page_blocks(
    page: PageData,
    imgs_dir: Path,
    output_dir: Path,
) -> str:
    """Render page blocks to HTML using absolute positioning.

    Args:
        page: PageData with blocks to render
        imgs_dir: Path to images directory
        output_dir: Path to output directory

    Returns:
        HTML string for all blocks
    """
    blocks = page["parsing_res_list"]
    width = page.get("width", PAGE_W)
    height = page.get("height", PAGE_H)

    # Sort by block_id to maintain order
    blocks.sort(key=lambda b: b.get("block_id", float("inf")))

    # Render ALL blocks (no filtering)
    html_blocks = build_html(blocks, imgs_dir=imgs_dir, output_dir=output_dir)

    page_html = f"""
    <div class="page-container">
        <div class="page"
            style="width:{width}px;height:{height}px;">
            {html_blocks}
        </div>
    </div>
    """

    return page_html
