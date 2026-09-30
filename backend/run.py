import sys
from pathlib import Path
import uvicorn

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config import load_config

if __name__ == "__main__":
    cfg = load_config()
    server_cfg = cfg.get("server", {})
    host = server_cfg.get("host", "0.0.0.0")
    port = int(server_cfg.get("port", 8000))

    print(f"[*] 启动 Paper Translator 后端服务在 http://127.0.0.1:{port}")
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False)
