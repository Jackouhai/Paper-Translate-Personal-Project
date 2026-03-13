"""Renderer module - Build, translate, and render page data."""

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..policies.translation_policy import should_translate
from ..types import Block, PageData, ProjectData, BlockLabel

if TYPE_CHECKING:
    from ..translators.base import BaseTranslator


# ============== Constants (reused from reconstructor.py) ==============
LABEL_TO_TAG = {
    "doc_title": "h1",
    "paragraph_title": "h2",
    "abstract": "div",
    "formula_number": "span",
}

CENTERED_LABELS = frozenset(
    ["figure_title", "image", "chart", "display_formula", "authors"]
)

VISUAL_LABELS = frozenset({"image", "chart", "table"})
CAPTION_LABELS = frozenset({"figure_title"})
REFERENCE_KEYWORDS = frozenset({"reference", "references", "bibliography"})


# ============== Helper Functions (reused from reconstructor.py) ==============
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


def _translate_text(text: str, label: str, translator: "BaseTranslator") -> str:
    """Translate text with prefix preservation."""
    prefix = ""
    text_to_translate = text

    if label == "abstract" and text.lower().startswith("abstract"):
        prefix = text[:8] + " "
        text_to_translate = text[8:]

    print(f"Translating: {text_to_translate[:50]}...")
    return prefix + translator.translate(text_to_translate)


def _render_caption(block: dict) -> str:
    """Render caption text (already translated)."""
    label = block.get("block_label", "")
    content = block.get("block_content", "").strip()

    if not content:
        return ""

    tag = LABEL_TO_TAG.get(label, "p")
    return f'<{tag} class="{label}">{content}</{tag}>\n'


def render_visual(block: dict, imgs_dir: Path, output_dir: Path) -> str:
    """Render visual block (image, chart, or table)."""
    label = block.get("block_label", "")
    bbox = block.get("block_bbox")
    content = block.get("block_content", "").strip()

    if label in ("image", "chart"):
        img_path = find_image_file(imgs_dir, output_dir, bbox, label)
        if not img_path:
            alt_label = "chart" if label == "image" else "image"
            img_path = find_image_file(imgs_dir, output_dir, bbox, alt_label)
        if img_path:
            return f'<img src="{img_path}" alt="{label}">\n'
        return ""

    if label == "table":
        return f'<div class="table-container">{content}</div>\n'

    return ""


def group_blocks(blocks: list[dict]) -> list[dict]:
    """Group visual blocks with captions into figure groups.

    Rules:
    - Visual (image/chart/table) opens buffer
    - figure_title after visual -> sub-caption
    - Two consecutive figure_titles -> parent caption, close group
    - Other block -> close group if buffer is open
    """
    result = []
    buffer = []
    prev_label = None

    def flush_buffer():
        if not buffer:
            return
        visuals = [b for b in buffer if b["block_label"] in VISUAL_LABELS]
        captions = [b for b in buffer if b["block_label"] in CAPTION_LABELS]
        if visuals:
            result.append(
                {"type": "figure_group", "visuals": visuals, "captions": captions}
            )
        else:
            for b in buffer:
                result.append({"type": "single", "block": b})

    for block in blocks:
        label = block.get("block_label")

        if label in VISUAL_LABELS:
            buffer.append(block)
            prev_label = label
            continue

        if label in CAPTION_LABELS and buffer:
            if prev_label in CAPTION_LABELS:
                # 2 captions consecutively -> parent caption, close group
                buffer.append(block)
                flush_buffer()
                buffer = []
                prev_label = None
            else:
                buffer.append(block)
                prev_label = label
            continue

        # Other block -> close group if buffer open
        flush_buffer()
        buffer = []
        prev_label = None
        result.append({"type": "single", "block": block})

    flush_buffer()
    return result


