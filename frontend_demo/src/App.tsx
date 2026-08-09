import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  Download,
  FileText,
  LoaderCircle,
  Minus,
  Plus,
  RotateCcw,
  Upload,
  XCircle,
} from "lucide-react";
import { Document, Page, pdfjs } from "react-pdf";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

type JobStatus = "queued" | "parsing" | "translating" | "rendering" | "completed" | "failed";
type Mode = "full" | "page";
type PdfSource = File | string | null;

interface Job {
  job_id: string;
  filename: string;
  mode: Mode;
  selected_page: number | null;
  total_pages: number;
  status: JobStatus;
  completed_pages: number;
  error: string | null;
  translated_pdf_available: boolean;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

function apiPath(path: string) {
  return `${API_BASE.replace(/\/$/, "")}${path}`;
}

async function readPageCount(file: File): Promise<number> {
  const document = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise;
  const pages = document.numPages;
  await document.destroy();
  return pages;
}

function formatSize(bytes: number) {
  return `${(bytes / 1024 / 1024).toFixed(bytes >= 10 * 1024 * 1024 ? 0 : 1)} MB`;
}

function statusLabel(job: Job | null) {
  if (!job) return "Chưa có bản dịch";
  if (job.status === "queued") return "Đang chờ xử lý";
  if (job.status === "parsing") return "Đang phân tích bố cục";
  if (job.status === "translating") return job.completed_pages ? `Đã dịch ${job.completed_pages} trang` : "Đang dịch nội dung";
  if (job.status === "rendering") return "Đang xuất PDF";
  if (job.status === "completed") return "Bản dịch đã sẵn sàng";
  return "Dịch không hoàn tất";
}

function App() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [mode, setMode] = useState<Mode>("full");
  const [pageNumber, setPageNumber] = useState(1);
  const [pageInput, setPageInput] = useState("1");
  const [scale, setScale] = useState(0.85);
  const [isReading, setIsReading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const jobActive = Boolean(job && job.status !== "completed" && job.status !== "failed");
  const controlsLocked = jobActive;
  const sourcePage = mode === "page" ? pageNumber : 1;
  const translatedSource = job?.status === "completed"
    ? apiPath(`/jobs/${job.job_id}/translated.pdf`)
    : null;
  const translatedPage = mode === "page" ? 1 : sourcePage;

  useEffect(() => {
    if (!jobActive || !job) return;
    const interval = window.setInterval(async () => {
      try {
        const response = await fetch(apiPath(`/jobs/${job.job_id}`));
        if (!response.ok) throw new Error("Không thể cập nhật trạng thái job.");
        setJob(await response.json() as Job);
      } catch (error) {
        setJob((current) => current
          ? { ...current, status: "failed", error: error instanceof Error ? error.message : "Không thể kết nối API." }
          : current);
      }
    }, 1200);
    return () => window.clearInterval(interval);
  }, [job, jobActive]);

  async function selectFile(nextFile: File | undefined) {
    setUploadError(null);
    if (!nextFile) return;
    if (nextFile.type !== "application/pdf" && !nextFile.name.toLowerCase().endsWith(".pdf")) {
      setFile(null);
      setUploadError("Chỉ hỗ trợ tệp PDF.");
      return;
    }

    setIsReading(true);
    setJob(null);
    try {
      setPageCount(await readPageCount(nextFile));
    } catch {
      setPageCount(0);
    } finally {
      setFile(nextFile);
      setPageNumber(1);
      setPageInput("1");
      setIsReading(false);
    }
  }

  function onFileInput(event: ChangeEvent<HTMLInputElement>) {
    void selectFile(event.target.files?.[0]);
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    void selectFile(event.dataTransfer.files?.[0]);
  }

  async function submit() {
    if (!file || isReading || controlsLocked) return;
    const requestedPage = normalizePageInput();
    setIsSubmitting(true);
    setUploadError(null);
    const data = new FormData();
    data.append("file", file);
    data.append("mode", mode);
    if (mode === "page") data.append("page_number", String(requestedPage));

    try {
      const response = await fetch(apiPath("/jobs"), { method: "POST", body: data });
      const payload = await response.json() as Job | { detail?: string };
      if (!response.ok) throw new Error("detail" in payload ? payload.detail : "Không thể tạo job dịch.");
      setJob(payload as Job);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Không thể tạo job dịch.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function reset() {
    setFile(null);
    setPageCount(0);
    setPageNumber(1);
    setPageInput("1");
    setUploadError(null);
    setJob(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  function updateMode(nextMode: Mode) {
    if (nextMode === mode) return;
    setMode(nextMode);
    if (job?.status === "completed") setJob(null);
  }

  function updatePage(nextPage: number) {
    if (nextPage === pageNumber) return;
    setPageNumber(nextPage);
    if (job?.status === "completed") setJob(null);
  }

  function normalizePageInput() {
    const candidate = Number(pageInput);
    const maximum = pageCount || 1;
    const normalized = Number.isInteger(candidate) ? Math.min(Math.max(candidate, 1), maximum) : 1;
    updatePage(normalized);
    setPageInput(String(normalized));
    return normalized;
  }

  return (
    <main className="workspace-shell">
      <header className="workspace-header">
        <div className="brand"><div className="brand-mark">PP</div><div><strong>PP-DocLayout</strong><span>Academic PDF Translation</span></div></div>
        <div className="header-actions">
          <div className="zoom-controls" aria-label="Thu phóng PDF">
            <button className="icon-button" title="Thu nhỏ PDF" onClick={() => setScale((value) => Math.max(0.5, value - 0.15))} type="button"><Minus size={16} /></button>
            <span>{Math.round(scale * 100)}%</span>
            <button className="icon-button" title="Phóng to PDF" onClick={() => setScale((value) => Math.min(1.6, value + 0.15))} type="button"><Plus size={16} /></button>
          </div>
          <span className="header-status">{file ? `${pageCount || "?"} trang` : "Sẵn sàng"}</span>
        </div>
      </header>

      <section className="workspace-grid">
        <aside className="control-column" aria-label="Tạo bản dịch">
          <div className="control-heading"><p className="eyebrow">Tài liệu</p><h1>Dịch PDF học thuật</h1><p>Chọn phạm vi trước khi bắt đầu dịch.</p></div>
          <input ref={inputRef} id="pdf-file" type="file" accept="application/pdf,.pdf" onChange={onFileInput} />
          <button className={`drop-zone ${file ? "has-file" : ""}`} onClick={() => inputRef.current?.click()} onDragOver={(event) => event.preventDefault()} onDrop={onDrop} disabled={controlsLocked} type="button">
            {isReading ? <LoaderCircle className="spin" size={27} /> : file ? <FileText size={27} /> : <Upload size={27} />}
            <span>{file ? file.name : "Chọn hoặc thả tệp PDF"}</span>
            <small>{file ? `${formatSize(file.size)} · ${pageCount ? `${pageCount} trang` : "Đang xác thực"}` : "PDF tối đa 100 MB"}</small>
          </button>

          <div className="scope-control" role="group" aria-label="Phạm vi dịch">
            <button className={mode === "full" ? "selected" : ""} onClick={() => updateMode("full")} disabled={!file || controlsLocked} type="button">Toàn bộ</button>
            <button className={mode === "page" ? "selected" : ""} onClick={() => updateMode("page")} disabled={!file || controlsLocked} type="button">Một trang</button>
          </div>

          {mode === "page" && <label className="page-picker">Trang cần dịch<div><input type="number" min="1" value={pageInput} onChange={(event) => { const next = event.target.value; setPageInput(next); const numericPage = Number(next); if (Number.isInteger(numericPage) && numericPage >= 1 && (!pageCount || numericPage <= pageCount)) updatePage(numericPage); }} onBlur={normalizePageInput} disabled={!file || controlsLocked} /><span>/ {pageCount || "?"}</span></div></label>}

          {uploadError && <p className="error-text"><XCircle size={16} />{uploadError}</p>}
          {job?.status === "failed" && <p className="error-text"><XCircle size={16} />{job.error}</p>}

          <button className="primary-action" onClick={() => void submit()} disabled={!file || isReading || isSubmitting || controlsLocked} type="button">
            {isSubmitting || jobActive ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}
            {jobActive ? statusLabel(job) : "Bắt đầu dịch"}
          </button>

          {job?.status === "completed" && <a className="download-button" href={translatedSource ?? undefined} download><Download size={17} />Tải PDF dịch</a>}
          {(file || job) && <button className="reset-button" onClick={reset} disabled={jobActive} type="button"><RotateCcw size={16} />Tài liệu mới</button>}
        </aside>

        <PdfPanel title="PDF gốc" source={file} mode={mode} pageNumber={sourcePage} knownPages={pageCount} scale={scale} onLoadPages={setPageCount} />
        <PdfPanel title="Bản dịch tiếng Việt" source={translatedSource} mode={mode} pageNumber={translatedPage} knownPages={mode === "full" ? job?.total_pages ?? 0 : 1} scale={scale} status={statusLabel(job)} completed={job?.status === "completed"} />
      </section>
    </main>
  );
}

function PdfPanel({ title, source, mode, pageNumber, knownPages, scale, onLoadPages, status, completed }: {
  title: string;
  source: PdfSource;
  mode: Mode;
  pageNumber: number;
  knownPages: number;
  scale: number;
  onLoadPages?: (pages: number) => void;
  status?: string;
  completed?: boolean;
}) {
  const [loadedPages, setLoadedPages] = useState(0);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoadedPages(0);
    setError(false);
  }, [source]);

  const totalPages = loadedPages || knownPages;
  const pages = mode === "full"
    ? Array.from({ length: totalPages }, (_, index) => index + 1)
    : [pageNumber];

  return (
    <section className="document-column">
      <header><div><strong>{title}</strong><small>{mode === "page" ? `Trang ${pageNumber}` : totalPages ? `${totalPages} trang` : ""}</small></div>{completed && <CheckCircle2 size={18} />}</header>
      <div className="document-scroll">
        {!source && <div className="document-placeholder">{status && status !== "Chưa có bản dịch" ? <><LoaderCircle className="spin" size={30} /><strong>{status}</strong><span>PDF dịch sẽ xuất hiện tại đây khi hoàn tất.</span></> : <><FileText size={30} /><strong>{title === "PDF gốc" ? "Chọn PDF để xem trước" : "Chưa có bản dịch"}</strong><span>{title === "PDF gốc" ? "Tài liệu nguồn sẽ hiển thị ngay sau khi chọn file." : "Chọn tài liệu và bắt đầu dịch để xem kết quả."}</span></>}</div>}
        {source && error && <p className="error-text"><XCircle size={16} />Không thể hiển thị PDF.</p>}
        {source && !error && <Document file={source} loading={<LoaderCircle className="spin" size={30} />} error={<p className="error-text"><XCircle size={16} />Không thể tải PDF.</p>} onLoadSuccess={({ numPages }) => { setLoadedPages(numPages); onLoadPages?.(numPages); }} onLoadError={() => setError(true)}>
          <div className="pdf-pages">{pages.map((page) => <Page key={page} pageNumber={page} scale={scale} renderTextLayer={false} renderAnnotationLayer={false} />)}</div>
        </Document>}
      </div>
    </section>
  );
}

export default App;
