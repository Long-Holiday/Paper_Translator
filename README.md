# Paper Translator 本地/服务器 Web 论文翻译阅读平台

基于 **PDFMathTranslate** 与 **FastAPI + React** 开发的学术论文高保真翻译与双栏对比阅读工具，支持本地及云端服务器自用部署。

针对 **单人使用、共享 CPU、1 GB 内存 + 8 GiB Swap**，默认采用独立翻译进程、4 个文本翻译线程、每批 5 页，并在完成后清理临时输出。Debian 可直接执行 `bash start.sh`，自动通过 uv 安装 Python 依赖、构建前端并后台运行。详见 [一键启动说明](deploy/one-click.md)。

---

## 🌟 核心特性

1. **论文目录与文件管理**
   - 快速导入英文论文 PDF（自动提取论文标题与页数，流式保存）
   - 论文列表搜索、实时状态追踪、一键删除
   - 翻译进度通过 SSE 长连接精准推送，任务完成后自动关闭，无无效网络轮询
   - 自动持久化记录每篇论文的最后阅读位置，随时继续阅读

2. **数学公式与排版高保真翻译**
   - 深度集成 `PDFMathTranslate` / `pdf2zh` 翻译核心
   - 支持 DeepSeek, OpenAI, 智谱 GLM, 硅基流动, Ollama, Google/Bing 等多翻译服务
   - 单用户串行任务队列，独立翻译子进程完成后释放模型内存，默认每批处理 5 页

3. **双栏对照阅读体验**
   - 原文与中文双栏并排显示
   - 页码双向联动同步翻页
   - 两栏按页内阅读进度双向同步滚动，兼容不同排版页面高度，缩放后保持对应位置
   - 支持鼠标滚轮与触控板自然翻页：页底继续下滚进入下一页，页顶继续上滚返回上一页
   - 支持键盘快捷键翻页（`←`/`→`/`空格`）、缩放联动
   - 防抖自动持久化保存阅读进度

4. **单人自用安全访问（环境变量密码锁）**
   - **单人模式无需账号**：仅需输入访问密码，免除复杂的账号系统
   - **密码写死在环境变量**：通过系统环境变量 `PAPER_TRANSLATOR_PASSWORD` 注入，安全不入代码库
   - **多端平滑授权**：同时支持 Bearer Token、HttpOnly Cookie 与 URL 签名校验，保障 PDF 文档流与 SSE 进度推送顺畅加载
   - **30天免密会话**：验证通过后自动维持 30 天会话，自用无需频繁重复输入，随时可一键“锁定退出”

---

## 🔐 访问密码配置（环境变量）

本系统为个人自用设计，**无需输入账号，只要输入访问密码即可解锁**。

### 设置环境变量

在服务器上启动或配置前，直接将密码写入环境变量：

```bash
# 方式 1：终端临时或启动脚本设置
export PAPER_TRANSLATOR_PASSWORD="your_secure_password"

# 方式 2：写入 ~/.bashrc 或 /etc/environment 实现永久生效
echo 'export PAPER_TRANSLATOR_PASSWORD="your_secure_password"' >> ~/.bashrc
source ~/.bashrc
```

> 💡 **提示**：若未设置 `PAPER_TRANSLATOR_PASSWORD`，系统启动时将打印黄色警示，并默认使用临时初始密码 `admin123` 兜底。

---

## 🚀 启动与部署

### 方式一：本地或开发环境直接启动

```bash
# 激活环境并启动服务（本地会自动打开浏览器）
uv run python start.py
```

浏览器访问：[http://127.0.0.1:8080](http://127.0.0.1:8080)

---

### 方式二：Debian 一键安装与后台启动（推荐）

```bash
bash start.sh          # 自动安装依赖、构建前端、后台启动
bash start.sh status   # 查看状态
bash start.sh logs     # 查看日志
bash start.sh stop     # 停止
bash start.sh restart  # 重启
```

Python 依赖统一使用 uv，服务采用独立 `.venv-server` 环境，默认端口 8080；首次密码保存在 `.env`，已有密码、API 密钥和端口会保留。配置已放宽为 4 个文本翻译线程、每批 5 页、100 MiB 上传和 2 小时超时，适合 1 GB RAM + 8 GiB Swap 的单人服务器。

权限、首次安装、配置迁移与可选 systemd 自启见 [一键启动说明](deploy/one-click.md)。

### 方式三：Docker 部署

在开发机器构建 `paper-translator:latest` 并通过 `docker save` / `docker load` 上传镜像，避免在 1 GB 服务器编译前端。服务器准备 `.env`、`config/config.yaml` 与数据目录后，使用仓库中的 Compose 配置：

```bash
docker compose up -d --no-build
```

默认限制 1 GiB 内存、最多 4 GiB Swap、CPU 1 核，并限制日志大小。详细步骤及可调整参数见 [低资源服务器部署说明](deploy/low-resource.md)。

---

## ⚙️ 翻译引擎配置

在项目目录中的 `config/config.yaml` 或直接在 Web 界面右上角点击 **设置** 按钮即可进行修改：

```yaml
translation:
  source_language: "en"
  target_language: "zh"
  service: "deepseek"           # 可选: deepseek, openai, zhipu, silicon, ollama 等
  model: "deepseek-chat"        # 模型名称
  api_key: "sk-xxxxxx"          # 填入您的 API Key
  base_url: "https://api.deepseek.com"
  thread: 4                     # 并发翻译线程数，实际受 resources.max_translation_threads 限制
```

---

## 🛠️ 项目目录结构

```text
Paper_Translator/
├── backend/                  # FastAPI 后端服务
│   ├── app/
│   │   ├── api/              # RESTful API 路由 (auth, papers, translation)
│   │   ├── services/         # 业务逻辑服务 (paper_service, translation_service)
│   │   ├── workers/          # 后台翻译线程 Worker
│   │   ├── auth.py           # 环境变量密码验证与安全 Token
│   │   ├── models.py         # SQLAlchemy 数据模型
│   │   └── config.py         # 配置管理与默认配置
│   └── run.py                # 后端独立运行入口
├── frontend/                 # React + TypeScript + Vite 前端
│   ├── src/
│   │   ├── api/              # 前端 API 请求封装与授权拦截 (authFetch)
│   │   ├── context/          # 全局认证状态 (AuthContext)
│   │   ├── components/       # 导航栏、双栏 PDF 渲染、受保护路由 ProtectedRoute
│   │   └── pages/            # 密码解锁页 LoginPage、论文目录页、双栏阅读页
│   └── dist/                 # 前端打包构建产物
├── deploy/                   # 服务器部署配置文件
│   ├── low-resource.md        # 1 GB / 单用户部署与资源调优
│   ├── paper-translator.service # Systemd 守护进程模板（包含资源上限）
│   └── nginx.conf            # Nginx 反向代理配置（含 SSE 防缓冲）
├── Dockerfile                # 多阶段容器构建 Dockerfile
├── docker-compose.yml        # Docker Compose 编排文件
├── data/                     # 本地 SQLite 数据库与论文 PDF 存储
├── config/config.yaml        # 翻译引擎配置文件
├── start.sh                  # Debian 一键安装、后台启动、状态/日志/停止
├── start.py                  # 一键启动脚本（支持 --no-browser 与环境变量提示）
└── README.md                 # 项目说明文档
```
