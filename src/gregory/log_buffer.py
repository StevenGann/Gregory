"""In-memory log buffer for debug UI. Captures logs from the root logger."""

import asyncio
import json
import logging
import threading
from collections import deque
from datetime import datetime


class LogBufferHandler(logging.Handler):
    """Handler that buffers log records and notifies SSE subscribers."""

    def __init__(self, buffer: "LogBuffer", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "ts": datetime.utcfromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3],
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            self._buffer.append(entry)
        except Exception:
            self.handleError(record)


class LogBuffer:
    """Thread-safe in-memory buffer of recent log entries. Supports SSE streaming."""

    def __init__(self, maxlen: int = 1000):
        self._deque: deque[dict] = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._subscribers: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for thread-safe SSE delivery."""
        self._loop = loop

    def append(self, entry: dict) -> None:
        with self._lock:
            self._deque.append(entry)
            subs = list(self._subscribers)

        if subs and self._loop is not None:
            def deliver():
                for q in subs:
                    try:
                        q.put_nowait(entry)
                    except asyncio.QueueFull:
                        pass

            try:
                self._loop.call_soon_thread_safe(deliver)
            except RuntimeError:
                pass

    def get_recent(self, limit: int = 500) -> list[dict]:
        with self._lock:
            items = list(self._deque)
        return items[-limit:] if limit else items

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass


_log_buffer: LogBuffer | None = None


def get_log_buffer() -> LogBuffer:
    """Return the global log buffer, creating it if needed."""
    global _log_buffer
    if _log_buffer is None:
        _log_buffer = LogBuffer()
    return _log_buffer


def install_log_handler() -> None:
    """Attach the buffer handler to the root logger."""
    buf = get_log_buffer()
    handler = LogBufferHandler(buf)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(handler)
