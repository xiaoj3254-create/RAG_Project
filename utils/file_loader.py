"""文件解析工具：支持 .txt / .md / .pdf -> List[langchain Document]，携带 source 元数据。

PDF 使用 PyPDF2 懒加载提取文本；txt/md 直接读取并做编码回退。
损坏文件 / 空文件通过异常捕获处理，返回 None（批量时自动跳过）。
"""
import os
from pathlib import Path
from typing import List, Optional, Union

import config
from langchain_core.documents import Document
from utils.logger import setup_logger

logger = setup_logger("file_loader", config.LOG_FILE)

SUPPORTED_EXTS = {".txt", ".md", ".pdf"}
_ENCODINGS = ("utf-8", "gbk", "latin-1")  # 中文文件优先 utf-8，失败回退 gbk


def load_file(path: Union[str, Path]) -> Optional[Document]:
    """解析单个文件，失败时返回 None（由调用方决定跳过）。"""
    path = Path(path)

    if path.suffix.lower() not in SUPPORTED_EXTS:
        logger.warning("不支持的文件类型: %s", path.suffix)
        return None

    try:
        text = _read_text(path)
        if not text or not text.strip():
            logger.warning("空文件跳过: %s", path.name)
            return None
        return Document(page_content=text, metadata={"source": path.name})
    except Exception as e:
        # 损坏文件 / 解析异常统一兜底
        logger.error("解析失败 %s: %s", path.name, e)
        return None


def load_files(paths: List[Union[str, Path]]) -> List[Document]:
    """批量加载文件，返回成功解析的文档列表。"""
    docs = []
    for p in paths:
        d = load_file(p)
        if d is not None:
            docs.append(d)
    return docs


def _read_text(path: Path) -> str:
    """读取文件文本。PDF 走 PyPDF2；txt/md 做编码回退。"""
    if path.suffix.lower() == ".pdf":
        # 懒加载，避免无 PyPDF2 时拖垮整个模块
        from PyPDF2 import PdfReader

        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    # txt / md：逐级尝试编码
    last_exc = None
    for enc in _ENCODINGS:
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError as e:
            last_exc = e
            continue
    # 全部失败，用 latin-1 兜底（保证不抛异常）
    if last_exc:
        logger.warning("编码解析异常 %s，使用 latin-1 兜底: %s", path.name, last_exc)
    return path.read_text(encoding="latin-1")