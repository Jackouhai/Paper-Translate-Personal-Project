import React, { useState, useRef, useEffect, useCallback } from "react";
import { useModelManager } from "./hooks/useModelManager";
import {
  FileText,
  Upload,
  Settings as SettingsIcon,
  History as HistoryIcon,
  Info,
  CheckCircle2,
  Download,
  FileCode,
  FileDown,
  Loader2,
  X,
  File as FileIcon,
  Languages,
  Cpu,
  ScanLine,
  Layers,
  Eye,
  Play,
  Square,
  RefreshCw,
  AlertCircle,
  Server,
} from "lucide-react";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8002";

/* -------------------------------------------------------------------------- */
/* Constants & mock data                                                       */
/* -------------------------------------------------------------------------- */

const NAV_ITEMS = [
  { id: "translate", label: "Translate Document", icon: Languages },
  { id: "history", label: "History", icon: HistoryIcon },
  { id: "settings", label: "Settings", icon: SettingsIcon },
  { id: "about", label: "About", icon: Info },
];

const TRANSLATION_MODELS = [
  {
    id: "translategemma",
    label: "TranslateGemma 4B",
    description: "Multimodal layout-aware model, optimized for scientific PDFs",
  },
];

const TRANSLATION_POLICY_OPTIONS = [
  { id: "abstract", label: "Translate Abstract" },
  { id: "mainText", label: "Translate Main Text" },
  { id: "figureCaptions", label: "Translate Figure Captions" },
  { id: "tableCaptions", label: "Translate Table Captions" },
];

const PRESERVATION_OPTIONS = [
  { id: "references", label: "Preserve References" },
  { id: "formulas", label: "Preserve Formulas" },
  { id: "tables", label: "Preserve Tables" },
  { id: "figures", label: "Preserve Figures" },
];

const OCR_OPTIONS = [
  { id: "layoutDetection", label: "Layout Detection", defaultValue: true },
  { id: "ocrInsideImages", label: "OCR Text Inside Images", defaultValue: true },
  { id: "autoRotate", label: "Auto Rotate Pages", defaultValue: true },
  { id: "chartRecognition", label: "Chart Recognition", defaultValue: false },
];

const EXPORT_FORMATS = [
  { id: "html", label: "HTML", icon: FileCode },
  { id: "pdf", label: "PDF", icon: FileDown },
  { id: "markdown", label: "Markdown", icon: FileText },
];

const PROGRESS_STEPS = [
  { id: "ocr", label: "OCR Analysis", fakeDuration: 2100 },
  { id: "layout", label: "Layout Detection", fakeDuration: 1600 },
  { id: "translation", label: "Translation", fakeDuration: 4500 },
  { id: "reconstruction", label: "Document Reconstruction", fakeDuration: 2200 },
  { id: "export", label: "Export", fakeDuration: 1400 },
];

const MODEL_STATE_STYLES = {
  stopped: {
    label: "Stopped",
    className: "bg-slate-100 text-slate-600",
  },
  starting: {
    label: "Starting",
    className: "bg-amber-50 text-amber-700",
  },
  ready: {
    label: "Ready",
    className: "bg-emerald-50 text-emerald-700",
  },
  failed: {
    label: "Failed",
    className: "bg-red-50 text-red-700",
  },
  external: {
    label: "Running externally",
    className: "bg-purple-50 text-purple-700",
  },
};

const MOCK_STATS = {
  pages: 15,
  figures: 22,
  tables: 8,
  formulas: 56,
  translatedBlocks: 312,
};

const MOCK_HISTORY = [
  {
    fileName: "attention_is_all_you_need.pdf",
    date: "2026-06-10",
    model: "TranslateGemma 4B",
    status: "Completed",
    output: "HTML, PDF",
  },
  {
    fileName: "deep_residual_learning.pdf",
    date: "2026-06-08",
    model: "HY-MT 1.8B",
    status: "Completed",
    output: "PDF, Markdown",
  },
  {
    fileName: "bert_pretraining.pdf",
    date: "2026-06-05",
    model: "TranslateGemma 4B",
    status: "Completed",
    output: "HTML",
  },
  {
    fileName: "gpt3_few_shot_learners.pdf",
    date: "2026-06-01",
    model: "TranslateGemma 4B",
    status: "Failed",
    output: "—",
  },
  {
    fileName: "vision_transformer.pdf",
    date: "2026-05-28",
    model: "HY-MT 1.8B",
    status: "Completed",
    output: "HTML, PDF, Markdown",
  },
];

