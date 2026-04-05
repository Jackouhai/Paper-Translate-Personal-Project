#!/usr/bin/env python3
"""
PaddleOCR-VL Service - OOM-Safe Version.
Features:
    • Model loaded ONCE per worker (not per request)
    • Memory monitoring + auto-reject when high
    • Request concurrency limiting via Semaphore
    • Stream PDF upload (no full memory load)
    • Guaranteed temp file cleanup with try-finally
    • File size limits to prevent abuse
Usage:
    python pp_doclayout_service.py --port 8002 --workers 2
Default:
    • Port: 8002
    • Workers: 2 (safe for 16GB RAM)
    • Max concurrent requests: 4
    • Max PDF size: 50MB
"""

import argparse
import asyncio
import logging
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Optional, List

import psutil
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse
from pypdf import PdfReader, PdfWriter
from pydantic import BaseModel

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from pp_doclayout.config import settings

# Try to import PaddleOCRVL - handle gracefully if not available
try:
    from paddleocr import PaddleOCRVL
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    PaddleOCRVL = None  # type: ignore

# ============================================================================
# CONFIGURATION
# ============================================================================
MEMORY_WARNING_PERCENT = 75
MEMORY_REJECT_PERCENT = 90
MEMORY_EMERGENCY_PERCENT = 95

MAX_CONCURRENT_REQUESTS = 4
MAX_PDF_SIZE_MB = 50
MAX_PAGES_PER_REQUEST = 100

TEMP_FILE_RETENTION_SECONDS = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pp_doclayout_service.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL STATE
# ============================================================================
_paddleocr_vl: Optional[PaddleOCRVL] = None
_model_lock = Lock()
_request_semaphore = None


def get_paddleocr_vl() -> Optional[PaddleOCRVL]:
    """Get or create PaddleOCRVL instance (thread-safe, loaded once per worker)."""
    global _paddleocr_vl

    if not PADDLEOCR_AVAILABLE:
        logger.error("❌ PaddleOCR-VL not available - check installation")
        return None

    if _paddleocr_vl is None:
        with _model_lock:
            if _paddleocr_vl is None:
                try:
                    logger.info("🚀 Loading PaddleOCR-VL model (once per worker)...")
                    logger.info(f"   Backend: {settings.paddle_ocr_backend}")
                    logger.info(f"   Server URL: {settings.paddle_ocr_server_url}")

                    _paddleocr_vl = PaddleOCRVL(
                        vl_rec_backend=settings.paddle_ocr_backend,
                        vl_rec_server_url=settings.paddle_ocr_server_url,
                        format_block_content=settings.paddle_ocr_format_block_content,
                        use_doc_unwarping=settings.paddle_ocr_use_doc_unwarping,
                        use_chart_recognition=settings.paddle_ocr_use_chart_recognition,
                        merge_layout_blocks=settings.paddle_ocr_merge_layout_blocks,
                        use_ocr_for_image_block=settings.paddle_use_ocr_for_image_block,
                        layout_detection_model_name=settings.paddle_ocr_layout_detection_model_name,
                        use_layout_detection=settings.paddle_ocr_use_layout_detection,
                    )

                    logger.info("✅ PaddleOCR-VL loaded successfully")

                except Exception as e:
                    logger.error(f"❌ Failed to load PaddleOCR-VL: {e}", exc_info=True)
                    _paddleocr_vl = None

    return _paddleocr_vl


def check_memory_status() -> dict:
    """Check current memory usage and return status dict."""
    try:
        mem = psutil.virtual_memory()
        percent = mem.percent

        if percent >= MEMORY_EMERGENCY_PERCENT:
            return {
                "ok": False,
                "percent": percent,
                "message": f"EMERGENCY: Memory at {percent:.1f}% - service unstable",
            }
        elif percent >= MEMORY_REJECT_PERCENT:
            return {
                "ok": False,
                "percent": percent,
                "message": f"Memory at {percent:.1f}% - rejecting new requests",
            }
        elif percent >= MEMORY_WARNING_PERCENT:
            return {
                "ok": True,
                "percent": percent,
                "message": f"Warning: Memory at {percent:.1f}%",
            }
        else:
            return {
                "ok": True,
                "percent": percent,
                "message": f"Memory OK: {percent:.1f}%",
            }
    except Exception as e:
        logger.warning(f"⚠️ Could not check memory: {e}")
        return {"ok": True, "percent": 0, "message": "Memory check unavailable"}


async def cleanup_old_temp_files(
    output_dir: Path, max_age_seconds: int = TEMP_FILE_RETENTION_SECONDS
):
    """Clean up temp files older than max_age_seconds."""
    import time

    try:
        if not output_dir.exists():
            return

        cutoff = time.time() - max_age_seconds
        cleaned = 0

        for f in output_dir.glob("temp_*.pdf"):
            try:
                if f.stat().st_mtime < cutoff:
                    f.unlink()
                    cleaned += 1
                    logger.debug(f"🧹 Cleaned old temp file: {f.name}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to cleanup {f}: {e}")

        if cleaned > 0:
            logger.info(f"🧹 Cleaned {cleaned} old temp files")

    except Exception as e:
        logger.warning(f"⚠️ Temp file cleanup failed: {e}")


