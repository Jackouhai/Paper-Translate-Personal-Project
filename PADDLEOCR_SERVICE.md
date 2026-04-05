# PaddleOCR-VL Service - Keep Models in Memory

Service này giữ PaddleOCRVL (bao gồm PP-DocLayoutV3) trong memory để tránh load mỗi lần chạy.

## 🚀 Cách sử dụng

### 1. Cài đặt dependencies

```bash
uv pip install fastapi uvicorn python-multipart
```

### 2. Khởi động PaddleOCR-VL Service

Mở terminal mới và chạy:

```bash
# Mặc định port 8002
python pp_doclayout_service.py

# Hoặc custom port
python pp_doclayout_service.py --port 8003 --host 127.0.0.1
```

**Thời gian khởi động:** Khoảng 5-10s để load PP-DocLayoutV3.

### 3. Cập nhật CLI để sử dụng service

Thêm vào `.env` file:

```bash
# PaddleOCR-VL Service URL
PPDOCLAYOUT_PADDLE_OCR_SERVICE_URL=http://127.0.0.1:8002
```

### 4. Chạy CLI như bình thường

```bash
# Model đã có trong memory, không load lại!
uv run -m pp_doclayout.cli run pdf/my_paper.pdf

# Từng bước
uv run -m pp_doclayout.cli parse pdf/my_paper.pdf
```

## 📊 Lợi ích

| Trước | Sau |
|--------|------|
| Mỗi lần run: load PP-DocLayoutV3 (~2-3s) | Model đã có trong memory (0s) |
| Tổng thời gian: 10s + 2s = **12s** | Tổng thời gian: **10s** |
| Memory usage: Spike mỗi lần khởi tạo | Memory: Stable (service giữ memory) |

## 🔄 Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│         PaddleOCR-VL Service (Background)                │
├─────────────────────────────────────────────────────────────────┤
│  Startup: Load PP-DocLayoutV3 (5-10s)              │
│  Runtime: Model giữ trong memory                           │
│                                                         │
│  ┌─────────────────────┐                               │
│  │ PP-DocLayoutV3    │ ← Giữ trong GPU memory      │
│  └─────────────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
                      ↑
                      │ HTTP Request (POST /parse)
                      │
┌─────────────────────────────────────────────────────────────────┐
│              CLI (Foreground)                              │
├─────────────────────────────────────────────────────────────────┤
│  - Upload PDF via HTTP                                   │
│  - Nhận kết quả parsing (JSON, markdown)                │
│  - Không cần load model                                   │
└─────────────────────────────────────────────────────────────────┘
```

## 🔧 API Endpoints

### POST /parse
Parse PDF file.

**Request:**
```bash
curl -X POST http://127.0.0.1:8002/parse \
  -F "pdf=@my_paper.pdf" \
  -F "output_dir=output"
```

**Response:**
```json
{
  "success": true,
  "project_dir": "output/my_paper",
  "num_pages": 15,
  "message": "Parsed 15 pages successfully"
}
```

### GET /health
Check service status.

**Response:**
```json
{
  "status": "ready",
  "backend": "vllm-server",
  "layout_model": "PP-DocLayoutV3"
}
```

## 📝 Notes

- Service cần chạy **liên tục** (đóng terminal sẽ dừng service)
- Model chỉ load 1 lần khi service start
- Multiple CLI calls có thể chạy song song trên cùng service
- Nếu restart service, model sẽ load lại (5-10s)

## 🔍 Troubleshooting

### Port đã được dùng
```bash
# Tìm process đang dùng port 8002
lsof -i :8002

# Hoặc dùng port khác
python pp_doclayout_service.py --port 8003
```

### Service không start
```bash
# Check logs
python pp_doclayout_service.py --log-level debug

# Kiểm tra vLLM PaddleOCR-VL server đang chạy
curl http://127.0.0.1:8000/v1/models
```
