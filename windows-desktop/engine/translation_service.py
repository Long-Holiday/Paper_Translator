import os
import shutil
import traceback
import tempfile

import fitz
from pathlib import Path
from typing import Optional, Callable
from engine.pdf_compat import pdf2zh_number_compatibility, validate_pdf


class TranslationService:
    _layout_model = None

    @classmethod
    def get_layout_model(cls):
        """单例加载版面分析 ONNX 模型，避免重复加载开销"""
        if cls._layout_model is None:
            from pdf2zh.doclayout import OnnxModel
            cls._layout_model = OnnxModel.load_available()
        return cls._layout_model

    def translate(
        self,
        source_pdf: Path,
        output_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        config: dict | None = None,
    ) -> Path:
        """
        调用 pdf2zh 执行 PDF 翻译。
        返回生成的中文翻译 PDF 路径。
        """
        if not source_pdf.exists():
            raise FileNotFoundError(f"源 PDF 文件不存在: {source_pdf}")

        output_dir.mkdir(parents=True, exist_ok=True)
        target_final_pdf = output_dir / "translated.pdf"

        cfg = config or {}
        service_name = cfg.get("service", "deepseek").strip() or "deepseek"
        model_name = cfg.get("model", "deepseek-chat").strip()
        api_key = cfg.get("api_key", "").strip()
        base_url = cfg.get("base_url", "").strip()
        lang_in = cfg.get("source_language", "en")
        lang_out = cfg.get("target_language", "zh")
        thread = int(cfg.get("thread", 4))

        # 构建 service 字符串，例如 "deepseek:deepseek-chat" 或 "openai:gpt-4o-mini"
        if model_name and ":" not in service_name:
            full_service = f"{service_name}:{model_name}"
        else:
            full_service = service_name

        # 环境变量与认证信息配置
        envs = {}
        if api_key:
            for prefix in ("DEEPSEEK", "OPENAI", "ZHIPU", "SILICON"):
                envs[f"{prefix}_API_KEY"] = api_key
            envs["DEEPSEEK_API_KEY"] = api_key
            os.environ["DEEPSEEK_API_KEY"] = api_key
            envs["OPENAI_API_KEY"] = api_key
            os.environ["OPENAI_API_KEY"] = api_key

        if base_url:
            envs["OPENAI_BASE_URL"] = base_url
            os.environ["OPENAI_BASE_URL"] = base_url
            if service_name == "ollama":
                envs["OLLAMA_HOST"] = base_url
            elif service_name == "deepseek":
                # OpenAI-compatible mode honors a configurable DeepSeek endpoint.
                full_service = f"openai:{model_name or 'deepseek-chat'}"

        # 检查是否缺少必要的 API Key
        if "deepseek" in service_name.lower() and not api_key:
            raise ValueError(
                "未配置 DeepSeek API Key，请在桌面程序的设置中填写。"
            )

        # 确保 IPv6 no_proxy 不崩溃
        for _key in ["NO_PROXY", "no_proxy"]:
            if _key in os.environ and "[::1]" in os.environ[_key]:
                _parts = [p.strip() for p in os.environ[_key].split(",") if p.strip() and p.strip() != "[::1]"]
                os.environ[_key] = ",".join(_parts)

        if progress_callback:
            progress_callback(15, "正在加载文档版面分析模型...")

        try:
            with fitz.open(source_pdf) as original:
                expected_pages = len(original)
                if original.needs_pass or not expected_pages:
                    raise ValueError("PDF 文件加密或没有页面")
            from pdf2zh import high_level

            # 获取版面模型（关键修复：必须向 translate 显式传入 model 参数）
            model = self.get_layout_model()

            if progress_callback:
                progress_callback(35, f"调用翻译引擎 ({full_service}) 翻译中...")

            last_progress = 35

            def on_engine_progress(progress):
                nonlocal last_progress
                # pdf2zh 在开始处理每页之前更新 tqdm 并调用 callback，
                # n-1 才是已完成页数；预留后续排版、校验和发布所需进度。
                total = progress.total or expected_pages
                completed = max(0, min(progress.n - 1, total))
                percent = 35 + int(45 * completed / total)
                if progress_callback and percent > last_progress:
                    last_progress = percent
                    progress_callback(percent, f"已翻译 {completed}/{total} 页，正在处理下一页...")

            # 隔离输出，避免使用旧译文；复制输入，防止 pdf2zh 删除 /tmp 下的源文件。
            with tempfile.TemporaryDirectory(prefix=".translation-", dir=output_dir) as staging:
                staging = Path(staging)
                staged_source = staging / source_pdf.name
                shutil.copy2(source_pdf, staged_source)
                with pdf2zh_number_compatibility(high_level):
                    results = high_level.translate(
                        files=[str(staged_source)],
                        output=str(staging),
                        lang_in=lang_in,
                        lang_out=lang_out,
                        service=full_service,
                        thread=thread,
                        envs=envs,
                        model=model,
                        callback=on_engine_progress,
                    )

                if progress_callback:
                    progress_callback(85, "正在生成中文排版 PDF...")

                mono_path = Path(results[0][0]) if results else staging / f"{staged_source.stem}-mono.pdf"
                if not mono_path.is_file():
                    raise FileNotFoundError("翻译完成但未找到生成的中文 PDF 文件")

                if progress_callback:
                    progress_callback(90, "正在校验中文排版 PDF...")
                validate_pdf(mono_path, expected_pages=expected_pages)
                mono_path.replace(target_final_pdf)

            if progress_callback:
                progress_callback(100, "翻译已完成")

            return target_final_pdf

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"PDF 翻译失败: {str(e)}")
