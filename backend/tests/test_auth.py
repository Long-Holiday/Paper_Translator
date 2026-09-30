import os
from pathlib import Path
import yaml
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.config import load_config, save_config, update_env_file, ENV_FILE, CONFIG_FILE

client = TestClient(app)


def test_auth_workflow_with_env_file():
    # 确保 .env 中的设置生效
    assert ENV_FILE.exists(), ".env 文件必须存在"

    # 1. 未授权访问受保护接口，应当返回 401
    resp = client.get("/api/papers")
    assert resp.status_code == 401

    # 2. 访问 /api/auth/me 返回未认证
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is False

    # 3. 错误密码登录，返回 400
    resp = client.post("/api/auth/login", json={"password": "incorrect_password"})
    assert resp.status_code == 400

    # 4. 正确密码登录（.env 中的 admin123），返回 200 与 token
    resp = client.post("/api/auth/login", json={"password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    token = data["token"]
    assert token

    # 5. Header 认证成功
    resp = client.get("/api/papers", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    # 6. Cookie 认证成功
    resp = client.get("/api/papers", cookies={"access_token": token})
    assert resp.status_code == 200

    # 7. Query 参数认证成功
    resp = client.get(f"/api/papers?token={token}")
    assert resp.status_code == 200

    # 8. 登出
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200


def test_api_key_stored_only_in_env_and_never_in_yaml():
    # 1. 验证 load_config 能够从 .env 自动读取 TRANSLATION_API_KEY
    cfg = load_config()
    loaded_key = cfg.get("translation", {}).get("api_key", "")
    assert loaded_key.startswith("sk-"), f"未能从 .env 正确读取 API Key, 当前为: {loaded_key}"

    # 2. 验证实际磁盘上的 config.yaml 文件中 api_key 绝对为空字符串，不会暴露
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw_yaml = yaml.safe_load(f)
    assert raw_yaml["translation"]["api_key"] == "", "严重安全隐患：config.yaml 中依然残留有 API Key！"

    # 3. 验证当通过接口或 save_config 保存新 API Key 时，会写回 .env 而不会写入 config.yaml
    test_new_key = "sk-test-secret-key-12345678"
    cfg["translation"]["api_key"] = test_new_key
    save_config(cfg)

    # 检查 .env 是否被安全更新
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        env_content = f.read()
    assert f"TRANSLATION_API_KEY={test_new_key}" in env_content

    # 检查 config.yaml 依然为空，没有被污染
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        raw_yaml_after = yaml.safe_load(f)
    assert raw_yaml_after["translation"]["api_key"] == "", "严重错误：save_config 将 API Key 写回了 config.yaml！"

    # 恢复原有的 key
    update_env_file("TRANSLATION_API_KEY", "sk-051105c7159b4a46a0bdcaf447504aa5")


if __name__ == "__main__":
    test_auth_workflow_with_env_file()
    test_api_key_stored_only_in_env_and_never_in_yaml()
    print("All .env & security isolation tests passed successfully!")
