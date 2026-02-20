import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from ..policies.translation_policy import should_translate
from .batch_processor import BatchProcessor

if TYPE_CHECKING:
    from ..translators.base import BaseTranslator


class _CachedTranslator:
    """Wrapper that caches translations for batch mode."""
    
    def __init__(self, translator: "BaseTranslator", cache: dict):
        self.translator = translator
        self.cache = cache
    
    def translate(self, text: str) -> str:
        if text in self.cache:
            return self.cache[text]
        result = self.translator.translate(text)
        self.cache[text] = result
        return result


LABEL_TO_TAG = {
    "doc_title": "h1",
    "paragraph_title": "h2",
    "abstract": "div",
    "formula_number": "span",
}

CENTERED_LABELS = frozenset(
    ["figure_title", "table_caption", "image", "chart", "display_formula", "authors"]
)

VISUAL_LABELS = frozenset({"image", "chart", "table"})
CAPTION_LABELS = frozenset({"figure_title", "table_caption"})
REFERENCE_KEYWORDS = frozenset({"reference", "references", "bibliography"})


def find_image_file(
    imgs_dir: Path, output_dir: Path, bbox: list, label: str
) -> str | None:
    """
    Image detection based on bbox

    Returns: File Path
    """
    x1, y1, x2, y2 = (int(v) for v in bbox)
    pattern = f"*{x1}_{y1}_{x2}_{y2}.jpg"
    files = list(imgs_dir.glob(pattern))
    if files:
        return str(files[0].relative_to(output_dir))
    return None


def _translate_text(text: str, label: str, translator: "BaseTranslator") -> str:
    if not text:
        return ""

    prefix = ""
    text_to_translate = text

    if label == "abstract" and text.lower().startswith("abstract"):
        prefix = text[:8] + " "
        text_to_translate = text[8:]

    print(f"Translating: {text_to_translate[:50]}...")
    return prefix + translator.translate(text_to_translate)


def _render_block(
    block: dict,
    imgs_dir: Path,
    output_dir: Path,
    translator: "BaseTranslator",
    in_reference: bool = False,
) -> str:
    label = block.get("block_label", "")
    content = block.get("block_content", "").strip()
    bbox = block.get("block_bbox")

    if in_reference and label == "text":
        label = "reference_content"

    action = should_translate(label, content)
    if action == "skip":
        return ""

    style_attr = ' style="text-align: center;"' if label in CENTERED_LABELS else ""

    if label in ("image", "chart"):
        img_path = find_image_file(imgs_dir, output_dir, bbox, label)
        if not img_path:
            alt_label = "chart" if label == "image" else "image"
            img_path = find_image_file(imgs_dir, output_dir, bbox, alt_label)
        if img_path:
            return f'<div class="{label}-container"{style_attr}><img src="{img_path}" alt="{label}"></div>\n'
        return ""

    if label == "table":
        return f'<div class="table-container"{style_attr}>{content}</div>\n'

    if label == "display_formula":
        return f'<div class="display_formula"{style_attr}>$${content}$$</div>\n'

    display_text = (
        _translate_text(content, label, translator)
        if action == "translate"
        else content
    )
    tag = LABEL_TO_TAG.get(label, "p")
    return f'<{tag} class="{label}"{style_attr}>{display_text}</{tag}>\n'


