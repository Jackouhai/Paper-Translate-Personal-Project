"""Server Manager - Quản lý PaddleOCR-VL và Gemma servers với model switching."""

import os
import signal
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional, Literal

import requests

from pp_doclayout.config import settings


# Server configs
PADDLE_OCR_PORT = 8000
GEMMA_PORT = 8001
PID_FILE = Path(".server_pids.txt")


class ServerManager:
    """Quản lý 2 servers với model switching."""

    def __init__(self):
        self.paddle_pid: Optional[int] = None
        self.gemma_pid: Optional[int] = None

        # Load PIDs từ file nếu có
        self._load_pids()

    def _load_pids(self):
        """Load saved PIDs."""
        if PID_FILE.exists():
            with open(PID_FILE, "r") as f:
                lines = f.readlines()
                for line in lines:
                    if line.startswith("PADDLE_OCR_PID="):
                        pid = int(line.split("=")[1].strip())
                        self.paddle_pid = pid if pid > 0 else None
                    elif line.startswith("GEMMA_PID="):
                        pid = int(line.split("=")[1].strip())
                        self.gemma_pid = pid if pid > 0 else None

    def _save_pids(self):
        """Save PIDs to file."""
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PID_FILE, "w") as f:
            f.write(f"PADDLE_OCR_PID={self.paddle_pid or 0}\n")
            f.write(f"GEMMA_PID={self.gemma_pid or 0}\n")

    def _is_port_available(self, port: int, timeout: int = 5) -> bool:
        """Check if port is available.

        Args:
            port: Port number to check
            timeout: Timeout in seconds

        Returns:
            True if port is available (not in use)
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            result = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            return result != 0  # Port is available if connection fails
        except (socket.timeout, OSError):
            return True  # Port is available

    def _wait_for_port(self, port: int, timeout: int = 30) -> bool:
        """Wait for port to become available.

        Args:
            port: Port number to wait for
            timeout: Timeout in seconds

        Returns:
            True if port became available
        """
        for i in range(timeout):
            if self._is_port_available(port, timeout=1):
                print(f"✅ Port {port} is available after {i+1}s")
                return True
            time.sleep(1)
        print(f"⚠️ Port {port} still in use after {timeout}s")
        return False

    def _wait_for_server_ready(self, port: int, timeout: int = 120) -> bool:
        """Wait for vLLM server to be fully initialized and ready.

        Checks that the server is not just listening on port, but actually
        ready to accept inference requests.

        Args:
            port: Port number
            timeout: Timeout in seconds

        Returns:
            True if server is ready
        """
        print(f"⏳ Waiting for server on port {port} to be fully ready...")
        url = f"http://127.0.0.1:{port}/v1/models"

        for i in range(timeout):
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print(f"✅ Server on port {port} is ready after {i+1}s")
                    return True
            except requests.exceptions.RequestException:
                pass  # Not ready yet

            time.sleep(1)

        print(f"⚠️ Server on port {port} still not ready after {timeout}s")
        return False

    def _is_process_running(self, pid: int) -> bool:
        """Check if process is running."""
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def start_paddle_ocr(self) -> int:
        """Start PaddleOCR-VL server.

        Returns:
            PID of started process
        """
        # Stop nếu đang chạy
        self.stop_paddle_ocr()
        time.sleep(2)  # Wait for graceful port release

        print(f"🚀 Starting PaddleOCR-VL on port {PADDLE_OCR_PORT}...")

        cmd = [
            "vllm", "serve",
            "PaddlePaddle/PaddleOCR-VL-1.5",
            "--served-model-name", "PaddleOCR-VL-1.5-0.9B",
            "--trust-remote-code",
            "--max-num-batched-tokens", "16384",
            "--max-num-seqs", "3",
            "--max-model-len", "32768",
            "--gpu-memory-utilization", "0.6",
            "--no-enable-prefix-caching",
            "--mm-processor-cache-gb", "0",
            "--dtype", "bfloat16",
            "--tensor-parallel-size", "1",
            "--port", str(PADDLE_OCR_PORT),
        ]

        # Start process detached
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=None  # Don't use start_new_session to simplify PID management
        )

        self.paddle_pid = process.pid
        self._save_pids()

        # Wait for server to actually listen on port
        if self._wait_for_port(PADDLE_OCR_PORT, timeout=60):
            # Then wait for server to be fully ready
            if self._wait_for_server_ready(PADDLE_OCR_PORT, timeout=120):
                print(f"✅ PaddleOCR-VL started (PID: {self.paddle_pid})")
                return self.paddle_pid
        
        print(f"❌ Failed to start PaddleOCR-VL - server not responding")
        self.stop_paddle_ocr()
        return None

    def start_gemma(self) -> int:
        """Start Gemma server.

        Returns:
            PID of started process
        """
        # Stop nếu đang chạy
        self.stop_gemma()
        time.sleep(2)  # Wait for graceful port release

        print(f"🚀 Starting Gemma on port {GEMMA_PORT}...")

        cmd = [
            "vllm", "serve",
            settings.vllm_model_name,
            "--dtype", "bfloat16",
            "--max-model-len", "32768",
            "--max-num-seqs", "16",
            "--max-num-batched-tokens", "8192",
            "--gpu-memory-utilization", "0.9",
            "--enforce-eager",
            "--port", str(GEMMA_PORT),
        ]

        # Start process detached
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=None  # Don't use start_new_session to simplify PID management
        )

        self.gemma_pid = process.pid
        self._save_pids()

        # Wait for server to actually listen on port
        if self._wait_for_port(GEMMA_PORT, timeout=60):
            # Then wait for server to be fully ready
            if self._wait_for_server_ready(GEMMA_PORT, timeout=120):
                print(f"✅ Gemma started (PID: {self.gemma_pid})")
                return self.gemma_pid
        
        print(f"❌ Failed to start Gemma - server not responding")
        self.stop_gemma()
        return None

    def _kill_process_tree(self, pid: int):
        """Kill process and its children.

        Args:
            pid: Process ID to kill
        """
        # Skip invalid PIDs
        if pid is None or pid <= 0:
            return
        
        print(f"🔨 Killing process {pid}...")
        
        # Method 1: Try graceful kill first with SIGTERM
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"  ↳ Sent SIGTERM to {pid}")
            time.sleep(2)  # Wait for graceful shutdown
            
            # Check if it's still running
            try:
                os.kill(pid, 0)  # Signal 0 = check if process exists
                print(f"  ↳ Process still running, forcing SIGKILL...")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
            except OSError:
                print(f"  ↳ Process terminated gracefully")
                return
                
        except ProcessLookupError:
            print(f"  ↳ Process {pid} already dead")
            return
        except Exception as e:
            print(f"  ⚠️ SIGTERM failed: {e}")
        
        # Method 2: Try pkill to kill children
        try:
            result = subprocess.run(
                ["pkill", "-P", str(pid)],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"  ↳ Killed child processes of {pid}")
                time.sleep(1)
        except Exception as e:
            print(f"  ⚠️ pkill children failed: {e}")
        
        # Method 3: Try pgrep to find any remaining processes
        try:
            result = subprocess.run(
                ["pgrep", "-P", str(pid)],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                remaining_pids = result.stdout.strip().split('\n')
                print(f"  ↳ Force killing remaining children: {remaining_pids}")
                for child_pid in remaining_pids:
                    if child_pid:
                        try:
                            os.kill(int(child_pid), signal.SIGKILL)
                        except ProcessLookupError:
                            pass
        except Exception as e:
            print(f"  ⚠️ Cleanup children failed: {e}")
        
        # Verify final state
        try:
            os.kill(pid, 0)  # Check if process still exists
            print(f"  ⚠️ Process {pid} still exists!")
        except OSError:
            print(f"✅ Process {pid} killed successfully")

    def stop_paddle_ocr(self):
        """Stop PaddleOCR-VL server."""
        # First, kill by PID if we have it
        if self.paddle_pid and self.paddle_pid > 0:
            print(f"🛑 Stopping PaddleOCR-VL (PID: {self.paddle_pid})...")
            self._kill_process_tree(self.paddle_pid)

        # Also kill any vllm processes on port 8000
        self._kill_vllm_on_port(PADDLE_OCR_PORT)
        
        # Verify port is actually free
        if self._is_port_available(PADDLE_OCR_PORT):
            print(f"✅ Port {PADDLE_OCR_PORT} is now free")
        else:
            print(f"⚠️ Port {PADDLE_OCR_PORT} still in use, retrying...")
            self._kill_vllm_on_port(PADDLE_OCR_PORT)
            time.sleep(2)

        self.paddle_pid = None
        self._save_pids()

        # Wait for GPU to free up
        self._wait_for_gpu_free()

    def stop_gemma(self):
        """Stop Gemma server."""
        # First, kill by PID if we have it
        if self.gemma_pid and self.gemma_pid > 0:
            print(f"🛑 Stopping Gemma (PID: {self.gemma_pid})...")
            self._kill_process_tree(self.gemma_pid)

        # Also kill any vllm processes on port 8001
        self._kill_vllm_on_port(GEMMA_PORT)
        
        # Verify port is actually free
        if self._is_port_available(GEMMA_PORT):
            print(f"✅ Port {GEMMA_PORT} is now free")
        else:
            print(f"⚠️ Port {GEMMA_PORT} still in use, retrying...")
            self._kill_vllm_on_port(GEMMA_PORT)
            time.sleep(2)

        self.gemma_pid = None
        self._save_pids()

        # Wait for GPU to free up
        self._wait_for_gpu_free()

        # Also kill any vllm processes on port 8001
        self._kill_vllm_on_port(GEMMA_PORT)

        self.gemma_pid = None
        self._save_pids()

        # Wait for GPU to free up
        self._wait_for_gpu_free()

    def _kill_vllm_on_port(self, port: int):
        """Kill any vllm processes listening on specific port.

        Args:
            port: Port number
        """
        pids = []
        
        # Method 1: Try lsof
        try:
            result = subprocess.run(
                ["lsof", "-t", "-i", f":{port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                pids = [int(pid) for pid in result.stdout.strip().split('\n') if pid.strip()]
        except Exception as e:
            print(f"  ⚠️ lsof failed: {e}")
        
        # Method 2: Try fuser as fallback
        if not pids:
            try:
                result = subprocess.run(
                    ["fuser", f"{port}/tcp"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0 and result.stdout.strip():
                    pids = [int(pid) for pid in result.stdout.strip().split()]
            except Exception as e:
                pass  # fuser may not be installed
        
        # Kill all found PIDs
        if pids:
            print(f"🔍 Found processes on port {port}: {pids}")
            for pid in pids:
                try:
                    self._kill_process_tree(pid)
                except ProcessLookupError:
                    pass
        else:
            print(f"ℹ️  No processes found on port {port}")

    def _wait_for_gpu_free(self, timeout: int = 10):
        """Wait for GPU memory to be freed.

        Args:
            timeout: Max wait time in seconds
        """
        print(f"⏳ Waiting for GPU to free up (max {timeout}s)...")

        for i in range(timeout):
            # Check GPU memory usage
            try:
                result = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=2
                )

                if result.returncode == 0:
                    memory_output = result.stdout.strip()
                    if memory_output:
                        try:
                            # Get the first GPU's memory (in case of multiple GPUs)
                            mem_val = float(memory_output.split('\n')[0])
                        except (ValueError, IndexError):
                            mem_val = 0

                        # If GPU is mostly free (< 2GB used), we're good
                        if mem_val < 2048:
                            print(f"✅ GPU memory freed ({mem_val:.0f}MB used)")
                            return True
            except Exception:
                pass  # nvidia-smi not available, skip check

            time.sleep(1)

        print(f"⚠️ GPU still in use after {timeout}s, but continuing...")
        return False

    def stop_all(self):
        """Stop all servers."""
        print("🛑 Stopping all servers...")
        self.stop_paddle_ocr()
        self.stop_gemma()
        # Clean up PID file
        if PID_FILE.exists():
            PID_FILE.unlink()

    def switch_to(self, server: Literal["paddle", "gemma"]) -> bool:
        """Switch to specific server.

        Args:
            server: "paddle" or "gemma"

        Returns:
            True if successful
        """
        print(f"\n🔄 Switching to {server}...")

        if server == "paddle":
            # Stop Gemma (with GPU cleanup), then start PaddleOCR-VL
            self.stop_gemma()
            print(f"⏳ Waiting for port {GEMMA_PORT} to be released...")
            time.sleep(3)  # Extra wait for GPU cleanup
            result = self.start_paddle_ocr()
            return result is not None
        elif server == "gemma":
            # Stop PaddleOCR-VL (with GPU cleanup), then start Gemma
            self.stop_paddle_ocr()
            print(f"⏳ Waiting for port {PADDLE_OCR_PORT} to be released...")
            time.sleep(3)  # Extra wait for GPU cleanup
            result = self.start_gemma()
            return result is not None
        else:
            print(f"❌ Unknown server: {server}")
            return False

    def status(self) -> dict:
        """Get status of both servers.

        Returns:
            Dict with "paddle" and "gemma" status
        """
        return {
            "paddle": "running" if self._is_process_running(self.paddle_pid) else "stopped",
            "paddle_pid": self.paddle_pid,
            "gemma": "running" if self._is_process_running(self.gemma_pid) else "stopped",
            "gemma_pid": self.gemma_pid,
        }


# Global instance
_manager: Optional[ServerManager] = None


def get_manager() -> ServerManager:
    """Get global server manager instance."""
    global _manager
    if _manager is None:
        _manager = ServerManager()
    return _manager


def main():
    """CLI cho server manager."""
    import argparse

    parser = argparse.ArgumentParser(description="Quản lý servers cho PP-DocLayout")
    subparsers = parser.add_subparsers(dest="command", help="Lệnh")

    # Start paddle
    subparsers.add_parser("start-paddle", help="Start PaddleOCR-VL")

    # Start gemma
    subparsers.add_parser("start-gemma", help="Start Gemma")

    # Stop paddle
    subparsers.add_parser("stop-paddle", help="Stop PaddleOCR-VL")

    # Stop gemma
    subparsers.add_parser("stop-gemma", help="Stop Gemma")

    # Stop all
    subparsers.add_parser("stop-all", help="Stop tất cả servers")

    # Switch
    switch_parser = subparsers.add_parser("switch", help="Switch server")
    switch_parser.add_argument("server", choices=["paddle", "gemma"], help="Server để switch")

    # Status
    subparsers.add_parser("status", help="Xem status servers")

    args = parser.parse_args()

    manager = ServerManager()

    if args.command == "start-paddle":
        manager.start_paddle_ocr()
    elif args.command == "start-gemma":
        manager.start_gemma()
    elif args.command == "stop-paddle":
        manager.stop_paddle_ocr()
    elif args.command == "stop-gemma":
        manager.stop_gemma()
    elif args.command == "stop-all":
        manager.stop_all()
    elif args.command == "switch":
        manager.switch_to(args.server)
    elif args.command == "status":
        status = manager.status()
        print(f"\n📊 Server Status:")
        print(f"  PaddleOCR-VL: {status['paddle']} (PID: {status['paddle_pid']})")
        print(f"  Gemma: {status['gemma']} (PID: {status['gemma_pid']})")


if __name__ == "__main__":
    main()
