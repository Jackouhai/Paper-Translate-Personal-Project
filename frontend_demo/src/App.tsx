import { ChangeEvent, DragEvent, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Download,
  FileCheck2,
  FileText,
  Info,
  LoaderCircle,
  Minus,
  Plus,
  RotateCcw,
  Sparkles,
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
type MobileView = "original" | "translated";
type StepState = "complete" | "current" | "locked";

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

function statusDescription(job: Job) {
  if (job.status === "queued") return "Hệ thống sẽ bắt đầu xử lý tài liệu ngay.";
  if (job.status === "parsing") return "Đang nhận diện cột, bảng, hình và công thức.";
  if (job.status === "translating") return "Bản dịch đang được tạo và giữ lại bố cục gốc.";
  if (job.status === "rendering") return "Đang ghép nội dung thành PDF để tải xuống.";
  if (job.status === "completed") return "Bạn có thể xem trước hoặc tải bản PDF tiếng Việt.";
  return "Có lỗi trong quá trình xử lý. Bạn có thể thử lại với tài liệu này.";
}

function statusProgress(job: Job) {
  if (job.status === "queued") return 8;
  if (job.status === "parsing") return 28;
  if (job.status === "translating") return Math.min(82, 35 + (job.completed_pages / Math.max(job.total_pages, 1)) * 42);
  if (job.status === "rendering") return 92;
  return job.status === "completed" ? 100 : 0;
}

function stepState(step: number, file: File | null, job: Job | null): StepState {
  if (step === 1) return file ? "complete" : "current";
  if (step === 2) return !file ? "locked" : job ? "complete" : "current";
  return job?.status === "completed" ? "complete" : job ? "current" : "locked";
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
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [mobileView, setMobileView] = useState<MobileView>("original");

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
      setPageCount(0);
      setUploadError("Chỉ hỗ trợ tệp PDF.");
      return;
    }

    setIsReading(true);
    setFile(null);
    setPageCount(0);
    setJob(null);
    try {
      const pages = await readPageCount(nextFile);
      setPageCount(pages);
      setFile(nextFile);
      setPageNumber(1);
      setPageInput("1");
      setMobileView("original");
    } catch {
      setUploadError("Không thể đọc tệp PDF này. Hãy kiểm tra tệp hoặc thử một bản PDF khác.");
    } finally {
      setIsReading(false);
    }
  }

  function onFileInput(event: ChangeEvent<HTMLInputElement>) {
    void selectFile(event.target.files?.[0]);
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setIsDragging(false);
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
      setMobileView("translated");
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
    setMobileView("original");
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

  const renderSteps = [
    { number: 1, label: "Tải tài liệu", hint: "PDF học thuật" },
    { number: 2, label: "Chọn phạm vi", hint: "Toàn bộ hoặc một trang" },
    { number: 3, label: "Bắt đầu dịch", hint: "Giữ nguyên bố cục" },
  ];

  return (
    <main className="workspace-shell">
      <header className="workspace-header">
        <div className="brand" aria-label="PP-DocLayout">
          <div className="brand-mark" aria-hidden="true">PP</div>
          <div className="brand-copy"><strong>PP-DocLayout</strong><span>Academic PDF Translation</span></div>
        </div>
        <div className="header-actions">
          <div className="zoom-controls" role="group" aria-label="Thu phóng PDF">
            <button className="icon-button" aria-label="Thu nhỏ PDF" title="Thu nhỏ PDF" onClick={() => setScale((value) => Math.max(0.5, value - 0.15))} type="button"><Minus size={16} /></button>
            <span aria-live="polite">{Math.round(scale * 100)}%</span>
            <button className="icon-button" aria-label="Phóng to PDF" title="Phóng to PDF" onClick={() => setScale((value) => Math.min(1.6, value + 0.15))} type="button"><Plus size={16} /></button>
          </div>
          <span className={`header-status ${file ? "has-document" : ""}`}><span className="status-dot" />{file ? `${pageCount || "?"} trang` : "Sẵn sàng"}</span>
        </div>
      </header>

      <section className="workspace-grid">
        <aside className="control-column" aria-label="Tạo bản dịch">
          <div className="control-heading">
            <p className="eyebrow"><Sparkles size={14} /> Translation workspace</p>
            <h1>Dịch PDF học thuật</h1>
            <p>Biến tài liệu tiếng Anh thành bản tiếng Việt dễ đọc, vẫn giữ cấu trúc và bố cục gốc.</p>
          </div>

          <ol className="workflow-steps" aria-label="Các bước dịch tài liệu">
            {renderSteps.map((step) => {
              const state = stepState(step.number, file, job);
              return <li className={`workflow-step ${state}`} key={step.number}>
                <span className="step-marker">{state === "complete" ? <Check size={15} /> : step.number}</span>
                <span className="step-copy"><strong>{step.label}</strong><small>{step.hint}</small></span>
              </li>;
            })}
          </ol>

          <input ref={inputRef} id="pdf-file" className="visually-hidden" type="file" accept="application/pdf,.pdf" onChange={onFileInput} />
          <button
            className={`drop-zone ${file ? "has-file" : ""} ${isDragging ? "is-dragging" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }}
            onDragOver={(event) => event.preventDefault()}
            onDragLeave={() => setIsDragging(false)}
            onDrop={onDrop}
            disabled={controlsLocked || isReading}
            aria-describedby="upload-hint"
            type="button"
          >
            <span className="drop-icon">{isReading ? <LoaderCircle className="spin" size={25} /> : file ? <FileCheck2 size={25} /> : <Upload size={25} />}</span>
            <span className="drop-title">{isReading ? "Đang đọc tài liệu..." : file ? file.name : "Chọn hoặc thả tệp PDF"}</span>
            <small id="upload-hint">{file ? `${formatSize(file.size)} · ${pageCount} trang` : "PDF tối đa 100 MB · xử lý ngay trên workspace"}</small>
          </button>

          <div className="section-label"><span>Phạm vi dịch</span><span className="section-number">02</span></div>
          <div className="scope-control" role="group" aria-label="Phạm vi dịch">
            <button className={mode === "full" ? "selected" : ""} aria-pressed={mode === "full"} onClick={() => updateMode("full")} disabled={!file || controlsLocked} type="button"><span>Toàn bộ</span><small>{pageCount || "—"} trang</small></button>
            <button className={mode === "page" ? "selected" : ""} aria-pressed={mode === "page"} onClick={() => updateMode("page")} disabled={!file || controlsLocked} type="button"><span>Một trang</span><small>Thử nhanh</small></button>
          </div>

          {mode === "page" && <label className="page-picker" htmlFor="page-number"><span>Trang cần dịch</span><span className="page-input-wrap"><input id="page-number" type="number" min="1" max={pageCount || undefined} value={pageInput} onChange={(event) => { const next = event.target.value; setPageInput(next); const numericPage = Number(next); if (Number.isInteger(numericPage) && numericPage >= 1 && (!pageCount || numericPage <= pageCount)) updatePage(numericPage); }} onBlur={normalizePageInput} disabled={!file || controlsLocked} /><span>/ {pageCount || "?"}</span></span></label>}

          {uploadError && <p className="error-text" role="alert"><XCircle size={16} />{uploadError}</p>}
          {job?.status === "failed" && <p className="error-text" role="alert"><XCircle size={16} />{job.error || "Không thể hoàn tất bản dịch."}</p>}

          {job && <div className={`status-card status-${job.status}`} role="status" aria-live="polite" aria-atomic="true">
            <div className="status-card-heading"><span className="status-icon">{job.status === "completed" ? <CheckCircle2 size={17} /> : job.status === "failed" ? <XCircle size={17} /> : <LoaderCircle className="spin" size={17} />}</span><span><strong>{statusLabel(job)}</strong><small>{statusDescription(job)}</small></span></div>
            {job.status !== "failed" && <div className="progress-track" aria-label={`Tiến độ ${Math.round(statusProgress(job))}%`}><span style={{ width: `${statusProgress(job)}%` }} /></div>}
            <div className="status-meta"><span>{job.mode === "page" ? "Một trang" : `${job.total_pages} trang`}</span>{job.status === "translating" && <span>{job.completed_pages}/{job.total_pages} đã dịch</span>}</div>
          </div>}

          <button className="primary-action" onClick={() => void submit()} disabled={!file || isReading || isSubmitting || controlsLocked} type="button">
            {isSubmitting || jobActive ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}
            <span>{jobActive ? statusLabel(job) : "Bắt đầu dịch"}</span>
          </button>

          {job?.status === "completed" && <a className="download-button" href={translatedSource ?? undefined} download><Download size={17} />Tải PDF dịch</a>}
          {(file || job) && <button className="reset-button" onClick={reset} disabled={jobActive} type="button"><RotateCcw size={16} />Tài liệu mới</button>}
          <p className="privacy-note"><Info size={14} /> Tài liệu chỉ được dùng cho phiên dịch hiện tại.</p>
        </aside>

        <div className="mobile-preview-tabs" role="tablist" aria-label="Chọn bản xem trước">
          <button role="tab" aria-selected={mobileView === "original"} className={mobileView === "original" ? "selected" : ""} onClick={() => setMobileView("original")} type="button">PDF gốc</button>
          <button role="tab" aria-selected={mobileView === "translated"} className={mobileView === "translated" ? "selected" : ""} onClick={() => setMobileView("translated")} type="button">Bản dịch tiếng Việt</button>
        </div>

        <PdfPanel title="PDF gốc" source={file} mode={mode} pageNumber={sourcePage} knownPages={pageCount} scale={scale} onLoadPages={setPageCount} mobileView={mobileView} panelView="original" />
        <PdfPanel title="Bản dịch tiếng Việt" source={translatedSource} mode={mode} pageNumber={translatedPage} knownPages={mode === "full" ? job?.total_pages ?? 0 : 1} scale={scale} status={statusLabel(job)} completed={job?.status === "completed"} mobileView={mobileView} panelView="translated" />
      </section>
    </main>
  );
}

function PdfPanel({ title, source, mode, pageNumber, knownPages, scale, onLoadPages, status, completed, mobileView, panelView }: {
  title: string;
  source: PdfSource;
  mode: Mode;
  pageNumber: number;
  knownPages: number;
  scale: number;
  onLoadPages?: (pages: number) => void;
  status?: string;
  completed?: boolean;
  mobileView: MobileView;
  panelView: MobileView;
}) {
  const [loadedPages, setLoadedPages] = useState(0);
  const [error, setError] = useState(false);
  const isOriginal = panelView === "original";

  useEffect(() => {
    setLoadedPages(0);
    setError(false);
  }, [source]);

  const totalPages = loadedPages || knownPages;
  const pages = mode === "full"
    ? Array.from({ length: totalPages }, (_, index) => index + 1)
    : [pageNumber];

  return (
    <section className={`document-column ${mobileView !== panelView ? "mobile-panel-hidden" : ""}`} aria-label={title}>
      <header className="document-header">
        <div className="document-heading"><span className={`document-icon ${isOriginal ? "original" : "translated"}`}>{isOriginal ? <FileText size={16} /> : <FileCheck2 size={16} />}</span><div><strong>{title}</strong><small>{mode === "page" ? `Trang ${pageNumber}` : totalPages ? `${totalPages} trang` : "Chưa có tài liệu"}</small></div></div>
        {completed && <span className="completed-badge"><CheckCircle2 size={16} /> Sẵn sàng</span>}
      </header>
      <div className="document-scroll" tabIndex={0} aria-label={`Vùng xem ${title}`}>
        {!source && <div className="document-placeholder">{status && status !== "Chưa có bản dịch" ? <><LoaderCircle className="placeholder-icon spin" size={30} /><strong>{status}</strong><span>PDF dịch sẽ xuất hiện tại đây khi hoàn tất.</span></> : <><span className="placeholder-icon"><FileText size={27} /></span><strong>{isOriginal ? "Chọn PDF để xem trước" : "Chưa có bản dịch"}</strong><span>{isOriginal ? "Tài liệu nguồn sẽ hiển thị ngay sau khi chọn file." : "Chọn tài liệu và bắt đầu dịch để xem kết quả."}</span></>}</div>}
        {source && error && <p className="error-text" role="alert"><XCircle size={16} />Không thể hiển thị PDF.</p>}
        {source && !error && <Document file={source} loading={<div className="document-loading" role="status"><LoaderCircle className="spin" size={26} /><span>Đang tải bản xem trước...</span></div>} error={<p className="error-text" role="alert"><XCircle size={16} />Không thể tải PDF.</p>} onLoadSuccess={({ numPages }) => { setLoadedPages(numPages); onLoadPages?.(numPages); }} onLoadError={() => setError(true)}>
          <div className="pdf-pages">{pages.map((page) => <Page key={page} pageNumber={page} scale={scale} renderTextLayer={false} renderAnnotationLayer={false} />)}</div>
        </Document>}
      </div>
    </section>
  );
}

export default App;
