import json
import os
import re
from collections import defaultdict
from html import unescape
from pathlib import Path

from lxml import etree, html


def normalize_bbox(bbox, page_width=1224, page_height=1584):
    x = bbox.get("x", 0)
    y = bbox.get("y", 0)
    width = bbox.get("width", 0)
    height = bbox.get("height", 0)

    if 0 <= x <= 1 and 0 <= y <= 1 and 0 <= width <= 1 and 0 <= height <= 1:
        return {"x": x, "y": y, "width": width, "height": height}

    return {
        "x": x / page_width,
        "y": y / page_height,
        "width": width / page_width,
        "height": height / page_height,
    }


def _norm_text(s: str) -> str:
    if s is None:
        return ""
    s = unescape(str(s))
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _strip_latex_cmds(s: str) -> str:
    if not s:
        return ""
    # remove common table formatting commands
    s = re.sub(r"\\(toprule|midrule|bottomrule|hline|cline\{[^}]*\})", "", s)
    # remove text formatting wrappers: \textbf{X} -> X
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\textit\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", s)
    s = s.replace("\\methodshort", "method")
    s = s.replace("\\%", "%")
    s = s.replace("\\downarrow", "↓")
    return _norm_text(s)


def latex_tabular_to_html(latex: str) -> str:
    """
    Very lightweight converter for:
    \\begin{tabular}{...} ... \\\\ ... \\end{tabular}
    """
    if not latex:
        return "<table></table>"

    m = re.search(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}", latex, flags=re.S)
    content = m.group(1) if m else latex

    # remove table rule commands
    content = re.sub(r"\\(toprule|midrule|bottomrule|hline|cline\{[^}]*\})", "", content)
    content = content.strip()

    # split rows by \\ not followed by letters (avoid breaking commands)
    rows = re.split(r"\\\\", content)
    out_table = etree.Element("table")

    for row in rows:
        row = row.strip()
        if not row:
            continue
        tr = etree.SubElement(out_table, "tr")
        cells = [c.strip() for c in row.split("&")]
        for c in cells:
            td = etree.SubElement(tr, "td")
            td.text = _strip_latex_cmds(c)

    return etree.tostring(out_table, encoding="unicode", method="html", with_tail=False)


def canonicalize_table_html(raw_html: str) -> str:
    if not raw_html:
        return "<table></table>"

    parser = html.HTMLParser(remove_comments=True, encoding="utf-8")

    try:
        root = html.fromstring(raw_html, parser=parser)
    except Exception:
        txt = _norm_text(raw_html)
        return f"<table><tr><td>{txt}</td></tr></table>"

    table = root if getattr(root, "tag", None) == "table" else (root.xpath("//table")[0] if root.xpath("//table") else None)

    if table is None:
        txt = _norm_text(root.text_content() if hasattr(root, "text_content") else raw_html)
        return f"<table><tr><td>{txt}</td></tr></table>"

    out_table = etree.Element("table")

    rows = table.xpath("./tbody/tr") or table.xpath("./tr") or table.xpath(".//tr")
    for tr_node in rows:
        tr = etree.SubElement(out_table, "tr")
        for c in tr_node.xpath("./th|./td"):
            td = etree.SubElement(tr, "td")
            rs = c.attrib.get("rowspan")
            cs = c.attrib.get("colspan")
            if rs and rs.isdigit() and int(rs) > 1:
                td.set("rowspan", str(int(rs)))
            if cs and cs.isdigit() and int(cs) > 1:
                td.set("colspan", str(int(cs)))
            td.text = _norm_text(c.text_content())

    return etree.tostring(out_table, encoding="unicode", method="html", with_tail=False)


def normalize_table_content(raw: str) -> str:
    s = (raw or "").strip()
    # latex tabular case
    if "\\begin{tabular}" in s and "\\end{tabular}" in s:
        return canonicalize_table_html(latex_tabular_to_html(s))
    # already html (or html-like)
    return canonicalize_table_html(s)


def parse_label_studio_json(input_file, output_file=None, page_width=1224, page_height=1584):
    with open(input_file, "r", encoding="utf-8") as f:
        raw = json.load(f)

# Normalize về list[dict] tasks
    if isinstance(raw, list):
        data = raw
    elif isinstance(raw, dict):
        if "tasks" in raw and isinstance(raw["tasks"], list):
            data = raw["tasks"]              # case {"tasks":[...]}
        elif "annotations" in raw:           # case 1 task object
            data = [raw]
        else:
            # fallback: lấy value nào là list các dict
            candidate = None
            for v in raw.values():
                if isinstance(v, list) and all(isinstance(x, dict) for x in v):
                    candidate = v
                    break
            if candidate is None:
                raise ValueError(f"Unsupported JSON structure in {input_file}")
            data = candidate
    else:
        raise ValueError(f"Unsupported root type: {type(raw)} in {input_file}")
    pages_dict = defaultdict(list)
    file_name = None

    for task in data:
        file_name = task.get("file_upload", "unknown")
        annotations = task.get("annotations", [])

        for annotation in annotations:
            results = annotation.get("result", [])

            for result in results:
                if result.get("type") != "ocrlabels":
                    continue

                value = result.get("value", {})
                meta = result.get("meta", {})
                page_index = value.get("pageIndex", 1) 

                order_list = meta.get("text", [])
                order = order_list[0] if order_list and order_list[0] != "null" else None

                labels = value.get("ocrlabels", [])
                label = labels[0] if labels else None

                content = value.get("ocrtext", "")
                if str(label).strip().lower() == "table":
                    content = normalize_table_content(content)

                bbox = {
                    "x": value.get("x"),
                    "y": value.get("y"),
                    "width": value.get("width"),
                    "height": value.get("height"),
                }

                block = {
                    "id": result.get("id"),
                    "order": order,
                    "bounding_box": normalize_bbox(bbox, page_width, page_height),
                    "block_content": content,
                    "label": label,
                }

                pages_dict[page_index].append(block)

    pages = [{"page_index": i, "blocks": pages_dict[i]} for i in sorted(pages_dict.keys())]
    result = {"file_name": file_name, "pages": pages}

    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"✅ Saved to {output_file}")

    return result


def batch_parse_label_studio(input_dir="data/raw_gt", output_dir="data/gt", prefix=None, page_width=1224, page_height=1584):
    os.makedirs(output_dir, exist_ok=True)

    pattern = "*.json" if not prefix else f"{prefix}*.json"
    input_files = sorted(Path(input_dir).glob(pattern), key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)

    if not input_files:
        print(f'⚠️  No files found matching pattern "{pattern}" in {input_dir}')
        return

    print(f"📂 Found {len(input_files)} files to process")
    for input_file in input_files:
        output_file = os.path.join(output_dir, f"gt_{input_file.stem}.json")
        try:
            print(f"⏳ Processing {input_file.name}...")
            parse_label_studio_json(str(input_file), output_file, page_width, page_height)
            print(f"   ✅ Success: {output_file}")
        except Exception as e:
            print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    batch_parse_label_studio(input_dir="data/raw_gt", output_dir="data/gt")