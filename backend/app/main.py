from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import FRONTEND_DIST
from backend.app.database import init_db, SessionLocal
from backend.app.models import Paper
from backend.app.api.papers import router as papers_router
from backend.app.api.translation import router as translation_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化数据库
    init_db()

    # 自动重置服务重启前未完成的孤儿任务，防止前端死循环轮询
    db = SessionLocal()
    try:
        stale_papers = db.query(Paper).filter(Paper.translation_status.in_(["translating", "queued"])).all()
        for p in stale_papers:
            p.translation_status = "failed"
            p.translation_error = "服务重启或上次异常中断，请点击重新翻译"
        if stale_papers:
            db.commit()
    finally:
        db.close()

    yield


app = FastAPI(
    title="Paper Translator API",
    description="PDFMathTranslate 本地 Web 论文翻译阅读平台",
    version="1.0.0",
    lifespan=lifespan,
)

# 允许跨域（前端本地开发 Vite 端口如 5173）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 API 路由
app.include_router(papers_router, prefix="/api")
app.include_router(translation_router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Paper Translator Service is running"}


# 前端生产打包静态资源托管与 SPA fallback
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        # 排除以 api 开头的请求
        if full_path.startswith("api/"):
            return {"error": "Not Found"}
        target_file = FRONTEND_DIST / full_path
        if target_file.is_file():
            return FileResponse(target_file)
        return FileResponse(FRONTEND_DIST / "index.html")
