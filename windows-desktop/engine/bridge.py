"""One translation request on stdin; JSON Lines events on stdout; logs on stderr."""
import argparse
import contextlib
import ctypes
import json
import multiprocessing
import os
import sys
import threading
import time
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import engine  # noqa: F401; sanitize proxy variables before dependency imports


def watch_parent(parent_pid: int):
    if not parent_pid:
        return
    if os.name == "nt":
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, parent_pid)  # SYNCHRONIZE
        if not handle:
            os._exit(1)
        while kernel.WaitForSingleObject(handle, 1000) == 0x00000102:
            pass
        kernel.CloseHandle(handle)
        os._exit(1)
    else:
        while True:
            time.sleep(1)
            try:
                os.kill(parent_pid, 0)
            except ProcessLookupError:
                os._exit(1)
            except PermissionError:
                pass


def run(input_stream, event_stream, translator=None) -> int:
    def emit(event):
        event_stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        event_stream.flush()

    config = {}
    try:
        line = input_stream.readline(1024 * 1024 + 1)
        if len(line) > 1024 * 1024:
            raise ValueError("翻译请求过大")
        request = json.loads(line)
        config = request.get("config", {})
        if not isinstance(config, dict):
            raise ValueError("翻译设置格式不正确")
        source = Path(request["source"]).resolve()
        output = Path(request["output_dir"]).resolve()
        if not source.is_file():
            raise ValueError("原文 PDF 不存在")
        parent_pid = int(request.get("parent_pid", 0))
        if parent_pid:
            threading.Thread(target=watch_parent, args=(parent_pid,), daemon=True).start()
        # pdf2zh/babeldoc and some model loaders print during import. Reserve
        # stdout exclusively for protocol messages, including import-time output.
        with contextlib.redirect_stdout(sys.stderr):
            if translator is None:
                from engine.translation_service import TranslationService
                translator = TranslationService().translate
            result = translator(
                source_pdf=source, output_dir=output, config=config,
                progress_callback=lambda value, message="": emit({
                    "type": "progress", "progress": min(99, value), "message": message,
                }),
            )
        emit({"type": "result", "path": str(result)})
        return 0
    except Exception as exc:
        import traceback
        traceback.print_exc(file=sys.stderr)
        message = str(exc)
        key = config.get("api_key", "") if isinstance(config, dict) else ""
        if key:
            message = message.replace(key, "***")
        emit({"type": "error", "message": message})
        return 1


def main():
    parser = argparse.ArgumentParser(description="PDFMathTranslate desktop engine")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if args.probe:
        with contextlib.redirect_stdout(sys.stderr):
            import fitz
            import pdf2zh
            import onnxruntime
        print(json.dumps({"type": "ready", "pdf2zh": pdf2zh.__version__,
                          "pymupdf": fitz.VersionBind, "onnxruntime": onnxruntime.__version__}))
        return 0
    return run(sys.stdin, sys.stdout)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
