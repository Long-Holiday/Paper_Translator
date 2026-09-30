import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    with TemporaryDirectory(prefix="paper-qt-engine-tests-") as tmp:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(root / "tests"), "-v"], cwd=tmp, env=env)
        raise SystemExit(result.returncode)
