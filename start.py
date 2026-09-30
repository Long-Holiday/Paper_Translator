import os
import sys
import argparse
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


def should_open_browser(no_browser_arg: bool) -> bool:
    """判断是否应当尝试打开本地浏览器"""
    if no_browser_arg:
        return False
    if os.environ.get("NO_BROWSER") in ("1", "true", "True"):
        return False

    # 检测是否为典型的 Linux 无桌面环境（无 DISPLAY 且非 WSL）
    is_wsl = "microsoft-standard" in os.uname().release.lower() or "wsl" in os.uname().release.lower()
    if not is_wsl and sys.platform.startswith("linux"):
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            return False

    return True


def open_browser_wsl_compatible(url: str):
    """自适应 WSL、Linux、macOS、Windows 的浏览器打开逻辑"""
    time.sleep(1.2)
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

    try:
        webbrowser.open(url)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Paper Translator 启动程序")
    parser.add_argument("--host", type=str, default=None, help="监听地址 (如 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None, help="监听端口 (如 8080)")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器 (服务器环境推荐)")
    parser.add_argument("--skip-frontend-build", action="store_true", help="使用预构建前端，缺失时直接报错")
    args = parser.parse_args()

    cfg = load_config()
    server_cfg = cfg.get("server", {})
    auth_cfg = cfg.get("auth", {})

    host = args.host or server_cfg.get("host", "0.0.0.0")
    port = args.port or int(server_cfg.get("port", 8080))
    local_url = f"http://127.0.0.1:{port}"

    print("=" * 60)
    print("  Paper Translator - 本地/服务器 Web 论文翻译阅读平台")
    print("=" * 60)

    # 检查前端构建
    if args.skip_frontend_build:
        if not (FRONTEND_DIST / "index.html").is_file():
            parser.error("缺少 frontend/dist/index.html，请在构建机器执行 npm ci && npm run build 后上传 dist")
    else:
        check_and_build_frontend()

    print(f"\n[*] 服务正在启动中...")
    print(f"[*] 本地访问地址: {local_url}")
    print(f"[*] 服务器/局域网访问: http://{host}:{port}")

    if auth_cfg.get("enabled", True):
        env_pwd = os.environ.get("PAPER_TRANSLATOR_PASSWORD") or os.environ.get("AUTH_PASSWORD")
        if env_pwd:
            print("[*] 🔒 访问认证: 已启用（密码已从 .env / 环境变量加载）")
        else:
            print("[!] 🔒 访问认证: 已启用（未在 .env 中设置，使用初始临时密码: admin123）")
            print("[!] 建议在 .env 文件中设置: PAPER_TRANSLATOR_PASSWORD=\"你的自用密码\"")
    else:
        print("[!] 提示: 访问认证已关闭")

    env_api_key = os.environ.get("TRANSLATION_API_KEY")
    if env_api_key:
        print("[*] 🔑 翻译密钥: 已从 .env 文件加载成功")
    else:
        print("[!] 🔑 翻译密钥: 未在 .env 中检测到 TRANSLATION_API_KEY，请在 .env 中配置")

    print("[*] 按 Ctrl+C 可停止运行\n")

    if should_open_browser(args.no_browser):
        import threading
        threading.Thread(target=open_browser_wsl_compatible, args=(local_url,), daemon=True).start()

    import uvicorn
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
