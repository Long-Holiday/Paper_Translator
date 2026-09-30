# Paper Translator 本地 Web 论文翻译阅读平台

基于 **PDFMathTranslate** 与 **FastAPI + React** 开发的个人本地学术论文翻译与双栏对比阅读工具。

## 🌟 核心特性

1. **论文目录管理**
   - 快速导入英文论文 PDF（自动提取标题与页数，流式保存）
   - 论文列表搜索、状态追踪、一键删除
   - 活跃翻译任务每秒批量轮询最新进度，任务结束或离开页面后自动停止；排版与校验完成后才显示 100%
   - 记录每篇论文的最后阅读位置，随时继续阅读

2. **数学公式与排版高保真翻译**
   - 封装 `PDFMathTranslate` / `pdf2zh` 翻译引擎
   - 支持 DeepSeek, OpenAI, 智谱 GLM, 硅基流动, Ollama, Google/Bing 等多翻译服务
   - 单用户本地后台排队任务池，低开销、不卡界面

3. **双栏对照阅读体验**
   - 原文与中文双栏并排显示
   - 页码双向联动同步翻页
   - 两栏按页内阅读进度双向同步滚动，兼容不同页面高度，缩放后保持对应位置
   - 支持鼠标滚轮与触控板上下滚动翻页：页底继续下滚进入下一页，页顶继续上滚返回上一页
   - 支持快捷键翻页（`←`/`→`/`空格`）、缩放联动
   - 防抖自动持久化保存阅读进度

4. **WSL 环境原生优化**
   - 彻底解决 WSL 下代理环境变量引发的 `httpx` IPv6 `[::1]` 解析崩溃 Bug
   - 自适应宿主机浏览器唤起逻辑

---

## 🚀 快速启动

### 1. 使用 uv 运行启动脚本
系统已支持自动检测并打包前端：

```bash
uv run python start.py
```

服务启动后将自动在浏览器中打开：
[http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## ⚙️ 翻译引擎配置

在项目目录中的 `config/config.yaml` 或直接在 Web 界面右上角点击 **设置** 按钮即可进行修改：

```yaml
translation:
  source_language: "en"
  target_language: "zh"
  service: "deepseek"           # 可选: deepseek, openai, zhipu, silicon, ollama, bing 等
  model: "deepseek-chat"        # 模型名称
  api_key: "sk-xxxxxx"          # 填入您的 API Key
  base_url: "https://api.deepseek.com"
  thread: 4                     # 翻译并发线程数
```

---

## 🛠️ 项目结构

```text
Paper_Translator/
├── backend/                  # FastAPI 后端服务
│   ├── app/
│   │   ├── api/              # RESTful API 路由 (papers, translation)
│   │   ├── services/         # 业务逻辑服务 (pdf_service, translation_service)
│   │   ├── workers/          # 后台翻译线程 Worker
│   │   ├── models.py         # SQLAlchemy 数据模型
│   │   └── config.py         # 环境变量与配置管理
│   └── run.py                # 后端独立运行入口
├── frontend/                 # React + TypeScript + Vite 前端
│   ├── src/
│   │   ├── components/       # 双栏 PDF 渲染、卡片、设置弹窗
│   │   ├── pages/            # 论文目录页、双栏阅读页
│   │   └── api/              # 前端 API 请求封装
│   └── dist/                 # 前端打包构建产物
├── data/                     # 本地 SQLite 数据库与论文 PDF 存储
├── config/config.yaml        # 翻译与服务配置文件
├── start.py                  # 一键启动脚本
└── plan.md                   # 开发规划文档
```
