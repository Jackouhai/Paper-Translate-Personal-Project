#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_project.py

Input: folder chứa các *_res.json và thư mục imgs/
Chức năng:
  - load tất cả *_res.json
  - (tuỳ chọn) dịch các block bằng translator (nếu có)
  - render từng trang thành HTML fragment (chỉ phần blocks)
  - gán result["html_content"] cho mỗi trang
  - gọi HTMLExporter.export(project_data, output_path)
  - (tuỳ chọn) export từng trang riêng lẻ với --export-pages

Usage:
    python render_project.py /path/to/project_dir --output-suffix v1
    python render_project.py /path/to/project_dir --no-translate --export-pages
    python render_project.py /path/to/project_dir --output-file /tmp/out.html
"""
from __future__ import annotations
import argparse
import json
import re
import html
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Type aliases for standalone script (so we don't rely on relative package imports) ---
Block = Dict[str, Any]
PageData = Dict[str, Any]
ProjectData = Dict[str, Any]
BlockLabel = str

# ======= Config / Labels =======
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


# ======= Helpers (kept logic / escaping as you wrote) =======
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


def build_block(b: Dict, imgs_dir: Path, output_dir: Path) -> str:
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


def build_html(blocks: List[Dict], 
                 imgs_dir : Path, 
                 output_dir: Path
                 ) -> str:
    # fixed: return type string and avoid mutating input list
    new_blocks: List[str] = []

    for b in blocks:
        div = build_block(b, imgs_dir, output_dir)
        new_blocks.append(div)

    return "\n".join(new_blocks)

def escape_inner_html(content: str) -> str:
    m = re.match(r"(<[^>]+>)(.*?)(</[^>]+>)", content, re.DOTALL)
    if not m:
        return html.escape(content)

    start_tag, inner, end_tag = m.groups()

    inner_escaped = html.escape(inner)

    return f"{start_tag}{inner_escaped}{end_tag}"


def render_visual(block: dict, imgs_dir: Path, output_dir: Path) -> str:
    """Render visual block (image, chart, table) with same block layout."""

    label = block.get("block_label", "")
    bbox = block.get("block_bbox", [0,0,0,0])
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

    blocks = page["parsing_res_list"]

    width = page.get("width", PAGE_W)
    height = page.get("height", PAGE_H)

    blocks.sort(key=lambda b: b.get("block_id", float("inf")))

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


# ======= Simple translation policy & translator loader =======
def should_translate(label: str, content: str) -> str:
    if not content or label in VISUAL_LABELS:
        return "skip"
    if len(content.strip()) < 3:
        return "skip"
    return "translate"


class NoOpTranslator:
    def translate_batch(self, texts: List[str]) -> List[str]:
        return texts


def load_translator() -> Any:
    """Thử import translator từ pp_doclayout.translators.gemma."""
    try:
        from pp_doclayout.translators.gemma import GemmaTranslator  # type: ignore
        from pp_doclayout.config import Settings
        config = Settings()
        return GemmaTranslator(
            base_url=config.vllm_base_url,
            model_name=config.vllm_model_name,
            max_tokens=config.vllm_max_tokens,
        )
    except Exception as e:
        print(f"⚠️ Không load được GemmaTranslator: {e}")
        return NoOpTranslator()


# ======= Load HTMLExporter có sẵn =======
# Add src to Python path (render_project.py nằm cùng cấp với thư mục src/)
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pp_doclayout.exporters.html import HTMLExporter


# ======= Export helpers =======
def try_export_with_exporter(exporter_instance: Any, project_data: Dict[str, Any], out_path: Path) -> None:
    """
    Thử gọi exporter.export(project_data, out_path).
    Nếu exporter không có export(), thử các method phổ biến khác; nếu không có thì fallback ghi 1 file HTML tối giản.
    """
    try:
        # chuẩn: exporter.export(project_data, out_path)
        if hasattr(exporter_instance, "export"):
            exporter_instance.export(project_data, out_path)
            return
        # thử tên khác (tùy implementer)
        if hasattr(exporter_instance, "export_project"):
            exporter_instance.export_project(project_data, out_path)
            return
        if hasattr(exporter_instance, "write"):
            exporter_instance.write(project_data, out_path)
            return
    except Exception as e:
        print(f"⚠️ Exporter raised exception: {e} — sẽ fallback ghi file tĩnh.")

    # fallback: ghi HTML tối giản (không đè templates/CSS của bạn)
    pages_html = "\n".join(p.get("html_content", "") for p in project_data.get("pages", []))
    fallback = f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(project_data.get('project_name','doc'))}</title></head><body>{pages_html}</body></html>"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(fallback, encoding="utf-8")
    print(f"⚠️ Exporter không khả dụng — đã ghi fallback HTML -> {out_path}")


def export_each_page_with_exporter(exporter_cls: Any, project_data: Dict[str, Any], out_dir: Path) -> None:
    """
    Xuất từng trang một: với mỗi trang tạo project_data nhỏ {'pages':[page], 'project_name': ...}
    và gọi exporter trên từng file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, page in enumerate(project_data.get("pages", []), start=1):
        single = {"pages": [page], "project_name": f"{project_data.get('project_name','project')}_page{idx}"}
        out_path = out_dir / f"page_{idx}.html"
        exporter_instance = exporter_cls()  # new instance per page
        try:
            try_export_with_exporter(exporter_instance, single, out_path)
            print(f"✓ Exported page {idx} -> {out_path}")
        except Exception as e:
            print(f"✗ Failed export page {idx}: {e}")