def render_figure_group(
    group: dict, imgs_dir: Path, output_dir: Path
) -> str:
    """Render a grouped figure with visual(s) and caption(s)."""
    visuals = group["visuals"]
    captions = group["captions"]

    sub_items = []
    parent_caption = None

    if len(captions) > 1 and len(visuals) > 1:
        parent_caption = captions[-1]
        sub_captions = captions[:-1]
    elif len(captions) == 1:
        # 1 caption with any number of visuals -> parent caption
        parent_caption = captions[0]
        sub_captions = []
    elif len(visuals) == 1 and len(captions) == 0:
        # 1 visual, no caption
        parent_caption = None
        sub_captions = []
    else:
        sub_captions = captions
        parent_caption = None

    caption_idx = 0
    for v in visuals:
        sub_cap = None
        if caption_idx < len(sub_captions):
            sub_cap = sub_captions[caption_idx]
            caption_idx += 1
        sub_items.append({"visual": v, "caption": sub_cap})

    html = '<figure class="figure-group">\n'

    if len(sub_items) > 1:
        html += '<div class="figure-row">\n'
        for item in sub_items:
            html += '<div class="sub-figure">\n'
            html += render_visual(item["visual"], imgs_dir, output_dir)
            if item["caption"]:
                html += _render_caption(item["caption"])
            html += "</div>\n"
        html += "</div>\n"
    else:
        item = sub_items[0]
        html += render_visual(item["visual"], imgs_dir, output_dir)

    if parent_caption:
        html += _render_caption(parent_caption)

    html += "</figure>\n"
    return html


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
    """Render blocks to HTML (blocks already translated).

    Args:
        page: PageData with translated blocks
        imgs_dir: Path to images directory
        output_dir: Path to output directory

    Returns:
        HTML string for page blocks
    """
    blocks = page["parsing_res_list"]
    # Sort by block_id
    blocks.sort(key=lambda b: b.get("block_id", float("inf")))

    # Check for reference section
    in_reference = False
    for block in blocks:
        if block.get("block_label") == "paragraph_title":
            title_lower = block.get("block_content", "").lower().strip()
            if any(kw in title_lower for kw in REFERENCE_KEYWORDS):
                in_reference = True
            else:
                in_reference = False
            break

    # Group visual blocks with captions
    grouped = group_blocks(blocks)

    # Render
    html = ""
    for item in grouped:
        if item["type"] == "figure_group":
            html += render_figure_group(item, imgs_dir, output_dir)
        else:
            block = item["block"]
            label = block.get("block_label", "")
            content = block.get("block_content", "").strip()
            bbox = block.get("block_bbox")

            # Check if should skip this block
            action = should_translate(label, content)
            if action == "skip":
                continue

            if in_reference and label == "text":
                label = "reference_content"

            # Skip empty content
            if not content:
                continue

            style_attr = ' style="text-align: center;"' if label in CENTERED_LABELS else ""

            if label in ("image", "chart"):
                img_path = find_image_file(imgs_dir, output_dir, bbox, label)
                if not img_path:
                    alt_label = "chart" if label == "image" else "image"
                    img_path = find_image_file(imgs_dir, output_dir, bbox, alt_label)
                if img_path:
                    html += f'<div class="{label}-container"{style_attr}><img src="{img_path}" alt="{label}"></div>\n'
                continue

            if label == "table":
                html += f'<div class="table-container"{style_attr}>{content}</div>\n'
                continue

            if label == "display_formula":
                # Fix LaTeX escaping: replace \\ with \ for MathJax
                fixed_content = content.replace('\\\\', '\\')
                html += f'<div class="display_formula"{style_attr}>{fixed_content}</div>\n'
                continue

            # Clean heading markers for doc_title and paragraph_title
            display_content = content
            if label in ("doc_title", "paragraph_title"):
                # Remove Markdown heading markers (#, ##, ###)
                display_content = content.lstrip('#').strip()

            # Render text content (already translated)
            tag = LABEL_TO_TAG.get(label, "p")
            html += f'<{tag} class="{label}"{style_attr}>{display_content}</{tag}>\n'

    return html
