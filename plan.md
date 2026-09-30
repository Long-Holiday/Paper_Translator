# PDFMathTranslate 本地 Web 论文翻译阅读平台开发设计方案

## 1. 项目定位

本项目用于个人本地使用，目标是开发一个基于 **PDFMathTranslate / PDFMathTranslate-next** 的论文翻译阅读 Web 应用。

系统只保留两个核心能力：

1. **论文目录管理**
2. **PDF 自动翻译与双栏阅读**

不加入账号系统、团队协作、支付、笔记、知识库、RAG、AI 问答、云同步等非必要功能。

---

## 2. 核心使用流程

```text
启动本地 Web 服务
        ↓
浏览器访问系统
        ↓
导入英文论文 PDF
        ↓
论文进入本地目录
        ↓
点击“翻译”
        ↓
后端调用 PDFMathTranslate
        ↓
生成中文翻译 PDF
        ↓
进入阅读页
        ↓
左侧原文 PDF
右侧中文 PDF
        ↓
左右同步翻页 / 滚动
        ↓
自动保存阅读位置
```

---

## 3. 产品形态

建议采用：

- 本地部署
- Web 前端
- Python 后端
- SQLite 数据库
- 本地文件存储
- 浏览器访问

启动方式：

```bash
python start.py
```

启动后自动打开：

```text
http://127.0.0.1:8000
```

从用户体验上，它就是一个本地论文阅读软件。

---

# 4. 系统总体架构

```text
┌──────────────────────────────────────────────┐
│                  Browser                     │
│                                              │
│             React / TypeScript               │
│                                              │
│  ┌──────────────┐    ┌──────────────────┐    │
│  │ Paper Library │    │ Dual PDF Reader  │    │
│  │              │    │                  │    │
│  │ 论文目录      │    │ Original PDF     │    │
│  │ 导入 / 删除   │    │ Chinese PDF      │    │
│  └──────────────┘    └──────────────────┘    │
└───────────────────────┬──────────────────────┘
                        │
                    REST API
                        │
┌───────────────────────▼──────────────────────┐
│                  FastAPI                     │
│                                              │
│  ┌──────────────┐    ┌──────────────────┐    │
│  │ Paper Service │    │ Translate Service │   │
│  └──────┬───────┘    └─────────┬────────┘    │
│         │                       │             │
│         │                PDFMathTranslate     │
│         │                       │             │
│         │                Translation Model    │
│         │                                     │
│  ┌──────▼──────┐    ┌──────────────────┐      │
│  │   SQLite    │    │ Local PDF Files  │      │
│  └─────────────┘    └──────────────────┘      │
└──────────────────────────────────────────────┘
```

---

# 5. 技术栈

## 5.1 前端

推荐：

```text
React
TypeScript
Vite
PDF.js
React Router
Axios / Fetch
```

可选 UI：

```text
Tailwind CSS
```

不建议第一版使用过重的 UI 框架。

---

## 5.2 后端

推荐：

```text
Python 3.11+
FastAPI
Uvicorn
SQLAlchemy / SQLModel
SQLite
Pydantic
```

翻译引擎：

```text
PDFMathTranslate-next
        ↓
BabelDOC
        ↓
LLM / Translation API
```

---

## 5.3 数据存储

### 数据库

使用 SQLite：

```text
data/app.db
```

### PDF 文件

直接保存在本地：

```text
data/papers/
```

结构：

```text
data/
├── app.db
└── papers/
    ├── 000001/
    │   ├── original.pdf
    │   └── translated.pdf
    │
    ├── 000002/
    │   ├── original.pdf
    │   └── translated.pdf
    │
    └── ...
```

---

# 6. 页面设计

系统只设计两个主要页面。

---

# 6.1 论文目录页

路由：

```text
/
```

布局：

