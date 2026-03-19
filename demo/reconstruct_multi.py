import json
import os
from pathlib import Path
import re
import sys
import traceback

# Thêm đường dẫn thư mục hiện tại vào sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from translator_engine import get_translator
    print("Initializing Translation Engine (this may take a minute)...")
    TRANSLATOR = get_translator()
except Exception as e:
    print(f"Warning: Could not import translation engine: {e}")
    traceback.print_exc()
    TRANSLATOR = None

# Cấu hình đường dẫn cơ bản
BASE_DIR = Path("/home/bocchi/Work/PP_DocLayout")

def find_image_file(imgs_dir, output_dir, bbox, label):
    x1, y1, x2, y2 = [int(val) for val in bbox]
    pattern = f"*{x1}_{y1}_{x2}_{y2}.jpg"
    files = list(imgs_dir.glob(pattern))
    if files:
        return os.path.relpath(files[0], output_dir)
    return None

def mock_translate_llm(text, label):
    # Hàm này giờ đóng vai trò là hàm gọi thực tế
    if not text: return ""
    
    # Xử lý đặc biệt cho Abstract
    prefix = ""
    text_to_translate = text
    
    if label == "abstract":
        if text.lower().startswith("abstract"):
            prefix = text[:8] + " "
            text_to_translate = text[8:]
    
    if TRANSLATOR:
        print(f"Translating: {text_to_translate[:50]}...")
        translated = TRANSLATOR.translate(text_to_translate)
        return prefix + translated
    else:
        return f"(Dịch) {text}"

def should_translate(block):
    label = block.get("block_label")
    content = block.get("block_content", "").strip()
    
    # 1. Các nhãn TUYỆT ĐỐI KHÔNG dịch
    if label in [
        "doc_title", "paragraph_title", "reference_content", 
        "footnote", "vision_footnote",
        "table", "image", "chart", "display_formula", "formula_number", "figure_title"
    ]:
        return False
        
    # 2. Loại bỏ hoàn toàn khỏi HTML
    if label in ["aside_text", "header", "footer", "number","content"]:
        return "SKIP"

    # 3. Các nhãn CÓ dịch
    if label in ["abstract", "text", "table_caption"]:
        words = content.split()
        if len(words) < 5 and label == "text" and "@" not in content:
            return False
        if "@" in content:
            return False
        return True

    return False

def process_project(project_name):
    # Đảm bảo lấy đúng tên thư mục dù người dùng truyền vào đường dẫn
    project_name = Path(project_name).name
    project_dir = BASE_DIR / "output" / project_name
    imgs_dir = project_dir / "imgs"
    html_output = project_dir / f"translated_{project_name}_final.html"
    
    if not project_dir.exists():
        print(f"Lỗi: Không tìm thấy thư mục {project_dir}")
        return

    json_files = sorted(list(project_dir.glob("*_res.json")), 
                        key=lambda x: int(re.search(r'_(\d+)_res', x.name).group(1)))
    
    html_pages_content = ""

    for json_path in json_files:
        page_num = re.search(r'_(\d+)_res', json_path.name).group(1)
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        blocks = data.get("parsing_res_list", [])
        blocks.sort(key=lambda x: (int(x['block_bbox'][1] // 5), x['block_bbox'][0]))

        page_html = f'<div class="paper-page" id="page-{page_num}">\n'
        page_html += f'<div class="page-number">Trang {int(page_num) + 1}</div>\n'

        for block in blocks:
            label = block.get("block_label")
            content = block.get("block_content", "").strip()
            bbox = block.get("block_bbox")

            action = should_translate(block)
            if action == "SKIP":
                continue

            style_attr = ''
            if label in ["figure_title", "table_caption", "image", "chart", "display_formula"]:
                style_attr = ' style="text-align: center;"'

            if label in ["image", "chart"]:
                img_rel_path = find_image_file(imgs_dir, project_dir, bbox, label)
                if not img_rel_path:
                    img_rel_path = find_image_file(imgs_dir, project_dir, bbox, "chart" if label == "image" else "image")
                if img_rel_path:
                    page_html += f'<div class="{label}-container"{style_attr}><img src="{img_rel_path}" alt="{label}"></div>\n'

            elif label == "table":
                page_html += f'<div class="table-container"{style_attr}>{content}</div>\n'

            elif label == "display_formula":
                page_html += f'<div class="display_formula"{style_attr}>$${content}$$</div>\n'

            else:
                if action is True:
                    display_text = mock_translate_llm(content, label)
                else:
                    display_text = content

                tag = "p"
                if label == "doc_title": tag = "h1"
                elif label == "paragraph_title": tag = "h2"
                elif label == "abstract": tag = "div"
                elif label == "formula_number": tag = "span"
                
                page_html += f'<{tag} class="{label}"{style_attr}>{display_text}</{tag}>\n'

        page_html += "</div>\n"
        html_pages_content += page_html

    mathjax_config = """
    <script>
    window.MathJax = {
      tex: {
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
        processEscapes: true
      }
    };
    </script>
    """

    style_content = """
    <style>
        body { font-family: 'Times New Roman', serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 20px; background: #e0e0e0; }
        .paper-page { background: white; padding: 60px; box-shadow: 0 0 15px rgba(0,0,0,0.2); margin-bottom: 30px; position: relative; min-height: 1100px; }
        .page-number { position: absolute; top: 20px; right: 20px; font-size: 12px; color: #ccc; }
        .doc_title { font-size: 26px; font-weight: bold; text-align: center; margin-bottom: 25px; color: #000; }
        .paragraph_title { font-size: 18px; font-weight: bold; margin-top: 25px; margin-bottom: 10px; color: #111; border-bottom: 1px solid #eee; }
        .figure_title, .table_caption { font-size: 13px; font-weight: bold; margin: 10px 0; font-style: italic; color: #444; }
        .abstract { font-style: italic; margin: 20px 40px; text-align: justify; border-left: 4px solid #ddd; padding-left: 15px; background: #fdfdfd; padding: 10px; }
        .text { text-align: justify; margin-bottom: 10px; text-indent: 1.5em; }
        .reference_content, .footnote, .vision_footnote { font-size: 12px; margin-bottom: 5px; padding-left: 25px; text-indent: -25px; color: #333; }
        .table-container { margin: 20px 0; overflow-x: auto; }
        table { border-collapse: collapse; width: 100%; font-size: 12px; }
        th, td { border: 1px solid #444; padding: 6px; text-align: left; }
        .image-container, .chart-container { margin: 20px 0; }
        img { max-width: 100%; height: auto; }
        .display_formula { margin: 15px 0; }
    </style>
    """

    full_html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Bản dịch {project_name}</title>
        {mathjax_config}
        <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
        {style_content}
    </head>
    <body>
        {html_pages_content}
    </body>
    </html>
    """

    with open(html_output, 'w', encoding='utf-8') as f:
        f.write(full_html)
    print(f"Thành công! File đã được lưu tại: {html_output}")

if __name__ == "__main__":
    projects = ["nougat", "HY-MT", "DeepSeekOCR"]
    if len(sys.argv) > 1:
        projects = [sys.argv[1]]
    
    for proj in projects:
        print(f"--- Đang xử lý dự án: {proj} ---")
        process_project(proj)