# ======= CLI main =======
def main():
    parser = argparse.ArgumentParser(description="Build+translate+render pages, then call existing HTMLExporter.")
    parser.add_argument("project_dir", type=Path, help="Thư mục project (_res.json + imgs/)")
    parser.add_argument("--output-suffix", "-s", default="output", help="Suffix cho tên file html")
    parser.add_argument("--no-translate", action="store_true", help="Không gọi translator")
    parser.add_argument("--output-file", type=Path, default=None, help="File HTML đầu ra (ghi đè output-suffix)")
    parser.add_argument("--export-pages", action="store_true", help="Xuất từng trang riêng lẻ vào thư mục <project>/_pages/")
    args = parser.parse_args()

    project_dir: Path = args.project_dir.resolve()
    if not project_dir.exists() or not project_dir.is_dir():
        raise SystemExit(f"Project dir không tồn tại: {project_dir}")

    print("✓ Build project data...")
    project_data = build_project_data(project_dir)

    if args.no_translate:
        translator = NoOpTranslator()
    else:
        translator = load_translator()

    imgs_dir = project_dir / "imgs"
    if not imgs_dir.exists():
        print("⚠️ Warning: imgs/ không tồn tại. Các block image/chart sẽ không tìm thấy file ảnh.")

    print("✓ Translate pages (nếu có) và render blocks...")
    new_pages = []
    for page in project_data["pages"]:
        translated_page = translate_page_data(page, translator)
        blocks_html = render_page_blocks(translated_page, imgs_dir=imgs_dir, output_dir=project_dir)
        translated_page["html_content"] = blocks_html
        new_pages.append(translated_page)
    project_data["pages"] = new_pages

    # Load user's HTMLExporter (must exist in project environment)
    exporter_instance = HTMLExporter()

    # determine output path
    if args.output_file:
        out_path = args.output_file
    else:
        out_path = project_dir / f"{args.output_suffix}_{project_data.get('project_name','project')}.html"

    print(f"✓ Exporting with HTMLExporter -> {out_path}")
    try_export_with_exporter(exporter_instance, project_data, out_path)

    # optional: export each page
    if args.export_pages:
        pages_dir = project_dir / "_pages"
        print(f"✓ Exporting each page into: {pages_dir}")
        export_each_page_with_exporter(HTMLExporter, project_data, pages_dir)

    print("✓ Done.")


if __name__ == "__main__":
    main()