import os
import sys
import subprocess
import shutil
import time
import webbrowser
from pathlib import Path

# 1. 规避 WSL 环境下 httpx/ollama 的 IPv6 [::1] 解析崩溃
for _key in ["NO_PROXY", "no_proxy"]:
    if _key in os.environ and "[::1]" in os.environ[_key]:
        _parts = [p.strip() for p in os.environ[_key].split(",") if p.strip() and p.strip() != "[::1]"]
        os.environ[_key] = ",".join(_parts)

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config import load_config, FRONTEND_DIST


def check_and_build_frontend():
    frontend_dir = project_root / "frontend"
    if not FRONTEND_DIST.exists() or not (FRONTEND_DIST / "index.html").exists():
        print("[*] 检测到前端静态资源未构建，正在自动编译前端...")
        if not (frontend_dir / "node_modules").exists():
            print("[*] 正在安装前端依赖 (npm install)...")
            subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
        print("[*] 正在执行前端打包 (npm run build)...")
        subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True)
        print("[+] 前端编译成功！")
    else:
        print("[+] 前端静态资源已就绪。")


def open_browser_wsl_compatible(url: str):
    """自适应 WSL、Linux、macOS、Windows 的浏览器打开逻辑"""
    time.sleep(1.2)  # 稍微等待后端就绪
    # 1. 检测 WSL
    is_wsl = "microsoft-standard" in os.uname().release.lower() or "wsl" in os.uname().release.lower()
    if is_wsl:
        if shutil.which("wslview"):
            try:
                subprocess.Popen(["wslview", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass
        if shutil.which("powershell.exe"):
            try:
                subprocess.Popen(["powershell.exe", "-c", f"Start-Process '{url}'"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass
        if shutil.which("cmd.exe"):
            try:
                subprocess.Popen(["cmd.exe", "/c", "start", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass

    # 2. 普通系统
    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    cfg = load_config()
    server_cfg = cfg.get("server", {})
    host = server_cfg.get("host", "0.0.0.0")
    port = int(server_cfg.get("port", 8000))
    local_url = f"http://127.0.0.1:{port}"

    print("=" * 60)
    print("  Paper Translator - 本地 Web 论文翻译阅读平台")
    print("=" * 60)

    # 检查前端构建
    check_and_build_frontend()

    print(f"\n[*] 服务已启动，正在浏览器打开: {local_url}")
    print(f"[*] 局域网访问地址: http://{host}:{port}")
    print("[*] 按 Ctrl+C 可停止运行\n")

    # 启动后台线程异步打开浏览器
    import threading
    threading.Thread(target=open_browser_wsl_compatible, args=(local_url,), daemon=True).start()

    # 启动 FastAPI 服务
    import uvicorn
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