```text
┌───────────────────────────────────────────────────────────┐
│ Paper Translator                             + 导入 PDF   │
├───────────────────────────────────────────────────────────┤
│                                                           │
│ 搜索论文...                                                │
│                                                           │
│ ┌───────────────────────────────────────────────────────┐ │
│ │ Attention Is All You Need                            │ │
│ │ 已翻译 · 15 页 · 阅读到第 8 页                       │ │
│ │                                        打开  删除     │ │
│ └───────────────────────────────────────────────────────┘ │
│                                                           │
│ ┌───────────────────────────────────────────────────────┐ │
│ │ DeepSeek-V3 Technical Report                         │ │
│ │ 未翻译 · 53 页                          翻译  删除     │ │
│ └───────────────────────────────────────────────────────┘ │
│                                                           │
│ ┌───────────────────────────────────────────────────────┐ │
│ │ Scaling Laws for Neural Language Models              │ │
│ │ 翻译中 · 42%                                          │ │
│ └───────────────────────────────────────────────────────┘ │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## 6.1.1 功能

只保留：

- 导入 PDF
- 查看论文
- 开始翻译
- 查看翻译状态
- 删除论文
- 搜索论文
- 显示最后阅读位置

状态：

```text
未翻译
翻译中
已完成
失败
```

---

# 6.2 双栏论文阅读页

路由：

```text
/paper/:id
```

界面：

```text
┌────────────────────────────────────────────────────────────────────┐
│ ← 返回目录      Attention Is All You Need        8 / 15            │
├─────────────────────────────────┬──────────────────────────────────┤
│                                 │                                  │
│          ORIGINAL PDF           │          中文 PDF                 │
│                                 │                                  │
│                                 │                                  │
│                                 │                                  │
│                                 │                                  │
│                                 │                                  │
├─────────────────────────────────┴──────────────────────────────────┤
│     上一页                 8 / 15                    下一页         │
└────────────────────────────────────────────────────────────────────┘
```

阅读器采用：

```text
PDF.js
```

左右各一个 Viewer。

---

# 7. 双栏 PDF 同步机制

这是系统最重要的交互之一。

第一版建议采用：

## 页码同步

左侧翻到：

```text
Page 12
```

右侧自动跳到：

```text
Page 12
```

反向同样成立。

伪代码：

```ts
function onLeftPageChange(page: number) {
    if (!syncLock) {
        rightViewer.goToPage(page)
    }
}

function onRightPageChange(page: number) {
    if (!syncLock) {
        leftViewer.goToPage(page)
    }
}
```

---

## 第二阶段可以加入滚动同步

计算：

```text
当前滚动比例 =
scrollTop /
(scrollHeight - clientHeight)
```

同步到另一边：

```text
targetScrollTop =
scrollRatio *
(targetScrollHeight - targetClientHeight)
```

但建议：

**V1 先只做页码同步。**

因为翻译后的 PDF 页面高度可能与原 PDF 略有差异，直接按像素同步容易产生偏移。

---

# 8. PDF 翻译架构

不要修改 PDFMathTranslate 的核心代码。

正确方式是：

```text
你的 Web 系统
      ↓
Translator Service
      ↓
PDFMathTranslate API
      ↓
translated.pdf
```

把 PDFMathTranslate 当成独立翻译引擎。

---

# 9. 翻译任务生命周期

```text
用户点击翻译
       ↓
创建 Translation Job
       ↓
status = pending
       ↓
后台线程 / Worker 执行
       ↓
status = translating
       ↓
PDFMathTranslate
       ↓
生成 translated.pdf
       ↓
status = completed
```

失败：

```text
status = failed
error_message = "..."
```

---

# 10. 为什么不能直接在 HTTP 请求里翻译

不要这样：

```text
POST /translate

等待 5~20 分钟

返回 translated.pdf
```

因为：

- HTTP 请求容易超时
- 页面刷新会影响体验
- 无法显示进度
- 出错难处理

应该：

```text
POST /papers/{id}/translate
        ↓
立即返回
{
    "status": "started"
}
```

然后前端轮询：

```text
GET /papers/{id}
```

例如每：

```text
2 秒
```

请求一次。

---

# 11. 第一版任务执行方式

因为是单人本地使用，不需要 Redis / Celery。

直接使用：

```text
FastAPI BackgroundTasks
```

或者：

```text
ThreadPoolExecutor
```

即可。

推荐：

```python
ThreadPoolExecutor(max_workers=1)
```

原因：

PDF 翻译本身可能占用较多：

- CPU
- 内存
- 网络 API
- PDF 解析资源

单用户同时翻译多个论文意义不大。

---

# 12. 数据库设计

第一版只需要：

```text
papers
```

一张表。

SQL：

```sql
CREATE TABLE papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    title TEXT NOT NULL,

    original_filename TEXT NOT NULL,

    original_pdf_path TEXT NOT NULL,

    translated_pdf_path TEXT,

    page_count INTEGER,

    translation_status TEXT NOT NULL DEFAULT 'pending',

    translation_progress INTEGER NOT NULL DEFAULT 0,

    translation_error TEXT,

    last_read_page INTEGER NOT NULL DEFAULT 1,

    created_at DATETIME NOT NULL,

    updated_at DATETIME NOT NULL
);
```

---

# 13. Paper 数据模型

Python：

```python
class Paper:
    id: int

    title: str

    original_filename: str

    original_pdf_path: str

    translated_pdf_path: str | None

    page_count: int | None

    translation_status: str

    translation_progress: int

    translation_error: str | None

    last_read_page: int

    created_at: datetime

    updated_at: datetime
