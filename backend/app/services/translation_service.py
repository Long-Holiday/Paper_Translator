import os
import shutil
import traceback
from pathlib import Path
from typing import Optional, Callable
from backend.app.config import load_config


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
        thread = int(cfg.get("thread", 4))

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
            from pdf2zh.high_level import translate as do_translate

            # 获取版面模型（关键修复：必须向 translate 显式传入 model 参数）
            model = self.get_layout_model()

            if progress_callback:
                progress_callback(35, f"调用翻译引擎 ({full_service}) 翻译中...")

            # 运行翻译
            results = do_translate(
                files=[str(source_pdf)],
                output=str(output_dir),
                lang_in=lang_in,
                lang_out=lang_out,
                service=full_service,
                thread=thread,
                envs=envs,
                model=model,
            )

            if progress_callback:
                progress_callback(85, "正在生成中文排版 PDF...")

            # results 返回的是 [(str(file_mono), str(file_dual))]
            if results and len(results) > 0:
                file_mono, file_dual = results[0]
                mono_path = Path(file_mono)
                if mono_path.exists():
                    shutil.copy2(mono_path, target_final_pdf)
                elif Path(file_dual).exists():
                    shutil.copy2(Path(file_dual), target_final_pdf)
                else:
                    raise FileNotFoundError("未找到生成的翻译 PDF 文件")
            else:
                # 备用方案：在 output_dir 寻找 *-mono.pdf
                mono_candidates = list(output_dir.glob("*-mono.pdf"))
                if mono_candidates:
                    shutil.copy2(mono_candidates[0], target_final_pdf)
                else:
                    raise FileNotFoundError("翻译完成但未找到生成的中文 PDF 文件")

            if progress_callback:
                progress_callback(100, "翻译已完成")

            return target_final_pdf

        except Exception as e:
            traceback.print_exc()
            raise RuntimeError(f"PDF 翻译失败: {str(e)}")
