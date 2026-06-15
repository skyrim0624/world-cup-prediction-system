from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # pragma: no cover - 生产环境目标是 Linux，这里保留跨平台兜底。
    fcntl = None


class ProcessLockBusy(RuntimeError):
    pass


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as file:
            temp_path = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


@contextmanager
def acquire_process_lock(lock_path: Path, timeout_seconds: float = 0) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0, timeout_seconds)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        while True:
            try:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as error:
                if time.monotonic() >= deadline:
                    raise ProcessLockBusy(f"已有任务持有锁: {lock_path}") from error
                time.sleep(0.05)

        lock_file.seek(0)
        lock_file.truncate()
        lock_file.write(f"pid={os.getpid()} acquiredAt={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
        lock_file.flush()
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
