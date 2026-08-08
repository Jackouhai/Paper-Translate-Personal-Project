import argparse
import asyncio
import json
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiohttp


DEFAULT_MODEL = "Infomaniak-AI/vllm-translategemma-4b-it"
DEFAULT_URL = "http://127.0.0.1:8001/v1/chat/completions"


@dataclass
class RequestResult:
    request_id: int
    success: bool
    status_code: int
    latency_seconds: float
    service_latency_seconds: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error: str | None = None


@dataclass
class GpuMemorySample:
    used_mib: int
    total_mib: int
    utilization_percent: int | None = None


@dataclass
class BenchmarkRun:
    concurrency: int
    total_duration: float
    results: list[RequestResult]
    gpu_samples: list[GpuMemorySample]
    baseline_gpu: GpuMemorySample | None
    final_gpu: GpuMemorySample | None


def write_report(
    path: Path,
    args: argparse.Namespace,
    run_summaries: list[tuple[BenchmarkRun, bool, str, float | None]],
) -> None:
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
        "runs": [],
    }

    for run, passed, risk_status, ratio in run_summaries:
        report["runs"].append(
            {
                "concurrency": run.concurrency,
                "total_duration_seconds": run.total_duration,
                "passed": passed,
                "vram_risk": risk_status,
                "vram_peak_ratio": ratio,
                "baseline_gpu": (
                    {
                        "used_mib": run.baseline_gpu.used_mib,
                        "total_mib": run.baseline_gpu.total_mib,
                        "utilization_percent": run.baseline_gpu.utilization_percent,
                    }
                    if run.baseline_gpu
                    else None
                ),
                "final_gpu": (
                    {
                        "used_mib": run.final_gpu.used_mib,
                        "total_mib": run.final_gpu.total_mib,
                        "utilization_percent": run.final_gpu.utilization_percent,
                    }
                    if run.final_gpu
                    else None
                ),
                "gpu_samples": [
                    {
                        "used_mib": sample.used_mib,
                        "total_mib": sample.total_mib,
                        "utilization_percent": sample.utilization_percent,
                    }
                    for sample in run.gpu_samples
                ],
                "requests": [
                    {
                        "request_id": result.request_id,
                        "success": result.success,
                        "status_code": result.status_code,
                        "latency_seconds": result.latency_seconds,
                        "service_latency_seconds": result.service_latency_seconds,
                        "prompt_tokens": result.prompt_tokens,
                        "completion_tokens": result.completion_tokens,
                        "error": result.error,
                    }
                    for result in run.results
                ],
            }
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Report saved:          {path}", flush=True)


def build_translation_text(approximate_tokens: int) -> str:
    """Build deterministic English input with approximately this many tokens."""
    sentence = (
        "Machine learning systems process scientific documents, preserve context, "
        "maintain technical terminology, and translate academic content accurately. "
    )
    target_characters = approximate_tokens * 4
    repetitions = target_characters // len(sentence) + 1
    return (sentence * repetitions)[:target_characters]


def build_pipeline_prompt(translation_text: str) -> str:
    """Match the prompt shape currently used by GemmaTranslator."""
    return (
        "You are a professional English (en) to Vietnamese (vi) translator "
        "research paper. Your goal is to accurately convey the meaning and "
        "nuances of the original English text while adhering to Vietnamese "
        "grammar, vocabulary, and cultural sensitivities. Warning: Do not use "
        "Arabic laguange. The following text is an excerpt from a technical "
        "academic research paper. Produce only the Vietnamese translation, "
        "without any additional explanations or commentary. Please translate "
        "the following English text into Vietnamese:\n\n"
        f"{translation_text}"
    )


def build_payload(
    model: str,
    translation_text: str,
    output_tokens: int,
    prompt_style: str,
    ignore_eos: bool,
) -> dict:
    if prompt_style == "pipeline":
        content = f"<<<custom>>>{build_pipeline_prompt(translation_text)}"
    else:
        content = (
            "<<<source>>>en"
            "<<<target>>>vi"
            f"<<<text>>>{translation_text}"
        )

    return {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": output_tokens,
        "temperature": 0,
        "ignore_eos": ignore_eos,
        "stream": False,
    }


def read_gpu_memory(gpu_index: int) -> GpuMemorySample | None:
    """Read memory usage without adding a Python NVML dependency."""
    command = [
        "nvidia-smi",
        "-i",
        str(gpu_index),
        "--query-gpu=memory.used,memory.total,utilization.gpu",
        "--format=csv,noheader,nounits",
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0:
        return None

    fields = [field.strip() for field in completed.stdout.split(",")]
    if len(fields) < 2 or any(field in {"", "N/A", "[N/A]"} for field in fields[:2]):
        return None

    try:
        used_mib = int(float(fields[0]))
        total_mib = int(float(fields[1]))
        utilization = int(float(fields[2])) if len(fields) >= 3 else None
    except ValueError:
        return None

    return GpuMemorySample(used_mib, total_mib, utilization)


async def monitor_gpu_memory(
    samples: list[GpuMemorySample],
    gpu_index: int,
    interval_seconds: float,
    stop_event: asyncio.Event,
) -> None:
    while not stop_event.is_set():
        sample = await asyncio.to_thread(read_gpu_memory, gpu_index)
        if sample is not None:
            samples.append(sample)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass


async def send_request(
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    url: str,
    payload: dict,
    request_id: int,
) -> RequestResult:
    # Start before semaphore so latency represents what the caller experiences.
    queued_at = time.perf_counter()

    async with semaphore:
        service_started_at = time.perf_counter()

        try:
            async with session.post(url, json=payload) as response:
                latency = time.perf_counter() - queued_at
                service_latency = time.perf_counter() - service_started_at

                if response.status != 200:
                    response_body = await response.text()
                    return RequestResult(
                        request_id=request_id,
                        success=False,
                        status_code=response.status,
                        latency_seconds=latency,
                        service_latency_seconds=service_latency,
                        error=response_body[:1000],
                    )

                try:
                    body = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError) as exc:
                    return RequestResult(
                        request_id=request_id,
                        success=False,
                        status_code=response.status,
                        latency_seconds=latency,
                        service_latency_seconds=service_latency,
                        error=f"invalid JSON response: {exc}",
                    )

                choices = body.get("choices") if isinstance(body, dict) else None
                if not isinstance(choices, list) or not choices:
                    return RequestResult(
                        request_id=request_id,
                        success=False,
                        status_code=response.status,
                        latency_seconds=latency,
                        service_latency_seconds=service_latency,
                        error="response has no choices",
                    )

                usage = body.get("usage", {})
                if not isinstance(usage, dict):
                    usage = {}

                def usage_int(name: str) -> int | None:
                    value = usage.get(name)
                    return int(value) if isinstance(value, (int, float)) else None

                return RequestResult(
                    request_id=request_id,
                    success=True,
                    status_code=response.status,
                    latency_seconds=latency,
                    service_latency_seconds=service_latency,
                    prompt_tokens=usage_int("prompt_tokens"),
                    completion_tokens=usage_int("completion_tokens"),
                )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            latency = time.perf_counter() - queued_at
            service_latency = time.perf_counter() - service_started_at
            return RequestResult(
                request_id=request_id,
                success=False,
                status_code=0,
                latency_seconds=latency,
                service_latency_seconds=service_latency,
                error=repr(exc),
            )


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * percent)
    return sorted_values[index]


