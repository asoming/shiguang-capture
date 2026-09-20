"""One reusable local inference process; cancellation kills only that process."""
from __future__ import annotations
import multiprocessing as mp
import threading
import time

from . import create_backend
from .base import assert_privacy_guard


def _serve(connection):
    backend = None
    try:
        while connection.poll(300):  # Release model memory after five idle minutes.
            image, mode, config = connection.recv()
            try:
                started = time.perf_counter()
                if backend is None:
                    backend = create_backend(config.ocr_engine)
                assert_privacy_guard(backend, False)
                from ..structured import code_from_blocks, detect_grid, table_from_blocks
                boxes = None
                specialized = getattr(backend, 'recognize_'+mode, None) if mode in {'table', 'code'} else None
                if mode == 'table' and specialized is None:
                    boxes, image = detect_grid(image)
                result = specialized(image) if specialized else backend.recognize(image)
                result.mode = mode
                if mode == 'code':
                    result.text = code_from_blocks(result.blocks)
                elif boxes is not None:
                    result.table = table_from_blocks(boxes, result.blocks)
                    result.text = '\n'.join('\t'.join(row) for row in result.table.cells)
                translation = None
                if mode == 'translate' and result.text.strip():
                    from ..translate import translate_text
                    translation = translate_text(result.text, config, allow_cloud=False)
                result.elapsed_ms = round((time.perf_counter() - started) * 1000)
                connection.send(('ok', (result, translation)))
            except Exception as exc:
                connection.send(('error', str(exc)))
    except (EOFError, BrokenPipeError, OSError):
        pass
    finally:
        connection.close()


class RecognitionCancelled(Exception):
    pass


class RecognitionRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._process = None
        self._connection = None

    def _stop(self):
        if self._process is not None:
            if self._process.is_alive():
                self._process.terminate()
            self._process.join(timeout=1)
            if self._process.is_alive():
                self._process.kill()
                self._process.join(timeout=1)
            self._process.close()
        if self._connection is not None:
            self._connection.close()
        self._process = self._connection = None

    def run(self, image, mode, config, cancel, timeout=60):
        while not self._lock.acquire(timeout=0.05):
            if cancel.is_set():
                raise RecognitionCancelled()
        try:
            if cancel.is_set():
                raise RecognitionCancelled()
            if self._process is None or not self._process.is_alive():
                self._stop()
                ctx = mp.get_context('spawn')
                self._connection, child = ctx.Pipe()
                self._process = ctx.Process(target=_serve, args=(child,), daemon=True)
                self._process.start()
                child.close()
            self._connection.send((image, mode, config))
            deadline = time.monotonic() + timeout
            while True:
                if cancel.is_set():
                    self._stop()
                    raise RecognitionCancelled()
                if time.monotonic() >= deadline:
                    self._stop()
                    raise TimeoutError('识别超时，已停止任务。可缩小图片后重试。')
                if self._connection.poll(0.05):
                    status, payload = self._connection.recv()
                    if status == 'error':
                        raise RuntimeError(payload)
                    return payload
                if not self._process.is_alive():
                    self._stop()
                    raise RuntimeError('识别进程意外结束，请重试。截图功能仍可使用。')
        except TimeoutError:
            raise
        except (EOFError, BrokenPipeError, OSError) as exc:
            self._stop()
            raise RuntimeError('识别进程连接中断，请重试。') from exc
        finally:
            self._lock.release()

    def close(self):
        with self._lock:
            self._stop()
