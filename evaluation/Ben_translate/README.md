# Đánh giá chất lượng bản dịch

Notebook `ben_translate (1).ipynb` đánh giá bản dịch Anh–Việt trên Google Colab bằng COMET, BLEU/chrF++, BLEURT và MetricX.

## Dữ liệu

Notebook giả định:

```text
/content/drive/MyDrive/Ours_data/
├── test.en       # nguồn tiếng Anh
├── test.vi       # tham chiếu tiếng Việt
└── hymt.vi       # bản dịch cần chấm
```

Mỗi dòng là một segment và ba file phải thẳng hàng. Hãy thay `DATA_DIR` và tên file dự đoán trong từng phần nếu dùng dữ liệu khác.

## Metric

| Metric | Đầu vào | Diễn giải |
| --- | --- | --- |
| COMET (`wmt22-comet-da`) | source, candidate, reference | Điểm câu và hệ thống; cao hơn tốt hơn. |
| SacreBLEU | candidate, reference | Độ trùng n-gram; cao hơn tốt hơn; tokenizer `13a`. |
| chrF++ | candidate, reference | Độ trùng ký tự và word n-gram; cao hơn tốt hơn. |
| BLEURT-20 | candidate, reference | Điểm học máy theo câu; cao hơn tốt hơn. |
| MetricX-24 Hybrid | source, candidate, reference | Điểm lỗi; **thấp hơn tốt hơn**. |

Không so sánh trực tiếp trị số giữa các metric vì thang đo và ý nghĩa khác nhau.

## Cách chạy

1. Mở notebook bằng Google Colab và chọn GPU nếu chạy COMET, BLEURT hoặc MetricX.
2. Chạy riêng từng cụm cell theo tiêu đề metric.
3. Mount Google Drive, sửa `DATA_DIR` và `PRED_FILE`/`HYPOTHESIS_FILE`.
4. Chạy cell kiểm tra dữ liệu trước cell tính điểm.

Các cụm có môi trường phụ thuộc khác nhau; nếu gặp xung đột TensorFlow/PyTorch/NumPy, hãy restart runtime trước khi chuyển metric.

Notebook tự cài:

- COMET: `unbabel-comet==2.2.7`
- BLEU/chrF++: `sacrebleu`
- BLEURT: clone `google-research/bleurt`, tải checkpoint `BLEURT-20`
- MetricX: clone `google-research/metricx`, dùng `google/metricx-24-hybrid-large-v2p6-bfloat16`

## Đầu ra

- COMET: `system_score` và điểm theo câu được in trong notebook.
- BLEU/chrF++: điểm corpus và BLEU signature.
- BLEURT: `bleurt_scores` và trung bình.
- MetricX: JSONL đầu vào/đầu ra trong `Ours_data`, sau đó in mean, median, độ lệch chuẩn và phân vị.

## Lưu ý MetricX

Cell chạy model khai báo `hymt_metricx_output.jsonl`, nhưng cell đọc kết quả phía sau dùng `metricx_output.jsonl`. Hãy sửa hai nơi về cùng tên trước khi chạy. Ngoài ra, không lọc dòng rỗng độc lập ở từng file vì có thể làm lệch source, candidate và reference.

Các cell clone repository hoặc tải checkpoint cần Internet và có thể tốn nhiều dung lượng runtime/Drive.
