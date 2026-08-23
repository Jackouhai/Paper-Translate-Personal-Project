# Đánh giá OCR tài liệu

Thư mục này chuẩn hóa ground truth và kết quả OCR về cùng một schema, ghép block theo vị trí, rồi đánh giá riêng văn bản, công thức và bảng.

## Metric

- **Phát hiện block:** Precision, Recall, F1 và IoU. Block được ghép tham lam theo IoU với ngưỡng mặc định `0.5`.
- **Text:** normalized Levenshtein similarity trong `[0, 1]` (càng cao càng tốt).
- **Formula:** normalized Levenshtein similarity và CDM (Character Detection Matching).
- **Table:** normalized Levenshtein similarity và TEDS trên HTML bảng đã chuẩn hóa.
- **Overall:** trung bình của Text similarity, Formula CDM và Table TEDS nếu các thành phần tồn tại.

Nhãn `paragraph`, `title`, `caption` được quy về `Text`; `equation`, `math`, `latex` về `Formula`; `tab` về `Table`. Nội dung chỉ được chấm khi block ghép được theo IoU và có cùng nhãn.

## Cấu trúc

```text
Ben_ocr/
├── parser/
│   ├── gt.py              # Label Studio JSON -> schema đánh giá
│   └── pred.py            # JSON OCR từng trang -> schema đánh giá
├── metric/                # Levenshtein, TEDS và CDM
├── main.py                # đánh giá toàn tập
├── run_metric.py          # demo FormulaMetric
├── helper.py              # tách mảng Label Studio thành từng JSON
├── sample.json            # ví dụ schema chuẩn hóa
└── result/                # kết quả và ảnh trung gian CDM
```

## Cài đặt

Chạy từ `Evaluation/Ben_ocr`:

```bash
pip install numpy rapidfuzz python-Levenshtein apted lxml tqdm pillow scipy pylatexenc
```

CDM render LaTeX thành ảnh nên cần thêm một bản phân phối TeX có `pdflatex` hoặc `xelatex`, cùng ImageMagick (`magick` trên Windows hoặc `convert` trên Linux) trong `PATH`. `run_metric.py` đang chứa đường dẫn ImageMagick riêng cho máy Windows của tác giả; hãy sửa nếu chạy demo này trên máy khác.

## Chuẩn bị dữ liệu

Pipeline mặc định mong đợi:

```text
data/
├── raw_gt/                # Label Studio: 1.json, 2.json, ...
├── raw_pred/
│   ├── paper_1/           # mỗi JSON là một trang OCR
│   └── paper_2/
├── gt/                    # sinh ra gt_1.json, gt_2.json, ...
└── deepseek/              # pred_1.json, pred_2.json, ... cho main.py
```

Chuyển đổi hai phía:

```bash
python parser/gt.py
python parser/pred.py
```

`parser/pred.py` mặc định ghi vào `data/pred`. Trước khi chấm, đổi `pred_dir` trong `main.py` thành `data/pred`, hoặc chuyển file sang `data/deepseek`. Kích thước trang mặc định để chuẩn hóa bbox là `1224 x 1584`; truyền giá trị khác vào parser nếu cần.

Schema trung gian tối thiểu:

```json
{
  "file_name": "paper_1",
  "pages": [{
    "page_index": 1,
    "blocks": [{
      "id": "0",
      "bounding_box": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.1},
      "content": "Nội dung block",
      "label": "Text"
    }]
  }]
}
```

Ground truth có thể dùng khóa `block_content` thay cho `content`.

## Chạy đánh giá

```bash
python main.py
```

Kết quả nằm tại `result/evaluation/evaluation_results.json`, gồm metric theo paper, theo nhãn và `dataset_summary`. Trung bình nội dung ở mức dataset là micro-average theo số block có điểm. CDM còn tạo bbox và ảnh trực quan trong `result/evaluation/CDM/`.

Demo công thức:

```bash
python run_metric.py
```

## Lưu ý

- Tên file phải khớp: `gt_1.json` đi với `pred_1.json`.
- `page_index` hai phía phải dùng cùng quy ước.
- Bảng nên là HTML `<table>...</table>`; parser chuẩn hóa cấu trúc và hỗ trợ LaTeX `tabular` đơn giản ở ground truth.
- `Image` được parser prediction nhận diện nhưng hiện không có metric nội dung riêng.
