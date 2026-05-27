from __future__ import annotations

import multiprocessing as mp
import queue
import threading
from typing import Any


def read_subprocess_result(
    worker: mp.Process,
    result_queue: mp.Queue,
    timeout_seconds: float,
) -> dict[str, Any] | None:
    """Drain the result queue while waiting for the worker to exit.

    On Windows spawn, ``Process.join()`` before ``Queue.get()`` deadlocks once
    the pipe buffer fills. A reader thread consumes the queue so the child can
    finish ``put()`` and exit.
    """

    payload_box: dict[str, Any] = {}

    def _reader() -> None:
        try:
            payload_box["payload"] = result_queue.get(timeout=max(timeout_seconds, 0.1) + 5.0)
        except queue.Empty:
            return

    reader = threading.Thread(target=_reader, daemon=True)
    reader.start()
    worker.join(timeout_seconds)
    reader.join(timeout=1.0)
    return payload_box.get("payload")


def terminate_subprocess_worker(worker: mp.Process) -> None:
    if worker.is_alive():
        worker.terminate()
        worker.join()