def parse_concurrency_levels(args: argparse.Namespace) -> list[int]:
    if args.concurrency_levels:
        raw_levels = args.concurrency_levels.split(",")
        try:
            levels = [int(level.strip()) for level in raw_levels if level.strip()]
        except ValueError as exc:
            raise ValueError("--concurrency-levels phải là danh sách số nguyên") from exc
    else:
        levels = [args.concurrency]

    if not levels or any(level <= 0 for level in levels):
        raise ValueError("concurrency phải lớn hơn 0")
    if len(set(levels)) != len(levels):
        raise ValueError("--concurrency-levels không được chứa giá trị trùng")
    return levels


def is_oom_error(error: str | None) -> bool:
    if not error:
        return False
    normalized = error.lower()
    return any(
        marker in normalized
        for marker in (
            "out of memory",
            "cuda out of memory",
            "cublas_status_alloc_failed",
            "kv cache",
        )
    )


def memory_risk(
    samples: list[GpuMemorySample],
    threshold: float,
) -> tuple[str, float | None]:
    if not samples:
        return "UNKNOWN", None

    peak = max(samples, key=lambda sample: sample.used_mib)
    ratio = peak.used_mib / peak.total_mib if peak.total_mib else None
    if ratio is None:
        return "UNKNOWN", None
    if ratio >= threshold:
        return "HIGH", ratio
    if ratio >= threshold - 0.05:
        return "WARNING", ratio
    return "OK", ratio


