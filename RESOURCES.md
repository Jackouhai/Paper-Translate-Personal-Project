# Docker Demo Resources

## Knowledge

- [Docker: Building best practices](https://docs.docker.com/build/building/best-practices/)
  Nguồn chính cho multi-stage build, `.dockerignore`, image nhỏ, pin base image, cache và chạy non-root. Dùng khi tối ưu Dockerfile và reproducibility.
- [Docker: Networking in Compose](https://docs.docker.com/compose/how-tos/networking/)
  Giải thích default network, service discovery bằng tên service và cách container gọi nhau mà không cần publish port ra host. Dùng khi thiết kế mạng Compose.
- [Docker: Run Compose services with GPU access](https://docs.docker.com/compose/how-tos/gpu-support/)
  Cú pháp GPU reservation trong Compose và ý nghĩa của `count`, `device_ids`, `capabilities`. Dùng khi cấp GPU cho đúng service.
- [Docker: Multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
  Cách tách build environment khỏi runtime image để giảm kích thước và attack surface. Dùng khi tách image web API, frontend và model server.
- [NVIDIA Container Toolkit: Installation Guide](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  Quy trình cấu hình Docker để dùng NVIDIA GPU và lệnh `nvidia-ctk`. Dùng khi chuẩn bị VPS hoặc kiểm tra GPU pass-through.

## Wisdom (Communities)

Chưa thêm community resource. Mission hiện tại ưu tiên tài liệu chính thức và thực hành trực tiếp trên VPS.

## Gaps

- Cần một bài thực hành đo VRAM/throughput cụ thể cho GPU của VPS sau khi xác định phần cứng.