async function downloadFile(url, filename) {
  if (!url) {
    throw new Error("Download URL is missing");
  }

  const absoluteUrl = url.startsWith("http://") || url.startsWith("https://")
    ? url
    : `http://127.0.0.1:8002${url}`;

  const response = await fetch(absoluteUrl);

  if (!response.ok) {
    throw new Error(
      `Download failed with HTTP ${response.status}: ${response.statusText}`,
    );
  }

  const blob = await response.blob();
  const blobUrl = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = blobUrl;
  link.download = filename;
  link.style.display = "none";

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  window.setTimeout(() => {
    URL.revokeObjectURL(blobUrl);
  }, 1000);
}

/* -------------------------------------------------------------------------- */
/* Helper components                                                          */
/* -------------------------------------------------------------------------- */

function formatFileSize(bytes) {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function Checkbox({ id, label, checked, onChange }) {
  return (
    <label
      htmlFor={id}
      className="flex items-center gap-2.5 cursor-pointer select-none py-1"
    >
      <span className="relative flex items-center justify-center w-4.5 h-4.5">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="peer appearance-none w-[18px] h-[18px] rounded-[4px] border border-slate-300 bg-white checked:bg-blue-600 checked:border-blue-600 transition-colors cursor-pointer"
        />
        <CheckCircle2
          className="pointer-events-none absolute w-3 h-3 text-white opacity-0 peer-checked:opacity-100 transition-opacity"
          strokeWidth={3}
        />
      </span>
      <span className="text-sm text-slate-700">{label}</span>
    </label>
  );
}

function RadioOption({ id, name, label, description, checked, onChange }) {
  return (
    <label
      htmlFor={id}
      className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
        checked
          ? "border-blue-400 bg-blue-50/60"
          : "border-slate-200 bg-white hover:border-slate-300"
      }`}
    >
      <span className="relative flex items-center justify-center w-4.5 h-4.5 mt-0.5 flex-shrink-0">
        <input
          id={id}
          type="radio"
          name={name}
          checked={checked}
          onChange={onChange}
          className="appearance-none w-[18px] h-[18px] rounded-full border border-slate-300 bg-white checked:border-blue-600 checked:border-[5px] transition-all cursor-pointer"
        />
      </span>
      <span>
        <span className="block text-sm font-medium text-slate-800">{label}</span>
        <span className="block text-xs text-slate-500 mt-0.5">{description}</span>
      </span>
    </label>
  );
}

function SectionCard({ title, icon: Icon, children, className = "" }) {
  return (
    <div className={`bg-white border border-slate-200 rounded-xl p-5 ${className}`}>
      <div className="flex items-center gap-2 mb-4">
        {Icon && <Icon className="w-4 h-4 text-blue-600" />}
        <h3 className="text-sm font-semibold text-slate-800">{title}</h3>
      </div>
      {children}
    </div>
  );
}
function ModelStatusBadge({ state }) {
  const style =
    MODEL_STATE_STYLES[state] ||
    MODEL_STATE_STYLES.stopped;

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${style.className}`}
    >
      {state === "starting" && (
        <Loader2 className="mr-1.5 h-3 w-3 animate-spin" />
      )}

      {style.label}
    </span>
  );
}

function ModelControlCard({
  title,
  description,
  model,
  loading,
  onStart,
  onStop,
}) {
  const state = model?.process_state || "stopped";

  const startDisabled =
    loading ||
    state === "starting" ||
    state === "ready" ||
    state === "external";

  const stopDisabled =
    loading ||
    state === "starting" ||
    state === "stopped" ||
    state === "failed" ||
    state === "external";

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Server className="h-4 w-4 text-blue-600" />

            <h3 className="text-sm font-semibold text-slate-800">
              {title}
            </h3>

            <ModelStatusBadge state={state} />
          </div>

          <p className="mt-2 text-xs leading-relaxed text-slate-500">
            {description}
          </p>

          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-slate-500">
            <span>
              Port:{" "}
              <strong className="font-medium text-slate-700">
                {model?.port ?? "—"}
              </strong>
            </span>

            <span>
              PID:{" "}
              <strong className="font-medium text-slate-700">
                {model?.pid ?? "—"}
              </strong>
            </span>

            <span>
              Managed by app:{" "}
              <strong className="font-medium text-slate-700">
                {model?.owned_by_app ? "Yes" : "No"}
              </strong>
            </span>
          </div>

          {state === "external" && (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-purple-200 bg-purple-50 p-3 text-xs text-purple-700">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />

              <span>
                This model was started outside PaperTranslate.
                The app will not stop or replace the external process.
              </span>
            </div>
          )}

          {model?.last_error && (
            <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />

              <span>{model.last_error}</span>
            </div>
          )}
        </div>

        <div className="flex flex-shrink-0 gap-2">
          <button
            type="button"
            onClick={onStart}
            disabled={startDisabled}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
              startDisabled
                ? "cursor-not-allowed bg-slate-100 text-slate-400"
                : "bg-blue-600 text-white hover:bg-blue-700"
            }`}
          >
            {loading && state !== "ready" ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}

            Start
          </button>

          <button
            type="button"
            onClick={onStop}
            disabled={stopDisabled}
            className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
              stopDisabled
                ? "cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400"
                : "border-red-200 bg-white text-red-600 hover:bg-red-50"
            }`}
          >
            <Square className="h-3.5 w-3.5" />
            Stop
          </button>
        </div>
      </div>
    </div>
  );
}
/* -------------------------------------------------------------------------- */
/* Upload section                                                              */
/* -------------------------------------------------------------------------- */

