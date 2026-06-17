"""PDF exporter using Playwright to render HTML."""

from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import sync_playwright

from .base import BaseExporter
from .html import HTMLExporter

if TYPE_CHECKING:
    from pp_doclayout.types import ProjectData


class PDFExporter(BaseExporter):
    """Export project data to PDF via HTML rendering in headless Chrome."""

    def export(self, project_data: "ProjectData", output_path: Path) -> Path:
        # 1. Render HTML bằng HTMLExporter
        html_exporter = HTMLExporter()
        tmp_html = output_path.with_suffix(".html")
        html_exporter.export(project_data, tmp_html)

        # 2. Dùng Playwright mở HTML, chờ render xong, xuất PDF
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path="/usr/bin/google-chrome",
                headless=True,
            )
            page = browser.new_page()
            page.goto(f"file://{tmp_html.resolve()}", wait_until="networkidle")

            # Chờ JS fitting xong
            page.wait_for_function(
                "() => { const els = document.querySelectorAll('.auto-fit'); return els.length === 0 || Array.from(els).every(el => el.style.fontSize !== ''); }",
                timeout=10000,
            )

            # Chờ MathJax render xong (nếu có)
            try:
                page.wait_for_function(
                    "() => { const mjx = document.querySelectorAll('mjx-container'); return mjx.length > 0 || !window.MathJax; }",
                    timeout=5000,
                )
            except Exception:
                pass

            # Lấy page size từ data
            first_page = project_data["pages"][0] if project_data["pages"] else None
            if first_page:
                width = first_page.get("width", 1224)
                height = first_page.get("height", 1584)
            else:
                width, height = 1224, 1584

            page.pdf(
                path=str(output_path),
                width=f"{width}px",
                height=f"{height}px",
                print_background=True,
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
            )
            browser.close()

        # 3. Xóa file HTML tạm
        tmp_html.unlink(missing_ok=True)

        return output_path
