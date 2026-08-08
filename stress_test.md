# vLLM Stress Test Report

Ngày tổng hợp: 2026-08-06

## Mục tiêu

Đánh giá throughput, latency và nguy cơ vượt VRAM của TranslateGemma/vLLM với cấu hình serving hiện tại.

Cấu hình server chính:

```text
quantization: fp8
max-model-len: 4096
max-num-seqs: 15 (cấu hình tham chiếu trong script server)
max-num-batched-tokens: 16384
gpu-memory-utilization: 0.8
kv-cache-dtype: fp8
enable-chunked-prefill: enabled
```

GPU báo cáo tổng cộng khoảng `16,311 MiB` VRAM.

> Lưu ý: theo xác nhận sau khi chạy, hai workload có report JSON là
> `256/256, 45 requests` và `1024/512, 20 requests` được chạy với
> `max-num-seqs=24`. JSON report hiện tại chưa ghi lại cờ cấu hình của server,
> nên thông tin này được bổ sung từ terminal/người chạy.

## Kết quả tổng quan

| Workload | max-num-seqs | Số request | Concurrency đã thử | Kết quả | Throughput cao nhất | VRAM peak |
|---|---:|---:|---|---|---:|---:|
| Input 256 / output 256 | 15 | 30 | 1, 2, 4, 8, 12, 15, 16, 20 | Tất cả pass | 568.8 tok/s tại c=15 | 40.3% |
| Input 256 / output 256 | **24** | 45 | 4, 8, 12, 15, 20 | Tất cả pass | 647.8 tok/s tại c=20 | 41.3% |
| Input 1024 / output 512 | **24** | 20 | 4, 8, 12, 15, 20 | Tất cả pass | 154.2 tok/s tại c=15 | 41.3% |
| Input 1024 / output 512 | **24** | 45 | 8, 12, 15, 20, 24 | Tất cả pass | **163.4 tok/s tại c=15** | 41.3% |
| Input 2048 / output 1024 | Chưa xác nhận | 45 | 4, 8, 12, 15, 20 | Chưa hoàn tất | Chưa kết luận | Chưa có report |

Throughput giữa các workload khác nhau không nên so sánh trực tiếp; chỉ nên so sánh các mức concurrency trong cùng một workload.

## Generation throughput theo concurrency

Đơn vị: generated tokens/giây.

| Workload | c=1 | c=2 | c=4 | c=8 | c=12 | c=15 | c=16 | c=20 | c=24 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 256/256, 30 requests | 61.8 | 123.2 | 228.6 | 391.6 | 483.7 | **568.8** | 559.1 | 537.5 | — |
| 256/256, 45 requests, max-seqs=24 | — | — | 228.4 | 427.6 | 525.4 | 572.7 | — | **647.8** | — |
| 1024/512, 20 requests, max-seqs=24 | — | — | 135.7 | 140.5 | 151.4 | **154.2** | — | 148.9 | — |
| 1024/512, 45 requests, max-seqs=24 | — | — | — | 149.7 | 150.6 | **163.4** | — | 154.1 | 157.9 |

## Latency và VRAM

| Workload | Mức tốt nhất | P95 service latency tại mức đó | VRAM baseline | VRAM peak | OOM |
|---|---:|---:|---:|---:|---|
| 256/256, 30 requests | c=15 | 7.14s | 6,575 MiB | 6,579 MiB | Không |
| 256/256, 45 requests, max-seqs=24 | c=20 | 7.96s | 6,735 MiB | 6,735 MiB | Không |
| 1024/512, 20 requests, max-seqs=24 | c=15 | 48.25s | 6,739 MiB | 6,739 MiB | Không |
| 1024/512, 45 requests, max-seqs=24 | c=15 | 48.28s | 6,739 MiB | 6,739 MiB | Không |

GPU utilization trong report `1024/512` thường xuyên đạt khoảng `92–100%`. VRAM không tăng đáng kể vì vLLM đã phân bổ model/cache trước; do đó cần xem cả GPU utilization và request latency, không chỉ nhìn mức VRAM.

