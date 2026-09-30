"""PDF compatibility regressions; no translation API calls or user-data writes."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

import fitz

from backend.app.services.pdf_compat import (
    normalize_pdf_numbers, pdf2zh_number_compatibility, validate_pdf,
)
from backend.app.services.translation_service import TranslationService
from backend.app.resources import ResourceLimits


BAD_CONTENT = b"q 1 0 1.4592924416655231e-08 1 0 0 cm 0 0 10 10 re f Q"
GOOD_CONTENT = normalize_pdf_numbers(BAD_CONTENT)


def write_pdf(path, content=GOOD_CONTENT):
    with fitz.open() as doc:
        page = doc.new_page()
        xref = doc.get_new_xref()
        doc.update_object(xref, "<<>>")
        doc.update_stream(xref, content)
        page.set_contents(xref)
        doc.save(path)


def import_test_engine():
    # Cache initialization writes to the user's home directory on import.
    # These tests exercise PDF generation only, so isolate that unused service.
    previous = sys.modules.get("pdf2zh.cache")
    sys.modules["pdf2zh.cache"] = SimpleNamespace(TranslationCache=Mock())
    try:
        from pdf2zh import high_level
    finally:
        if previous is None:
            sys.modules.pop("pdf2zh.cache", None)
        else:
            sys.modules["pdf2zh.cache"] = previous
    return high_level


class NumberTests(unittest.TestCase):
    def test_preserves_precision_and_handles_exponents(self):
        self.assertEqual(
            normalize_pdf_numbers(b"1.4592924416655231e-08 -2E+3 +.5e-2 1e-20"),
            b"0.000000014592924416655231 -2000 0.005 0.00000000000000000001",
        )

    def test_preserves_strings_names_hex_comments_and_keywords(self):
        opaque = b"(1e-8 (nested) \\( 2e-8) /1e-8 <1e08> % 1e-8\n /Tag1e-8"
        self.assertEqual(normalize_pdf_numbers(opaque + b" [1e-8] << /N 2e-8 >>"),
                         opaque + b" [0.00000001] << /N 0.00000002 >>")
        self.assertEqual(normalize_pdf_numbers(b"foo1e-8 1e-8foo"), b"foo1e-8 1e-8foo")
        utf8 = "(中文 1e-8) 1e-8".encode()
        self.assertEqual(normalize_pdf_numbers(utf8), "(中文 1e-8) 0.00000001".encode())

    def test_refuses_unsafe_inline_image_or_unbounded_number(self):
        for content in (b"BI /W 1 ID 1e-8 EI", b"1e-9999999"):
            with self.assertRaises(ValueError):
                normalize_pdf_numbers(content)

    def test_hook_restores_dependency_on_success_and_failure(self):
        original = Mock(return_value={1: BAD_CONTENT.decode(), 2: ""})
        module = SimpleNamespace(translate_patch=original)
        with pdf2zh_number_compatibility(module):
            self.assertEqual(module.translate_patch("argument"), {1: GOOD_CONTENT.decode(), 2: ""})
        self.assertIs(module.translate_patch, original)
        original.assert_called_once_with("argument")
        with self.assertRaises(RuntimeError), pdf2zh_number_compatibility(module):
            raise RuntimeError("engine failed")
        self.assertIs(module.translate_patch, original)


class PdfTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pdf = Path(self.temp.name) / "translated.pdf"

    def test_detects_syntax_diagnostics_even_when_render_does_not_raise(self):
        write_pdf(self.pdf, BAD_CONTENT)
        with self.assertRaisesRegex(ValueError, "第 1 页渲染校验失败"):
            validate_pdf(self.pdf)
        write_pdf(self.pdf)
        self.assertEqual(validate_pdf(self.pdf, expected_pages=1), 1)
        with self.assertRaisesRegex(ValueError, "页数校验失败"):
            validate_pdf(self.pdf, expected_pages=2)

    def test_real_pdf2zh_pipeline_normalizes_before_font_subsetting(self):
        high_level = import_test_engine()

        write_pdf(self.pdf)
        def fake_patch(*args, **kwargs):
            doc = kwargs["doc_zh"]
            return {doc[0].get_contents()[0]: BAD_CONTENT.decode()}

        original_subset = fitz.Document.subset_fonts
        subset_calls = []
        def checked_subset(doc, *args, **kwargs):
            for xref in range(1, doc.xref_length()):
                if doc.xref_is_stream(xref):
                    self.assertNotIn(b"1.4592924416655231e", doc.xref_stream(xref))
            subset_calls.append(len(doc))
            return original_subset(doc, *args, **kwargs)

        with patch.object(high_level, "translate_patch", fake_patch), \
                patch.object(high_level, "download_remote_fonts", return_value=None), \
                patch.object(high_level, "NOTO_NAME", "helv"), \
                patch.object(fitz.Document, "subset_fonts", checked_subset):
            with pdf2zh_number_compatibility(high_level):
                mono, dual = high_level.translate_stream(self.pdf.read_bytes(), lang_out="zh")
            self.assertIs(high_level.translate_patch, fake_patch)
        self.assertEqual(subset_calls, [1, 2])
        self.pdf.write_bytes(mono)
        self.assertEqual(validate_pdf(self.pdf, expected_pages=1), 1)
        self.pdf.write_bytes(dual)
        self.assertEqual(validate_pdf(self.pdf, expected_pages=2), 2)


class TranslationTests(unittest.TestCase):
    def test_batch_sizes_order_thread_limit_metadata_and_cleanup(self):
        high_level = import_test_engine()
        with TemporaryDirectory() as directory:
            output = Path(directory)
            source = output / "original.pdf"
            with fitz.open() as doc:
                for number in range(5):
                    doc.new_page().insert_text((50, 50), f"Page {number + 1}")
                doc.set_metadata({"title": "Batch test"})
                doc.set_toc([[1, "Chapter", 3]])
                doc.save(source)
            original_bytes = source.read_bytes()
            batches = []

            def translate_batch(**kwargs):
                self.assertEqual(kwargs["thread"], 1)
                mono = Path(kwargs["output"]) / "input-mono.pdf"
                with fitz.open(kwargs["files"][0]) as doc:
                    batches.append(len(doc))
                    doc.save(mono)
                return [(str(mono), str(mono.parent / "missing-dual.pdf"))]

            with patch("backend.app.services.translation_service.load_config",
                       return_value={"translation": {"service": "google", "model": "", "thread": 16}}), \
                    patch("backend.app.services.translation_service.get_resource_limits",
                          return_value=ResourceLimits(translation_batch_pages=2, max_translation_threads=1)), \
                    patch.object(TranslationService, "get_layout_model", return_value=object()), \
                    patch.object(high_level, "translate", side_effect=translate_batch):
                final = TranslationService().translate(source, output)
            self.assertEqual(batches, [2, 2, 1])
            self.assertEqual(source.read_bytes(), original_bytes)
            with fitz.open(final) as doc:
                self.assertEqual(len(doc), 5)
                self.assertEqual(doc.metadata["title"], "Batch test")
                self.assertEqual(doc.get_toc(), [[1, "Chapter", 3]])
                self.assertEqual([page.get_text().strip() for page in doc], [f"Page {n}" for n in range(1, 6)])
            self.assertEqual(sorted(p.name for p in output.iterdir()), ["original.pdf", "translated.pdf"])

    def test_only_validated_output_is_published_and_failed_runs_keep_previous_pdf(self):
        high_level = import_test_engine()

        with TemporaryDirectory() as directory:
            output = Path(directory)
            source = output / "original.pdf"
            final = output / "translated.pdf"
            write_pdf(source)
            write_pdf(final)
            existing = final.read_bytes()
            progress = Mock()
            config = {"translation": {"service": "google", "model": ""}}

            def fake_translate(**kwargs):
                mono = Path(kwargs["output"]) / "original-mono.pdf"
                write_pdf(mono, BAD_CONTENT)
                return [(str(mono), str(mono.parent / "missing-dual.pdf"))]

            with patch("backend.app.services.translation_service.load_config", return_value=config), \
                    patch.object(TranslationService, "get_layout_model", return_value=object()), \
                    patch.object(high_level, "translate", side_effect=fake_translate):
                with self.assertRaisesRegex(RuntimeError, "渲染校验失败"):
                    TranslationService().translate(source, output, progress)
                self.assertEqual(final.read_bytes(), existing)
                self.assertNotIn(100, [call.args[0] for call in progress.call_args_list])
                self.assertEqual(list(output.glob(".translation-*")), [])

            def valid_translate(**kwargs):
                mono = Path(kwargs["output"]) / "original-mono.pdf"
                write_pdf(mono)
                return [(str(mono), str(mono.parent / "missing-dual.pdf"))]

            with patch("backend.app.services.translation_service.load_config", return_value=config), \
                    patch.object(TranslationService, "get_layout_model", return_value=object()), \
                    patch.object(high_level, "translate", side_effect=valid_translate):
                self.assertEqual(TranslationService().translate(source, output, progress), final)
            self.assertEqual(validate_pdf(final, expected_pages=1), 1)
            self.assertEqual(sorted(p.name for p in output.iterdir()), ["original.pdf", "translated.pdf"])
            self.assertEqual(progress.call_args.args[0], 100)


if __name__ == "__main__":
    unittest.main()