```

---

# 14. 翻译状态设计

建议使用：

```text
pending
queued
translating
completed
failed
```

对应中文：

| 状态 | 含义 |
|---|---|
| pending | 未翻译 |
| queued | 等待翻译 |
| translating | 翻译中 |
| completed | 已完成 |
| failed | 翻译失败 |

---

# 15. API 设计

基础前缀：

```text
/api
```

---

## 15.1 获取论文列表

```http
GET /api/papers
```

返回：

```json
[
    {
        "id": 1,
        "title": "Attention Is All You Need",
        "translation_status": "completed",
        "translation_progress": 100,
        "last_read_page": 8
    }
]
```

---

# 15.2 导入论文

```http
POST /api/papers
```

类型：

```text
multipart/form-data
```

参数：

```text
file
```

返回：

```json
{
    "id": 12,
    "title": "paper.pdf",
    "translation_status": "pending"
}
```

---

# 15.3 获取论文信息

```http
GET /api/papers/{paper_id}
```

---

# 15.4 删除论文

```http
DELETE /api/papers/{paper_id}
```

删除：

```text
数据库记录
original.pdf
translated.pdf
```

---

# 15.5 开始翻译

```http
POST /api/papers/{paper_id}/translate
```

返回：

```json
{
    "status": "started"
}
```

---

# 15.6 获取原始 PDF

```http
GET /api/papers/{paper_id}/original
```

返回：

```text
application/pdf
```

---

# 15.7 获取翻译 PDF

```http
GET /api/papers/{paper_id}/translated
```

---

# 15.8 更新阅读位置

```http
PUT /api/papers/{paper_id}/reading-position
```

请求：

```json
{
    "page": 12
}
```

---

# 16. 后端目录结构

推荐：

```text
backend/
│
├── app/
│   │
│   ├── main.py
│   │
│   ├── config.py
│   │
│   ├── database.py
│   │
│   ├── models.py
│   │
│   ├── schemas.py
│   │
│   ├── dependencies.py
│   │
│   ├── api/
│   │   ├── papers.py
│   │   └── translation.py
│   │
│   ├── services/
│   │   ├── paper_service.py
│   │   ├── translation_service.py
│   │   └── pdf_service.py
│   │
│   └── workers/
│       └── translation_worker.py
│
├── requirements.txt
└── run.py
```

---

# 17. 前端目录结构

```text
frontend/
│
├── src/
│   │
│   ├── pages/
│   │   ├── LibraryPage.tsx
│   │   └── ReaderPage.tsx
│   │
│   ├── components/
│   │   ├── PaperCard.tsx
│   │   ├── ImportButton.tsx
│   │   ├── PdfViewer.tsx
│   │   ├── DualPdfViewer.tsx
│   │   └── TranslationStatus.tsx
│   │
│   ├── api/
│   │   └── papers.ts
│   │
│   ├── hooks/
│   │   ├── usePaper.ts
│   │   └── usePdfSync.ts
│   │
│   ├── types/
│   │   └── paper.ts
│   │
│   ├── App.tsx
│   └── main.tsx
│
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

# 18. 整体项目目录

最终：

```text
paper-translator/
│
├── backend/
│   ├── app/
│   ├── requirements.txt
│   └── run.py
│
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
│
├── data/
│   ├── app.db
│   └── papers/
│
├── scripts/
│
├── config/
│   └── config.yaml
│
├── start.py
│
├── README.md
└── .gitignore
```

---

# 19. TranslationService 设计

核心接口：

```python
class TranslationService:

    def translate(
        self,
        source_pdf: str,
        output_pdf: str
    ) -> None:
        pass
```

PDFMathTranslate 相关代码全部封装在这里。

不要让：

```text
API Controller
```

直接调用 PDFMathTranslate。

这样以后如果更换：

```text
PDFMathTranslate
BabelDOC
其他 PDF 翻译引擎
```

前端和 API 都不用改。

---

# 20. TranslationService 执行流程

```text
translate()
     ↓
读取配置
     ↓
建立 PDFMathTranslate 参数
     ↓
启动翻译
     ↓
监听进度
     ↓
更新 database.progress
     ↓
获得生成 PDF
     ↓
移动为 translated.pdf
     ↓
更新 status = completed
```

---

# 21. 翻译配置

建议使用：

```text
config/config.yaml
```

例如：

```yaml
translation:

  source_language: en
  target_language: zh

  provider: openai

  model: gpt-4.1-mini

  api_key: ""

  preserve_layout: true

  translate_first_page: true
```

