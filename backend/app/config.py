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

# 确保必要目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
PAPERS_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)


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
            "port": 8000,
        },
    }


def load_config() -> Dict[str, Any]:
    default_cfg = get_default_config()
    if not CONFIG_FILE.exists():
        save_config(default_cfg)
        return default_cfg

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            # 简单合并默认值
            for section in ["translation", "server"]:
                if section not in cfg:
                    cfg[section] = default_cfg[section]
                else:
                    for k, v in default_cfg[section].items():
                        if k not in cfg[section]:
                            cfg[section][k] = v
            return cfg
    except Exception as e:
        print(f"[Config] 加载配置文件失败，使用默认配置: {e}", file=sys.stderr)
        return default_cfg


def save_config(cfg: Dict[str, Any]) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
