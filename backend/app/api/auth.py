from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from pydantic import BaseModel
from backend.app.auth import (
    is_auth_enabled,
    verify_password,
    create_access_token,
    get_token_from_request,
    verify_access_token,
    TOKEN_EXPIRE_SECONDS,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    """单人密码验证登录"""
    if not is_auth_enabled():
        return {"status": "success", "token": "not_required", "message": "未开启访问密码"}

    if not verify_password(payload.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="访问密码错误",
        )

    token = create_access_token()

    # 写入 HttpOnly Cookie
    response.set_cookie(
        key="access_token",
        value=token,
        max_age=TOKEN_EXPIRE_SECONDS,
        httponly=True,
        samesite="lax",
        path="/",
    )

    return {
        "status": "success",
        "token": token,
        "message": "解锁成功",
    }


@router.post("/logout")
def logout(response: Response):
    """退出登录接口"""
    response.delete_cookie(key="access_token", path="/")
    return {"status": "success", "message": "已锁定并退出登录"}


@router.get("/me")
def get_auth_status(
    request: Request,
    token: Optional[str] = Depends(get_token_from_request),
):
    """获取当前访问授权状态"""
    auth_enabled = is_auth_enabled()

    if not auth_enabled:
        return {
            "authenticated": True,
            "auth_enabled": False,
        }

    if not token:
        return {
            "authenticated": False,
            "auth_enabled": True,
        }

    payload = verify_access_token(token)
    if not payload:
        return {
            "authenticated": False,
            "auth_enabled": True,
        }

    return {
        "authenticated": True,
        "auth_enabled": True,
    }