也可以未来支持：

```text
OpenAI
DeepSeek
Gemini
Ollama
```

但第一版建议：

**只实现一个翻译 Provider。**

---

# 22. 配置页面

严格按照最小产品原则，可以不做独立设置页。

直接：

```text
config.yaml
```

修改即可。

后续如果需要，再加：

```text
/settings
```

---

# 23. PDF Viewer 实现

推荐直接使用：

```text
pdfjs-dist
```

基础组件：

```tsx
<PdfViewer
    url="/api/papers/1/original"
    page={currentPage}
    onPageChange={setCurrentPage}
/>
```

右侧：

```tsx
<PdfViewer
    url="/api/papers/1/translated"
    page={currentPage}
    onPageChange={setCurrentPage}
/>
```

两个 Viewer 共用：

```text
currentPage
```

这是最简单可靠的同步方案。

---

# 24. Reader 状态模型

```ts
interface ReaderState {
    currentPage: number
    zoom: number
    syncEnabled: boolean
}
```

第一版可以让：

```text
zoom
```

也同步。

例如：

```text
左侧缩放 120%
右侧也调整为 120%
```

---

# 25. 阅读位置保存

用户翻到：

```text
Page 18
```

前端 debounce：

```text
1 秒
```

后调用：

```http
PUT /api/papers/1/reading-position
```

这样再次打开论文时直接：

```text
Page 18
```

---

# 26. 导入 PDF 流程

```text
选择文件
    ↓
POST /api/papers
    ↓
生成 paper_id
    ↓
建立目录
data/papers/{id}
    ↓
保存 original.pdf
    ↓
读取 PDF metadata
    ↓
写入 SQLite
    ↓
返回 Paper
```

例如：

```text
data/papers/42/original.pdf
```

---

# 27. 论文标题解析

优先级：

```text
PDF Metadata Title
      ↓
如果不存在
      ↓
文件名
```

例如：

```text
attention_is_all_you_need.pdf
```

可以转换为：

```text
Attention Is All You Need
```

第一版不要为了标题识别引入额外 AI。

---

# 28. 翻译进度

如果 PDFMathTranslate 能提供任务进度：

```text
12%
36%
72%
100%
```

就直接展示。

如果无法稳定获得细粒度进度，则只展示：

```text
正在解析 PDF
正在翻译
正在生成 PDF
翻译完成
```

不要为了假的精确进度复杂化实现。

---

# 29. 前端状态轮询

翻译状态为：

```text
queued
translating
```

时：

```ts
setInterval(() => {
    fetchPaper(id)
}, 2000)
```

完成后：

```text
停止轮询
加载 translated.pdf
```

---

# 30. 错误处理

翻译失败：

```text
翻译失败
[重新翻译]
```

后端保留：

```text
translation_error
```

例如：

```text
API timeout
PDF parsing failed
Invalid PDF
Provider rate limit
```

日志保存在：

```text
logs/app.log
```

---

# 31. 文件安全

因为是本地单用户工具，不需要复杂鉴权。

但仍建议：

### 禁止路径穿越

不要使用上传文件名直接构造路径：

错误：

```python
save_path = f"data/{upload.filename}"
```

正确：

```text
data/papers/{paper_id}/original.pdf
```

---

# 32. 大文件处理

上传时：

```text
流式写入磁盘
```

不要：

```text
一次性读取整个 PDF 到内存
```

尤其论文可能包含：

```text
100 MB+
```

---

# 33. 服务启动

项目根目录：

```text
start.py
```

功能：

```text
启动 FastAPI
        ↓
检查前端 build
        ↓
启动浏览器
        ↓
打开 localhost
```

例如：

```python
import webbrowser

webbrowser.open(
    "http://127.0.0.1:8000"
)
```

---

# 34. 前后端部署方式

开发阶段：

```text
React
http://localhost:5173

FastAPI
http://localhost:8000
```

生产 / 自用阶段：

先执行：

```bash
npm run build
```

生成：

```text
frontend/dist/
```

FastAPI 直接托管：

```text
frontend/dist
```

最终只运行：

```text
localhost:8000
```

不需要同时启动两个服务。

---

# 35. 最终运行架构

```text
                Browser
                   │
                   │ localhost:8000
                   ↓
               FastAPI
              /       \
             /         \
        REST API     React SPA
           |
           |
        SQLite
           |
           |
   PDFMathTranslate
           |
           |
      Local PDFs
```

---

# 36. 第一版不做的功能

明确排除：

