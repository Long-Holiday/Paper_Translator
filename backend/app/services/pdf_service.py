import re
from pathlib import Path
from typing import Tuple, Optional
import fitz  # PyMuPDF


class PdfService:
    @staticmethod
    def extract_pdf_info(pdf_path: Path, fallback_filename: str) -> Tuple[str, int]:
        """
        提取 PDF 的标题和总页数。
        标题优先级:
        1. PDF metadata 中的 title
        2. 若不存在或无意义，将文件名转化为易读的标题
        """
        title = ""
        page_count = 0
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            meta_title = doc.metadata.get("title")
            if meta_title and isinstance(meta_title, str) and meta_title.strip():
                # 过滤无意义的默认标题
                cleaned = meta_title.strip()
                if not re.match(r"^untitled|microsoft word|pdf document$", cleaned, re.I):
                    title = cleaned
            doc.close()
        except Exception as e:
            print(f"[PdfService] 解析 PDF 元数据失败: {e}")

        if not title:
            # 文件名处理：去掉 .pdf 后缀，替换下划线/连字符为空格，大写规范
            name = Path(fallback_filename).stem
            name = re.sub(r"[_\-]+", " ", name).strip()
            # 单词首字母大写
            title = " ".join(word.capitalize() for word in name.split()) if name else "Untitled Paper"

        return title, max(page_count, 1)
