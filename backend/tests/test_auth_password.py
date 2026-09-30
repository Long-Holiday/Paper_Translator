import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.auth import router


@pytest.mark.parametrize(
    "configured_password, submitted_password, expected_status",
    [
        ("admin123", "admin123", 200),
        ("admin123", "wrong-password", 400),
        ("论文密码123", "论文密码123", 200),
        ("päss🔒123", "päss🔒123", 200),
        ("admin123", "错误密码", 400),
        ("论文密码123", "admin123", 400),
        ("论文密码123", "错误密码123", 400),
        ("  论文密码123  ", "\t论文密码123\n", 200),
    ],
    ids=[
        "ascii-match",
        "ascii-mismatch",
        "chinese-match",
        "accent-and-emoji-match",
        "unicode-input-mismatch",
        "unicode-config-mismatch",
        "unicode-both-mismatch",
        "unicode-with-whitespace",
    ],
)
def test_login_password_characters(
    monkeypatch, configured_password, submitted_password, expected_status
):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("PAPER_TRANSLATOR_PASSWORD", configured_password)
    monkeypatch.setenv("AUTH_SECRET_KEY", "test-auth-password-secret")

    # Exercise real auth routes without touching the database or saved config.
    app = FastAPI()
    app.include_router(router, prefix="/api")
    with TestClient(app) as client:
        response = client.post("/api/auth/login", json={"password": submitted_password})
        assert response.status_code == expected_status

        if expected_status == 200:
            assert response.json()["status"] == "success"
            assert response.json()["token"] == response.cookies["access_token"]
            assert client.get("/api/auth/me").json()["authenticated"] is True
        else:
            assert response.json()["detail"] == "访问密码错误"
            assert "access_token" not in response.cookies
            assert client.get("/api/auth/me").json()["authenticated"] is False
