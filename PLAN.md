# Kế hoạch: Tích hợp Frontend với Backend

## Context

Project dịch thuật PDF hiện chỉ hoạt động qua CLI. User muốn thêm web UI để:
- Upload PDF qua browser
- Theo dõi tiến trình dịch thuật
- Xem kết quả HTML dịch thuật

Frontend React đã có sẵn (từ AI Studio) nhưng chỉ dùng mock data. Cần tạo API layer (FastAPI) để kết nối.

---

## Architecture

```
Browser (React:3000) ──proxy──> FastAPI (:5000) ──> PaddleOCR-VL (:8000)
                                        │                + Gemma vLLM (:8001)
                                        │
                                   background task
                                   (parse + translate)
```

**Production:** FastAPI serve cả frontend static files → chỉ cần 1 server (:5000)

---

## Step 1: Tạo API skeleton (`src/pp_doclayout/api.py`)

File mới `src/pp_doclayout/api.py` với:
- FastAPI app + CORS middleware
- `GET /api/health` → `{"status": "ok"}`

**Cài thêm:** `fastapi`, `uvicorn[standard]`, `python-multipart`

**Test:** `uvicorn src.pp_doclayout.api:app --reload --port 5000` → mở `http://localhost:5000/api/health`

---

## Step 2: Upload endpoint

`POST /api/documents/upload`
- Nhận multipart file (PDF)
- Lưu vào `output/uploads/{uuid}.pdf`
- Tạo job record (in-memory dict)
- Return `{"document_id": "uuid", "status": "processing"}`

---

## Step 3: Background processing + Status endpoint

**process_document()** - chạy parse + translate (giống CLI `run` command):
1. Status → "parsing": gọi PaddleOCR-VL predict
2. Status → "translating": gọi `build_project_data()` → `translate_page_data()` → `render_page_blocks()`
3. Status → "done": export HTML

`GET /api/documents/{document_id}/status`
- Return `{"status": "...", "progress": {"current_page": N, "total_pages": M}}`

---

## Step 4: Result + file serving

- `GET /api/documents/{document_id}/result` → trả file HTML
- `GET /api/documents/{document_id}/files/{path}` → serve images

---

## Step 5: Kết nối Frontend - API client

Tạo `frontend_project/src/api.ts`:
```typescript
const API_URL = '';  // Vite proxy handle

export function uploadPdf(file: File) { ... }
export function getDocumentStatus(id: string) { ... }
export function getResultUrl(id: string) { ... }
```

**Thay đổi:**
- `vite.config.ts`: thêm proxy `/api` → `localhost:5000`, xóa Gemini config
- `package.json`: xóa `@google/genai`
- `.env.example`: `VITE_API_URL=http://localhost:5000`

---

## Step 6: Frontend - Upload flow

Sửa `App.tsx`:
- Thêm hidden `<input type="file" accept=".pdf">`
- Drag & drop handler gọi `uploadPdf(file)`
- Lưu `document_id` vào state
- Bắt đầu polling status mỗi 2 giây

---

## Step 7: Frontend - Progress + Result

- Upload spinner → hiển thị phase ("Parsing PDF..." / "Translating...") + page progress
- Khi `status === 'done'` → chuyển sang Workspace
- Workspace: thay `TranslatedContent` mock bằng `<iframe src={resultUrl}>`

---

## Step 8: Production build

- `npm run build` → `frontend_project/dist/`
- `api.py` thêm `StaticFiles` mount serve `dist/`
- Chỉ cần chạy 1 server: `uvicorn src.pp_doclayout.api:app --port 5000`

---

## Key decisions

| Quyết định | Lý do |
|-----------|-------|
| Polling (không WebSocket) | Đơn giản, 1 user local, job chạy phút |
| In-memory jobs dict | MVP, không cần DB |
| BackgroundTasks (không Celery) | Cùng process, truy cập GPU translator |
| iframe hiển thị HTML | Isolate CSS (Tailwind vs translation styles) |
| Single api.py | 5 endpoints, không cần sub-package |

## Files cần tạo/sửa

| File | Action | Mô tả |
|------|--------|-------|
| `src/pp_doclayout/api.py` | **NEW** | FastAPI API layer (~150-200 dòng) |
| `frontend_project/src/api.ts` | **NEW** | API client (fetch) |
| `frontend_project/src/App.tsx` | **EDIT** | Real upload + polling + iframe |
| `frontend_project/vite.config.ts` | **EDIT** | Proxy + cleanup |
| `frontend_project/package.json` | **EDIT** | Xóa @google/genai |
| `frontend_project/.env.example` | **EDIT** | VITE_API_URL |

## Verify

```bash
# 1. API health check
curl http://localhost:5000/api/health

# 2. Upload test
curl -X POST -F "file=@test.pdf" http://localhost:5000/api/documents/upload

# 3. Full flow qua browser
# Mở http://localhost:3000 → upload PDF → xem progress → xem result
```