def print_gpu_summary(
    run: BenchmarkRun,
    gpu_risk_threshold: float,
) -> tuple[str, float | None]:
    samples = list(run.gpu_samples)
    if run.baseline_gpu is not None:
        samples.append(run.baseline_gpu)
    if run.final_gpu is not None:
        samples.append(run.final_gpu)

    status, ratio = memory_risk(samples, gpu_risk_threshold)
    if not samples:
        print("VRAM:                 unavailable (nvidia-smi not usable)", flush=True)
        return status, ratio

    peak = max(samples, key=lambda sample: sample.used_mib)
    baseline = run.baseline_gpu or samples[0]
    delta = peak.used_mib - baseline.used_mib
    ratio_text = f" ({ratio * 100:.1f}%)" if ratio is not None else ""
    print(
        f"VRAM baseline/peak:    {baseline.used_mib:,}/{peak.used_mib:,} MiB "
        f"of {peak.total_mib:,} MiB{ratio_text}",
        flush=True,
    )
    print(f"VRAM increase:         {delta:+,} MiB", flush=True)
    print(f"VRAM risk:             {status}", flush=True)
    return status, ratio


def print_run_summary(
    run: BenchmarkRun,
    gpu_risk_threshold: float,
) -> tuple[bool, str, float | None]:
    successful = [result for result in run.results if result.success]
    failed = [result for result in run.results if not result.success]
    latencies = [result.latency_seconds for result in successful]
    service_latencies = [result.service_latency_seconds for result in successful]

    print("===== Result =====", flush=True)
    print(f"Concurrency:          {run.concurrency}", flush=True)
    print(f"Total duration:       {run.total_duration:.2f}s", flush=True)
    print(f"Successful requests:  {len(successful)}", flush=True)
    print(f"Failed requests:      {len(failed)}", flush=True)

    if run.total_duration > 0:
        print(
            f"Request throughput:   {len(successful) / run.total_duration:.3f} req/s",
            flush=True,
        )

    if latencies:
        print(f"Mean end-to-end:      {sum(latencies) / len(latencies):.2f}s", flush=True)
        print(f"P50 end-to-end:       {percentile(latencies, 0.50):.2f}s", flush=True)
        print(f"P95 end-to-end:       {percentile(latencies, 0.95):.2f}s", flush=True)
        print(
            f"P95 server service:   {percentile(service_latencies, 0.95):.2f}s",
            flush=True,
        )

    prompt_tokens = [result.prompt_tokens for result in successful]
    completion_tokens = [result.completion_tokens for result in successful]
    if successful and all(
        value is not None for value in prompt_tokens + completion_tokens
    ) and run.total_duration > 0:
        total_prompt_tokens = sum(value for value in prompt_tokens if value is not None)
        total_completion_tokens = sum(
            value for value in completion_tokens if value is not None
        )
        print(f"Prompt tokens:        {total_prompt_tokens:,}", flush=True)
        print(f"Completion tokens:    {total_completion_tokens:,}", flush=True)
        print(
            f"Prompt throughput:    {total_prompt_tokens / run.total_duration:.1f} tok/s",
            flush=True,
        )
        print(
            f"Generation throughput:{total_completion_tokens / run.total_duration:.1f} tok/s",
            flush=True,
        )
    else:
        print("Token throughput:     unavailable (server omitted usage)", flush=True)

    risk_status, ratio = print_gpu_summary(run, gpu_risk_threshold)

    if failed:
        print("First failed requests:", flush=True)
        for result in failed[:10]:
            print(
                f"- Request {result.request_id}: status={result.status_code}, "
                f"error={result.error}",
                flush=True,
            )

    oom_detected = any(is_oom_error(result.error) for result in failed)
    passed = not failed and not oom_detected
    print(
        "PASS: tất cả request hợp lệ."
        if passed
        else "FAIL: có request lỗi; kiểm tra log vLLM và VRAM.",
        flush=True,
    )
    return passed, risk_status, ratio


