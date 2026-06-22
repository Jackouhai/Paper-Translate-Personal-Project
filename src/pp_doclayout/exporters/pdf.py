"""PDF exporter using Playwright to render HTML."""

import logging
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


class PDFExporter(BaseExporter):
    """Export project data to PDF via HTML rendering in headless Chrome."""

    def export(self, project_data: "ProjectData", output_path: Path) -> Path:
        # Render HTML bằng HTMLExporter
        html_exporter = HTMLExporter()
        tmp_html = output_path.with_suffix(".html")
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
                            "() => { const els = document.querySelectorAll('.auto-fit'); return els.length === 0 || Array.from(els).every(el => el.style.fontSize !== ''); }",
                            timeout=10000,
                        )
                    except PlaywrightTimeoutError:
                        logger.warning(
                            "Text auto-fit timed out; continuing PDF export"
                        )
                    # Chờ MathJax render
                    try:
                        page.wait_for_function(
                            "() => { const mjx = document.querySelectorAll('mjx-container'); return mjx.length > 0 || !window.MathJax; }",
                            timeout=5000,
                        )
                    except PlaywrightTimeoutError:
                        logger.warning(
                            "MathJax rendering timed out; continuing PDF export"
                        )
                    # Extract page size từ data
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
                finally:
                    browser.close()
        finally:
            # 3. Xóa file HTML tạm
            tmp_html.unlink(missing_ok=True)

        return output_path
