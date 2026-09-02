import os
from pathlib import Path
from typing import List, Optional, Union
from langchain_community.document_loaders import CSVLoader, PyPDFLoader, TextLoader, JSONLoader
import config
from langchain_core.documents import Document
from utils.logger import setup_logger

logger = setup_logger("file_loader", config.LOG_FILE)

SUPPORTED_EXTS = {".txt", ".md", ".pdf", ".json", ".csv"}
_ENCODINGS = ("utf-8", "gbk", "latin-1")  # 中文优先utf‑8，失败回退gbk

def load_file(path: Union[str, Path]) -> Optional[List[Document]]:
    """
    解析单个文件，失败返回 None（调用方批量自动跳过）
    返回：该文件解析出的Document列表；PDF一页一个Document
    """
    path = Path(path)

    if path.suffix.lower() not in SUPPORTED_EXTS:
        logger.warning("不支持的文件类型: %s", path.suffix)
        return None

    try:
        docs = _read_file(path)
        # 空文档判断：列表为空，或者所有doc的page_content都是空白
        valid_docs = [d for d in docs if d.page_content and d.page_content.strip()]
        if not valid_docs:
            logger.warning("文件无有效文本，跳过: %s", path.name)
            return None
        return valid_docs

    except Exception as e:
        logger.error("解析失败 %s: %s", path.name, str(e))
        return None


def load_files(paths: List[Union[str, Path]]) -> List[Document]:
    """批量加载文件，返回全部成功解析的文档平铺列表"""
    total_docs = []
    for p in paths:
        doc_list = load_file(p)
        if doc_list is not None:
            total_docs.extend(doc_list)
    return total_docs


def _read_file(path: Path) -> List[Document]:
    """分发加载器，读取文件返回原始Document列表"""
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        pdf_loader = PyPDFLoader(file_path=str(path))
        doc_list = pdf_loader.load()
        # 扫描版PDF告警：所有页面文本为空
        all_empty = all(not d.page_content.strip() for d in doc_list)
        if all_empty:
            logger.warning("PDF可能是扫描图片版，提取不到文本: %s", path.name)
        return doc_list

    elif suffix in (".txt", ".md"):
        last_err: Optional[UnicodeDecodeError] = None
        for enc in _ENCODINGS:
            try:
                text_loader = TextLoader(file_path=str(path), encoding=enc)
                return text_loader.load()
            except UnicodeDecodeError as e:
                last_err = e
                continue
        # 全部编码失败兜底
        if last_err:
            logger.warning("编码解析异常 %s，使用 latin‑1 兜底: %s", path.name, str(last_err))
            return [Document(page_content=path.read_text(encoding="latin‑1"), metadata={"source": str(path)})]

    elif suffix == ".json":
        json_loader = JSONLoader(
            file_path=str(path),
            jq_schema=".",
            text_content=False
        )
        return json_loader.load()

    elif suffix == ".csv":
        csv_loader = CSVLoader(file_path=str(path))
        return csv_loader.load()

    else:
        # load_file上层已经拦截后缀，理论不会走到这里
        raise ValueError(f"未处理的后缀 {path.suffix}")





# 方案二

# """文件解析工具：支持 .txt / .md / .pdf -> List[langchain Document]，携带 source 元数据。

# PDF 使用 PyPDF2 懒加载提取文本；txt/md 直接读取并做编码回退。
# 损坏文件 / 空文件通过异常捕获处理，返回 None（批量时自动跳过）。
# """
# import os
# from pathlib import Path
# from typing import List, Optional, Union

# import config
# from langchain_core.documents import Document
# from utils.logger import setup_logger

# logger = setup_logger("file_loader", config.LOG_FILE)

# SUPPORTED_EXTS = {".txt", ".md", ".pdf"}
# _ENCODINGS = ("utf-8", "gbk", "latin-1")  # 中文文件优先 utf-8，失败回退 gbk


# def load_file(path: Union[str, Path]) -> Optional[Document]:
#     """解析单个文件，失败时返回 None（由调用方决定跳过）。"""
#     path = Path(path)

#     if path.suffix.lower() not in SUPPORTED_EXTS:
#         logger.warning("不支持的文件类型: %s", path.suffix)
#         return None

#     try:
#         text = _read_text(path)
#         if not text or not text.strip():
#             logger.warning("空文件跳过: %s", path.name)
#             return None
#         return Document(page_content=text, metadata={"source": path.name})
#     except Exception as e:
#         # 损坏文件 / 解析异常统一兜底
#         logger.error("解析失败 %s: %s", path.name, e)
#         return None


# def load_files(paths: List[Union[str, Path]]) -> List[Document]:
#     """批量加载文件，返回成功解析的文档列表。"""
#     docs = []
#     for p in paths:
#         d = load_file(p)
#         if d is not None:
#             docs.append(d)
#     return docs


# def _read_text(path: Path) -> str:
#     """读取文件文本。PDF 走 PyPDF2；txt/md 做编码回退。"""
#     if path.suffix.lower() == ".pdf":
#         # 懒加载，避免无 PyPDF2 时拖垮整个模块
#         from PyPDF2 import PdfReader

#         reader = PdfReader(str(path))
#         return "\n".join(page.extract_text() or "" for page in reader.pages)

#     # txt / md：逐级尝试编码
#     last_exc = None
#     for enc in _ENCODINGS:
#         try:
#             return path.read_text(encoding=enc)
#         except UnicodeDecodeError as e:
#             last_exc = e
#             continue
#     # 全部失败，用 latin-1 兜底（保证不抛异常）
#     if last_exc:
#         logger.warning("编码解析异常 %s，使用 latin-1 兜底: %s", path.name, last_exc)
#     return path.read_text(encoding="latin-1")






