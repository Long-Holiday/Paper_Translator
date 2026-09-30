import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.app.config import load_config, save_config

security_bearer = HTTPBearer(auto_error=False)

TOKEN_EXPIRE_SECONDS = 30 * 24 * 3600  # 30 天免密有效


def get_auth_password() -> str:
    """从环境变量获取访问密码"""
    return (
        os.environ.get("PAPER_TRANSLATOR_PASSWORD")
        or os.environ.get("AUTH_PASSWORD")
        or "admin123"
    )


def is_auth_enabled() -> bool:
    """是否开启访问密码验证，支持环境变量 AUTH_ENABLED 覆盖"""
    env_enabled = os.environ.get("AUTH_ENABLED")
    if env_enabled is not None:
        return env_enabled.lower() not in ("0", "false", "no", "off")

    cfg = load_config()
    return cfg.get("auth", {}).get("enabled", True)


def get_jwt_secret() -> str:
    """获取 Token 签名密钥"""
    env_secret = os.environ.get("AUTH_SECRET_KEY")
    if env_secret:
        return env_secret

    cfg = load_config()
    auth_cfg = cfg.get("auth", {})
    secret_key = auth_cfg.get("secret_key", "")
    if not secret_key:
        secret_key = secrets.token_urlsafe(32)
        if "auth" not in cfg:
            cfg["auth"] = {}
        cfg["auth"]["secret_key"] = secret_key
        save_config(cfg)
    return secret_key


def verify_password(plain_password: str) -> bool:
    """常数时间校验密码，防止时序攻击"""
    configured_password = get_auth_password()
    # compare_digest 的 str 参数仅支持 ASCII；UTF-8 字节支持中文等字符。
    return hmac.compare_digest(
        plain_password.strip().encode("utf-8"),
        configured_password.strip().encode("utf-8"),
    )


def create_access_token(expires_in: int = TOKEN_EXPIRE_SECONDS) -> str:
    """生成带签名的访问 Token"""
    secret = get_jwt_secret().encode("utf-8")
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": "owner",
        "iat": int(time.time()),
        "exp": int(time.time()) + expires_in,
    }

    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).decode("utf-8").rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")

    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    """校验 Token 签名和是否在有效期内"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts

        secret = get_jwt_secret().encode("utf-8")
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")

        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return None

        rem = len(payload_b64) % 4
        if rem > 0:
            payload_b64 += "=" * (4 - rem)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8"))

        if payload.get("exp", 0) < time.time():
            return None

        return payload
    except Exception:
        return None


def get_token_from_request(
    request: Request,
    bearer_cred: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> Optional[str]:
    """支持从 Authorization 头、Cookie 或 URL query 获取 Token"""
    if bearer_cred and bearer_cred.credentials:
        return bearer_cred.credentials

    token_cookie = request.cookies.get("access_token")
    if token_cookie:
        return token_cookie

    token_query = request.query_params.get("token")
    if token_query:
        return token_query

    return None


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(get_token_from_request),
) -> Dict[str, Any]:
    """FastAPI 依赖注入：校验是否有权访问"""
    if not is_auth_enabled():
        return {"authenticated": True, "auth_enabled": False}

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请输入访问密码后继续",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新输入访问密码",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"authenticated": True, "auth_enabled": True}
