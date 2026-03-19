import json
import os
from pathlib import Path
import re
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from translator_engine_gemma import get_translator

    print("Initializing TranslateGemma Engine...")
    TRANSLATOR = get_translator()
except Exception as e:
    print(f"Error loading Gemma engine: {e}")
    import traceback

    traceback.print_exc()
    TRANSLATOR = None

BASE_DIR = Path("/home/bocchi/Work/PP_DocLayout")

VISUAL_LABELS = {"image", "chart", "table"}
CAPTION_LABELS = {"figure_title", "table_caption"}
SKIP_LABELS = {"aside_text", "header", "footer", "number", "content"}
NO_TRANSLATE_LABELS = {
    "doc_title",
    "paragraph_title",
    "reference_content",
    "footnote",
    "vision_footnote",
    "table",
    "image",
    "chart",
    "display_formula",
    "formula_number",
}
TRANSLATE_LABELS = {"abstract", "text", "figure_title", "table_caption"}
REFERENCE_KEYWORDS = {"reference", "references", "bibliography"}
TAG_MAP = {
    "doc_title": "h1",
    "paragraph_title": "h2",
    "abstract": "div",
    "formula_number": "span",
}


def find_image_file(imgs_dir, output_dir, bbox, label):
    x1, y1, x2, y2 = [int(val) for val in bbox]
    pattern = f"*{x1}_{y1}_{x2}_{y2}.jpg"
    files = list(imgs_dir.glob(pattern))
    if files:
        return os.path.relpath(files[0], output_dir)
    return None


def translate_text(text, label):
    if not text:
        return ""
    prefix = ""
    text_to_translate = text
    if label == "abstract" and text.lower().startswith("abstract"):
        prefix = text[:8] + " "
        text_to_translate = text[8:]
    if TRANSLATOR:
        print(f"Gemma Translating: {text_to_translate[:50]}...")
        return prefix + TRANSLATOR.translate(text_to_translate)
    return f"(Gemma-Dịch) {text}"


def should_translate(label, content):
    if label in SKIP_LABELS:
        return "skip"
    # Skip paragraph_title with content "content"
    if label == "paragraph_title" and content.strip().lower() == "contents":
        return "skip"
    if label in NO_TRANSLATE_LABELS:
        return "keep"
    if label in TRANSLATE_LABELS:
        words = content.strip().split()
        if len(words) < 5 and label == "text" and "@" not in content:
            return "keep"
        if "@" in content:
            return "keep"
        return "translate"
    return "keep"