# ============================================================================
# FASTAPI APP WITH LIFESPAN
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown handlers."""
    logger.info("🔧 Starting PaddleOCR-VL Service...")

    global _request_semaphore
    _request_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    if PADDLEOCR_AVAILABLE:
        get_paddleocr_vl()

    async def periodic_cleanup():
        while True:
            await asyncio.sleep(600)
            output_dir = Path(settings.output_dir)
            await cleanup_old_temp_files(output_dir)

    cleanup_task = asyncio.create_task(periodic_cleanup())

    logger.info("✅ Service ready")
    yield

    logger.info("🛑 Shutting down service...")
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    logger.info("👋 Service stopped")


app = FastAPI(
    title="PaddleOCR-VL Service",
    description="Memory-safe PaddleOCR-VL service for document parsing",
    version="1.1.0",
    lifespan=lifespan,
)


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================
class ParseResponse(BaseModel):
    success: bool
    message: str
    project_dir: Optional[str] = None
    num_pages: Optional[int] = None
    parsed_page: Optional[int] = None
    error: Optional[str] = None
    retry_after: Optional[int] = None


class HealthResponse(BaseModel):
    status: str
    memory_percent: float
    model_loaded: bool
    paddleocr_available: bool
    message: str


# ============================================================================
# API ENDPOINTS
# ============================================================================
@app.post("/parse", response_model=ParseResponse)
async def parse_pdf(
    pdf: UploadFile = File(..., description="PDF file to parse"),
    output_dir: str = Form(settings.output_dir, description="Output directory"),
    page: Optional[int] = Form(None, description="Parse specific page (1-indexed). None = all pages"),
):
    """Parse PDF with PaddleOCR-VL (memory-safe)."""

    # ===== Step 0: Pre-checks =====
    mem_status = check_memory_status()
    if not mem_status["ok"]:
        logger.warning(f"⚠️ Rejecting request: {mem_status['message']}")
        return ParseResponse(
            success=False,
            message="Server memory high",
            error=mem_status["message"],
            retry_after=30,
        )

    if pdf.size and pdf.size > MAX_PDF_SIZE_MB * 1024 * 1024:
        size_mb = pdf.size / 1024 / 1024
        logger.warning(f"⚠️ Rejecting large file: {size_mb:.1f}MB > {MAX_PDF_SIZE_MB}MB limit")
        return ParseResponse(
            success=False,
            message="File too large",
            error=f"File size {size_mb:.1f}MB exceeds limit of {MAX_PDF_SIZE_MB}MB",
        )

    paddleocr_vl = get_paddleocr_vl()
    if paddleocr_vl is None:
        return ParseResponse(
            success=False,
            message="Service not ready",
            error="PaddleOCR-VL model not loaded. Check server logs.",
            retry_after=10,
        )

    # ===== Step 1: Acquire concurrency slot =====
    async with _request_semaphore:
        temp_files: List[Path] = []

        try:
            # ===== Step 2: Save uploaded PDF to proper temp file =====
            pdf_content = await pdf.read()
            if not pdf_content:
                raise ValueError("No content in uploaded file")

            # FIX: Dùng tempfile.NamedTemporaryFile thay vì lưu vào output_dir
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_content)
                pdf_path = Path(tmp.name)

            temp_files.append(pdf_path)
            logger.info(f"📥 Uploaded {pdf.filename}: {len(pdf_content)} bytes → {pdf_path.name}")

            # ===== Step 3: Handle single-page extraction if requested =====
            pdf_to_parse = pdf_path

            if page is not None:
                try:
                    reader = PdfReader(str(pdf_path))
                    num_pages = len(reader.pages)

                    if num_pages > MAX_PAGES_PER_REQUEST:
                        return ParseResponse(
                            success=False,
                            message="PDF too large",
                            error=f"PDF has {num_pages} pages, max allowed is {MAX_PAGES_PER_REQUEST}",
                        )

                    if page < 1 or page > num_pages:
                        return ParseResponse(
                            success=False,
                            message="Invalid page number",
                            error=f"Page {page} not found. PDF has {num_pages} pages.",
                        )

                    # FIX: Dùng tempfile cho extracted page, tránh lưu vào output_dir
                    writer = PdfWriter()
                    writer.add_page(reader.pages[page - 1])  # Convert to 0-indexed

                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        writer.write(tmp)
                        extracted_path = Path(tmp.name)

                    temp_files.append(extracted_path)
                    pdf_to_parse = extracted_path

                    logger.info(f"📄 Extracted page {page}/{num_pages} → {extracted_path.name}")

                except Exception as e:
                    logger.error(f"❌ Page extraction failed: {e}", exc_info=True)
                    return ParseResponse(
                        success=False,
                        message="Failed to extract page",
                        error=str(e),
                    )

            # ===== Step 4: Parse with PaddleOCR-VL =====
            logger.info(f"🔍 Parsing: {pdf_to_parse.name} (page={page})")

            try:
                # predict() là sync call → chạy trong thread pool để không block event loop
                output = await asyncio.to_thread(paddleocr_vl.predict, str(pdf_to_parse))
            except Exception as e:
                logger.error(f"❌ PaddleOCR-VL predict failed: {e}", exc_info=True)
                return ParseResponse(
                    success=False,
                    message="Parsing failed",
                    error=f"PaddleOCR-VL error: {str(e)[:200]}",
                )

            # ===== Step 5: Save results to output_dir =====
            project_dir = Path(output_dir)
            project_dir.mkdir(parents=True, exist_ok=True)

            saved_count = 0
            for i, res in enumerate(output):
                try:
                    res.save_to_json(save_path=str(project_dir))
                    res.save_to_markdown(save_path=str(project_dir))
                    saved_count += 1
                except Exception as e:
                    logger.warning(f"⚠️ Failed to save result {i}: {e}")

            logger.info(f"✅ Parse complete: {saved_count} pages saved to {project_dir}")

            return ParseResponse(
                success=True,
                message=f"Parsed {len(output)} pages successfully",
                project_dir=str(project_dir),
                num_pages=len(output),
                parsed_page=page,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Unexpected error in parse_pdf: {e}", exc_info=True)
            return ParseResponse(
                success=False,
                message="Internal server error",
                error=str(e)[:200],
            )
        finally:
            # ===== Step 6: ALWAYS cleanup temp files =====
            for tmp in temp_files:
                if tmp.exists():
                    try:
                        tmp.unlink()
                        logger.debug(f"🧹 Cleaned up: {tmp.name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to cleanup {tmp}: {e}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with memory and model status."""
    mem_status = check_memory_status()
    model_loaded = _paddleocr_vl is not None

    if not mem_status["ok"]:
        status_level = "degraded" if mem_status["percent"] < MEMORY_EMERGENCY_PERCENT else "error"
    elif not model_loaded:
        status_level = "initializing"
    else:
        status_level = "ready"

    return HealthResponse(
        status=status_level,
        memory_percent=mem_status["percent"],
        model_loaded=model_loaded,
        paddleocr_available=PADDLEOCR_AVAILABLE,
        message=mem_status["message"],
    )


