import os
import ast
import tempfile
import traceback
from pathlib import Path
from typing import Optional, Callable
import fitz
from backend.app.config import load_config
from backend.app.resources import get_resource_limits
from backend.app.services.pdf_compat import pdf2zh_number_compatibility, validate_pdf


class TranslationService:
    _layout_model = None

    @classmethod
    def get_layout_model(cls):
        """单例加载版面分析 ONNX 模型，避免重复加载开销"""
        if cls._layout_model is None:
            from pdf2zh.doclayout import OnnxModel
            from babeldoc.assets.assets import get_doclayout_onnx_model_path
            import cv2
            import onnxruntime

            limits = get_resource_limits()
            cv2.setNumThreads(limits.cpu_threads)
            options = onnxruntime.SessionOptions()
            options.intra_op_num_threads = limits.cpu_threads
            options.inter_op_num_threads = 1
            options.execution_mode = onnxruntime.ExecutionMode.ORT_SEQUENTIAL
            options.enable_cpu_mem_arena = False
            options.enable_mem_pattern = False
            options.add_session_config_entry("session.intra_op.allow_spinning", "0")

            # pdf2zh 1.9.11 normally loads ONNX into Python, serializes it, then
            # loads it again in ORT. Load directly from disk to avoid those copies.
            model = OnnxModel.__new__(OnnxModel)
            model.model_path = str(get_doclayout_onnx_model_path())
            model.model = onnxruntime.InferenceSession(
                model.model_path, sess_options=options, providers=["CPUExecutionProvider"]
            )
            metadata = model.model.get_modelmeta().custom_metadata_map
            model._stride = ast.literal_eval(metadata["stride"])
            model._names = ast.literal_eval(metadata["names"])
            cls._layout_model = model
        return cls._layout_model

    def translate(
        self,
        source_pdf: Path,
        output_dir: Path,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        *,
        work_dir: Optional[Path] = None,
    ) -> Path:
        """
        调用 pdf2zh 执行 PDF 翻译。
        返回生成的中文翻译 PDF 路径。
        """
        if not source_pdf.exists():
            raise FileNotFoundError(f"源 PDF 文件不存在: {source_pdf}")

        output_dir.mkdir(parents=True, exist_ok=True)
        target_final_pdf = output_dir / "translated.pdf"

        cfg = load_config().get("translation", {})
        service_name = cfg.get("service", "deepseek").strip() or "deepseek"
        model_name = cfg.get("model", "deepseek-chat").strip()
        api_key = cfg.get("api_key", "").strip()
        base_url = cfg.get("base_url", "").strip()
        lang_in = cfg.get("source_language", "en")
        lang_out = cfg.get("target_language", "zh")
        limits = get_resource_limits()
        thread = max(1, min(int(cfg.get("thread", 1)), limits.max_translation_threads))

        # 构建 service 字符串，例如 "deepseek:deepseek-chat" 或 "openai:gpt-4o-mini"
        if model_name and ":" not in service_name:
            full_service = f"{service_name}:{model_name}"
        else:
            full_service = service_name

        # 环境变量与认证信息配置
        envs = {}
        if api_key:
            envs["DEEPSEEK_API_KEY"] = api_key
            os.environ["DEEPSEEK_API_KEY"] = api_key
            envs["OPENAI_API_KEY"] = api_key
            os.environ["OPENAI_API_KEY"] = api_key

        if base_url:
            envs["OPENAI_BASE_URL"] = base_url
            os.environ["OPENAI_BASE_URL"] = base_url

        # 检查是否缺少必要的 API Key
        if "deepseek" in service_name.lower() and not api_key:
            raise ValueError(
                "检测到未配置 DeepSeek API Key！请点击右上角「设置」填入您的 DeepSeek API Key，或在 config/config.yaml 中配置。"
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
                if expected_pages > limits.max_pdf_pages:
                    raise ValueError(f"PDF 超过 {limits.max_pdf_pages} 页的小内存部署限制")
            from pdf2zh import high_level

            # 获取版面模型（关键修复：必须向 translate 显式传入 model 参数）
            model = self.get_layout_model()

            if progress_callback:
                progress_callback(35, f"调用翻译引擎 ({full_service}) 翻译中...")

            # 独立临时目录避免误用上次输出；校验成功后才替换可下载译文。
            with tempfile.TemporaryDirectory(prefix=".translation-", dir=work_dir or output_dir) as staging:
                staging = Path(staging)
                candidate = staging / "translated.pdf"
                batch_pages = limits.translation_batch_pages or expected_pages
                with fitz.open(source_pdf) as original, fitz.open() as merged:
                    for start in range(0, expected_pages, batch_pages):
                        end = min(start + batch_pages, expected_pages)
                        with tempfile.TemporaryDirectory(prefix="batch-", dir=staging) as batch:
                            batch = Path(batch)
                            # Always copy the input: pdf2zh deletes inputs located
                            # beneath /tmp, including during local tests/deployments.
                            batch_source = batch / "input.pdf"
                            with fitz.open() as part:
                                part.insert_pdf(original, from_page=start, to_page=end - 1)
                                part.set_metadata(original.metadata)
                                part.save(batch_source)
                            with pdf2zh_number_compatibility(high_level):
                                results = high_level.translate(
                                    files=[str(batch_source)], output=str(batch),
                                    lang_in=lang_in, lang_out=lang_out,
                                    service=full_service, thread=thread, envs=envs, model=model,
                                )
                            file_mono = Path(results[0][0]) if results else batch / "input-mono.pdf"
                            if not file_mono.is_file():
                                raise FileNotFoundError("翻译完成但未找到生成的中文 PDF 文件")
                            validate_pdf(file_mono, expected_pages=end - start)
                            with fitz.open(file_mono) as translated:
                                merged.insert_pdf(translated)
                        if progress_callback:
                            progress_callback(35 + int(50 * end / expected_pages),
                                              f"已翻译 {end}/{expected_pages} 页")
                    merged.set_metadata(original.metadata)
                    merged.set_toc(original.get_toc())
                    merged.save(candidate, garbage=3, deflate=True)

                if progress_callback:
                    progress_callback(90, "正在校验中文排版 PDF...")
                validate_pdf(candidate, expected_pages=expected_pages)
                # Only the original and the validated translation are kept.
                candidate.replace(target_final_pdf)

            if progress_callback:
                progress_callback(100, "翻译已完成")

            return target_final_pdf

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"PDF 翻译失败: {str(e)}")