def group_blocks(blocks):
    """
    Duyệt tuần tự theo block_id, gom visual + caption thành figure groups.

    Rule:
    - Gặp visual (image/chart/table) → mở buffer
    - Gặp figure_title sau visual → sub-caption, thêm vào buffer
    - Gặp figure_title sau figure_title → parent caption, đóng group
    - Gặp block khác → đóng group nếu buffer đang mở
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
                # 2 caption liên tiếp → cái này là parent → đóng group
                buffer.append(block)
                flush_buffer()
                buffer = []
                prev_label = None
            else:
                buffer.append(block)
                prev_label = label
            continue

        # Block khác → đóng group nếu đang mở
        flush_buffer()
        buffer = []
        prev_label = None
        result.append({"type": "single", "block": block})

    flush_buffer()
    return result


def _render_caption(text, label):
    action = should_translate(label, text)
    if action == "translate":
        return translate_text(text, label)
    return text


def render_figure_group(group, imgs_dir, project_dir):
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
            html += render_visual(item["visual"], imgs_dir, project_dir)
            if item["caption"]:
                cap_text = item["caption"].get("block_content", "").strip()
                cap_label = item["caption"]["block_label"]
                html += f'<figcaption class="sub-caption">{_render_caption(cap_text, cap_label)}</figcaption>\n'
            html += "</div>\n"
        html += "</div>\n"
    else:
        item = sub_items[0]
        html += render_visual(item["visual"], imgs_dir, project_dir)

    if parent_caption:
        cap_text = parent_caption.get("block_content", "").strip()
        cap_label = parent_caption["block_label"]
        html += f"<figcaption>{_render_caption(cap_text, cap_label)}</figcaption>\n"

    html += "</figure>\n"
    return html


def render_visual(block, imgs_dir, project_dir):
    label = block["block_label"]
    content = block.get("block_content", "").strip()
    bbox = block["block_bbox"]

    if label in ("image", "chart"):
        img_path = find_image_file(imgs_dir, project_dir, bbox, label)
        if not img_path:
            alt_label = "chart" if label == "image" else "image"
            img_path = find_image_file(imgs_dir, project_dir, bbox, alt_label)
        if img_path:
            return f'<img src="{img_path}" alt="{label}">\n'
        return ""

    if label == "table":
        return f'<div class="table-container">{content}</div>\n'

    return ""


def render_single_block(block, imgs_dir, project_dir, in_reference=False):
    label = block.get("block_label")
    content = block.get("block_content", "").strip()
    bbox = block.get("block_bbox")

    if in_reference and label == "text":
        label = "reference_content"

    action = should_translate(label, content)
    if action == "skip":
        return ""

    style_attr = (
        ' style="text-align: center;"'
        if label in ("figure_title", "table_caption", "display_formula")
        else ""
    )

    if label in ("image", "chart"):
        img_path = find_image_file(imgs_dir, project_dir, bbox, label)
        if not img_path:
            alt_label = "chart" if label == "image" else "image"
            img_path = find_image_file(imgs_dir, project_dir, bbox, alt_label)
        if img_path:
            return f'<div class="{label}-container"{style_attr}><img src="{img_path}" alt="{label}"></div>\n'
        return ""

    if label == "table":
        return f'<div class="table-container"{style_attr}>{content}</div>\n'

    if label == "display_formula":
        return f'<div class="display_formula"{style_attr}>$${content}$$</div>\n'

    display_text = translate_text(content, label) if action == "translate" else content
    tag = TAG_MAP.get(label, "p")
    return f'<{tag} class="{label}"{style_attr}>{display_text}</{tag}>\n'


def process_project(project_name):
    project_name = Path(project_name).name
    project_dir = BASE_DIR / "output" / project_name
    imgs_dir = project_dir / "imgs"
    html_output = project_dir / f"translated_{project_name}_gemma.html"

    if not project_dir.exists():
        print(f"Lỗi: Không tìm thấy thư mục {project_dir}")
        return

    json_files = sorted(
        project_dir.glob("*_res.json"),
        key=lambda x: int(re.search(r"_(\d+)_res", x.name).group(1)),  # type: ignore[union-attr]
    )

    html_pages_content = ""
    in_reference = False

    for json_path in json_files:
        page_num = re.search(r"_(\d+)_res", json_path.name).group(1)  # type: ignore[union-attr]
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        blocks = data.get("parsing_res_list", [])
        grouped = group_blocks(blocks)

        page_blocks_html = ""

        for item in grouped:
            if item["type"] == "figure_group":
                page_blocks_html += render_figure_group(item, imgs_dir, project_dir)
            else:
                block = item["block"]
                label = block.get("block_label", "")
                content = block.get("block_content", "").strip()

                if label == "paragraph_title":
                    title_lower = content.lower().strip()
                    if any(kw in title_lower for kw in REFERENCE_KEYWORDS):
                        in_reference = True
                    else:
                        in_reference = False

                page_blocks_html += render_single_block(
                    block, imgs_dir, project_dir, in_reference
                )

        if not page_blocks_html.strip():
            continue

        page_html = f'<div class="paper-page" id="page-{page_num}">\n'
        page_html += f'<div class="page-number">Trang {int(page_num) + 1}</div>\n'
        page_html += page_blocks_html
        page_html += "</div>\n"
        html_pages_content += page_html

    mathjax_config = "<script>window.MathJax = {tex: {inlineMath: [['$', '$'], ['\\\\(', '\\\\)']], displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']], processEscapes: true}};</script>"
    style_content = """
    <style>
        body { font-family: 'Times New Roman', serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; background: #e0e0e0; }
        .paper-page { background: white; padding: 60px; box-shadow: 0 0 15px rgba(0,0,0,0.2); margin-bottom: 30px; position: relative; min-height: 1100px; }
        .page-number { position: absolute; top: 20px; right: 20px; font-size: 12px; color: #ccc; }
        .doc_title { font-size: 26px; font-weight: bold; text-align: center; margin-bottom: 25px; }
        .paragraph_title { font-size: 18px; font-weight: bold; margin-top: 20px; border-bottom: 1px solid #eee; }
        .abstract { font-style: italic; margin: 20px 40px; text-align: justify; border-left: 4px solid #ddd; padding: 10px; background: #fdfdfd; }
        .text { text-align: justify; margin-bottom: 10px; text-indent: 1.5em; }
        .reference_content, .footnote { font-size: 12px; margin-bottom: 5px; padding-left: 25px; text-indent: -25px; }
        img { max-width: 100%; height: auto; }
        .figure-group { margin: 20px 0; text-align: center; }
        .figure-group figcaption { font-size: 13px; font-weight: bold; font-style: italic; color: #444; margin-top: 8px; }
        .figure-row { display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; }
        .sub-figure { flex: 1; min-width: 200px; text-align: center; }
        .sub-figure img { max-width: 100%; height: auto; }
        .sub-caption { font-size: 12px; font-style: italic; color: #555; margin-top: 4px; }
        .table-container { margin: 20px 0; overflow-x: auto; }
        table { border-collapse: collapse; width: 100%; font-size: 12px; }
        th, td { border: 1px solid #444; padding: 6px; text-align: left; }
        .display_formula { margin: 15px 0; text-align: center; }
        .figure_title, .table_caption { font-size: 13px; font-weight: bold; margin: 10px 0; font-style: italic; color: #444; text-align: center; }
    </style>
    """
    full_html = f"<html><head><meta charset='UTF-8'><title>Gemma Translated {project_name}</title>{mathjax_config}<script id='MathJax-script' async src='https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js'></script>{style_content}</head><body>{html_pages_content}</body></html>"

    with open(html_output, "w", encoding="utf-8") as f:
        f.write(full_html)
    print(f"Success! Saved to: {html_output}")


if __name__ == "__main__":
    proj = sys.argv[1] if len(sys.argv) > 1 else "nougat"
    process_project(proj)
