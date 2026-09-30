"""Offline installer and detached process tests; no host packages or user data."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import yaml

from deploy import server_manager as manager


ROOT = Path(__file__).resolve().parents[2]
HEALTH_SERVER = '''import argparse, json
from http.server import BaseHTTPRequestHandler, HTTPServer
parser = argparse.ArgumentParser()
parser.add_argument("--host")
parser.add_argument("--port", type=int)
args, _ = parser.parse_known_args()
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode())
HTTPServer((args.host, args.port), Handler).serve_forever()
'''


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="paper server ")
        self.addCleanup(self.directory.cleanup)
        self.project = Path(self.directory.name)
        (self.project / "config").mkdir()
        shutil.copy(ROOT / "config/config.example.yaml", self.project / "config/config.example.yaml")
        self.addCleanup(lambda: manager.stop(self.project, timeout=1))

    def prepare(self):
        with contextlib.redirect_stdout(io.StringIO()):
            manager.prepare(self.project)

    def test_new_config_credentials_and_permissions(self):
        self.prepare()
        env = manager.env_values(self.project / ".env")
        self.assertGreaterEqual(len(env["PAPER_TRANSLATOR_PASSWORD"]), 24)
        self.assertEqual(env["TRANSLATION_API_KEY"], "")
        self.assertEqual(env["PT_MAX_TRANSLATION_THREADS"], "4")
        self.assertEqual(env["PT_TRANSLATION_BATCH_PAGES"], "5")
        self.assertEqual((self.project / ".env").stat().st_mode & 0o777, 0o600)

    def test_keep_resource_config_preserves_explicit_low_limits(self):
        config = {"resources": manager.OLD_LIMITS, "translation": {"thread": 1}}
        (self.project / "config/config.yaml").write_text(yaml.safe_dump(config))
        with patch.dict(os.environ, {"PT_KEEP_RESOURCE_CONFIG": "1"}):
            self.prepare()
        self.assertEqual(manager.env_values(self.project / ".env")["PT_MAX_TRANSLATION_THREADS"], "1")
        saved = yaml.safe_load((self.project / "config/config.yaml").read_text())
        self.assertEqual(saved["translation"]["thread"], 1)

    def test_old_defaults_upgraded_once_and_credentials_port_custom_values_kept(self):
        config = {"server": {"port": 9011}, "translation": {"thread": 1},
                  "auth": {"secret_key": "keep-signing-key"},
                  "resources": {**manager.OLD_LIMITS, "max_pdf_pages": 432}}
        (self.project / "config/config.yaml").write_text(yaml.safe_dump(config))
        (self.project / ".env").write_text("PAPER_TRANSLATOR_PASSWORD='literal$(value)'\nTRANSLATION_API_KEY=test-key\nPT_MAX_TRANSLATION_THREADS=1\n")
        self.prepare()
        env = manager.env_values(self.project / ".env")
        config = yaml.safe_load((self.project / "config/config.yaml").read_text())
        self.assertEqual(env["PAPER_TRANSLATOR_PASSWORD"], "literal$(value)")
        self.assertEqual(env["TRANSLATION_API_KEY"], "test-key")
        self.assertEqual(env["PT_MAX_TRANSLATION_THREADS"], "4")
        self.assertEqual(env["PT_MAX_PDF_PAGES"], "432")
        self.assertEqual(config["server"]["port"], 9011)
        self.assertEqual(config["auth"]["secret_key"], "keep-signing-key")
        backup = self.project / "data/run/env-before-bootstrap"
        self.assertIn("PT_MAX_TRANSLATION_THREADS=1", backup.read_text())
        text = (self.project / ".env").read_text().replace("PT_MAX_TRANSLATION_THREADS=4", "PT_MAX_TRANSLATION_THREADS=1")
        (self.project / ".env").write_text(text)
        self.prepare()
        self.assertEqual(manager.env_values(self.project / ".env")["PT_MAX_TRANSLATION_THREADS"], "1")

    def test_frontend_fingerprint_tracks_sources_but_ignores_build_and_dependencies(self):
        frontend = self.project / "frontend"
        (frontend / "src").mkdir(parents=True)
        (frontend / "src/app.tsx").write_text("initial")
        (frontend / "package-lock.json").write_text("{}")
        initial = manager.frontend_hash(self.project)
        (frontend / "dist").mkdir()
        (frontend / "dist/index.html").write_text("built")
        self.assertEqual(manager.frontend_hash(self.project), initial)
        (frontend / "src/app.tsx").write_text("updated")
        self.assertNotEqual(manager.frontend_hash(self.project), initial)

    def configure_server(self, source=HEALTH_SERVER):
        self.prepare()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        config = yaml.safe_load((self.project / "config/config.yaml").read_text())
        config["server"] = {"host": "127.0.0.1", "port": port}
        (self.project / "config/config.yaml").write_text(yaml.safe_dump(config))
        python = self.project / ".venv-server/bin/python"
        python.parent.mkdir(parents=True, exist_ok=True)
        python.symlink_to(sys.executable)
        (self.project / "start.py").write_text(source)
        return port

    def test_background_start_health_duplicate_and_stop(self):
        self.configure_server()
        # The launcher exits before we inspect the service: it must survive.
        launched = subprocess.run([sys.executable, str(ROOT / "deploy/server_manager.py"),
                                   "start", "--project", str(self.project)],
                                  capture_output=True, text=True, timeout=10)
        self.assertEqual(launched.returncode, 0, launched.stdout + launched.stderr)
        first = manager.running_record(self.project)
        self.assertIsNotNone(first)
        self.assertEqual(os.getsid(first["pid"]), first["pid"])
        manager.start(self.project, timeout=5)
        self.assertEqual(manager.running_record(self.project)["pid"], first["pid"])
        manager.stop(self.project, timeout=3)
        self.assertIsNone(manager.running_record(self.project))
        self.assertFalse((self.project / "data/run/server.json").exists())

    def test_startup_failure_and_timeout_remove_process_and_record(self):
        for source in ("raise SystemExit(7)", "import time; time.sleep(30)"):
            with self.subTest(source=source):
                python = self.project / ".venv-server/bin/python"
                if python.exists():
                    python.unlink()
                self.configure_server(source)
                with self.assertRaises(RuntimeError):
                    manager.start(self.project, timeout=1)
                self.assertIsNone(manager.running_record(self.project))
                self.assertFalse((self.project / "data/run/server.json").exists())

    def test_occupied_port_is_rejected_without_launching_service(self):
        port = self.configure_server()
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", port))
            with self.assertRaisesRegex(RuntimeError, "端口是否被占用"):
                manager.start(self.project, timeout=1)
        self.assertFalse((self.project / "data/run/server.json").exists())

    def test_stale_record_never_signals_an_unrelated_process(self):
        state = self.project / "data/run/server.json"
        manager.write_atomic(state, json.dumps({"pid": os.getpid(), "starttime": manager.process_identity(os.getpid()), "port": 8080}))
        self.assertIsNone(manager.running_record(self.project))
        manager.stop(self.project)
        self.assertFalse(state.exists())

    def configure_shell_bootstrap(self):
        shutil.copy(ROOT / "start.sh", self.project / "start.sh")
        (self.project / "deploy").mkdir()
        shutil.copy(ROOT / "deploy/server_manager.py", self.project / "deploy/server_manager.py")
        (self.project / "backend").mkdir()
        (self.project / "backend/requirements.txt").write_text("test-requirement\n")
        frontend = self.project / "frontend"
        (frontend / "src").mkdir(parents=True)
        (frontend / "src/app.tsx").write_text("initial")
        (frontend / "package-lock.json").write_text("{}")
        bin_dir = self.project / "mock-bin"
        bin_dir.mkdir()
        python = self.project / ".venv-server/bin/python"
        python.parent.mkdir(parents=True)
        # Simulate a Python 3.11 installation; delegate helper execution to the
        # test interpreter. No real installer or package manager is invoked.
        python.write_text('''#!/bin/bash
if [[ ${1:-} == -c ]]; then
    if [[ $2 == *TextTranslateRequest* && -f "$PT_TEST_SDK_BROKEN" ]]; then
        echo "ImportError: cannot import name 'TextTranslateRequest'" >&2
        exit 1
    fi
    exit 0
fi
exec ''' + json.dumps(sys.executable) + ' "$@"\n')
        commands = {
            "uv": '''#!/bin/bash
printf "%s\\n" "$*" >> "$PT_TEST_CALLS"
if [[ $1 == pip && $2 == install && ${PT_TEST_REPAIR_SDK:-0} == 1 ]]; then
    rm -f "$PT_TEST_SDK_BROKEN"
fi
''',
            "node": "#!/bin/bash\nexit 0\n",
            "npm": '#!/bin/bash\nprintf "npm %s\\n" "$*" >> "$PT_TEST_CALLS"\nif [[ $1 == run ]]; then mkdir -p dist; echo built >dist/index.html; fi\n',
        }
        python.chmod(0o755)
        for name, text in commands.items():
            path = bin_dir / name
            path.write_text(text)
            path.chmod(0o755)
        calls = self.project / "calls.txt"
        env = {**os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
               "PT_SKIP_SYSTEM_PACKAGES": "1", "PT_TEST_CALLS": str(calls),
               "PT_TEST_SDK_BROKEN": str(self.project / "broken-sdk")}
        return calls, env

    def run_shell_install(self, env):
        return subprocess.run(["bash", str(self.project / "start.sh"), "install"], env=env,
                              capture_output=True, text=True, timeout=15)

    def test_shell_bootstrap_uses_uv_and_reuses_unchanged_artifacts(self):
        calls, env = self.configure_shell_bootstrap()
        for _ in range(2):
            result = self.run_shell_install(env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        recorded = calls.read_text().splitlines()
        self.assertEqual(sum(line.startswith("pip install --no-cache --python") for line in recorded), 1)
        self.assertEqual(sum(line == "npm run build" for line in recorded), 1)
        (self.project / "frontend/src/app.tsx").write_text("changed")
        result = self.run_shell_install(env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls.read_text().count("npm run build"), 2)

    def test_cached_dependencies_with_broken_sdk_are_reinstalled(self):
        calls, env = self.configure_shell_bootstrap()
        result = self.run_shell_install(env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        Path(env["PT_TEST_SDK_BROKEN"]).touch()
        result = self.run_shell_install({**env, "PT_TEST_REPAIR_SDK": "1"})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls.read_text().count("pip install --no-cache --python"), 2)
        self.assertEqual(calls.read_text().count("npm run build"), 1)
        self.assertFalse(Path(env["PT_TEST_SDK_BROKEN"]).exists())

    def test_metadata_check_passing_does_not_hide_broken_sdk_after_install(self):
        calls, env = self.configure_shell_bootstrap()
        Path(env["PT_TEST_SDK_BROKEN"]).touch()
        result = self.run_shell_install(env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TextTranslateRequest", result.stderr)
        self.assertIn("翻译依赖导入检查失败", result.stderr)
        self.assertIn("pip check --python", calls.read_text())
        self.assertNotIn("npm run build", calls.read_text())
        self.assertFalse((self.project / "data/run/backend-deps.sha256").exists())
        self.assertFalse((self.project / "data/run/server.json").exists())


if __name__ == "__main__":
    unittest.main()
