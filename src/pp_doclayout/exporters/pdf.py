"""PDF exporter using Playwright to render HTML."""

import logging
from pypdf import PdfReader
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from .base import BaseExporter
from .html import HTMLExporter
from pp_doclayout.config import settings

if TYPE_CHECKING:
    from pp_doclayout.types import ProjectData

logger = logging.getLogger(__name__)

CSS_PIXELS_PER_POINT = 96 / 72
MILLIMETERS_PER_POINT = 25.4 / 72

def get_first_source_page_size(project_data: "ProjectData") -> tuple[float, float]:
    """
    Lấy kích thước của trang pdf đầu
    """
    if not project_data["pages"]:
        raise ValueError("Cannot export PDF without parsed pages")

    source_pdf = Path(project_data["pages"][0]["input_path"])
    reader = PdfReader(str(source_pdf))
    crop_box = reader.pages[0].cropbox

    return float(crop_box.width), float(crop_box.height)

class PDFExporter(BaseExporter):
    """Export project data to PDF via HTML rendering in headless Chrome."""

    def export(self, project_data: "ProjectData", output_path: Path) -> Path:
        # Render HTML bằng HTMLExporter
        html_exporter = HTMLExporter()
        tmp_html = output_path.with_name(
            f".{output_path.stem}.pdf-export.html"
        )
        html_exporter.export(project_data, tmp_html)
        try:
            # Dùng Playwright xuất PDF
            with sync_playwright() as p:
                launch_options = {"headless": True}

                if settings.playwright_browser_channel:
                    launch_options["channel"] = (
                        settings.playwright_browser_channel
                    )
                browser = p.chromium.launch(**launch_options)
                try:
                    page = browser.new_page()
                    page.goto(tmp_html.resolve().as_uri(), wait_until="networkidle")

                    try:
                        # Chờ JS fitting
                        page.wait_for_function(
                            "() => window.__ppDoclayoutFitComplete === true",
                            timeout=15000,
                        )
                    except PlaywrightTimeoutError:
                        logger.warning(
                            "Text/MathJax auto-fit timed out; continuing PDF export"
                        )
                    # Extract page size từ data
                    first_page = project_data["pages"][0]
                    json_width = float(first_page["width"])
                    json_height = float(first_page["height"])

                    if json_width <= 0 or json_height <= 0:
                        raise ValueError("Parsed page dimensions must be positive")

                    pdf_width_pt, pdf_height_pt = get_first_source_page_size(project_data)

                    pdf_width_css_px = pdf_width_pt * CSS_PIXELS_PER_POINT
                    pdf_height_css_px = pdf_height_pt * CSS_PIXELS_PER_POINT

                    print_scale_x = pdf_width_css_px / json_width
                    print_scale_y = pdf_height_css_px / json_height

                    pdf_width_mm = pdf_width_pt * MILLIMETERS_PER_POINT
                    pdf_height_mm = pdf_height_pt * MILLIMETERS_PER_POINT

                    # Add thẻ style kèm @media print để CSS bên trong chỉ áp dụng khi in hoặc export PDF.
                    page.add_style_tag(
                        content=f"""
                        @media print {{
                        .paper-page,
                        .page-container {{
                            width: {pdf_width_css_px}px !important;
                            height: {pdf_height_css_px}px !important;
                            margin: 0 !important;
                            padding: 0 !important;
                            overflow: hidden !important;
                        }}

                        .page {{
                            transform: scale({print_scale_x:.8f},
                            {print_scale_y:.8f});
                            transform-origin: top left;
                        }}
                        }}
                        """
                    )

                    page.pdf(
                        path=str(output_path),
                        width=f"{pdf_width_mm:.8f}mm",
                        height=f"{pdf_height_mm:.8f}mm",
                        print_background=True,
                        margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                    )
                finally:
                    browser.close()
        finally:
            # 3. Xóa file HTML tạm
            tmp_html.unlink(missing_ok=True)

        return output_path
