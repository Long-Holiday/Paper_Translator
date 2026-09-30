from typing import Dict, Any
from fastapi import APIRouter
from backend.app.config import load_config, save_config

router = APIRouter(prefix="/translation", tags=["translation"])


@router.get("/config")
def get_translation_config():
    """获取当前的翻译设置（脱敏展示）"""
    cfg = load_config()
    tr_cfg = dict(cfg.get("translation", {}))
    # 对 API Key 进行安全掩码展示
    key = tr_cfg.get("api_key", "")
    if key and len(key) > 8:
        tr_cfg["api_key_masked"] = f"{key[:4]}...{key[-4:]}"
    elif key:
        tr_cfg["api_key_masked"] = "******"
    else:
        tr_cfg["api_key_masked"] = ""
    return tr_cfg


@router.put("/config")
def update_translation_config(payload: Dict[str, Any]):
    """更新翻译配置"""
    cfg = load_config()
    if "translation" not in cfg:
        cfg["translation"] = {}

    for k, v in payload.items():
        if k == "api_key" and not v:
            # 如果传入空则不覆盖已有的 key
            continue
        cfg["translation"][k] = v

    save_config(cfg)
    return {"status": "success", "message": "配置已更新"}
