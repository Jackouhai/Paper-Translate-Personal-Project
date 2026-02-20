# PP-DocLayout: Phân tích & Dịch thuật Tài liệu Khoa học

Dự án này cung cấp một quy trình khép kín để xử lý các tệp PDF học thuật, bao gồm: phân tích bố cục (Layout Analysis), nhận dạng ký tự (OCR), dịch thuật nội dung bằng LLM (Tencent HY-MT hoặc Google TranslateGemma), và tái cấu trúc thành file HTML chuyên nghiệp giữ nguyên định dạng gốc.

## 🚀 Tính năng chính
- **Layout Analysis**: Nhận diện chính xác Tiêu đề, Abstract, Văn bản, Bảng biểu, Hình ảnh, Công thức.
- **OCR chuyên sâu**: Trích xuất nội dung bảng dưới dạng HTML và công thức dưới dạng LaTeX.
- **Dịch thuật thông minh**: Tích hợp các mô hình LLM chuyên dụng dịch thuật (MT) chạy cục bộ trên GPU.
- **Translation Guard**: Logic bảo vệ thông minh - giữ nguyên Tiêu đề gốc, Tài liệu tham khảo, và Tên tác giả để đảm bảo tính chuyên nghiệp.
- **Reconstruction**: Tái tạo tài liệu dưới dạng HTML chuẩn SEO, hỗ trợ render công thức bằng MathJax.

## 🛠 Yêu cầu hệ thống
- **OS**: Linux (Khuyên dùng)
- **GPU**: NVIDIA RTX (Khuyên dùng 8GB VRAM trở lên cho bản Gemma)
- **Môi trường**: Python 3.10+, CUDA 12.8
- **Công cụ quản lý**: `uv` (Khuyên dùng)

## 📦 Cài đặt
Sử dụng `uv` để cài đặt nhanh các thư viện cần thiết:
```bash
uv pip install transformers accelerate bitsandbytes sentencepiece protobuf paddlepaddle-gpu paddleocr paddleocrvl
```

## 📖 Hướng dẫn sử dụng

### Bước 1: Phân tích PDF (Layout & OCR)
Mở file `main.py`, điều chỉnh đường dẫn `pdf_input` trỏ đến file của bạn, sau đó chạy:
```bash
uv run main.py
```
Kết quả sẽ được lưu vào thư mục `output/<tên_file>/` dưới dạng các file JSON (chứa tọa độ và nội dung) và ảnh đã cắt.

### Bước 2: Dịch thuật & Tái cấu trúc (HTML)
Bạn có hai lựa chọn mô hình dịch thuật tùy theo cấu hình GPU:

#### Lựa chọn A: Sử dụng Tencent HY-MT (Nhẹ & Nhanh)
Mô hình `tencent/HY-MT1.5-1.8B` chỉ chiếm khoảng ~3.6GB VRAM, dịch thuật chuyên dụng.
```bash
uv run reconstruct_multi.py <tên_thư_mục_output>
# Ví dụ: uv run reconstruct_multi.py HY-MT
```

#### Lựa chọn B: Sử dụng Google TranslateGemma (Chất lượng cao)
Mô hình `google/translategemma-4b-it` chiếm khoảng ~8GB VRAM (chế độ bfloat16), cho chất lượng dịch học thuật rất tốt.
```bash
uv run reconstruct_gemma.py <tên_thư_mục_output>
```

### Bước 3: Xem kết quả
Mở file HTML được tạo ra trong thư mục output (ví dụ: `translated_HY-MT_gemma.html`) bằng trình duyệt:
```bash
xdg-open output/HY-MT/translated_HY-MT_gemma.html
```

## 🧠 Logic Dịch thuật (Translation Policy)
Để giữ tính học thuật, hệ thống được cấu hình:
- **Dịch**: Nội dung văn bản (`text`), nội dung tóm tắt (`abstract`), chú thích ảnh/bảng (`figure_title`).
- **Giữ nguyên**: Tiêu đề chính (`doc_title`), tiêu đề mục (`paragraph_title`), tài liệu tham khảo (`reference_content`), công thức toán học, tên tác giả và email.
- **Loại bỏ**: Các thông tin nhiễu như số trang, đầu trang (`header/footer`), và văn bản lề (`aside_text`).

## 📁 Cấu trúc Project
- `main.py`: Script khởi đầu xử lý PDF.
- `reconstruct_multi.py`: Script dịch & dựng HTML (Model Tencent).
- `reconstruct_gemma.py`: Script dịch & dựng HTML (Model Gemma).
- `translator_engine.py`: Module quản lý mô hình Tencent.
- `translator_engine_gemma.py`: Module quản lý mô hình Gemma.
- `output/`: Nơi lưu trữ toàn bộ dữ liệu trung gian và kết quả cuối cùng.
