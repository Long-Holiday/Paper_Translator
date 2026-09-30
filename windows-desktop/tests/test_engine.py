import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import fitz

from engine.bridge import run
from engine.translation_service import TranslationService
from engine.pdf_compat import validate_pdf
from tests.test_pdf_compat import import_test_engine, write_pdf, BAD_CONTENT


class BridgeTests(unittest.TestCase):
    def test_stdout_is_json_even_when_engine_prints(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "original.pdf"
            source.write_bytes(b"fixture")
            events, logs = io.StringIO(), io.StringIO()
            def translate(**kwargs):
                print("third party log")
                kwargs["progress_callback"](100, "validated")
                return Path(tmp) / "translated.pdf"
            request = {"source": str(source), "output_dir": tmp, "config": {"service": "google"}}
            with patch("sys.stderr", logs):
                result = run(io.StringIO(json.dumps(request)), events, translate)
            self.assertEqual(result, 0)
            payloads = [json.loads(line) for line in events.getvalue().splitlines()]
            self.assertEqual([p["type"] for p in payloads], ["progress", "result"])
            self.assertEqual(payloads[0]["progress"], 99)
            self.assertIn("third party log", logs.getvalue())

    def test_bad_request_emits_error_and_nonzero_status(self):
        events = io.StringIO()
        with patch("sys.stderr", io.StringIO()):
            self.assertEqual(run(io.StringIO("not JSON"), events), 1)
        self.assertEqual(json.loads(events.getvalue())["type"], "error")

    def test_error_event_does_not_expose_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "original.pdf"
            source.touch()
            request = {"source": str(source), "output_dir": tmp, "config": {"api_key": "secret-fixture"}}
            events = io.StringIO()
            with patch("sys.stderr", io.StringIO()):
                status = run(io.StringIO(json.dumps(request)), events,
                             Mock(side_effect=RuntimeError("failed secret-fixture")))
            self.assertEqual(status, 1)
            self.assertNotIn("secret-fixture", events.getvalue())


class TranslationTests(unittest.TestCase):
    def test_progress_and_configured_endpoint(self):
        high_level = import_test_engine()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "original.pdf"
            write_pdf(source)
            progress = Mock()
            def fake_translate(**kwargs):
                self.assertEqual(kwargs["service"], "openai:deepseek-chat")
                self.assertEqual(kwargs["envs"]["OPENAI_BASE_URL"], "https://example.invalid/v1")
                for n in (1, 2, 2, 3, 4):
                    kwargs["callback"](SimpleNamespace(n=n, total=4))
                self.assertEqual(progress.call_args.args[0], 68)
                output = Path(kwargs["output"]) / "original-mono.pdf"
                write_pdf(output)
                return [(str(output), "")]
            with patch.object(TranslationService, "get_layout_model", return_value=object()), \
                    patch.object(high_level, "translate", side_effect=fake_translate):
                final = TranslationService().translate(source, Path(tmp), progress, config={
                    "service": "deepseek", "model": "deepseek-chat", "api_key": "fixture",
                    "base_url": "https://example.invalid/v1",
                })
            self.assertEqual(validate_pdf(final, 1), 1)
            self.assertEqual([call.args[0] for call in progress.call_args_list], [15, 35, 46, 57, 68, 85, 90, 100])

    def test_invalid_output_preserves_previous_translation(self):
        high_level = import_test_engine()
        with tempfile.TemporaryDirectory() as tmp:
            source, final = Path(tmp) / "original.pdf", Path(tmp) / "translated.pdf"
            write_pdf(source); write_pdf(final)
            previous = final.read_bytes()
            def fake_translate(**kwargs):
                output = Path(kwargs["output"]) / "original-mono.pdf"
                write_pdf(output, BAD_CONTENT)
                return [(str(output), "")]
            with patch.object(TranslationService, "get_layout_model", return_value=object()), \
                    patch.object(high_level, "translate", side_effect=fake_translate), \
                    patch("sys.stderr", io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "校验失败"):
                    TranslationService().translate(source, Path(tmp), config={"service": "google", "model": ""})
            self.assertEqual(final.read_bytes(), previous)
            self.assertEqual(list(Path(tmp).glob(".translation-*")), [])