function UploadSection({ file, onFileSelect, onClear }) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setIsDragging(false);
      const dropped = e.dataTransfer.files?.[0];
      if (dropped && dropped.type === "application/pdf") {
        onFileSelect(dropped);
      }
    },
    [onFileSelect]
  );

  const handleSelect = (e) => {
    const selected = e.target.files?.[0];
    if (selected) onFileSelect(selected);
  };

  if (file) {
    return (
      <div className="bg-white border border-slate-200 rounded-xl p-5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
            <FileIcon className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <p className="text-sm font-medium text-slate-800">{file.name}</p>
            <p className="text-xs text-slate-500">{formatFileSize(file.size)}</p>
          </div>
        </div>
        <button
          onClick={onClear}
          className="text-slate-400 hover:text-slate-600 transition-colors p-1.5 rounded-lg hover:bg-slate-100"
          aria-label="Remove file"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`border-2 border-dashed rounded-xl p-10 flex flex-col items-center justify-center text-center cursor-pointer transition-colors ${
        isDragging
          ? "border-blue-400 bg-blue-50/60"
          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50/50"
      }`}
    >
      <div className="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center mb-3">
        <Upload className="w-5 h-5 text-blue-600" />
      </div>
      <p className="text-sm font-medium text-slate-700">
        Drag and drop your PDF here
      </p>
      <p className="text-xs text-slate-500 mt-1">
        or click to browse from your computer
      </p>
      <p className="text-xs text-slate-400 mt-3">Accepted format: .pdf</p>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        onChange={handleSelect}
        className="hidden"
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Configuration panel                                                         */
/* -------------------------------------------------------------------------- */

function ConfigurationPanel({ config, setConfig }) {
  const toggleCheckbox = (group, id) => {
    setConfig((prev) => ({
      ...prev,
      [group]: { ...prev[group], [id]: !prev[group][id] },
    }));
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <SectionCard title="Translation model" icon={Cpu}>
        <div className="space-y-2">
          {TRANSLATION_MODELS.map((m) => (
            <RadioOption
              key={m.id}
              id={`model-${m.id}`}
              name="translation-model"
              label={m.label}
              description={m.description}
              checked={config.model === m.id}
              onChange={() => setConfig((prev) => ({ ...prev, model: m.id }))}
            />
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Translation policy" icon={Languages}>
        <div className="space-y-0.5">
          {TRANSLATION_POLICY_OPTIONS.map((opt) => (
            <Checkbox
              key={opt.id}
              id={`policy-${opt.id}`}
              label={opt.label}
              checked={config.policy[opt.id]}
              onChange={() => toggleCheckbox("policy", opt.id)}
            />
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Preservation options" icon={Layers}>
        <div className="space-y-0.5">
          {PRESERVATION_OPTIONS.map((opt) => (
            <Checkbox
              key={opt.id}
              id={`preserve-${opt.id}`}
              label={opt.label}
              checked={config.preservation[opt.id]}
              onChange={() => toggleCheckbox("preservation", opt.id)}
            />
          ))}
        </div>
      </SectionCard>

      <SectionCard title="OCR options" icon={ScanLine}>
        <div className="space-y-0.5">
          {OCR_OPTIONS.map((opt) => (
            <Checkbox
              key={opt.id}
              id={`ocr-${opt.id}`}
              label={opt.label}
              checked={config.ocr[opt.id]}
              onChange={() => toggleCheckbox("ocr", opt.id)}
            />
          ))}
        </div>
      </SectionCard>

      <SectionCard title="Export format" icon={Download} className="lg:col-span-2">
        <div className="flex flex-wrap gap-3">
          {EXPORT_FORMATS.map((fmt) => {
            const Icon = fmt.icon;
            const checked = config.exportFormat[fmt.id];
            return (
              <label
                key={fmt.id}
                htmlFor={`export-${fmt.id}`}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                  checked
                    ? "border-blue-400 bg-blue-50/60 text-blue-700"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300"
                }`}
              >
                <input
                  id={`export-${fmt.id}`}
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleCheckbox("exportFormat", fmt.id)}
                  className="hidden"
                />
                <Icon className="w-4 h-4" />
                <span className="text-sm font-medium">{fmt.label}</span>
              </label>
            );
          })}
        </div>
      </SectionCard>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Progress modal                                                              */
/* -------------------------------------------------------------------------- */

function ProgressModal({ steps, currentStepIndex, progressValues, totalElapsed, isComplete, onViewResults }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
        <div className="flex items-center gap-3 mb-1">
          {!isComplete ? (
            <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />
          ) : (
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          )}
          <h2 className="text-base font-semibold text-slate-800">
            {isComplete ? "Translation complete" : "Translating document..."}
          </h2>
        </div>
        <p className="text-xs text-slate-500 mb-5 ml-8">
          {isComplete
            ? `Finished in ${(totalElapsed / 1000).toFixed(1)}s`
            : "This may take a moment. Please don't close this window."}
        </p>

        <div className="space-y-4">
          {steps.map((step, idx) => {
            const value = progressValues[idx] ?? 0;
            const isDone = value >= 100;
            const isActive = idx === currentStepIndex && !isDone;
            return (
              <div key={step.id}>
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    {isDone ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    ) : isActive ? (
                      <Loader2 className="w-3.5 h-3.5 text-blue-600 animate-spin" />
                    ) : (
                      <div className="w-3.5 h-3.5 rounded-full border border-slate-300" />
                    )}
                    <span
                      className={`text-xs font-medium ${
                        isDone || isActive ? "text-slate-700" : "text-slate-400"
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>
                  <span className="text-xs text-slate-400">
                    {isDone
                      ? `${(step.fakeDuration / 1000).toFixed(1)}s`
                      : `${Math.round(value)}%`}
                  </span>
                </div>
                <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-150 ease-linear ${
                      isDone ? "bg-emerald-500" : "bg-blue-600"
                    }`}
                    style={{ width: `${value}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {isComplete && (
          <button
            onClick={onViewResults}
            className="mt-6 w-full bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2.5 rounded-lg transition-colors"
          >
            View results
          </button>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Results area                                                                */
/* -------------------------------------------------------------------------- */

function KatexFormula({ tex, display = false }) {
  const ref = useRef(null);
  useEffect(() => {
    if (window.katex && ref.current) {
      try {
        window.katex.render(tex, ref.current, {
          throwOnError: false,
          displayMode: display,
        });
      } catch {
        ref.current.textContent = tex;
      }
    }
  }, [tex, display]);
  return <span ref={ref} className={display ? "block my-3 overflow-x-auto" : ""} />;
}

function StatCard({ label, value }) {
  return (
    <div className="bg-slate-50 rounded-lg p-3 text-center">
      <p className="text-lg font-semibold text-slate-800">{value}</p>
      <p className="text-xs text-slate-500 mt-0.5">{label}</p>
    </div>
  );
}

function ResultArea({ fileName, totalElapsed, exportFormat, onDownload, resultUrls }) {  
  const [activeTab, setActiveTab] = useState("original");

  const stats = [
    { label: "Pages", value: MOCK_STATS.pages },
    { label: "Figures", value: MOCK_STATS.figures },
    { label: "Tables", value: MOCK_STATS.tables },
    { label: "Formulas", value: MOCK_STATS.formulas },
    { label: "Translated blocks", value: MOCK_STATS.translatedBlocks },
    { label: "Processing time", value: `${(totalElapsed / 1000).toFixed(1)}s` },
  ];

  const downloadButtons = [
    { id: "html", label: "Download HTML", icon: FileCode },
    { id: "pdf", label: "Download PDF", icon: FileDown },
    { id: "markdown", label: "Download Markdown", icon: FileText },
  ].filter((btn) => exportFormat[btn.id]);

  return (
    <div className="space-y-4">
      <div className="bg-white border border-slate-200 rounded-xl p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-lg bg-emerald-50 flex items-center justify-center flex-shrink-0">
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">
              Translation complete
            </p>
            <p className="text-xs text-slate-500">{fileName}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {stats.map((s) => (
            <StatCard key={s.label} label={s.label} value={s.value} />
          ))}
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <div className="flex border-b border-slate-200">
          <button
            onClick={() => setActiveTab("original")}
            className={`px-5 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === "original"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            Original
          </button>
          <button
            onClick={() => setActiveTab("translated")}
            className={`px-5 py-3 text-sm font-medium transition-colors border-b-2 ${
              activeTab === "translated"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            Translated
          </button>
        </div>

        <div className="p-5">
          {activeTab === "original" ? (
            resultUrls?.originalPdf ? (
              <iframe
                src={resultUrls.originalPdf}
                title="Original PDF Preview"
                className="w-full h-[700px] rounded-lg border border-slate-200 bg-white"
              />
            ) : (
              <div className="bg-slate-100 rounded-lg h-96 flex items-center justify-center">
                <div className="text-center">
                  <FileText className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                  <p className="text-sm text-slate-400">Original PDF preview</p>
                </div>
              </div>
            )
          ) : (
            resultUrls?.html ? (
              <div className="w-full min-w-0 max-w-full overflow-hidden">
                <iframe
                  src={resultUrls.html}
                  title="Translated HTML Preview"
                  className="block h-[75vh] w-full max-w-full rounded-lg border border-slate-200 bg-white"
                />
              </div>
            ) : (
              <div className="bg-slate-100 rounded-lg h-96 flex items-center justify-center">
                <p className="text-sm text-slate-400">Translated preview</p>
              </div>
            )
          )}
        </div>
      </div>

      {downloadButtons.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">Download results</h3>
          <div className="flex flex-wrap gap-3">
            {downloadButtons.map((btn) => {
              const Icon = btn.icon;
              return (
                <button
                  key={btn.id}
                  onClick={() => onDownload(btn.label)}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-slate-200 text-sm font-medium text-slate-700 hover:border-blue-300 hover:bg-blue-50/40 transition-colors"
                >
                  <Icon className="w-4 h-4" />
                  {btn.label}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Toast                                                                       */
/* -------------------------------------------------------------------------- */

function Toast({ message, onClose }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000);
    return () => clearTimeout(timer);
  }, [onClose]);

  return (
    <div className="fixed bottom-6 right-6 z-50 bg-slate-800 text-white text-sm px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 animate-in fade-in slide-in-from-bottom-2">
      <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
      {message}
    </div>
  );
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForTranslator() {
  while (true) {
    const response = await fetch(
      `${API_BASE_URL}/pipeline/model-status`,
    );

    if (!response.ok) {
      throw new Error("Could not check model status");
    }

    const data = await response.json();

    if (data.translator_ready) {
      return;
    }

    await sleep(3000);
  }
}

/* -------------------------------------------------------------------------- */
/* Translate page                                                              */
/* -------------------------------------------------------------------------- */

function TranslatePage() {
  const [file, setFile] = useState(null);
  const [config, setConfig] = useState({
    model: "translategemma",
    policy: {
      abstract: true,
      mainText: true,
      figureCaptions: true,
      tableCaptions: true,
    },
    preservation: {
      references: true,
      formulas: true,
      tables: true,
      figures: true,
    },
    ocr: OCR_OPTIONS.reduce(
      (acc, opt) => ({ ...acc, [opt.id]: opt.defaultValue }),
      {}
    ),
    exportFormat: { html: true, pdf: true, markdown: false },
  });

  const [status, setStatus] = useState("idle"); // idle | processing | complete
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [progressValues, setProgressValues] = useState(
    PROGRESS_STEPS.map(() => 0)
  );
  const [totalElapsed, setTotalElapsed] = useState(0);
  const [showResults, setShowResults] = useState(false);
  const [toast, setToast] = useState(null);
  const [resultUrls, setResultUrls] = useState({
    originalPdf: null,
    translatedPdf: null,
    html: null,
    markdownUrls: [],
    jsonUrls: [],
  });

  const [projectName, setProjectName] = useState(null);
  const [pipelineStage, setPipelineStage] = useState("idle");
  // idle | parsing | parsed | translating | completed | failed

  const handleFileSelect = (f) => {
    setFile(f);
    setStatus("idle");
    setPipelineStage("idle");
    setProjectName(null);
    setShowResults(false);
    setTotalElapsed(0);
    setCurrentStepIndex(0);
    setResultUrls({
      originalPdf: null,
      translatedPdf: null,
      html: null,
      markdownUrls: [],
      jsonUrls: [],
    });
    setProgressValues(PROGRESS_STEPS.map(() => 0));
  };

  const handleClearFile = () => {
    setFile(null);
    setStatus("idle");
    setPipelineStage("idle");
    setProjectName(null);
    setShowResults(false);
    setTotalElapsed(0);
    setCurrentStepIndex(0);
    setResultUrls({
      originalPdf: null,
      translatedPdf: null,
      html: null,
      markdownUrls: [],
      jsonUrls: [],
    });
    setProgressValues(PROGRESS_STEPS.map(() => 0));
  };

  const startTranslation = async () => {
    if (!file) {
      setToast("Please select a PDF file");
      return;
    }

    setStatus("processing");
    setPipelineStage("parsing");
    setShowResults(false);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const parseResponse = await fetch(
        `${API_BASE_URL}/pipeline/parse`,
        {
          method: "POST",
          body: formData,
        },
      );

      const parseData = await parseResponse.json();

      if (!parseResponse.ok) {
        throw new Error(parseData.detail || "PDF parsing failed");
      }

      setProjectName(parseData.project_name);

      setResultUrls({
        originalPdf: parseData.pdf_url,
        translatedPdf: null,
        html: null,
        markdownUrls: [],
        jsonUrls: [],
      });

      setPipelineStage("waiting_for_translator");
      setToast("Stop PaddleOCR and start TranslateGemma");

      await waitForTranslator();

      setPipelineStage("translating");
      setToast("TranslateGemma detected. Starting translation.");

      const translateResponse = await fetch(
        `${API_BASE_URL}/pipeline/translate/${encodeURIComponent(
          parseData.project_name,
        )}`,
        {
          method: "POST",
        },
      );

      const translateData = await translateResponse.json();

      if (!translateResponse.ok) {
        throw new Error(
          translateData.detail || "Translation failed",
        );
      }

      setResultUrls((current) => ({
        ...current,
        html: translateData.html_url,
        markdownUrls: translateData.markdown_urls,
        jsonUrls: translateData.json_urls || [],
        translatedPdf: translateData.pdf_url,
      }));

      setPipelineStage("completed");
      setStatus("complete");
      setShowResults(true);
      setToast("Translation completed");
    } catch (error) {
      console.error(error);
      setPipelineStage("failed");
      setStatus("idle");
      setToast(error.message || "Pipeline failed");
    }
  };
  const handleDownload = async (label) => {
    const outputName =
      projectName ||
      file?.name?.replace(/\.pdf$/i, "") ||
      "translated_document";

    try {
      if (label.includes("HTML")) {
        if (!resultUrls.html) {
          setToast("Translated HTML is not available yet");
          return;
        }

        await downloadFile(resultUrls.html, `${outputName}.html`);
        setToast("HTML download started");
        return;
      }

      if (label.includes("Markdown")) {
        const firstMarkdownUrl = resultUrls.markdownUrls?.[0];

        if (!firstMarkdownUrl) {
          setToast("Markdown is not available yet");
          return;
        }

        await downloadFile(firstMarkdownUrl, `${outputName}.md`);
        setToast("Markdown download started");
        return;
      }

      if (label.includes("PDF")) {
        if (!resultUrls.translatedPdf) {
          setToast("Translated PDF export is not available yet");
          return;
        }

        await downloadFile(resultUrls.translatedPdf, `${outputName}.pdf`);
        setToast("PDF download started");
        return;
      }

      setToast(`${label} is not available yet`);
    } catch (error) {
      console.error("Download failed:", error);
      setToast(error?.message || "Could not download file");
    }
  };

  const isComplete = status === "complete";
  const isProcessing = status === "processing";
  const isParsing = pipelineStage === "parsing";
  const isTranslating = pipelineStage === "translating";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">
          Translate document
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Upload an English scientific PDF and configure how it should be
          translated into Vietnamese.
        </p>
      </div>

      <UploadSection
        file={file}
        onFileSelect={handleFileSelect}
        onClear={handleClearFile}
      />

      <ConfigurationPanel config={config} setConfig={setConfig} />

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={startTranslation}
          disabled={!file || status === "processing"}
          className={`w-full rounded-xl py-3.5 text-sm font-semibold transition-colors ${
            !file || status === "processing"
              ? "cursor-not-allowed bg-slate-100 text-slate-400"
              : "bg-blue-600 text-white hover:bg-blue-700"
          }`}
        >
          {pipelineStage === "parsing" && "Parsing PDF..."}

          {pipelineStage === "waiting_for_translator" &&
            "Waiting for TranslateGemma..."}

          {pipelineStage === "translating" &&
            "Translating document..."}

          {![
            "parsing",
            "waiting_for_translator",
            "translating",
          ].includes(pipelineStage) && "Start Translation"}
        </button>
      </div>
      
      {pipelineStage === "waiting_for_translator" && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          OCR completed. Stop PaddleOCR-VL and start TranslateGemma.
          Translation will continue automatically.
        </div>
      )}

      {pipelineStage === "parsed" && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          <p className="font-semibold">OCR and layout parsing completed.</p>
          <p className="mt-1">
            Stop PaddleOCR-VL, start TranslateGemma on port 8001, then click
            Continue Translation.
          </p>
        </div>
      )}

      {pipelineStage === "failed" && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          The current pipeline stage failed. Check the backend and model-server
          terminals, then try the stage again.
        </div>
      )}

      {(showResults || isComplete) && file && (
        <ResultArea
          fileName={file.name}
          totalElapsed={totalElapsed}
          exportFormat={config.exportFormat}
          onDownload={handleDownload}
          resultUrls={resultUrls}
        />
      )}

      {(isProcessing || (isComplete && !showResults)) && (
        <ProgressModal
          steps={PROGRESS_STEPS}
          currentStepIndex={currentStepIndex}
          progressValues={progressValues}
          totalElapsed={totalElapsed}
          isComplete={isComplete}
          onViewResults={() => setShowResults(true)}
        />
      )}

      {toast && <Toast message={toast} onClose={() => setToast(null)} />}
    </div>
  );
  }

/* -------------------------------------------------------------------------- */
/* History page                                                                */
/* -------------------------------------------------------------------------- */

function HistoryPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">History</h1>
        <p className="text-sm text-slate-500 mt-1">
          Previously translated documents and their export status.
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/60">
              <th className="text-left font-medium text-slate-500 px-5 py-3">
                File name
              </th>
              <th className="text-left font-medium text-slate-500 px-5 py-3">
                Date
              </th>
              <th className="text-left font-medium text-slate-500 px-5 py-3">
                Model
              </th>
              <th className="text-left font-medium text-slate-500 px-5 py-3">
                Status
              </th>
              <th className="text-left font-medium text-slate-500 px-5 py-3">
                Output
              </th>
            </tr>
          </thead>
          <tbody>
            {MOCK_HISTORY.map((row, idx) => (
              <tr
                key={idx}
                className="border-b border-slate-100 last:border-b-0 hover:bg-slate-50/50"
              >
                <td className="px-5 py-3 text-slate-700 font-medium">
                  {row.fileName}
                </td>
                <td className="px-5 py-3 text-slate-500">{row.date}</td>
                <td className="px-5 py-3 text-slate-500">{row.model}</td>
                <td className="px-5 py-3">
                  <span
                    className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      row.status === "Completed"
                        ? "bg-emerald-50 text-emerald-600"
                        : "bg-red-50 text-red-500"
                    }`}
                  >
                    {row.status}
                  </span>
                </td>
                <td className="px-5 py-3 text-slate-500">{row.output}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Settings page                                                               */
/* -------------------------------------------------------------------------- */

function SettingsPage() {
  const [theme, setTheme] = useState("light");
  const [language, setLanguage] = useState("english");
  const [defaultModel, setDefaultModel] =
    useState("translategemma");
  const [defaultExport, setDefaultExport] =
    useState("html");

  const {
    status: modelStatus,
    loading: modelLoading,
    error: modelManagerError,
    refreshStatus,
    startModel,
    stopModel,
  } = useModelManager();

  const [modelActionError, setModelActionError] =
    useState(null);

  const fieldClass =
    "w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-200 focus:border-blue-400";

  const handleModelAction = async (
    modelName,
    action,
  ) => {
    setModelActionError(null);

    try {
      if (action === "start") {
        await startModel(modelName);
      } else {
        await stopModel(modelName);
      }
    } catch (error) {
      setModelActionError(
        error?.message || "Model action failed",
      );
    }
  };

  const displayedError =
    modelActionError || modelManagerError;

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">
          Settings
        </h1>

        <p className="mt-1 text-sm text-slate-500">
          Configure application preferences and local AI
          model services.
        </p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-800">
          Application preferences
        </h2>

        <div className="space-y-4">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Theme
            </label>

            <select
              value={theme}
              onChange={(event) =>
                setTheme(event.target.value)
              }
              className={fieldClass}
            >
              <option value="light">Light</option>
              <option value="dark">Dark</option>
              <option value="system">System</option>
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Interface language
            </label>

            <select
              value={language}
              onChange={(event) =>
                setLanguage(event.target.value)
              }
              className={fieldClass}
            >
              <option value="english">English</option>
              <option value="vietnamese">
                Vietnamese
              </option>
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Default translation model
            </label>

            <select
              value={defaultModel}
              onChange={(event) =>
                setDefaultModel(event.target.value)
              }
              className={fieldClass}
            >
              {TRANSLATION_MODELS.map((model) => (
                <option
                  key={model.id}
                  value={model.id}
                >
                  {model.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              Default export format
            </label>

            <select
              value={defaultExport}
              onChange={(event) =>
                setDefaultExport(event.target.value)
              }
              className={fieldClass}
            >
              {EXPORT_FORMATS.map((format) => (
                <option
                  key={format.id}
                  value={format.id}
                >
                  {format.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">
              Model management
            </h2>

            <p className="mt-1 text-xs text-slate-500">
              Start and stop local OCR and translation
              services.
            </p>
          </div>

          <button
            type="button"
            onClick={refreshStatus}
            className="inline-flex items-center gap-2 self-start rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition-colors hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh status
          </button>
        </div>

        {displayedError && (
          <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
            <span>{displayedError}</span>
          </div>
        )}

        <ModelControlCard
          title="PaddleOCR-VL"
          description="Detects document layout and extracts text, tables, figures, formulas, and other visual elements."
          model={modelStatus.ocr}
          loading={modelLoading.ocr}
          onStart={() =>
            handleModelAction("ocr", "start")
          }
          onStop={() =>
            handleModelAction("ocr", "stop")
          }
        />

        <ModelControlCard
          title="TranslateGemma 4B"
          description="Translates extracted scientific document content from English into Vietnamese."
          model={modelStatus.translator}
          loading={modelLoading.translator}
          onStart={() =>
            handleModelAction(
              "translator",
              "start",
            )
          }
          onStop={() =>
            handleModelAction(
              "translator",
              "stop",
            )
          }
        />

        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-relaxed text-amber-800">
          On GPUs with limited VRAM, run only one model at a
          time. Stop PaddleOCR-VL before starting
          TranslateGemma.
        </div>
      </div>
    </div>
  );
}
/* -------------------------------------------------------------------------- */
/* About page                                                                  */
/* -------------------------------------------------------------------------- */

function AboutPage() {
  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">About</h1>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-6">
        <div>
          <h2 className="text-sm font-semibold text-slate-800 mb-2">
            Project title
          </h2>
          <p className="text-sm text-slate-600 leading-relaxed">
            Applying multimodal LLMs for English–Vietnamese scientific document
            translation with layout preservation on local infrastructure
          </p>
        </div>

        <div>
          <h2 className="text-sm font-semibold text-slate-800 mb-2">
            Project description
          </h2>
          <p className="text-sm text-slate-600 leading-relaxed">
            PaperTranslate Local is a research prototype for translating
            English scientific PDF documents into Vietnamese while preserving
            the original layout, figures, tables, and mathematical formulas.
            The system runs entirely on local infrastructure using multimodal
            large language models, making it suitable for academic
            institutions handling sensitive or large-scale document
            collections.
          </p>
        </div>

        <div>
          <h2 className="text-sm font-semibold text-slate-800 mb-2">
            Team members
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {["Team member 1", "Team member 2", "Team member 3", "Team member 4"].map(
              (name, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-3 p-3 rounded-lg bg-slate-50"
                >
                  <div className="w-9 h-9 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 text-xs font-semibold">
                    {idx + 1}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">{name}</p>
                    <p className="text-xs text-slate-400">Role placeholder</p>
                  </div>
                </div>
              )
            )}
          </div>
        </div>

        <div>
          <h2 className="text-sm font-semibold text-slate-800 mb-2">
            Technology stack
          </h2>
          <div className="flex flex-wrap gap-2">
            {[
              "React",
              "TypeScript",
              "Vite",
              "TailwindCSS",
              "shadcn/ui",
              "Lucide Icons",
              "KaTeX",
            ].map((tech) => (
              <span
                key={tech}
                className="px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-medium"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Sidebar                                                                     */
/* -------------------------------------------------------------------------- */

function Sidebar({ activePage, setActivePage }) {
  return (
    <aside className="w-[280px] bg-white border-r border-slate-200 flex flex-col flex-shrink-0 h-screen sticky top-0">
      <div className="px-6 py-6 border-b border-slate-100">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center flex-shrink-0">
            <Languages className="w-4.5 h-4.5 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800 leading-tight">
              PaperTranslate Local
            </p>
            <p className="text-xs text-slate-400 leading-tight">
              Scientific PDF translation
            </p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-4 py-4 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActivePage(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? "bg-blue-50 text-blue-700"
                  : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </button>
          );
        })}
      </nav>

      <div className="px-6 py-4 border-t border-slate-100">
        <p className="text-xs text-slate-400">Local-only prototype</p>
        <p className="text-xs text-slate-400">No data leaves your device</p>
      </div>
    </aside>
  );
}

/* -------------------------------------------------------------------------- */
/* Placeholder for unimplemented "main" pages (none currently used)            */
/* -------------------------------------------------------------------------- */

/* -------------------------------------------------------------------------- */
/* Root app                                                                    */
/* -------------------------------------------------------------------------- */

export default function PaperTranslateApp() {
  const [activePage, setActivePage] = useState("translate");

  useEffect(() => {
    if (window.katex) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href =
      "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css";
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.src =
      "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js";
    document.head.appendChild(script);
  }, []);

  return (
    <div className="flex min-h-screen bg-slate-50 font-sans">
      <Sidebar activePage={activePage} setActivePage={setActivePage} />
      <main className="flex-1 px-8 py-8 max-w-6xl">
        {activePage === "translate" && <TranslatePage />}
        {activePage === "history" && <HistoryPage />}
        {activePage === "settings" && <SettingsPage />}
        {activePage === "about" && <AboutPage />}
      </main>
    </div>
  );
}
