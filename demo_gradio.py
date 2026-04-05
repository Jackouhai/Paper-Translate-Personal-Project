"""Gradio Demo for PP-DocLayout (Fixed Version).

Usage:
    python demo_gradio.py

Requirements:
    - PaddleOCR-VL vLLM server running on port 8000
    - Gemma vLLM server running on port 8001
    - Install: uv pip install gradio pypdf
"""

import base64
import re
import tempfile
import traceback
from pathlib import Path

import gradio as gr
from pypdf import PdfReader

# Kiểm tra import các module nội bộ
try:
    from pp_doclayout.config import settings
    from pp_doclayout.core.renderer import (
        build_project_data,
        translate_page_data,
        render_page_blocks,
    )
    from pp_doclayout.exporters import HTMLExporter
    from pp_doclayout.translators import get_gemma
    from pp_doclayout.utils.service_client import get_service_client
except ImportError as e:
    print(f"❌ Lỗi import module: {e}")
    print("💡 Đảm bảo bạn đã cài đặt package pp_doclayout (pip install -e .)")
    raise


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_pdf_page_count(pdf_file_path) -> int:
    """Đếm số trang PDF."""
    try:
        reader = PdfReader(pdf_file_path)
        return len(reader.pages)
    except Exception as e:
        print(f"[WARNING] Không thể đếm trang PDF: {e}")
        return 1


def encode_images_to_base64(html_content: str, project_dir: Path) -> str:
    """Encode all images in HTML to base64 for preview."""

    def replace_src(match):
        img_tag = match.group(0)
        src_match = re.search(r'src="([^"]+)"', img_tag)
        if not src_match:
            return img_tag

        src = src_match.group(1)

        if src.startswith("data:"):
            return img_tag

        img_path = project_dir / src
        if not img_path.exists():
            imgs_dir = project_dir / "imgs"
            if imgs_dir.exists():
                img_path = imgs_dir / Path(src).name
        
        if not img_path.exists():
            return img_tag

        try:
            ext = img_path.suffix.lower()
            mime_types = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            mime_type = mime_types.get(ext, "image/jpeg")
            img_data = img_path.read_bytes()
            b64_data = base64.b64encode(img_data).decode("utf-8")
            new_src = f"data:{mime_type};base64,{b64_data}"
            return img_tag.replace(f'src="{src}"', f'src="{new_src}"')
        except Exception as e:
            print(f"[WARNING] Không thể encode ảnh {src}: {e}")
            return img_tag

    return re.sub(r"<img[^>]+>", replace_src, html_content)


# ============================================================================
# MAIN PROCESSING FUNCTION
# ============================================================================

