"""统一日志工具：控制台输出 + 可选日志文件。"""

import logging
import os
import sys


def setup_logger(name: str = "rag", log_file: str = None, level: int = logging.INFO):
    """获取统一的 logger 实例。

    Args:
        name: logger 名称（自动补全为 rag_xxx 风格）。
        log_file: 可选日志文件路径；为 None 时只输出控制台。
        level: 日志级别。
    """
    logger = logging.getLogger(name)
    # 防止重复添加 handler（多次调用时日志刷屏）
    if logger.handlers:
        return logger

    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Windows 控制台默认 GBK，emoji/中文混合时编码会抛 UnicodeEncodeError。
    # errors="replace" 兜底，保证日志不因字符集问题中断服务链路。
    # Windows 控制台默认 GBK，中文/emoji 无法编码会抛 UnicodeEncodeError
    # 并让 uvicorn 等服务的中文日志炸栈。把 stdout/stderr 强制重配置为 UTF-8 兜底。
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                try:
                    stream.reconfigure(encoding="utf-8", errors="replace")
                except (OSError, ValueError):
                    pass  # 非文本流（如已替换为管道且不可重配置）时忽略

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    # 防止日志向上传播到 root logger，避免重复打印
    logger.propagate = False
    return logger