def group_blocks(blocks: list[dict]) -> list[dict]:
    """
    Duyệt tuần tự theo block_id, gom visual + caption thành figure groups.

    Rule:
    - Gặp visual (image/chart/table) -> mở buffer
    - Gặp figure_title sau visual -> sub-caption, thêm vào buffer
    - Gặp figure_title -> parent caption, đóng group
    - Gặp block khác -> đóng group nếu buffer đang mở
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
                # 2 caption liên tiếp -> cái này là parent -> đóng group
                buffer.append(block)
                flush_buffer()
                buffer = []
                prev_label = None
            else:
                buffer.append(block)
                prev_label = label
            continue

        # Block khác -> đóng group nếu đang mở
        flush_buffer()
        buffer = []
        prev_label = None
        result.append({"type": "single", "block": block})

    flush_buffer()
    return result


def _render_caption(block: dict, translator: "BaseTranslator") -> str:
    """Render caption text with translation."""
    label = block.get("block_label", "")
    content = block.get("block_content", "").strip()

    action = should_translate(label, content)
    if action == "skip":
        return ""

    display_text = (
        _translate_text(content, label, translator)
        if action == "translate"
        else content
    )

    tag = LABEL_TO_TAG.get(label, "p")
    return f'<{tag} class="{label}">{display_text}</{tag}>\n'


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


def render_figure_group(
    group: dict, imgs_dir: Path, output_dir: Path, translator: "BaseTranslator"
) -> str:
    """Render a grouped figure with visual(s) and caption(s)."""
    visuals = group["visuals"]
    captions = group["captions"]

    sub_items = []
    parent_caption = None

    if len(captions) > 1 and len(visuals) > 1:
        parent_caption = captions[-1]
        sub_captions = captions[:-1]
    elif len(captions) == 1 and len(visuals) == 1:
        parent_caption = captions[0]
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
                html += _render_caption(item["caption"], translator)
            html += "</div>\n"
        html += "</div>\n"
    else:
        item = sub_items[0]
        html += render_visual(item["visual"], imgs_dir, output_dir)

    if parent_caption:
        html += _render_caption(parent_caption, translator)

    html += "</figure>\n"
    return html


def _render_page(
    json_path: Path,
    imgs_dir: Path,
    output_dir: Path,
    translator: "BaseTranslator",
    in_reference: bool,
) -> str:
    match = re.search(r"_(\d+)_res", json_path.name)
    if not match:
        return ""
    page_num = match.group(1)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    blocks = data.get("parsing_res_list", [])
    # Sort by block_id (not bbox) to preserve JSON order
    blocks.sort(key=lambda b: b.get("block_id", float("inf")))

    # Check for reference section heading
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

    # Build page HTML buffer for empty page skip
    page_blocks_html = ""

    for item in grouped:
        if item["type"] == "figure_group":
            page_blocks_html += render_figure_group(
                item, imgs_dir, output_dir, translator
            )
        else:
            block = item["block"]
            page_blocks_html += _render_block(
                block, imgs_dir, output_dir, translator, in_reference
            )

    # Skip empty pages
    if not page_blocks_html.strip():
        return ""

    page_html = f'<div class="paper-page" id="page-{page_num}">\n'
    page_html += f'<div class="page-number">Trang {int(page_num) + 1}</div>\n'
    page_html += page_blocks_html
    page_html += "</div>\n"
    return page_html


STYLE = """\
<style>
    body { font-family: 'Times New Roman', serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; background: #e0e0e0; }
    .paper-page { background: white; padding: 60px; box-shadow: 0 0 15px rgba(0,0,0,0.2); margin-bottom: 30px; position: relative; min-height: 1100px; }
    .page-number { position: absolute; top: 20px; right: 20px; font-size: 12px; color: #ccc; }
    .doc_title { font-size: 26px; font-weight: bold; text-align: center; margin-bottom: 25px; color: #000; }
    .paragraph_title { font-size: 18px; font-weight: bold; margin-top: 25px; margin-bottom: 10px; color: #111; border-bottom: 1px solid #eee; }
    .figure_title, .table_caption { font-size: 13px; font-weight: bold; margin: 10px 0; font-style: italic; color: #444; text-align: center; }
    .abstract { font-style: italic; margin: 20px 40px; text-align: justify; border-left: 4px solid #ddd; padding-left: 15px; background: #fdfdfd; padding: 10px; }
    .text { text-align: justify; margin-bottom: 10px; text-indent: 1.5em; }
    .reference_content, .footnote, .vision_footnote { font-size: 12px; margin-bottom: 5px; padding-left: 25px; text-indent: -25px; color: #333; }
    .table-container { margin: 20px 0; overflow-x: auto; }
    table { border-collapse: collapse; width: 100%; font-size: 12px; }
    th, td { border: 1px solid #444; padding: 6px; text-align: left; }
    .image-container, .chart-container { margin: 20px 0; }
    img { max-width: 100%; height: auto; }
    .display_formula { margin: 15px 0; }
    .figure-group { margin: 20px 0; text-align: center; }
    .figure-group figcaption { font-size: 13px; font-weight: bold; font-style: italic; color: #444; margin-top: 8px; }
    .figure-row { display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; }
    .sub-figure { flex: 1; min-width: 200px; text-align: center; }
    .sub-figure img { max-width: 100%; height: auto; }
    .sub-caption { font-size: 12px; font-style: italic; color: #555; margin-top: 4px; }
</style>"""

MATHJAX_CONFIG = """\
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
    processEscapes: true
  }
};
</script>
<script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>"""


def process_project(
    project_dir: Path,
    translator: "BaseTranslator",
    output_suffix: str = "translated",
) -> Path:
    imgs_dir = project_dir / "imgs"
    project_name = project_dir.name
    html_output = project_dir / f"{output_suffix}_{project_name}.html"

    json_files = sorted(
        project_dir.glob("*_res.json"),
        key=lambda x: (lambda m: int(m.group(1)) if m else 0)(
            re.search(r"_(\d+)_res", x.name)
        ),
    )

    if not json_files:
        raise FileNotFoundError(f"No *_res.json files found in {project_dir}")

    # Initialize reference state before processing pages
    in_reference = False

    pages_html = "".join(
        _render_page(jp, imgs_dir, project_dir, translator, in_reference)
        for jp in json_files
    )

    full_html = (
        f"<html>\n<head>\n"
        f'<meta charset="UTF-8">\n'
        f"<title>Bản dịch {project_name}</title>\n"
        f"{MATHJAX_CONFIG}\n"
        f"{STYLE}\n"
        f"</head>\n<body>\n"
        f"{pages_html}"
        f"</body>\n</html>\n"
    )

    html_output.write_text(full_html, encoding="utf-8")
    print(f"Saved: {html_output}")
    return html_output
