"""PaddleOCR-VL Service Client."""

import logging
from pathlib import Path
from typing import Optional

import requests

from pp_doclayout.config import settings

logger = logging.getLogger(__name__)


class PaddleOCRServiceClient:
    """Client cho PaddleOCR-VL Service."""

    def __init__(self, service_url: Optional[str] = None):
        """
        Args:
            service_url: URL của PaddleOCR-VL service. None → dùng từ settings.
        """
        self.service_url = service_url or settings.paddle_ocr_service_url

    def is_available(self) -> bool:
        """Check nếu service đang chạy."""
        if not self.service_url:
            logger.warning("Service URL is None")
            return False
        try:
            response = requests.get(f"{self.service_url}/health", timeout=10)
            is_ready = response.status_code == 200 and response.json().get("status") == "ready"
            logger.info(f"Service check: {self.service_url}/health → ready={is_ready}")
            return is_ready
        except requests.exceptions.Timeout:
            logger.warning(f"Service timeout: {self.service_url}/health (10s)")
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"Service not available: {e}")
            return False

    def parse_pdf(
        self,
        pdf_path: str | Path,
        output_dir: str | Path | None = None,
        page: int | None = None,
    ) -> tuple[bool, str | None, str | None]:
        """
        Gọi PaddleOCR-VL service để parse PDF.

        Args:
            pdf_path: Path đến file PDF
            output_dir: Thư mục output (optional)
            page: Page number để parse (1-indexed). None = parse all pages.

        Returns:
            (success: bool, error: str|None, project_dir: str|None)
        """
        if output_dir is None:
            output_dir = settings.output_dir

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return False, f"PDF file không tồn tại: {pdf_path}", None

        logger.info(f"📡 Gọi PaddleOCR-VL service: {self.service_url}")
        if page is not None:
            logger.info(f"📄 Requesting single page: {page}")

        try:
            with open(pdf_path, "rb") as f:
                files = {"pdf": (pdf_path.name, f, "application/pdf")}
                data = {"output_dir": str(output_dir)}
                if page is not None:
                    data["page"] = str(page)

                response = requests.post(
                    f"{self.service_url}/parse",
                    files=files,
                    data=data,
                    timeout=600,
                )

            if response.status_code != 200:
                return False, f"Service error: {response.status_code}", None

            result = response.json()

            # FIX: chỉ fail khi error có nội dung thật, không check "error" in result
            # vì response luôn có field "error": null kể cả khi thành công
            success = result.get("success", False)

            if not success:
                error_msg = result.get("error") or result.get("message") or "Unknown error"
                return False, error_msg, None

            project_dir = result.get("project_dir")
            num_pages = result.get("num_pages", 0)
            parsed_page = result.get("parsed_page")

            if parsed_page:
                logger.info(f"✅ Service đã parse page {parsed_page} → {project_dir}")
            else:
                logger.info(f"✅ Service đã parse: {num_pages} pages → {project_dir}")

            return True, None, project_dir

        except requests.exceptions.Timeout:
            return False, "Service timeout", None
        except requests.exceptions.RequestException as e:
            return False, f"Service error: {e}", None
        except Exception as e:
            return False, f"Lỗi không xác định: {e}", None


# Global client instance (lazy init)
_client: Optional[PaddleOCRServiceClient] = None


def get_service_client() -> Optional[PaddleOCRServiceClient]:
    """Get PaddleOCR-VL service client (singleton)."""
    global _client
    if _client is None:
        _client = PaddleOCRServiceClient()
    return _client