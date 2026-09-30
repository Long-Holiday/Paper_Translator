# 单人使用：共享 CPU / 1 GB 内存部署

系统默认只运行一个 API 进程，翻译任务串行排队。每个任务启动独立子进程，完成、报错或超时后退出，释放 ONNX 与 PDF 库占用的内存。不要使用 Uvicorn 多 worker：任务队列在进程内，多 worker 会重复运行模型并互相干扰任务状态。

## 默认限制

| 项目 | 默认值 | 环境变量 |
| --- | --- | --- |
| ONNX / 数学库 CPU 线程 | 1 | `PT_CPU_THREADS` |
| 文本翻译并发 | 1 | `PT_MAX_TRANSLATION_THREADS` |
| 每批处理页数 | 2 | `PT_TRANSLATION_BATCH_PAGES` |
| 运行及排队任务总数 | 3 | `PT_MAX_PENDING_TASKS` |
| 单文件大小 | 20 MiB | `PT_MAX_UPLOAD_MB` |
| 单文件页数 | 200 | `PT_MAX_PDF_PAGES` |
| 单任务超时（包含下载模型） | 1800 秒 | `PT_TRANSLATION_TIMEOUT_SECONDS` |
| Docker 内存上限（API + 子进程） | 768 MiB | `PT_CONTAINER_MEMORY` |
| Docker CPU 配额 | 0.75 核 | `PT_CONTAINER_CPUS` |

前七项也可在 `config/config.yaml` 的 `resources` 中设置。环境变量优先；文本翻译线程取 Web 设置与服务器上限的较小值。若平台只分配 0.25 核，把 `PT_CONTAINER_CPUS` 调为 `0.25`，同时按论文长度增加超时。

新任务只长期保存 `original.pdf` 和 `translated.pdf`，引擎产生的 mono/dual 中间文件每批删除，双栏阅读仍使用原文与译文。旧版本留下的 mono/dual 文件不会自动删除。模型、字体和翻译缓存会复用，避免每个任务重复下载；Docker 镜像把 `/root/.cache` 链接到持久化的 `/app/data/cache`。

分批处理保留页面顺序、文档元数据及普通目录书签；跨批次的 PDF 内部链接可能丢失。需要完整保留原引擎的整篇处理方式时，可设 `PT_TRANSLATION_BATCH_PAGES=0`，但内存峰值会增加。

## 方案一：原生 Python + 预构建前端

适合希望少装服务的服务器。服务器上不需要 Node.js、Vite 或本地大语言模型。

在开发机器构建前端：

```bash
cd frontend
npm ci
npm run build
```

将项目源码与 `frontend/dist` 上传到服务器 `/opt/Paper_Translator`，不要上传开发机器的 `.venv`、`node_modules` 或真实 `.env`。不要覆盖已有服务器的 `data/`、`config/config.yaml` 或 `.env`。

在服务器创建 Python 环境并安装依赖（建议 Python 3.11）：

```bash
cd /opt/Paper_Translator
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -r backend/requirements.txt
```

首次部署时，复制 `.env.example` 为 `.env` 并填写密码及翻译 API 密钥。若没有 `config/config.yaml`，可使用 `config/config.example.yaml`；请保留已有配置。翻译服务使用远程 API，1 GB 机器不适合同时运行 Ollama 模型。

```bash
.venv/bin/python start.py --no-browser --skip-frontend-build
```

生产自启使用 `deploy/paper-translator.service`。修改 `WorkingDirectory`、`ExecStart` 和 `User` 对应的路径；访问密码可以放在 `.env` 中，并删除模板里的占位 `Environment=PAPER_TRANSLATOR_PASSWORD=...`（系统环境优先于 `.env`）。模板限制整个服务为 768 MiB / 75% CPU，必要时修改 `MemoryMax` / `CPUQuota` / `TimeoutStopSec`。

```bash
sudo cp deploy/paper-translator.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now paper-translator
sudo journalctl -u paper-translator -n 50
```

首次翻译需要下载模型及字体，服务器必须能访问相应下载源。原生方式缓存保存在服务用户的 `~/.cache/babeldoc` 与 `~/.cache/pdf2zh`，应保留这些目录。

## 方案二：Docker 镜像在开发机器构建

不要在 1 GB 服务器上执行前端编译或完整镜像构建。开发机器需与服务器使用相同 CPU 架构；不同架构应使用对应的构建目标。

开发机器：

```bash
docker build -t paper-translator:latest .
docker save -o paper-translator.tar paper-translator:latest
```

上传镜像包、`docker-compose.yml`、配置模板和 `.env.example`；服务器上创建 `data/` 与 `config/`，准备真实 `.env` 和 `config/config.yaml` 后运行：

```bash
docker load -i paper-translator.tar
docker compose up -d --no-build
docker compose logs --tail=50
docker stats --no-stream paper-translator
```

Compose 已限制 CPU、内存、进程数及日志大小，并挂载数据、配置与 `.env`。`.dockerignore` 排除真实密钥、历史论文、虚拟环境与前端依赖，镜像使用无密钥的示例配置。镜像和模型缓存仍会占用磁盘空间，应为依赖、论文与临时输出预留空间。

可直接通过 8080 端口访问；若使用 Nginx，使用 `deploy/nginx.conf`。上传限制是 21 MiB 请求体（包含 multipart 头），应用再检查 20 MiB 文件大小；调整文件上限时也需调整 Nginx。SSE 必须关闭缓冲，静态 assets 可长期缓存。

## 已完成的验证与边界

开发环境实测：API 导入峰值 RSS 约 **93 MiB**，未加载 pdf2zh / ONNX；取现有论文前 5 页，以真实 ONNX 版面推理和 PDF 排版运行、用本地文本桩替代远程翻译，翻译进程峰值 RSS 约 **514 MiB**，输出通过逐页渲染校验。该数据不代表所有文档或目标服务器的峰值，也不包含真实 API 延迟。

回归测试覆盖串行队列容量、重复任务、提交失败、子进程崩溃/超时/停止与回收、临时目录清理、上传回滚、分批页序/元数据/目录保留、译文校验失败时保留旧文件及 SSE 状态通知。

图片密集的 PDF 仍可能超过限制。出现内存不足时先将 `PT_TRANSLATION_BATCH_PAGES=1` 并减小文件上限；容器硬限制可以保护宿主机，但严重 OOM 仍可能触发整个容器重启。重启后任务标记为失败，可手动重试。当前环境没有可用的 Docker 服务，因此未执行镜像构建或容器运行验证。
