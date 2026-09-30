"""One spawned process per task: native model/PDF memory is freed on exit."""

import multiprocessing
import os
import tempfile
import time
from pathlib import Path

from backend.app.resources import get_resource_limits


def _translate_child(connection, source, output, work_dir, cpu_threads):
    # Set before importing NumPy / OpenCV / ONNX, and leave API process untouched.
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = str(cpu_threads)
    try:
        from backend.app.services.translation_service import TranslationService

        def progress(percent, message=""):
            connection.send(("progress", percent, message))

        result = TranslationService().translate(Path(source), Path(output), progress, work_dir=Path(work_dir))
        connection.send(("result", str(result)))
    except Exception as exc:
        connection.send(("error", str(exc)[:4000]))
    finally:
        connection.close()


def _run_process(target, args, progress_callback, timeout_seconds, stop_event=None):
    """Private transport helper; handles timeout, crashes and shutdown alike."""
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=target, args=(writer, *args), daemon=True)
    started = False
    deadline = time.monotonic() + timeout_seconds
    try:
        process.start()
        started = True
        writer.close()
        while True:
            if stop_event is not None and stop_event.is_set():
                raise RuntimeError("服务正在停止，翻译任务已中断，请重新翻译")
            if time.monotonic() >= deadline:
                raise RuntimeError(f"翻译超过 {timeout_seconds} 秒，已终止以释放资源")
            if reader.poll(0.2):
                try:
                    message = reader.recv()
                except EOFError:
                    process.join(timeout=1)
                    raise RuntimeError(f"翻译进程异常退出 (exit code {process.exitcode})，可能内存不足")
                if message[0] == "progress":
                    if progress_callback:
                        progress_callback(message[1], message[2])
                elif message[0] == "result":
                    return Path(message[1])
                elif message[0] == "error":
                    raise RuntimeError(message[1])
            elif not process.is_alive():
                raise RuntimeError(f"翻译进程异常退出 (exit code {process.exitcode})，可能内存不足")
    finally:
        writer.close()
        reader.close()
        if started:
            process.join(timeout=1)
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join()
            process.close()


def translate_isolated(source_pdf, output_dir, progress_callback=None, stop_event=None):
    limits = get_resource_limits()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Parent owns cleanup, including when the child is killed / runs out of memory.
    with tempfile.TemporaryDirectory(prefix=".translation-job-", dir=output_dir) as work_dir:
        return _run_process(
            _translate_child,
            (str(source_pdf), str(output_dir), work_dir, limits.cpu_threads),
            progress_callback,
            limits.translation_timeout_seconds,
            stop_event,
        )
