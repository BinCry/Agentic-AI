"""Small bounded subprocess primitive shared by approved Phase 2 tools."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class BoundedProcessResult:
    command: tuple[str, ...]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool
    duration_ms: int


def run_bounded(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: float,
    maximum_output_bytes: int,
    environment: dict[str, str],
) -> BoundedProcessResult:
    if not command or any(not isinstance(item, str) or not item for item in command):
        raise ValueError("command must be a non-empty list of non-empty strings")
    if timeout_seconds <= 0 or maximum_output_bytes < 1:
        raise ValueError("timeout and output limits must be positive")
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=environment,
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=(os.name != "nt"),
    )
    stdout_buffer: list[bytes] = []
    stderr_buffer: list[bytes] = []
    stdout_size = [0]
    stderr_size = [0]

    def drain(stream: object, buffer: list[bytes], size: list[int]) -> None:
        while True:
            chunk = stream.read(8192)  # type: ignore[union-attr]
            if not chunk:
                return
            remaining = max(0, maximum_output_bytes - size[0])
            if remaining:
                buffer.append(chunk[:remaining])
            size[0] += len(chunk)

    stdout_thread = threading.Thread(
        target=drain, args=(process.stdout, stdout_buffer, stdout_size), daemon=True
    )
    stderr_thread = threading.Thread(
        target=drain, args=(process.stderr, stderr_buffer, stderr_size), daemon=True
    )
    stdout_thread.start()
    stderr_thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_tree(process)
        process.wait()
    stdout_thread.join(timeout=2)
    stderr_thread.join(timeout=2)
    if process.stdout is not None:
        process.stdout.close()
    if process.stderr is not None:
        process.stderr.close()
    return BoundedProcessResult(
        command=tuple(command),
        exit_code=process.returncode,
        stdout=b"".join(stdout_buffer).decode("utf-8", errors="replace"),
        stderr=b"".join(stderr_buffer).decode("utf-8", errors="replace"),
        timed_out=timed_out,
        stdout_truncated=stdout_size[0] > maximum_output_bytes,
        stderr_truncated=stderr_size[0] > maximum_output_bytes,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )


def safe_environment(paths_root: Path, runtime_root: Path) -> dict[str, str]:
    """Build a small environment and keep temp/home writes in the workspace."""
    allowed = {"PATH", "Path", "PATHEXT", "SystemRoot", "SYSTEMROOT", "WINDIR"}
    environment = {key: value for key, value in os.environ.items() if key in allowed}
    temp_root = runtime_root / "process-temp"
    home_root = runtime_root / "process-home"
    temp_root.mkdir(parents=True, exist_ok=True)
    home_root.mkdir(parents=True, exist_ok=True)
    environment.update(
        {
            "TEMP": str(temp_root),
            "TMP": str(temp_root),
            "HOME": str(home_root),
            "USERPROFILE": str(home_root),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(paths_root / "src"),
            "PYTHONNOUSERSITE": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=5,
                shell=False,
            )
            return
        except (OSError, subprocess.TimeoutExpired):
            pass
    process.kill()