async def run_single_test(
    args: argparse.Namespace,
    concurrency: int,
) -> BenchmarkRun:
    print(f"===== vLLM stress test: concurrency={concurrency} =====", flush=True)
    print(f"URL:                  {args.url}", flush=True)
    print(f"Model:                {args.model}", flush=True)
    print(f"Approx input tokens:  {args.input_tokens}", flush=True)
    print(f"Output tokens:        {args.output_tokens}", flush=True)
    print(f"Requests:             {args.num_requests}", flush=True)
    print(f"Prompt style:         {args.prompt_style}", flush=True)
    print(f"Ignore EOS:           {args.ignore_eos}", flush=True)

    estimated_overhead = 128 if args.prompt_style == "pipeline" else 16
    estimated_context = args.input_tokens + estimated_overhead + args.output_tokens
    if estimated_context > args.max_model_len:
        print(
            f"WARNING: estimated context {estimated_context} > "
            f"--max-model-len {args.max_model_len}; request may be rejected.",
            flush=True,
        )

    translation_text = build_translation_text(args.input_tokens)
    payload = build_payload(
        model=args.model,
        translation_text=translation_text,
        output_tokens=args.output_tokens,
        prompt_style=args.prompt_style,
        ignore_eos=args.ignore_eos,
    )

    timeout = aiohttp.ClientTimeout(
        total=args.timeout if args.timeout > 0 else None,
        connect=30,
        sock_connect=30,
        sock_read=args.timeout if args.timeout > 0 else None,
    )
    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
    semaphore = asyncio.Semaphore(concurrency)
    baseline_gpu = await asyncio.to_thread(read_gpu_memory, args.gpu_index)
    gpu_samples: list[GpuMemorySample] = []
    stop_gpu_monitor = asyncio.Event()
    if args.gpu_sample_interval > 0:
        gpu_monitor_task = asyncio.create_task(
            monitor_gpu_memory(
                gpu_samples,
                args.gpu_index,
                args.gpu_sample_interval,
                stop_gpu_monitor,
            )
        )
    else:
        gpu_monitor_task = None

    started_at = time.perf_counter()
    results: list[RequestResult] = []
    try:
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            tasks = [
                asyncio.create_task(
                    send_request(
                        session=session,
                        semaphore=semaphore,
                        url=args.url,
                        payload=payload,
                        request_id=request_id,
                    )
                )
                for request_id in range(1, args.num_requests + 1)
            ]

            for completed_count, completed_task in enumerate(
                asyncio.as_completed(tasks),
                start=1,
            ):
                result = await completed_task
                results.append(result)
                status_text = "OK" if result.success else f"FAILED HTTP {result.status_code}"
                print(
                    f"[{completed_count:>3}/{args.num_requests}] "
                    f"request={result.request_id:<3} {status_text:<16} "
                    f"latency={result.latency_seconds:.2f}s",
                    flush=True,
                )
                if not result.success and result.error:
                    print(f"    Error: {result.error[:500]}", flush=True)
    finally:
        stop_gpu_monitor.set()
        if gpu_monitor_task is not None:
            await gpu_monitor_task

    total_duration = time.perf_counter() - started_at
    final_gpu = await asyncio.to_thread(read_gpu_memory, args.gpu_index)
    return BenchmarkRun(
        concurrency=concurrency,
        total_duration=total_duration,
        results=results,
        gpu_samples=gpu_samples,
        baseline_gpu=baseline_gpu,
        final_gpu=final_gpu,
    )


