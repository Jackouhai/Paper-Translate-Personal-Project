"""Demo Streamlit app cho PP-DocLayout với Model Switching."""

from pathlib import Path
from typing import Optional

import streamlit as st
from paddleocr import PaddleOCRVL

from pp_doclayout.config import settings
from pp_doclayout.translators import get_gemma
from pp_doclayout.core import process_project
from server_manager import get_manager


st.set_page_config(
    page_title="PP-DocLayout Demo",
    page_icon="📄",
    layout="wide",
)


def save_uploaded_file(uploaded_file, save_dir: Path) -> Path:
    """Save uploaded file to disk."""
    save_dir.mkdir(parents=True, exist_ok=True)
    file_path = save_dir / uploaded_file.name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def show_server_status(manager):
    """Show server status in UI."""
    status = manager.status()

    st.subheader("Server Status")
    col1, col2 = st.columns(2)

    with col1:
        paddle_status = status["paddle"]
        paddle_emoji = "🟢" if paddle_status == "running" else "🔴"
        st.metric("PaddleOCR-VL", paddle_status, help=f"PID: {status['paddle_pid']}")
        st.write(f"{paddle_emoji} {paddle_status.upper()}")

    with col2:
        gemma_status = status["gemma"]
        gemma_emoji = "🟢" if gemma_status == "running" else "🔴"
        st.metric("Gemma", gemma_status, help=f"PID: {status['gemma_pid']}")
        st.write(f"{gemma_emoji} {gemma_status.upper()}")

    st.divider()


def main():
    """Main Streamlit app."""
    manager = get_manager()

    # Header
    st.title("📄 PP-DocLayout Demo")
    st.markdown("Pipeline dịch thuật tài liệu học thuật sang tiếng Việt")
    st.markdown("*Model Switching - Chỉ chạy 1 model tại 1 thời điểm*")

    # Show server status
    show_server_status(manager)

    # Sidebar - Server Controls
    st.sidebar.header("🎛️ Server Controls")
    st.sidebar.subheader("Manual Switch")
    st.sidebar.info("💡 Chỉ 1 server chạy cùng lúc do GPU 16GB VRAM")

    if st.sidebar.button("🔄 Switch to PaddleOCR-VL", key="switch_paddle"):
        manager.switch_to("paddle")
        st.rerun()

    if st.sidebar.button("🔄 Switch to Gemma", key="switch_gemma"):
        manager.switch_to("gemma")
        st.rerun()

    st.sidebar.divider()
    st.sidebar.subheader("Stop All")
    if st.sidebar.button("🛑 Stop All Servers", key="stop_all"):
        manager.stop_all()
        st.rerun()

    # Sidebar - Output Settings
    st.sidebar.subheader("⚙️ Cấu hình")
    output_suffix = st.sidebar.text_input(
        "Output suffix",
        value="translated",
        help="Hậu tố tên file output"
    )

    # Main content
    st.header("📤 Upload PDF")
    uploaded_file = st.file_uploader(
        "Chọn file PDF",
        type=["pdf"],
        help="Chọn file PDF để xử lý"
    )

    if not uploaded_file:
        st.info("⬆️ Hãy upload file PDF để bắt đầu")
        return

    # Show file info
    st.success(f"✅ File đã upload: `{uploaded_file.name}`")
    st.info(f"📊 Kích thước: `{uploaded_file.size / 1024 / 1024:.2f} MB`")

    # Save to temp directory
    temp_dir = Path(".streamlit_temp")
    pdf_path = save_uploaded_file(uploaded_file, temp_dir)
    project_dir = Path(settings.output_dir) / pdf_path.stem

    st.divider()

    # Step 1: Parse
    st.header("🔍 Bước 1: Parse PDF")

    if st.button("🚀 Parse PDF", key="parse", type="primary"):
        # Auto-switch to PaddleOCR-VL
        with st.spinner("🔄 Chuyển đến PaddleOCR-VL server..."):
            if not manager.switch_to("paddle"):
                st.error("❌ Không thể start PaddleOCR-VL server. Kiểm tra GPU VRAM.")
                st.error("💡 Hãy chọi sidebar 'Stop All Servers' rồi thử lại")
                return
            # Extra wait to ensure server is ready
            import time
            time.sleep(3)

        with st.spinner("⏳ Đang parsing PDF với PaddleOCR-VL..."):
            try:
                # Create output folder
                project_dir.mkdir(parents=True, exist_ok=True)

                # Initialize PaddleOCR-VL
                pipeline = PaddleOCRVL(
                    vl_rec_backend=settings.paddle_ocr_backend,
                    vl_rec_server_url=settings.paddle_ocr_server_url,
                )

                # Process
                output = pipeline.predict(str(pdf_path))
                for i, res in enumerate(output):
                    st.progress(
                        (i + 1) / len(output),
                        f"Parsing page {i + 1}/{len(output)}...",
                    )
                    try:
                        res.save_to_json(save_path=str(project_dir))
                        res.save_to_markdown(save_path=str(project_dir))
                    except Exception as e:
                        st.error(f"Lỗi lưu trang {i + 1}: {e}")

                st.success(f"✅ Parse hoàn tất! Kết quả: `{project_dir}`")

                # Show some info
                json_files = list(project_dir.glob("*_res.json"))
                st.info(f"📄 Số trang đã parse: `{len(json_files)}`")

                # Suggest to translate
                st.info("💡 Next: Click 'Translate' ở dưới để dịch")

            except Exception as e:
                st.error(f"❌ Lỗi parsing: {e}")
                import traceback
                st.error(traceback.format_exc())
                return

    st.divider()

    # Step 2: Translate
    st.header("🌐 Bước 2: Translate")

    if st.button("🔤 Translate", key="translate", type="primary"):
        if not project_dir.exists():
            st.warning("⚠️ Vui lòng parse PDF trước!")
            return

        # Auto-switch to Gemma
        with st.spinner("🔄 Chuyển đến Gemma server..."):
            if not manager.switch_to("gemma"):
                st.error("❌ Không thể start Gemma server. Kiểm tra GPU VRAM.")
                return

        with st.spinner("⏳ Đang dịch với Gemma model..."):
            try:
                translator = get_gemma()

                output_path = process_project(
                    project_dir, translator=translator, output_suffix=output_suffix
                )

                st.success(f"✅ Translate hoàn tất! Output: `{output_path}`")

                # Show download link
                with open(output_path, "rb") as f:
                    st.download_button(
                        label="📥 Tải HTML",
                        data=f,
                        file_name=output_path.name,
                        mime="text/html"
                    )

                # Show preview
                st.divider()
                st.header("📖 Preview")

                # Read HTML content
                html_content = output_path.read_text(encoding="utf-8")

                # Show iframe preview
                st.components.v1.html(
                    f'<iframe srcdoc="{html_content}" width="100%" height="800"></iframe>',
                    height=800,
                    scrolling=True
                )

            except Exception as e:
                st.error(f"❌ Lỗi translating: {e}")
                import traceback
                st.error(traceback.format_exc())
                return

    # Footer
    st.divider()
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center;">
            <small>PP-DocLayout Demo (Model Switching) - Pipeline dịch thuật tài liệu học thuật</small>
        </div>
        """,
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