def process_single_page(pdf_file, page_number: int):
    """Process PDF: parse -> translate -> render -> encode for preview."""
    try:
        # ===== Validate input =====
        if not pdf_file:
            yield "<p style='color:red;'>❌ Hãy upload PDF file</p>", None, "❌ Hãy upload PDF file"
            return

        pdf_path = Path(pdf_file)
        if not pdf_path.exists():
            yield "", None, "❌ Lỗi: File không tồn tại"
            return

        # Đếm tổng số trang từ file gốc
        try:
            reader = PdfReader(str(pdf_path))
            total_pages = len(reader.pages)
        except Exception as e:
            print(f"[WARNING] Lỗi đọc PDF: {e}")
            total_pages = 1

        if page_number < 1 or page_number > total_pages:
            yield (
                "",
                None,
                f"❌ Lỗi: PDF có {total_pages} trang, vui lòng chọn trang 1-{total_pages}",
            )
            return

        yield "", None, f"📄 Đang parse PDF (trang {page_number}/{total_pages})..."

        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir) / pdf_path.stem
            project_dir.mkdir(parents=True, exist_ok=True)

            # ===== STEP 1: Parse PDF =====
            service_client = get_service_client()
            print(f"[DEBUG] Service URL: {service_client.service_url}")
            use_service = service_client and service_client.is_available()
            print(f"[DEBUG] Service available: {use_service}")

            try:
                if use_service:
                    yield "", None, "📡 Sử dụng PaddleOCR-VL Service (model đã preload)"
                    success, error, result_dir = service_client.parse_pdf(
                        str(pdf_path), str(project_dir), page=page_number
                    )
                    if result_dir:
                        print(f"[DEBUG] Service result dir: {result_dir}")
                    if not success:
                        yield "", None, f"❌ Lỗi service: {error}"
                        return
                    if result_dir:
                        project_dir = Path(result_dir)
                else:
                    yield "", None, "⏳ Sử dụng PaddleOCR-VL Local"
                    try:
                        from paddleocr import PaddleOCRVL
                    except ImportError:
                        yield "", None, "❌ Lỗi: Không tìm thấy module PaddleOCRVL"
                        return

                    pipeline = PaddleOCRVL(
                        vl_rec_backend="vllm-server",
                        vl_rec_server_url=settings.paddle_ocr_server_url,
                        format_block_content=settings.paddle_ocr_format_block_content,
                        use_doc_unwarping=settings.paddle_ocr_use_doc_unwarping,
                        use_chart_recognition=settings.paddle_ocr_use_chart_recognition,
                        merge_layout_blocks=settings.paddle_ocr_merge_layout_blocks,
                        use_ocr_for_image_block=settings.paddle_use_ocr_for_image_block,
                        layout_detection_model_name=settings.paddle_ocr_layout_detection_model_name,
                        use_layout_detection=settings.paddle_ocr_use_layout_detection,
                    )
                    output = pipeline.predict(str(pdf_path))
                    for res in output:
                        if hasattr(res, 'save_to_json'):
                            res.save_to_json(save_path=str(project_dir))
                        if hasattr(res, 'save_to_markdown'):
                            res.save_to_markdown(save_path=str(project_dir))

            except Exception as e:
                yield "", None, f"❌ Lỗi parse PDF: {e}"
                print(traceback.format_exc())
                return

            yield "", None, "🔄 Đang xây dựng dữ liệu..."

            # ===== STEP 2: Build project data =====
            try:
                project_data = build_project_data(project_dir)
            except Exception as e:
                yield "", None, f"❌ Lỗi xây dựng dữ liệu: {e}"
                print(traceback.format_exc())
                return

            # === DEBUG: Kiểm tra số trang thực tế ===
            total_parsed_pages = len(project_data.get("pages", []))
            print(f"[DEBUG] PDF gốc có: {total_pages} trang")
            print(f"[DEBUG] OCR phân tích được: {total_parsed_pages} trang")
            print(f"[DEBUG] User chọn trang: {page_number}")
            
            # === SỬA LOGIC: Xử lý trường hợp OCR chỉ trả về 1 trang ===
            if total_parsed_pages == 1:
                selected_idx = 0
                print(f"[DEBUG] Chỉ có 1 trang trong dữ liệu, ép index về 0")
            else:
                selected_idx = page_number - 1
            
            if selected_idx < 0 or selected_idx >= total_parsed_pages:
                yield (
                    "", 
                    None, 
                    f"❌ Lỗi: OCR chỉ phân tích {total_parsed_pages} trang, không có trang {page_number}"
                )
                return

            project_data["pages"] = [project_data["pages"][selected_idx]]

            yield "", None, f"🌐 Đang dịch trang {page_number}..."

            # ===== STEP 3: Translate =====
            try:
                translator = get_gemma()
                translated_pages = []
                for page in project_data["pages"]:
                    translated_page = translate_page_data(page, translator)
                    imgs_dir = project_dir / "imgs"
                    blocks_html = render_page_blocks(translated_page, imgs_dir, project_dir)
                    translated_page["html_content"] = blocks_html
                    translated_pages.append(translated_page)
                project_data["pages"] = translated_pages
            except Exception as e:
                yield "", None, f"❌ Lỗi dịch thuật: {e}"
                print(traceback.format_exc())
                return

            yield "", None, "🎨 Đang render HTML..."

            # ===== STEP 4: Export HTML =====
            try:
                exporter = HTMLExporter()
                output_filename = (
                    f"translated_{project_data['project_name']}_page{page_number}.html"
                )
                output_path = project_dir / output_filename
                exporter.export(project_data, output_path)
                html_content = output_path.read_text(encoding="utf-8")
                print(f"[DEBUG] HTML content length: {len(html_content)}")
            except Exception as e:
                yield "", None, f"❌ Lỗi export HTML: {e}"
                print(traceback.format_exc())
                return

            yield "", None, "🖼️ Đang encode images..."

            # ===== STEP 5: Encode images to base64 =====
            try:
                imgs_dir = project_dir / "imgs"
                print(f"[DEBUG] Images dir: {imgs_dir}, exists: {imgs_dir.exists()}")
                if imgs_dir.exists():
                    img_files = list(imgs_dir.glob("*"))
                    print(f"[DEBUG] Found {len(img_files)} image files")
                html_content = encode_images_to_base64(html_content, project_dir)
            except Exception as e:
                print(f"[DEBUG] Encode images error: {e}")

            # ===== STEP 6: Save download file =====
            download_dir = Path("downloads")
            download_dir.mkdir(exist_ok=True)
            download_path = download_dir / output_filename
            download_path.write_text(html_content, encoding="utf-8")

            # ===== STEP 7: Build preview via iframe =====
            html_b64 = base64.b64encode(html_content.encode("utf-8")).decode("utf-8")

            iframe_preview = f"""
            <iframe
                src="data:text/html;base64,{html_b64}"
                style="
                    width: 100%;
                    height: 700px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background: white;
                "
                sandbox="allow-same-origin allow-scripts"
            ></iframe>
            """

            print(f"[DEBUG] HTML b64 length: {len(html_b64)}")

            yield (
                iframe_preview,
                str(download_path),
                f"✅ Hoàn tất! Trang {page_number}/{total_pages}",
            )

    except Exception as e:
        error_msg = f"❌ Lỗi không xác định: {str(e)}"
        print(f"[ERROR] {error_msg}\n{traceback.format_exc()}")
        yield f"<p style='color:red;'>{error_msg}</p>", None, error_msg


