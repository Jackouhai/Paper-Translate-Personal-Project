# Báo Cáo Benchmark Serving TranslateGemma

**Ngày chạy:** 2026-08-25  
**Mục đích:** Chọn mức song song phù hợp cho TranslateGemma trong pipeline PP-DocLayout.

## 1. Phạm vi đo

Benchmark đánh giá hiệu năng API serving của TranslateGemma: throughput, thời
gian đến token đầu tiên và độ trễ sinh token. Benchmark không đánh giá chất
lượng bản dịch, parse PDF, render HTML hay export PDF.

## 2. Môi trường thí nghiệm

| Thành phần | Cấu hình |
|---|---|
| GPU | NVIDIA GeForce RTX 5060 Ti |
| vLLM | 0.16.0 |
| Mô hình | `Infomaniak-AI/vllm-translategemma-4b-it` |
| Quantization | FP8 |
| `max_model_len` | 4096 |
| `max_num_seqs` | 24 |
| `max_num_batched_tokens` | 16384 |
| `gpu_memory_utilization` | 0.80 |
| KV cache dtype | FP8 |
| Scheduler | Chunked prefill bật |

Server được khởi động bằng
[`scripts/start_translate_gemma.sh`](../scripts/start_translate_gemma.sh).

## 3. Workload thực tế

Dataset được tạo bằng
[`scripts/build_translation_benchmark_dataset.py`](../scripts/build_translation_benchmark_dataset.py)
từ output parse thực tế. Script dùng chung translation policy, cách chuẩn bị
source text, prompt `<<<custom>>>` và giới hạn output của `GemmaTranslator`.

| Thuộc tính dataset | Giá trị |
|---|---:|
| Số request | 100 |
| Tổng input token | 21,014 |
| Input trung bình/request | 210.1 token |
| Tổng output token | 12,541-12,583, tùy lần chạy |
| Output trung bình/request | Khoảng 125.6 token |
| Paper nguồn | `2210.17323v2`: 91 block; `2306.00978v6-e760e338`: 9 block |
| Nhãn block | `text`: 68; `figure_title`: 30; `abstract`: 2 |
| Dịch `paragraph_title` | Tắt |

Nội dung request là các đoạn tiếng Anh học thuật thật. Benchmark dùng
`--dataset-name custom`, không dùng `--skip-chat-template`, do đó vLLM áp dụng
chat template của TranslateGemma cho nội dung user hợp lệ bắt đầu bằng
`<<<custom>>>`. Không dùng `--ignore-eos`, vì model cần tự kết thúc bản dịch
như pipeline thật.

## 4. Quy trình

Mỗi mức concurrency dùng cùng một JSONL 100 record, server đã được nạp sẵn vào
GPU, request rate không giới hạn và `temperature=0`. Mỗi cấu hình được chạy một
lần.

```bash
cd services/llm-server
UV_CACHE_DIR="$PWD/.uv-cache" uv run --no-sync vllm bench serve \
  --backend openai \
  --base-url http://127.0.0.1:8001 \
  --endpoint /v1/completions \
  --model Infomaniak-AI/vllm-translategemma-4b-it \
  --dataset-name custom \
  --dataset-path ../../bench_data/translation_blocks.jsonl \
  --no-oversample \
  --num-prompts 100 \
  --max-concurrency <C> \
  --num-warmups 3 \
  --temperature 0 \
  --save-result --save-detailed \
  --result-dir ../../logs/vllm-bench-real
```

## 5. Kết quả

Cả 100 request đều thành công ở tất cả các mức đã thử.

| Concurrency | Thời gian (s) | Throughput request (req/s) | Throughput output (tok/s) | Mean TTFT (ms) | P99 TTFT (ms) | Mean TPOT (ms) | P99 TPOT (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 226.0 | 0.44 | 55.55 | 189.67 | 3,103.27 | 16.62 | 21.85 |
| 2 | 103.95 | 0.96 | 120.65 | 54.73 | 68.86 | 16.17 | 16.35 |
| 3 | 95.46 | 1.05 | 131.55 | 601.31 | 4,395.75 | 17.93 | 39.25 |
| 4 | 59.74 | 1.67 | **210.11** | 109.29 | **875.70** | 17.54 | 31.42 |
| 6 | 54.29 | 1.84 | 231.77 | 583.56 | 4,003.23 | 22.38 | 75.73 |
| 8 | 54.07 | 1.85 | 232.41 | 1,500.76 | 4,401.87 | 23.55 | 79.66 |

TTFT (Time To First Token) là thời gian từ khi gửi request đến token đầu tiên.
TPOT (Time Per Output Token) là thời gian trung bình cho mỗi token sau token
đầu tiên. TTFT và TPOT thấp hơn là tốt hơn; throughput cao hơn là tốt hơn.

## 6. Phân tích và cấu hình được chọn

Chọn **concurrency = 4** cho server TranslateGemma trên máy thí nghiệm.

- So với concurrency 2, throughput output tăng từ 120.65 lên 210.11 token/s,
  tương đương tăng **74.2%**.
- P99 TTFT ở concurrency 4 vẫn dưới một giây (875.70 ms), phù hợp với demo
  tương tác.
- Tăng từ 4 lên 6 chỉ tăng 10.3% throughput, nhưng P99 TTFT tăng từ 0.88 s lên
  4.00 s và P99 TPOT tăng hơn hai lần.
- Concurrency 8 gần như không tăng throughput so với 6, trong khi độ trễ token
  đầu tiên và token tiếp theo đều cao hơn.

Hai mức c=1 và c=3 có outlier TTFT dài. Các kết quả này vẫn được giữ lại để
minh bạch; quyết định dựa trên cân bằng throughput-độ trễ của toàn bộ sweep,
không dựa trên một median đơn lẻ.

## 7. Cấu hình áp dụng

```env
PPDOCLAYOUT_MAX_CONCURRENT_REQUESTS=4
WEB_DEMO_TRANSLATION_WORKERS=1
WEB_DEMO_MAX_CONCURRENT_REQUESTS=4
```

Với Docker demo mặc định, một job dịch chạy tại một thời điểm và gửi tối đa bốn
request đến TranslateGemma. Nếu thay đổi hai biến `WEB_DEMO_*`, tích của chúng
không nên vượt quá bốn trên một GPU; nếu không, kết quả latency trong báo cáo
này không còn áp dụng.

Profile `.env.24gb` được giữ nguyên `5` worker và `6` request vì profile đó
chưa được benchmark lại với workload này.

## 8. Giới hạn và khả năng tái lập

- Mỗi mức concurrency chỉ chạy một lần. Để đưa vào báo cáo cuối cùng, nên lặp
  lại c=2 và c=4 ít nhất ba lần, sau đó báo cáo trung bình và độ phân tán.
- Dataset gồm 100 block từ hai paper, chưa đại diện cho mọi thể loại paper hay
  context dài nhất model hỗ trợ.
- Model được phép kết thúc tự nhiên (EOS), phản ánh dịch bình thường nhưng
  không phải worst-case decode độ dài cố định.
- Peak VRAM trong lúc benchmark chưa được lấy mẫu, vì vậy báo cáo chỉ kết luận
  về completion, latency và throughput.

Raw result JSON là artifact local bị ignore và không nằm trong bản nộp. Bảng
kết quả ở trên là số liệu đã tổng hợp từ các JSON đó.