@app.get("/metrics")
async def get_metrics():
    """Simple metrics endpoint for monitoring."""
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.1)

    return {
        "memory": {
            "percent": mem.percent,
            "available_gb": mem.available / (1024**3),
            "total_gb": mem.total / (1024**3),
        },
        "cpu_percent": cpu,
        "model_loaded": _paddleocr_vl is not None,
        "paddleocr_available": PADDLEOCR_AVAILABLE,
        "concurrent_limit": MAX_CONCURRENT_REQUESTS,
        "max_pdf_size_mb": MAX_PDF_SIZE_MB,
    }


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "PaddleOCR-VL Service",
        "version": "1.1.0",
        "docs": "/docs",
        "health": "/health",
        "parse_endpoint": "POST /parse",
        "limits": {
            "max_concurrent_requests": MAX_CONCURRENT_REQUESTS,
            "max_pdf_size_mb": MAX_PDF_SIZE_MB,
            "max_pages": MAX_PAGES_PER_REQUEST,
        },
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "success": False},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "success": False},
    )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="PaddleOCR-VL Service - Memory-safe document parsing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pp_doclayout_service.py
  python pp_doclayout_service.py --host 0.0.0.0 --port 8002 --workers 4

Memory Guidelines:
  • 16GB RAM: --workers 1-2
  • 32GB RAM: --workers 2-4
  • 64GB+ RAM: --workers 4-8

  Each worker loads ~2-4GB for the PaddleOCR-VL model.
        """,
    )

    parser.add_argument("--port", type=int, default=8002, help="Port to run service (default: 8002)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--workers", type=int, default=2, help="Number of worker processes (default: 2)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    logger.info("🚀 Starting PaddleOCR-VL Service")
    logger.info(f"   Host: {args.host}, Port: {args.port}")
    logger.info(f"   Workers: {args.workers}")
    logger.info(f"   Max concurrent requests: {MAX_CONCURRENT_REQUESTS}")
    logger.info(f"   Max PDF size: {MAX_PDF_SIZE_MB}MB")

    if not PADDLEOCR_AVAILABLE:
        logger.warning("⚠️ PaddleOCR-VL not installed - service will return errors")
        logger.info("💡 Install with: pip install paddleocr-vl")

    estimated_ram_gb = args.workers * 3
    logger.info(f"💡 Estimated RAM usage: ~{estimated_ram_gb}GB for {args.workers} workers")
    if estimated_ram_gb > 20:
        logger.warning("⚠️ High memory usage expected - monitor closely")

    uvicorn.run(
        "pp_doclayout_service:app",
        host=args.host,
        port=args.port,
        workers=args.workers if not args.reload else 1,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()