# ============================================================================
# GRADIO UI
# ============================================================================

def update_page_slider(pdf_file):
    """Update page slider max value when PDF is uploaded."""
    if not pdf_file:
        return gr.update(maximum=100, value=1), "Vui lòng upload PDF"
    try:
        page_count = get_pdf_page_count(pdf_file)
        return gr.update(maximum=page_count, value=1), f"PDF có {page_count} trang"
    except Exception as e:
        return gr.update(maximum=100, value=1), f"Lỗi đọc PDF: {e}"


with gr.Blocks(title="PP-DocLayout Demo") as demo:
    gr.Markdown("# 📄 PP-DocLayout Demo")
    gr.Markdown("Phân tích & Dịch thuật Tài liệu Khoa học sang Tiếng Việt")

    with gr.Row():
        with gr.Column(scale=1):
            pdf_input = gr.File(
                label="Upload PDF",
                file_types=[".pdf"],
                type="filepath",
            )
            page_slider = gr.Slider(
                minimum=1,
                maximum=100,
                step=1,
                value=1,
                label="Chọn trang cần dịch",
            )
            translate_btn = gr.Button("🔄 Dịch", variant="primary", size="lg")

        with gr.Column(scale=2):
            status = gr.Textbox(
                label="Trạng thái",
                value="Vui lòng upload PDF và chọn trang",
                interactive=False,
            )
            preview = gr.HTML(
                label="Preview",
                value="<div style='text-align:center; padding: 50px; color: #666;'>Chưa có kết quả</div>",
            )
            download = gr.File(
                label="Tải xuống HTML",
                visible=True,
            )

    pdf_input.change(
        fn=update_page_slider,
        inputs=[pdf_input],
        outputs=[page_slider, status],
    )

    # ✅ API EXPOSE: Đặt api_name trực tiếp trên .click()
    translate_btn.click(
        fn=process_single_page,  # ← Hàm này đã được định nghĩa ở trên
        inputs=[pdf_input, page_slider],
        outputs=[preview, download, status],
        api_name="process_page",  # ← Endpoint: /api/process_page
    )

    gr.Markdown("---")
    gr.Markdown("### 📌 Hướng dẫn sử dụng")
    gr.Markdown("""
    1. **Upload PDF**: Chọn file PDF cần dịch
    2. **Chọn trang**: Sử dụng slider để chọn 1 trang
    3. **Dịch**: Nhấn nút "Dịch" để bắt đầu
    4. **Xem kết quả**: Preview sẽ hiển thị kết quả dịch
    5. **Tải xuống**: Nhấn vào file để tải HTML về máy
    
    ### 🔌 API Access
    - Endpoint: `/api/process_page`
    - Method: POST
    - Payload: `{"data": ["/path/to/file.pdf", page_number]}`
    """)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("🚀 Starting PP-DocLayout Gradio Demo...")
    print(f"   Gradio version: {gr.__version__}")
    try:
        print(f"   PaddleOCR-VL: {settings.paddle_ocr_server_url}")
        print(f"   Gemma: {settings.vllm_base_url}")
    except Exception:
        print("   ⚠️  Không thể đọc settings (kiểm tra file config)")

    # ✅ QUEUE CONFIG: Gọi queue() trước launch(), không gán lại
    demo.queue(
        max_size=20,
        api_open=True,            # ← BẮT BUỘC: Bật API access
        default_concurrency_limit=4
    )

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
    )