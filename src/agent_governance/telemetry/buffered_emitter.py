from __future__ import annotations

import queue
import threading
from typing import Any, Callable, Dict, Optional


class BufferedEmitter:
    def __init__(self, emit_fn: Callable[[Dict[str, Any]], None], buffer_size: int = 1000) -> None:
        self._emit_fn = emit_fn
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=buffer_size)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._stop = threading.Event()
        self._thread.start()

    def enqueue(self, payload: Dict[str, Any]) -> None:
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            # Drop oldest to keep system non-blocking
            try:
                _ = self._queue.get_nowait()
            except queue.Empty:
                pass
            self._queue.put_nowait(payload)

    def flush(self) -> None:
        while not self._queue.empty():
            try:
                payload = self._queue.get_nowait()
            except queue.Empty:
                break
            self._emit_fn(payload)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                payload = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            self._emit_fn(payload)

    def close(self) -> None:
        self._stop.set()
