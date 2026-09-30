"""External process fixture for C++ protocol tests; never used by the product."""
import json
import shutil
import sys
import time
from pathlib import Path

request = json.loads(sys.stdin.readline())
mode = sys.argv[1]
if mode == "invalid":
    print("not JSON", flush=True)
    time.sleep(60)
elif mode == "hang":
    print(json.dumps({"type": "progress", "progress": 50}), flush=True)
    time.sleep(60)
elif mode == "fail":
    print(json.dumps({"type": "error", "message": "test engine failure"}), flush=True)
    raise SystemExit(1)
elif mode == "missing":
    raise SystemExit(0)
else:
    output = Path(request["output_dir"]) / "translated.pdf"
    shutil.copyfile(request["source"], output)
    # Deliberately fragment a UTF-8 JSON event across process reads.
    event = (json.dumps({"type": "progress", "progress": 100, "message": "已完成排版"}, ensure_ascii=False) + "\n").encode()
    sys.stdout.buffer.write(event[:13]); sys.stdout.buffer.flush(); time.sleep(0.03)
    sys.stdout.buffer.write(event[13:]); sys.stdout.buffer.flush()
    path = request["source"] if mode == "wrong-path" else str(output)
    print(json.dumps({"type": "result", "path": path}), flush=True)
