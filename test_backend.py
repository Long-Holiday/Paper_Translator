import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

for k in ["NO_PROXY", "no_proxy"]:
    if k in os.environ and "[::1]" in os.environ[k]:
        parts = [p.strip() for p in os.environ[k].split(",") if p.strip() and p.strip() != "[::1]"]
        os.environ[k] = ",".join(parts)

project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.main import app
from backend.app.database import init_db

client = TestClient(app)

def test_full_integration():
    print("[1] 测试数据库初始化...")
    init_db()

    print("[2] 测试健康检查 /api/health 与登录认证...")
    res = client.get("/api/health")
    assert res.status_code == 200, res.text
    print("  -> 健康检查正常")

    # 登录获取 token (默认初始密码 admin123)
    login_res = client.post("/api/auth/login", json={"password": "admin123"})
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    print("  -> 访问密码验证通过并设置认证请求头")

    print("[3] 测试前端静态页面托管与 SPA Fallback...")
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "Paper Translator" in res_root.text
    print("  -> 根路径 (/) 正确返回 index.html")

    res_spa = client.get("/paper/1")
    assert res_spa.status_code == 200
    assert "Paper Translator" in res_spa.text
    print("  -> 客户端路由 (/paper/1) 正确 Fallback 到 index.html")

    print("[4] 测试导入论文与元数据提取...")
    pdf_path = project_root / "ICLR-2024-dformer-rethinking-rgbd-representation-learning-for-semantic-segmentation-Paper-Conference.pdf"
    if not pdf_path.exists():
        pdf_path = project_root / "data" / "papers" / "1" / "original.pdf"
    assert pdf_path.exists(), "测试 PDF 文件不存在"

    with open(pdf_path, "rb") as f:
        res = client.post("/api/papers", files={"file": ("dformer.pdf", f, "application/pdf")})
    assert res.status_code == 200
    paper = res.json()
    paper_id = paper["id"]
    print(f"  -> 成功导入论文 ID: {paper_id}, 标题: {paper['title']}, 页数: {paper['page_count']}")

    print("[5] 测试更新阅读进度...")
    res = client.put(f"/api/papers/{paper_id}/reading-position", json={"page": 7})
    assert res.status_code == 200
    assert res.json()["last_read_page"] == 7
    print("  -> 进度保存正常")

    print("[6] 测试原始 PDF 下载流...")
    res = client.get(f"/api/papers/{paper_id}/original")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    print("  -> 原始 PDF 流传输正常")

    print("[7] 测试配置读取与修改...")
    res = client.get("/api/translation/config")
    assert res.status_code == 200
    res_update = client.put("/api/translation/config", json={"service": "deepseek", "thread": 4})
    assert res_update.status_code == 200
    print("  -> 配置读写正常")

    print("[8] 测试论文删除与本地目录清理...")
    res = client.delete(f"/api/papers/{paper_id}")
    assert res.status_code == 200
    paper_dir = project_root / "data" / "papers" / str(paper_id)
    assert not paper_dir.exists(), "本地论文目录应已被清理"
    print("  -> 论文删除与文件清理正常")

    print("\n✅ 全流程端到端集成测试全部通过！")

if __name__ == "__main__":
    test_full_integration()
