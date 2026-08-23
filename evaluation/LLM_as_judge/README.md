# LLM-as-a-Judge cho bản dịch Anh–Việt

Thư mục này dùng Gemini làm giám khảo reference-free theo rubric MQM ở mức segment. Model so sánh trực tiếp nguồn tiếng Anh với bản dịch tiếng Việt, gắn lỗi theo span, loại lỗi và mức độ nghiêm trọng.

## Thành phần

```text
LLM_as_judge/
├── gemini_mqm_judge.py    # pipeline chính
├── test.en                # nguồn mẫu, một segment mỗi dòng
├── gemma_promt.vi         # candidate mẫu
├── mqm_results/           # output mặc định
├── Root_Split/            # dữ liệu/kết quả thí nghiệm cũ
└── test.py                # tiện ích thử liệt kê model Gemini
```

Các thư mục `gemini_batch_evaluation`, `gemini_comparison`, `gemini_evaluation` và một số thư mục trong `Root_Split` hiện là nơi lưu thí nghiệm, không được pipeline chính đọc tự động.

## Rubric và điểm

Nhóm lỗi gồm mistranslation, omission, addition, untranslated, grammar, punctuation, word order, inconsistency, terminology, source issue, scientific notation, citation/reference và academic style.

- `MINOR`: phạt 1
- `MAJOR`: phạt 5
- `CRITICAL`: phạt 10

Điểm segment là `max(0, 100 - tổng điểm phạt)`. Đây là điểm riêng của pipeline, không phải MQM chuẩn hóa theo số từ. Tổng hợp còn báo lỗi trên 1.000 từ candidate, tỷ lệ segment không lỗi và phân bố lỗi.

## Cài đặt và API key

```bash
pip install -U google-genai pydantic
```

Không ghi key trực tiếp vào mã nguồn. Thiết lập biến môi trường:

```powershell
# PowerShell
$env:GEMINI_API_KEY = "YOUR_API_KEY"
```

```bash
# Bash
export GEMINI_API_KEY="YOUR_API_KEY"
```

## Dữ liệu đầu vào

Hai file UTF-8 phải có cùng số dòng và không có segment rỗng:

```text
test.en dòng 1  <->  gemma_promt.vi dòng 1
test.en dòng 2  <->  gemma_promt.vi dòng 2
```

Có thể đổi tên bằng `--source` và `--candidate`.

## Chạy

Từ `Evaluation/LLM_as_judge`:

```bash
# Pilot 5 segment
python gemini_mqm_judge.py --input-dir . --limit 5

# Toàn bộ
python gemini_mqm_judge.py --input-dir .

# Model và output tùy chỉnh
python gemini_mqm_judge.py --input-dir . --model gemini-3.5-flash --output-dir results/run_01
```

| Tùy chọn | Mặc định | Ý nghĩa |
| --- | --- | --- |
| `--source` | `test.en` | File nguồn trong `input-dir`. |
| `--candidate` | `gemma_promt.vi` | File bản dịch. |
| `--output-dir` | `<input-dir>/mqm_results` | Nơi ghi kết quả. |
| `--limit N` | toàn bộ | Chỉ chấm N segment đầu. |
| `--max-retries` | `5` | Số lần thử lại lỗi API/schema. |
| `--request-delay` | `1.0` | Nghỉ sau request thành công. |
| `--overwrite` | tắt | Xóa output cũ và chấm lại. |

Không dùng `--overwrite`, chương trình resume từ `mqm_details.jsonl`. Hash source/candidate và model được kiểm tra để tránh nối nhầm kết quả.

## Đầu ra

Trong `mqm_results/`:

- `mqm_details.jsonl`: judgment đầy đủ theo segment.
- `mqm_segments.csv`: bảng phẳng để phân tích.
- `mqm_summary.json`: thống kê toàn tập.
- `mqm_failed.jsonl`: request thất bại.

Chi phí và thời gian tăng theo số segment; nên chạy `--limit` trước để kiểm tra model, quota, schema và rubric.

## Bảo mật

`test.py` chỉ là script thử nghiệm và hiện chứa API key trực tiếp. Hãy thu hồi key đã lộ, xóa key khỏi file, và dùng `GEMINI_API_KEY` như pipeline chính trước khi chia sẻ repository.
