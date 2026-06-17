import shutil
import subprocess

def run_command(command: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def check_nvidia_smi() -> bool:
    if shutil.which("nvidia-smi") is None:
        print("nvidia-smi not found. NVIDIA driver may not be installed.")
        return False
    code, stdout, stderr = run_command(["nvidia-smi"])
    
    if code != 0:
        print("nvidia-smi failed:")
        print(stderr)
        return False

    print("nvidia-smi detected:")
    print(stdout)
    return True

def check_paddle() -> bool:
    try: 
        import paddle 
    except ImportError:
        print("paddle is not installed in the current Python environment.")
        return False

    print(f"Paddle version: {paddle.__version__}")
    print(f"Compiled with CUDA: {paddle.device.is_compiled_with_cuda()}")
    
    try:
        paddle.utils.run_check()
    except Exception as exc:
        print("paddle.utils.run_check() failed:")
        print(exc)
        return False
    return True

def main() -> int:
    print("Checking NVIDIA environment...")
    has_gpu = check_nvidia_smi()
    
    print()
    print("Checking PaddlePaddle...")
    has_paddle = check_paddle()

    print()
    if has_gpu and has_paddle:
        print("GPU and Paddle environment look usable.")
        return 0
    print("Environment check failed. See messages above.")
    return 1

if __name__ == "__main__":
    raise SystemExit(main())