```text
用户登录
注册
权限系统
云端数据库
对象存储
Docker 集群
Redis
Celery
WebSocket
多人协作
批注
笔记
知识库
Embedding
Vector DB
RAG
AI 聊天
论文总结
论文推荐
在线支付
移动端 App
```

原则：

> 所有不能直接改善“导入 → 翻译 → 双栏阅读”的功能都暂时不做。

---

# 37. MVP 功能列表

## 论文管理

- [ ] 导入 PDF
- [ ] 展示论文列表
- [ ] 搜索论文
- [ ] 删除论文
- [ ] 保存阅读页码

## 翻译

- [ ] 点击翻译
- [ ] 调用 PDFMathTranslate
- [ ] 显示翻译状态
- [ ] 保存 translated.pdf
- [ ] 翻译失败后重新执行

## 阅读器

- [ ] 原始 PDF 阅读
- [ ] 中文 PDF 阅读
- [ ] 双栏布局
- [ ] 页码同步
- [ ] 缩放
- [ ] 自动恢复阅读位置

---

# 38. 开发阶段规划

## Phase 1：翻译引擎验证

目标：

```text
Python
   ↓
输入 original.pdf
   ↓
PDFMathTranslate
   ↓
输出 translated.pdf
```

这一阶段不要开发 UI。

先确保：

```text
PDFMathTranslate 在目标机器稳定工作
```

---

## Phase 2：后端

完成：

```text
FastAPI
SQLite
导入 PDF
论文 CRUD
翻译任务
PDF 文件接口
```

此时可以用：

```text
Swagger UI
```

测试全部功能。

---

## Phase 3：论文目录前端

完成：

```text
论文列表
导入
删除
翻译按钮
翻译状态
```

---

## Phase 4：PDF 阅读器

完成：

```text
PDF.js
原文 Viewer
译文 Viewer
双栏布局
```

---

## Phase 5：同步阅读

完成：

```text
页码同步
缩放同步
阅读位置保存
```

---

## Phase 6：体验优化

最后再处理：

```text
进度展示
错误提示
拖拽上传
搜索
页面样式
启动脚本
```

---

# 39. 推荐开发顺序

最重要的一点：

**不要先开发完整前端。**

正确顺序：

```text
1. 跑通 PDFMathTranslate
        ↓
2. 封装 TranslationService
        ↓
3. FastAPI API
        ↓
4. SQLite
        ↓
5. 论文目录
        ↓
6. PDF.js
        ↓
7. 双栏同步
        ↓
8. UI 优化
```

---

# 40. V1 验收标准

V1 达到以下效果即可认为完成。

### 场景 1

用户打开：

```text
localhost:8000
```

看到论文目录。

### 场景 2

拖入：

```text
paper.pdf
```

论文出现在目录。

### 场景 3

点击：

```text
翻译
```

后台执行 PDFMathTranslate。

### 场景 4

翻译完成后点击论文。

进入：

```text
Original | 中文翻译
```

双栏阅读页面。

### 场景 5

左侧进入：

```text
Page 15
```

右侧自动：

```text
Page 15
```

### 场景 6

关闭浏览器。

重新打开论文后：

```text
恢复 Page 15
```

如果以上全部实现，这个项目的核心目标已经完成。

---

# 41. 推荐最终技术方案

| 模块 | 技术 |
|---|---|
| Web 前端 | React + TypeScript |
| 构建工具 | Vite |
| PDF 阅读 | PDF.js |
| 后端 | FastAPI |
| 数据库 | SQLite |
| ORM | SQLModel / SQLAlchemy |
| PDF 翻译 | PDFMathTranslate-next |
| PDF 引擎 | BabelDOC |
| 文件存储 | 本地目录 |
| 后台任务 | ThreadPoolExecutor |
| 部署 | localhost |
| Web Server | Uvicorn |
| 生产前端 | FastAPI StaticFiles |

---

# 42. 最终项目目标

最终产品不是一个复杂的“AI 论文平台”，而是一个非常聚焦的工具：

```text
                     Paper Translator

                        Import PDF
                            │
                            ▼
                      Paper Library
                            │
                            ▼
                       Translate
                            │
                            ▼
                   PDFMathTranslate
                            │
                            ▼
              ┌─────────────────────────┐
              │ Original │ 中文 Translation │
              │   PDF    │       PDF       │
              └─────────────────────────┘
                            │
                            ▼
                     Continue Reading
```

核心设计原则：

> **尽可能少的功能，尽可能好的 PDF 翻译阅读体验。**

第一版只解决：

```text
论文在哪里？
        +
这篇论文怎么翻译？
        +
怎样同时看原文和中文？
```

这三个问题即可。
