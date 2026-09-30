# Paper Translator · C++ / Qt 桌面版

`windows-desktop/` 已直接重写为 **C++17 + Qt 6 Widgets / Qt PDF / Qt SQL**。界面、论文导入与搜索、SQLite 存储、阅读记录、双栏阅读、设置、任务队列、取消与导出均由 C++ 实现。Python 仅保留 **PDFMathTranslate（pdf2zh）翻译与排版引擎**，通过 `QProcess` 的标准输入/输出通信。程序无需浏览器、WebView2、Node.js 或 HTTP 服务。

## 功能

- 多文件 PDF 导入、标题/页数提取、论文搜索、删除与译文导出。
- Qt PDF 原生双栏阅读：页码联动、页内滚动比例同步、缩放、适合宽度。
- 滚轮在页底/页顶继续滚动会翻页；阅读区支持左右箭头、PageUp/PageDown、空格和 Ctrl+滚轮缩放。
- 阅读位置按页立即写入 SQLite，下次打开恢复。
- 串行翻译队列，每个任务使用独立 Python 进程；支持取消排队/运行任务。
- 窗口关闭前确认中断任务，关闭后终止引擎；异常退出后重启将未完成任务标记为失败，可重新翻译。
- 支持 DeepSeek、OpenAI、智谱、硅基流动、Ollama、Google 和 Bing。新设置对之后加入队列的任务生效。
- 保留原项目的 PDF 科学计数法修复和逐页渲染校验。仅在输出校验通过且引擎正常退出后显示 100%。

## WSL / Linux 编译与运行

安装 Qt 6.4 或更新版本、Qt PDF、SQLite 驱动、CMake 和 C++ 编译器：

```bash
sudo apt-get update
sudo apt-get install -y cmake ninja-build qt6-base-dev qt6-pdf-dev libqt6sql6-sqlite
cd windows-desktop
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build --parallel 4
ctest --test-dir build --output-on-failure
./build/PaperTranslator
```

WSL 图形界面需要 WSLg。无显示设备时可以检查程序启动：

```bash
QT_QPA_PLATFORM=offscreen PAPER_TRANSLATOR_HOME=/tmp/paper-qt-smoke ./build/PaperTranslator --smoke-test
```

源码运行时，仅翻译功能需要 Python 依赖；论文管理和阅读独立于 Python：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r engine/requirements.txt
.venv/bin/python scripts/test-engine.py
```

开发版会优先检测本目录或上层项目的 `.venv`。也可在「设置」中指定 Python 解释器。首次翻译需联网下载版面模型、字体，在线翻译服务还需要 API Key；本地 PDF 阅读不需要这些服务。

## Windows 编译和打包

构建环境：Windows 10/11 x64、Visual Studio 2022 C++ 桌面开发工具（含 Windows SDK）、CMake、Python 3.12 x64，以及 **Qt 6 的 MSVC 2022 x64 Kit，包含 Qt PDF / PdfWidgets / SQL**。通过 Qt 安装器准备该 Kit，确认目录内有 `bin/windeployqt.exe` 和 `lib/cmake/Qt6PdfWidgets`。

将此目录放在 Windows 本地磁盘，在 PowerShell 中运行（Qt 路径请替换为实际路径）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 -QtDir "C:\Qt\6.8.3\msvc2022_64"
```

脚本创建 Python 构建环境，执行引擎测试、C++ 构建与集成测试；再用 PyInstaller 冻结翻译引擎，用 `windeployqt` 部署 Qt DLL 与插件，检查引擎和桌面 EXE 启动，最后生成：

- `dist\PaperTranslator\PaperTranslator.exe`：原生 Qt 主程序。
- `dist\PaperTranslator\engine\pdfmathtranslate-engine.exe`：内置 Python 翻译引擎及其依赖。
- `dist\PaperTranslator-Qt-windows-x64.zip`：完整便携分发包。

分发必须保留整个 `PaperTranslator` 目录。用户无需另装 Python、Qt、Node.js 或 WebView2。首次翻译的模型/字体下载仍需要网络。

使用 Ninja 或其他 Qt Kit 时，可通过 `-Generator` 指定生成器，并在相应编译器开发终端运行；Qt Kit 和编译器架构须匹配。

安装 [Inno Setup 6](https://jrsoftware.org/isinfo.php) 后可生成安装包：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1 -QtDir "C:\Qt\6.8.3\msvc2022_64" -Installer -Iscc "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
```

输出 `dist\PaperTranslator-Qt-Setup-2.0.0-x64.exe`，包含开始菜单和可选桌面快捷方式、卸载入口。

## 用户数据和旧库

Windows 默认存到 `%LOCALAPPDATA%\PaperTranslator`；Linux 默认使用 Qt 的应用数据目录。用 `PAPER_TRANSLATOR_HOME` 可以指定其他目录。

```text
PaperTranslator/
├── data/app.db                 # C++ / Qt SQL 管理论文与阅读记录
├── data/papers/<id>/           # original.pdf / translated.pdf
├── config/settings.ini        # C++ QSettings 管理翻译服务设置
├── logs/translation-<id>.log   # Python 引擎 stderr 日志，重试时覆盖
└── desktop.lock               # Qt 单实例锁
```

数据库使用相对 PDF 路径，关闭应用后可以整体复制该数据目录。既有 WebView 桌面版的论文数据库和 PDF 可直接使用同一数据目录，旧绝对路径会优先解析到当前论文目录；旧 YAML 翻译设置需在 Qt 设置中重新填写。API Key 保存在用户配置中，构建不会打包用户论文或设置。

从其他位置迁移旧项目时，在**空论文库**中选择「文件 → 导入旧项目论文库」，选中旧项目的 `data` 目录。C++ 将复制论文和阅读记录，改用新目录内的相对路径；缺失文件时撤销导入，源数据保持不变。导入前请关闭旧项目。

升级或卸载不会删除用户论文目录。备份前应关闭程序。PDFMathTranslate 自身的模型、字体、翻译缓存仍由第三方库保存在用户缓存目录中。

## 结构与验证

```text
windows-desktop/
├── CMakeLists.txt
├── src/                 # C++ / Qt 主程序、SQLite、阅读器、设置与任务管理
├── engine/              # Python 翻译引擎、JSONL 桥接、PDF 兼容修复
├── tests/               # Qt 集成测试、独立进程模拟器、Python 排版回归
├── scripts/             # Windows 构建、引擎测试入口
└── packaging/           # 引擎 PyInstaller spec、Inno Setup 配置
```

已在当前 WSL/Ubuntu 环境实际编译并通过 Qt 集成测试、13 项 Python 引擎测试和桌面程序无界面启动检查。测试不调用在线翻译 API。Windows 构建脚本尚需在装有 Windows Qt Kit 和 C++ 编译器的宿主环境中执行，当前没有生成 Windows EXE / 安装包。

实现参考 [Qt PDF View](https://doc.qt.io/qt-6/qpdfview.html)、[Qt PDF 页码导航](https://doc.qt.io/qt-6/qpdfpagenavigator.html) 和 [Qt Windows 部署](https://doc.qt.io/qt-6/windows-deployment.html)。
