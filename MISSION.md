# Mission: Tối ưu Docker demo PP-DocLayout trên VPS/public host

## Why

Hiểu và tự tối ưu Docker để có thể chạy demo dịch PDF trên một VPS NVIDIA hoặc public host một cách an toàn, ổn định và tiết kiệm tài nguyên — không chỉ copy lệnh mà không biết chúng làm gì.

## Success looks like

- Giải thích được vai trò của từng service, image, volume, network và port trong `compose.yaml`.
- Tự kiểm tra được GPU pass-through, healthcheck, port public và kết nối nội bộ.
- Biết thay đổi cấu hình VRAM, build cache và image layout có lý do, rồi đo lại kết quả.
- Chạy demo trên VPS với chỉ frontend/tunnel public, model API được giữ trong mạng nội bộ.
- Biết xem log, chẩn đoán lỗi khởi động và rollback cấu hình an toàn.

## Constraints

- Repo dùng GPU NVIDIA/CUDA; TranslateGemma và PaddleOCR-VL là các service nặng.
- Mục tiêu trước mắt là demo học tập trên VPS/public host, không phải nền tảng multi-tenant production.
- Cần hướng dẫn từng bước, giải thích thuật ngữ trước khi yêu cầu thay đổi file.

## Out of scope

- Kubernetes, orchestration nhiều node và autoscaling.
- Train/fine-tune model hoặc tự xây OCR/layout detector.
- Thiết kế hệ thống production multi-tenant hoàn chỉnh.
