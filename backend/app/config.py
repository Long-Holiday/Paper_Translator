import os
import sys
from pathlib import Path
from typing import Any, Dict
import yaml

# 1. 规避 WSL 环境下 httpx/ollama 的 IPv6 [::1] 解析崩溃问题
for _key in ["NO_PROXY", "no_proxy"]:
    if _key in os.environ and "[::1]" in os.environ[_key]:
        _parts = [p.strip() for p in os.environ[_key].split(",") if p.strip() and p.strip() != "[::1]"]
        os.environ[_key] = ",".join(_parts)

# 2. 基础路径配置
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PAPERS_DIR = DATA_DIR / "papers"
DB_PATH = DATA_DIR / "app.db"
CONFIG_FILE = BASE_DIR / "config" / "config.yaml"
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
ENV_FILE = BASE_DIR / ".env"

# 确保必要目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
PAPERS_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "cache").mkdir(parents=True, exist_ok=True)
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_env_file() -> None:
    """
    轻量原生加载根目录 .env 文件，将敏感凭证注入 os.environ
    """
    if not ENV_FILE.exists():
        return

    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                # 去除外层引号
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                # 只有系统环境未设置时才用 .env 填充，允许环境变量更高优先级
                if k not in os.environ:
                    os.environ[k] = v
    except Exception as e:
        print(f"[Config] 读取 .env 失败: {e}", file=sys.stderr)


def update_env_file(key: str, value: str) -> None:
    """
    将敏感密钥安全更新回 .env 文件，防止写入 config.yaml 导致 git 泄露
    """
    os.environ[key] = value

    lines = []
    found = False
    if ENV_FILE.exists():
        try:
            with open(ENV_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = []

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k == key:
                new_lines.append(f"{key}={value}\n")
                found = True
                continue
        new_lines.append(line)

    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{key}={value}\n")

    try:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        print(f"[Config] 写入 .env 失败: {e}", file=sys.stderr)


# 启动时第一时间加载 .env
load_env_file()


def get_default_config() -> Dict[str, Any]:
    return {
        "translation": {
            "source_language": "en",
            "target_language": "zh",
            "service": "deepseek",
            "model": "deepseek-chat",
            "api_key": "",
            "base_url": "https://api.deepseek.com",
            "thread": 4,
            "preserve_layout": True,
        },
        "server": {
            "host": "0.0.0.0",
            "port": 8080,
        },
        "auth": {
            "enabled": True,
            "secret_key": "",
        },
        "resources": {
            "cpu_threads": 1,
            "max_translation_threads": 4,
            "translation_batch_pages": 5,
            "max_pending_tasks": 10,
            "max_upload_mb": 100,
            "max_pdf_pages": 1000,
            "translation_timeout_seconds": 7200,
        },
    }


def load_config() -> Dict[str, Any]:
    default_cfg = get_default_config()
    if not CONFIG_FILE.exists():
        save_config(default_cfg)
        cfg = default_cfg
    else:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
                for section in ["translation", "server", "auth", "resources"]:
                    if section not in cfg:
                        cfg[section] = default_cfg[section]
                    else:
                        for k, v in default_cfg[section].items():
                            if k not in cfg[section]:
                                cfg[section][k] = v
        except Exception as e:
            print(f"[Config] 加载配置文件失败，使用默认配置: {e}", file=sys.stderr)
            cfg = default_cfg

    # 关键安全保证：api_key 优先从环境变量/.env中读取填充，运行时无缝使用
    env_api_key = os.environ.get("TRANSLATION_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if env_api_key:
        cfg["translation"]["api_key"] = env_api_key

    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    """
    保存常规配置到 config.yaml。
    若包含 api_key，则安全重定向保存到 .env，并在 yaml 中存为空，彻底防止上传远程仓库泄露。
    """
    api_key_to_save = cfg.get("translation", {}).get("api_key", "")
    if api_key_to_save:
        update_env_file("TRANSLATION_API_KEY", api_key_to_save)

    # 制作纯净的配置副本写入 config.yaml，不带任何私密 key
    clean_cfg = {}
    for section, values in cfg.items():
        if isinstance(values, dict):
            clean_cfg[section] = dict(values)
        else:
            clean_cfg[section] = values

    if "translation" in clean_cfg and "api_key" in clean_cfg["translation"]:
        clean_cfg["translation"]["api_key"] = ""

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(clean_cfg, f, allow_unicode=True, sort_keys=False)
