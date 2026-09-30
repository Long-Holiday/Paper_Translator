# --- 阶段 1：构建前端 ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 阶段 2：构建后端与运行镜像 ---
FROM python:3.11-slim
WORKDIR /app

# 安装必要的系统运行时（如字体库和渲染依赖）
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 安装后端依赖
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# 复制项目代码
COPY backend/ backend/
COPY config/config.example.yaml config/config.yaml
COPY start.py .
COPY --from=frontend-builder /app/frontend/dist frontend/dist

# 环境变量
ENV PYTHONUNBUFFERED=1
ENV NO_BROWSER=1
ENV OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
# pdf2zh / babeldoc 1.x use ~/.cache directly, ignoring XDG_CACHE_HOME.
RUN mkdir -p /app/data/cache && ln -s /app/data/cache /root/.cache

# 暴露端口
EXPOSE 8080

# 挂载数据和配置目录
VOLUME ["/app/data", "/app/config"]

CMD ["python", "start.py", "--no-browser", "--skip-frontend-build"]