async def run_stress_test(args: argparse.Namespace) -> int:
    levels = parse_concurrency_levels(args)
    run_summaries: list[tuple[BenchmarkRun, bool, str, float | None]] = []

    for index, concurrency in enumerate(levels):
        run = await run_single_test(args, concurrency)
        passed, risk_status, ratio = print_run_summary(run, args.vram_risk_threshold)
        run_summaries.append((run, passed, risk_status, ratio))

        if index < len(levels) - 1:
            if not passed:
                print("Dừng sweep sau mức đầu tiên bị lỗi.", flush=True)
                break
            print(f"Chờ {args.cooldown:.1f}s trước mức tiếp theo...", flush=True)
            await asyncio.sleep(args.cooldown)

    if len(run_summaries) > 1:
        print("\n===== Sweep summary =====", flush=True)
        no_high_risk_levels: list[int] = []
        ok_levels: list[int] = []
        passing_levels: list[int] = []
        for run, passed, risk_status, ratio in run_summaries:
            ratio_text = f", peak={ratio * 100:.1f}% VRAM" if ratio is not None else ""
            print(
                f"concurrency={run.concurrency}: "
                f"{'PASS' if passed else 'FAIL'}, VRAM={risk_status}{ratio_text}",
                flush=True,
            )
            if passed:
                passing_levels.append(run.concurrency)
                if risk_status in {"OK", "WARNING"}:
                    no_high_risk_levels.append(run.concurrency)
                if risk_status == "OK":
                    ok_levels.append(run.concurrency)

        if passing_levels:
            print(f"Highest passing concurrency: {max(passing_levels)}", flush=True)
        if no_high_risk_levels:
            print(
                "Highest passing concurrency below HIGH VRAM threshold: "
                f"{max(no_high_risk_levels)}",
                flush=True,
            )
        else:
            print("Chưa có mức passing nào dưới HIGH VRAM threshold.", flush=True)
        if ok_levels:
            print(
                f"Highest passing concurrency with VRAM status OK: {max(ok_levels)}",
                flush=True,
            )

    write_report(args.log_file, args, run_summaries)

    return 0 if all(passed for _, passed, _, _ in run_summaries) else 1


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stress test vLLM TranslateGemma server.")
    parser.add_argument(
        "--input-tokens",
        type=int,
        required=True,
        help="Số token input ước lượng; 1 token tiếng Anh ≈ 4 ký tự.",
    )
    parser.add_argument("--output-tokens", type=int, required=True)
    parser.add_argument("--num-requests", type=int, required=True)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Concurrency cho một lần chạy. Default: 1.",
    )
    parser.add_argument(
        "--concurrency-levels",
        help="Sweep, ví dụ: 1,2,4,8,12,15,20. Ghi đè --concurrency.",
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--timeout",
        type=float,
        default=0,
        help="Timeout mỗi request theo giây; 0 là không giới hạn.",
    )
    parser.add_argument(
        "--prompt-style",
        choices=("pipeline", "tags"),
        default="pipeline",
        help="pipeline mô phỏng GemmaTranslator hiện tại; tags dùng format raw.",
    )
    parser.add_argument(
        "--ignore-eos",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Ép sinh đến max_tokens để stress decode. Dùng --no-ignore-eos để tắt.",
    )
    parser.add_argument(
        "--max-model-len",
        type=int,
        default=4096,
        help="Chỉ dùng để cảnh báo context theo serving hiện tại. Default: 4096.",
    )
    parser.add_argument("--gpu-index", type=int, default=0)
    parser.add_argument(
        "--gpu-sample-interval",
        type=float,
        default=0.5,
        help="Chu kỳ đọc nvidia-smi theo giây. Đặt 0 để tắt monitor.",
    )
    parser.add_argument(
        "--vram-risk-threshold",
        type=float,
        default=0.90,
        help="Ngưỡng VRAM tuyệt đối để báo HIGH. Default: 0.90.",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=5,
        help="Thời gian nghỉ giữa các mức sweep. Default: 5 giây.",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Đường dẫn report JSON; mặc định là logs/stress_vllm_<timestamp>.json.",
    )

    args = parser.parse_args()
    if args.input_tokens <= 0 or args.output_tokens <= 0 or args.num_requests <= 0:
        parser.error("input/output tokens và num-requests phải lớn hơn 0")
    if args.concurrency <= 0:
        parser.error("--concurrency phải lớn hơn 0")
    if args.timeout < 0:
        parser.error("--timeout không được âm")
    if args.max_model_len <= 0:
        parser.error("--max-model-len phải lớn hơn 0")
    if args.gpu_index < 0:
        parser.error("--gpu-index không được âm")
    if args.gpu_sample_interval < 0 or args.cooldown < 0:
        parser.error("--gpu-sample-interval và --cooldown không được âm")
    if not 0 < args.vram_risk_threshold <= 1:
        parser.error("--vram-risk-threshold phải nằm trong (0, 1]")

    if args.log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.log_file = Path("logs") / f"stress_vllm_{timestamp}.json"

    try:
        parse_concurrency_levels(args)
    except ValueError as exc:
        parser.error(str(exc))

    return args


def main() -> None:
    args = parse_arguments()
    try:
        exit_code = asyncio.run(run_stress_test(args))
    except KeyboardInterrupt:
        print("\nStress test bị dừng bởi người dùng.", flush=True)
        raise SystemExit(130)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