## Phân tích

- Với workload ngắn `256/256`, throughput tăng đáng kể khi concurrency tăng. Kết quả tốt nhất quan sát được nằm ở khoảng `15–20`, tùy số request và trạng thái warm-up.
- Với workload dài `1024/512` chạy ở `max-num-seqs=24`, test 45 requests đạt đỉnh `163.4 tok/s` tại `c=15`. Tăng lên `c=20` giảm còn `154.1 tok/s`, còn `c=24` là `157.9 tok/s`; P95 service latency tăng lên `81.07s` tại c=24. Như vậy tăng concurrency đến 24 chưa đem lại lợi ích rõ ràng.
- Với `256/256` chạy ở `max-num-seqs=24`, `c=20` vẫn chưa chạm giới hạn 24. Kết quả này cho thấy throughput cao hơn, nhưng chưa thể quy toàn bộ mức tăng cho `max-num-seqs=24` vì số request và trạng thái warm-up khác test `256/256` trước đó.
- Chưa thể kết luận giá trị tối ưu của `max-num-seqs` chỉ từ các log hiện tại; cần chạy cùng một workload với `max-num-seqs=15` và `24` trong điều kiện tương đương.
- Các test đã hoàn tất không cho thấy nguy cơ vượt VRAM: peak chỉ khoảng `40–41%` tổng VRAM và không có lỗi CUDA OOM.

## Test 2048/1024 chưa hoàn tất

Lần chạy:

```bash
uv run stress_vllm.py \
  --input-tokens 2048 \
  --output-tokens 1024 \
  --num-requests 45 \
  --concurrency-levels 4,8,12,15,20 \
  --timeout 300 \
  --log-file logs/stress_vllm_current.json
```

Chỉ thấy hai request đầu tại concurrency 4 hoàn thành sau khoảng `16.9s/request`. Vì sweep chưa kết thúc nên report JSON của lần chạy này chưa được ghi; sau đó `stress_vllm_current.json` đã bị ghi đè bởi test `1024/512`, 45 requests mới hơn.

Workload này nặng hơn nhiều vì mỗi request có khoảng 2048 input tokens và bị ép sinh đủ 1024 output tokens bởi `ignore_eos=True`. Không nên coi việc terminal im lặng trong vài chục giây là OOM; script chỉ in khi request hoàn thành.

## Kết luận và khuyến nghị

- Cấu hình hiện tại chạy ổn với workload đã hoàn tất, chưa có bằng chứng vượt VRAM.
- `max-num-seqs=24` không gây OOM trong hai workload đã xác nhận, nhưng chưa chứng minh tốt hơn `15` cho workload dài.
- Với pipeline thực tế, nên bắt đầu ở `max_concurrent_requests=12–15`; chỉ tăng thêm nếu benchmark cùng workload cho thấy generation throughput tăng rõ rệt.
- Với workload `1024/512`, mức hiện tại hợp lý nhất là `c=15`: throughput cao nhất và latency thấp hơn đáng kể so với c=20/24.
- Nếu cần kiểm tra context dài, nên chạy ít request hơn, ví dụ `num_requests=15–20`, để tránh mỗi sweep kéo dài quá lâu.
- Khi đánh giá worst-case VRAM, giữ `--ignore-eos`; khi đánh giá latency dịch thực tế, dùng `--no-ignore-eos`.

## Log nguồn

- [stress_vllm_current.json](logs/stress_vllm_current.json): workload mới nhất `1024/512`, 45 requests.
- [stress_vllm_quick.json](logs/stress_vllm_quick.json): workload `1024/512`, 20 requests.
- Test `256/256`, 30 requests: dữ liệu lấy từ terminal, chưa có JSON report.
- Test `256/256`, 45 requests: dữ liệu đã tổng hợp trước đó; JSON report đã bị ghi đè bởi lần test `1024/512` mới nhất.
- Test `2048/1024`, 45 requests: chưa hoàn tất nên chưa có JSON report.
