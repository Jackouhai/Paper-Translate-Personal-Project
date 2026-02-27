# PP-DocLayout Demo - Model Switching

## 🚀 Cách chạy Demo (Model Switching)

Do GPU 16GB VRAM, chỉ chạy 1 model tại 1 thời điểm.

### 1. Cách dùng Server Manager CLI

```bash
# Start PaddleOCR-VL
python server_manager.py start-paddle

# Start Gemma
python server_manager.py start-gemma

# Switch servers (tự động stop/start)
python server_manager.py switch paddle    # Switch to PaddleOCR-VL
python server_manager.py switch gemma      # Switch to Gemma

# Xem status
python server_manager.py status

# Stop tất cả
python server_manager.py stop-all
```

### 2. Chạy Demo Streamlit

```bash
./start_demo.sh
# Hoặc
uv run streamlit run demo_app.py
```

Demo sẽ mở tại: **http://localhost:8501**

---

## 📖 Workflow Demo

### Bước 1: Start Server

Chọn server cần start:

| Lệnh | Mô tả |
|-------|---------|
| `python server_manager.py start-paddle` | Start PaddleOCR-VL để parse |
| `python server_manager.py start-gemma` | Start Gemma để translate |

### Bước 2: Chạy Demo

```bash
uv run streamlit run demo_app.py
```

### Bước 3: Parse PDF

1. Mở http://localhost:8501
2. Upload file PDF
3. Click **"🚀 Parse PDF"**
4. Chờ parse hoàn tất (sẽ thấy progress bar)

### Bước 4: Switch Server

Vì parse xong rồi, cần switch sang Gemma:

**Cách 1: Sử dụng sidebar**
- Click **"🔄 Switch to Gemma"** ở sidebar
- App sẽ auto rerun và hiển thị server status mới

**Cách 2: Dùng CLI**
```bash
python server_manager.py switch gemma
```

### Bước 5: Translate

1. Xem server status hiển thị **🟢 GEMMA RUNNING**
2. Click **"🔤 Translate"**
3. Chờ translate hoàn tất

### Bước 6: Download

- Click **"📥 Tải HTML"** để tải kết quả
- Hoặc xem **Preview** trực tiếp trong app

---

## 🎨 UI Demo

```
┌─────────────────────────────────────────────────────────────────┐
│  📄 PP-DocLayout Demo                                    │
│  Pipeline dịch thuật tài liệu học thuật sang tiếng Việt      │
│  *Model Switching - Chỉ chạy 1 model tại 1 thời điểm* │
└─────────────────────────────────────────────────────────────────┘

┌─────────────┐  ┌────────────────────────────────────────────────┐
│ 🎛️ Controls│  │  📊 Server Status                       │
│             │  │                                         │
│ Manual Switch│  │  PaddleOCR-VL    │  Gemma           │
│             │  │  🟢 RUNNING (PID: 12345) 🟢 RUNNING (PID: 67890) │
│ [Switch to  │  │                                         │
│  PaddleOCR-VL]│  └────────────────────────────────────────────────┘
│ [Switch to  │
│  Gemma]     │  ┌────────────────────────────────────────────────┐
│             │  │  📤 Upload PDF                           │
│ Stop All    │  │  ┌──────────────────────────────────────┐   │
│ [Stop All]  │  │  │  [Choose PDF file...]          │   │
│             │  │  └──────────────────────────────────────┘   │
│             │  │  ✅ File: paper.pdf                     │
│ ⚙️ Config  │  │  📊 Size: 2.5 MB                        │
│             │  └────────────────────────────────────────────────┘
│ [Output     │
│  suffix]    │
└─────────────┘
```

---

## 🐛 Xử lý lỗi

### Lỗi: "Server chưa chạy"
- Kiểm tra server status:
  ```bash
  python server_manager.py status
  ```
- Start server tương ứng:
  ```bash
  python server_manager.py switch paddle  # hoặc switch gemma
  ```

### Lỗi: "Port vẫn in use" khi switch
- Nếu port vẫn busy sau 30s, thủ công kill:
  ```bash
  pkill -f "vllm serve"
  rm -f .server_pids.txt
  ```
- Chạy lại switch command

### Lỗi: "Connection error" khi translate
- Đảm bảo Gemma server đang chạy
- Chạy demo app lại để cập nhật status

### Lỗi: GPU OOM
- Tự động stop server khi switch rồi
- Nếu vẫn OOM, giảm `gpu_memory_utilization` trong `server_manager.py`

### Lỗi: Switch bị stuck/timout
- Process có thể bị lock, thủ công cleanup:
  ```bash
  # Kill vllm processes
  pkill -f "vllm serve"

  # Clean PID file
  rm -f .server_pids.txt
  ```

---

## 📝 Notes

- **PID file**: `.server_pids.txt` lưu process IDs để track running servers
- **Auto-switch**: Demo app có buttons ở sidebar để switch servers
- **Status check**: Luôn kiểm tra server status trước khi chạy operation
- **Auto-cleanup**: `stop-all` sẽ stop cả 2 servers và cleanup PID file

---

## 🔄 Server Manager Commands

| Command | Mô tả |
|---------|---------|
| `start-paddle` | Start PaddleOCR-VL server |
| `start-gemma` | Start Gemma server |
| `stop-paddle` | Stop PaddleOCR-VL server |
| `stop-gemma` | Stop Gemma server |
| `stop-all` | Stop cả 2 servers |
| `switch paddle` | Stop Gemma → Start PaddleOCR-VL |
| `switch gemma` | Stop PaddleOCR-VL → Start Gemma |
| `status` | Hiển thị status cả 2 servers |
