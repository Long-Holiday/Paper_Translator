"""Repair pdf2zh's scientific-notation operands before MuPDF reads them."""

from contextlib import contextmanager
from decimal import Decimal
from functools import wraps
from pathlib import Path
import re
import threading

import fitz


_PDF_LOCK = threading.RLock()
_EXPONENT = re.compile(rb"[+-]?(?:\d+\.?\d*|\.\d+)[eE][+-]?\d+")
_DELIMITERS = b"\x00\t\n\x0c\r ()<>[]{}/%"


def normalize_pdf_numbers(content: bytes) -> bytes:
    """Convert numeric operands, preserving names, strings, hex and comments.

    Generated pdf2zh patches contain no inline images. Refuse to rewrite raw
    inline-image data rather than risk changing image bytes during a repair.
    """
    if not _EXPONENT.search(content):
        return content
    parts = []
    start = index = 0
    while index < len(content):
        char = content[index]
        if char == ord("%"):
            while index < len(content) and content[index] not in b"\r\n":
                index += 1
        elif char == ord("("):
            depth = 1
            index += 1
            while index < len(content) and depth:
                char = content[index]
                if char == ord("\\"):
                    index += 2
                    continue
                if char == ord("("):
                    depth += 1
                elif char == ord(")"):
                    depth -= 1
                index += 1
        elif char == ord("<") and content[index:index + 2] != b"<<":
            end = content.find(b">", index + 1)
            index = len(content) if end < 0 else end + 1
        elif char == ord("/"):
            index += 1
            while index < len(content) and content[index] not in _DELIMITERS:
                index += 1
        elif char in _DELIMITERS:
            # Consume dictionary delimiters together, so the second '<' is
            # not mistaken for the beginning of a hex string.
            index += 2 if content[index:index + 2] in (b"<<", b">>") else 1
        else:
            token_start = index
            while index < len(content) and content[index] not in _DELIMITERS:
                index += 1
            token = content[token_start:index]
            if token == b"BI":
                raise ValueError("PDF 内容流含内联图像，无法安全修复数值格式")
            if _EXPONENT.fullmatch(token):
                value = Decimal(token.decode("ascii"))
                if len(token) > 128 or abs(value.as_tuple().exponent) > 400:
                    raise ValueError("PDF 数值超出可安全修复的范围")
                parts.extend((content[start:token_start], format(value, "f").encode("ascii")))
                start = index
    parts.append(content[start:])
    return b"".join(parts)


@contextmanager
def pdf2zh_number_compatibility(high_level):
    """Normalize object patches before update_stream and font subsetting.

    Keep the shim in project code, and restore the dependency even on failure.
    The lock serializes our uses of the temporary module-level hook.
    """
    with _PDF_LOCK:
        original = high_level.translate_patch

        @wraps(original)
        def normalized_patch(*args, **kwargs):
            patches = original(*args, **kwargs)
            return {
                xref: normalize_pdf_numbers(ops.encode("utf-8")).decode("utf-8")
                for xref, ops in patches.items()
            }

        high_level.translate_patch = normalized_patch
        try:
            yield
        finally:
            high_level.translate_patch = original


def validate_pdf(pdf_path: Path, expected_pages: int | None = None) -> int:
    """Render every page; MuPDF syntax diagnostics do not always raise Python exceptions."""
    with _PDF_LOCK:
        fitz.TOOLS.mupdf_warnings(reset=True)
        with fitz.open(pdf_path) as doc:
            diagnostics = fitz.TOOLS.mupdf_warnings(reset=True)
            if doc.needs_pass or doc.is_repaired or diagnostics:
                raise ValueError(f"PDF 文件结构校验失败: {diagnostics or '文件加密或结构损坏'}")
            if not len(doc) or (expected_pages is not None and len(doc) != expected_pages):
                raise ValueError(f"PDF 页数校验失败: 实际 {len(doc)} 页，预期 {expected_pages} 页")
            for number, page in enumerate(doc, 1):
                page.get_pixmap(matrix=fitz.Matrix(0.25, 0.25))
                diagnostics = fitz.TOOLS.mupdf_warnings(reset=True)
                if diagnostics:
                    raise ValueError(f"PDF 第 {number} 页渲染校验失败: {diagnostics}")
            return len(doc)

